"""Ficha do animal — equivalente a `modules/pages/animal_page.py` (e ao
painel de colheitas `modules/components/colheitas_widget.py`).

Égua/receptora: Resumo (editar ficha), Diário clínico (registo de hoje,
editar, apagar — registar conclui as tarefas de hoje do animal e pode
agendar a próxima observação), Historial reprodutivo (resultado +/− de
cada inseminação pendente) e Estadias (com o acompanhamento
pós-inseminação da estadia ativa).

Garanhão: Resumo + colheitas agendadas, Produção de sémen, Fertilidade e
Alertas.

As consultas e escritas são as da página atual, reaproveitadas.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.deps import get_current_user
from backend.serial import registos, valor
from modules.db import get_connection
from modules.pages.animal_page import (
    _apagar_diario_clinico,
    _atualizar_animal,
    _atualizar_diario_clinico,
    _atualizar_garanhao_estadia,
    _carregar_animal,
    _carregar_diario_clinico,
    _carregar_estadias_do_animal,
    _carregar_inseminacoes_animal,
    _carregar_inseminacoes_garanhao,
    _carregar_stock_garanhao,
    _concluir_tarefas_animal_hoje,
    _inserir_diario_clinico,
    _inserir_tarefa_acompanhamento,
    _kpis_fertilidade_garanhao,
    _kpis_stock_garanhao,
    _obter_acompanhamento,
    _obter_estadia_activa,
    _obter_estadia_activa_inseminacao,
    _ultima_producao_garanhao,
    _upsert_acompanhamento,
)
from modules.repositories.colheita_repo import agendar_colheita, cancelar_colheita, listar_colheitas_futuras
from modules.repositories.insemination_repo import InseminacaoError, registar_resultado

router = APIRouter(prefix="/api/animais", tags=["animais"])

COMPORTAMENTOS = ("cio_ativo", "sem_cio", "anestro", "pos_ovulacao")


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _texto(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _animal(animal_id: int) -> dict:
    a = _carregar_animal(animal_id)
    if not a:
        raise _erro(404, "web.animal.error.not_found")
    return {k: valor(v) for k, v in a.items()}


# ── Ficha ─────────────────────────────────────────────────────────────────

@router.get("/{animal_id:int}")
def ficha(animal_id: int, _user: dict = Depends(get_current_user)):
    a = _animal(animal_id)
    with_ins = _obter_estadia_activa_inseminacao(animal_id)
    proprietario = None
    if a.get("dono_id"):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT nome FROM dono WHERE id = %s", (a["dono_id"],))
                row = cur.fetchone()
                proprietario = row[0] if row else None
    return {
        **a,
        "proprietario": proprietario,
        "estadia_ativa": _obter_estadia_activa(animal_id),
        "estadia_inseminacao": {k: valor(v) for k, v in with_ins.items()} if with_ins else None,
    }


class AnimalIn(BaseModel):
    nome: str | None = None
    tipo: Literal["egua", "garanhao", "receptora"] = "egua"
    raca: str | None = None
    data_nascimento: date | None = None
    numero_registo: str | None = None
    pelagem: str | None = None
    altura: float | None = Field(default=None, ge=0, le=999.9)
    peso: float | None = Field(default=None, ge=0, le=99999.9)
    chip: str | None = None
    pai: str | None = None
    mae: str | None = None
    avo_paterno: str | None = None
    avo_materno: str | None = None
    observacoes: str | None = None
    # Proprietário do animal (pode ser escolhido ou criado na ficha).
    dono_id: int | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


@router.put("/{animal_id:int}")
def editar(animal_id: int, d: AnimalIn, _user: dict = Depends(get_current_user)):
    _animal(animal_id)
    if not d.nome:
        raise _erro(422, "web.stays.error.animal_name_required")
    if "dono_id" in d.model_fields_set and d.dono_id is not None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM dono WHERE id = %s", (d.dono_id,))
                if not cur.fetchone():
                    raise _erro(404, "web.animal.error.owner_not_found")
    dados = d.model_dump(exclude={"dono_id"})
    # 0 conta como "não indicado", como na app atual.
    dados["altura"] = d.altura or None
    dados["peso"] = d.peso or None
    # A receptora é um tipo próprio: a marca acompanha sempre o tipo.
    dados["is_receptora"] = d.tipo == "receptora"
    _atualizar_animal(animal_id, dados)
    # Só mexe no proprietário quando o pedido o traz.
    if "dono_id" in d.model_fields_set:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE animais SET dono_id = %s, updated_at = NOW() WHERE id = %s", (d.dono_id, animal_id))
            conn.commit()
    return ficha(animal_id)


# ── Diário clínico ────────────────────────────────────────────────────────

class RegistoIn(BaseModel):
    data_registo: date
    foliculo_mm: int | None = Field(default=None, ge=0, le=99)
    edema_grau: int = Field(default=0, ge=0, le=3)
    fluido_uterino: bool = False
    comportamento: Literal["cio_ativo", "sem_cio", "anestro", "pos_ovulacao"] = "cio_ativo"
    temperatura: float | None = Field(default=None, ge=0, le=45)
    tratamentos: str | None = None
    proxima_observacao: date | None = None
    observacoes: str | None = None

    @field_validator("tratamentos", "observacoes", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)

    def dados(self) -> dict:
        d = self.model_dump()
        d["foliculo_mm"] = self.foliculo_mm or None
        d["temperatura"] = self.temperatura or None
        return d


_COL_DIARIO = ["id", "data_registo", "foliculo_mm", "edema_grau", "fluido_uterino", "comportamento",
               "temperatura", "tratamentos", "proxima_observacao", "observacoes"]


def _registo_do_animal(animal_id: int, rid: int):
    if not any(r["id"] == rid for r in registos(_carregar_diario_clinico(animal_id), ["id"])):
        raise _erro(404, "web.animal.error.record_not_found")


@router.get("/{animal_id:int}/diario")
def diario(animal_id: int, _user: dict = Depends(get_current_user)):
    _animal(animal_id)
    return registos(_carregar_diario_clinico(animal_id), _COL_DIARIO)


@router.post("/{animal_id:int}/diario", status_code=201)
def novo_registo(animal_id: int, d: RegistoIn, user: dict = Depends(get_current_user)):
    _animal(animal_id)
    estadia_id = _obter_estadia_activa(animal_id)
    if estadia_id is None:
        raise _erro(409, "web.animal.error.no_active_stay")
    rid = _inserir_diario_clinico({**d.dados(), "animal_id": animal_id, "estadia_id": estadia_id, "utilizador": user["username"][:50]})
    # Como a app atual: conclui as tarefas de hoje do animal e, se houver
    # próxima observação, agenda-a no Trabalho diário.
    concluidas = _concluir_tarefas_animal_hoje(animal_id, user["username"])
    if d.proxima_observacao:
        _inserir_tarefa_acompanhamento(animal_id, estadia_id, d.proxima_observacao, user["username"])
    return {"id": rid, "tarefas_concluidas": concluidas}


@router.put("/{animal_id:int}/diario/{rid:int}")
def editar_registo(animal_id: int, rid: int, d: RegistoIn, _user: dict = Depends(get_current_user)):
    _registo_do_animal(animal_id, rid)
    _atualizar_diario_clinico(rid, d.dados())
    return {"ok": True}


@router.delete("/{animal_id:int}/diario/{rid:int}")
def apagar_registo(animal_id: int, rid: int, _user: dict = Depends(get_current_user)):
    _registo_do_animal(animal_id, rid)
    _apagar_diario_clinico(rid)
    return {"ok": True}


# ── Historial reprodutivo e estadias ──────────────────────────────────────

def _etapa(data_inseminacao: date | None) -> tuple[str, str]:
    """Etapa do diagnóstico pelos dias desde a inseminação (como a app atual)."""
    dias = (date.today() - data_inseminacao).days if data_inseminacao else 0
    if dias >= 45:
        return "segunda_confirmacao", "D+45"
    if dias >= 28:
        return "confirmacao_gestacao", "D+28"
    return "diagnostico_gestacao", "D+14"


def _como_data(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


@router.get("/{animal_id:int}/reprodutivo")
def reprodutivo(animal_id: int, _user: dict = Depends(get_current_user)):
    a = _animal(animal_id)
    df = _carregar_inseminacoes_animal(animal_id, a.get("nome") or "")
    ins = registos(df, ["data_inseminacao", "garanhao", "proprietario", "palhetas_gastas", "num_lotes", "resultado", "observacoes", "op_key"])
    for r in ins:
        # Só operações reais (não linhas antigas "solo_") podem receber resultado aqui.
        r["pode_resultado"] = r["resultado"] == "pendente" and not str(r["op_key"]).startswith("solo_") and r["data_inseminacao"] is not None
        r["etapa"] = _etapa(_como_data(r["data_inseminacao"]))[1]
    total = len(ins)
    gest = sum(1 for r in ins if r["resultado"] == "gestacao_confirmada")
    return {"total": total, "gestacoes": gest, "taxa": round(gest / total * 100) if total else None, "inseminacoes": ins}


class ResultadoIn(BaseModel):
    op_key: str
    resultado: Literal["positivo", "negativo"]


@router.post("/{animal_id:int}/resultado")
def resultado(animal_id: int, d: ResultadoIn, user: dict = Depends(get_current_user)):
    rep = reprodutivo(animal_id)
    linha = next((r for r in rep["inseminacoes"] if r["op_key"] == d.op_key), None)
    if not linha or not linha["pode_resultado"]:
        raise _erro(409, "web.animal.error.result_not_allowed")
    tipo_tarefa, _ = _etapa(_como_data(linha["data_inseminacao"]))
    try:
        r = registar_resultado(
            operation_id=d.op_key, resultado=d.resultado, tipo_tarefa=tipo_tarefa, data=date.today(), utilizador=user["username"],
        )
    except InseminacaoError as e:
        raise _erro(409, "web.animal.error.result_failed", detalhe=str(e)) from e
    return {"resultado": r.get("resultado_gravado")}


@router.get("/{animal_id:int}/estadias")
def estadias(animal_id: int, _user: dict = Depends(get_current_user)):
    _animal(animal_id)
    lista = registos(_carregar_estadias_do_animal(animal_id), ["tipo_registo", "motivo", "estado", "data_entrada", "data_saida", "dias"])
    est = _obter_estadia_activa_inseminacao(animal_id)
    acomp = None
    if est:
        a = _obter_acompanhamento(est["id"]) or {}
        acomp = {
            "estadia_id": est["id"],
            "garanhao": est.get("garanhao"),
            "data_entrada": valor(est.get("data_entrada")),
            **{k: valor(a.get(k)) for k in ("data_inseminacao", "data_1o_diagnostico", "data_confirmacao", "data_2a_confirmacao", "data_parto_previsto", "resultado")},
        }
    return {"estadias": lista, "acompanhamento": acomp}


class AcompanhamentoIn(BaseModel):
    garanhao: str | None = None
    data_inseminacao: date | None = None
    data_1o_diagnostico: date | None = None
    data_confirmacao: date | None = None
    data_2a_confirmacao: date | None = None
    data_parto_previsto: date | None = None

    @field_validator("garanhao", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


@router.put("/{animal_id:int}/acompanhamento")
def acompanhamento(animal_id: int, d: AcompanhamentoIn, _user: dict = Depends(get_current_user)):
    est = _obter_estadia_activa_inseminacao(animal_id)
    if not est:
        raise _erro(409, "web.animal.error.no_insemination_stay")
    _atualizar_garanhao_estadia(est["id"], d.garanhao)
    _upsert_acompanhamento(animal_id, est["id"], d.model_dump(exclude={"garanhao"}))
    return estadias(animal_id)


# ── Garanhão ──────────────────────────────────────────────────────────────

@router.get("/{animal_id:int}/producao")
def producao(animal_id: int, _user: dict = Depends(get_current_user)):
    _animal(animal_id)
    df = _carregar_stock_garanhao(animal_id)
    total, lotes, motil, internas, externas = _kpis_stock_garanhao(df)
    return {
        "kpis": {"palhetas": total, "lotes": lotes, "motilidade": motil, "internas": internas, "externas": externas},
        "lotes": registos(df, ["data_producao", "origem_externa", "proprietario", "palhetas_iniciais", "palhetas_restantes",
                               "motilidade", "concentracao", "qualidade", "contentor", "canister", "andar"]),
    }


@router.get("/{animal_id:int}/fertilidade")
def fertilidade(animal_id: int, _user: dict = Depends(get_current_user)):
    _animal(animal_id)
    df = _carregar_inseminacoes_garanhao(animal_id)
    total, gest, _, taxa = _kpis_fertilidade_garanhao(df)
    return {
        "total": total,
        "gestacoes": gest,
        "taxa": round(taxa) if taxa is not None else None,
        "inseminacoes": registos(df, ["data_inseminacao", "egua", "proprietario", "palhetas_gastas", "num_lotes", "resultado"]),
    }


@router.get("/{animal_id:int}/alertas")
def alertas(animal_id: int, _user: dict = Depends(get_current_user)):
    """As mesmas regras da app atual: stock < 10 crítico, < 25 baixo; sem
    produção há mais de 30 dias (ou nunca); fertilidade > 70 % excelente."""
    _animal(animal_id)
    total, *_ = _kpis_stock_garanhao(_carregar_stock_garanhao(animal_id))
    *_, taxa = _kpis_fertilidade_garanhao(_carregar_inseminacoes_garanhao(animal_id))
    lista = []
    if total < 10:
        lista.append({"nivel": "erro", "chave": "web.animal.alert.stock_critical", "params": {"n": total}})
    elif total < 25:
        lista.append({"nivel": "aviso", "chave": "web.animal.alert.stock_low", "params": {"n": total}})
    ultima = _ultima_producao_garanhao(animal_id)
    if isinstance(ultima, str):
        try:
            ultima = datetime.strptime(ultima[:10], "%Y-%m-%d").date()
        except ValueError:
            ultima = None
    ultima = _como_data(ultima)
    if ultima:
        dias = (date.today() - ultima).days
        if dias > 30:
            lista.append({"nivel": "info", "chave": "web.animal.alert.no_recent", "params": {"data": ultima.isoformat(), "dias": dias}})
    else:
        lista.append({"nivel": "info", "chave": "web.animal.alert.no_production", "params": {}})
    if taxa is not None and taxa > 70:
        lista.append({"nivel": "ok", "chave": "web.animal.alert.great_fertility", "params": {"taxa": round(taxa)}})
    return lista


@router.get("/{animal_id:int}/colheitas")
def colheitas(animal_id: int, _user: dict = Depends(get_current_user)):
    _animal(animal_id)
    return registos(listar_colheitas_futuras(animal_id), ["id", "data_tarefa", "urgencia", "motivo"])


class ColheitaIn(BaseModel):
    data: date


@router.post("/{animal_id:int}/colheitas", status_code=201)
def agendar(animal_id: int, d: ColheitaIn, user: dict = Depends(get_current_user)):
    a = _animal(animal_id)
    if d.data < date.today():
        raise _erro(422, "web.animal.error.collection_past")
    tid = agendar_colheita(animal_id=animal_id, data_tarefa=d.data, utilizador=user["username"], motivo=f"Colheita — {a.get('nome') or '—'}")
    return {"id": tid}


@router.delete("/{animal_id:int}/colheitas/{tarefa_id:int}")
def cancelar(animal_id: int, tarefa_id: int, _user: dict = Depends(get_current_user)):
    if not any(c["id"] == tarefa_id for c in colheitas(animal_id)):
        raise _erro(404, "web.animal.error.collection_not_found")
    if not cancelar_colheita(tarefa_id):
        raise _erro(409, "web.animal.error.collection_not_found")
    return {"ok": True}
