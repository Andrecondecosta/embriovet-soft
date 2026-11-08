"""Registo clínico das éguas (novo "Registo de hoje") — desenho com ovário
esquerdo/direito, útero e cérvix, mais diagnóstico de gestação (DG) e
tratamento (TX). Desenhado pelo utilizador em folhas (out. 2026).

Fica na tabela `registo_clinico` (conteúdo em JSONB). Os registos antigos
de `diario_clinico` continuam a aparecer no histórico, só de leitura.

Ao gravar um registo novo:
- conclui as tarefas de hoje da égua (como o registo antigo);
- DG positivo/negativo regista o resultado da inseminação pendente
  (a mesma função dos botões +/− do historial);
- "Marcar TX" cria tarefas de tratamento nos dias seguintes; a indução
  fica como tarefa no dia marcado;
- "!" (prioritário) passa a próxima tarefa da égua a urgente;
- antibióticos/infusões escritos à mão ficam guardados para a próxima vez.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.deps import get_current_user
from backend.serial import valor
from modules.db import get_connection
from modules.pages.animal_page import _carregar_animal, _concluir_tarefas_animal_hoje, _obter_estadia_activa
from modules.repositories.insemination_repo import InseminacaoError, registar_diagnostico, registar_resultado

router = APIRouter(prefix="/api/animais", tags=["registo_clinico"])

HORAS = ("8h", "10h", "12h", "14h", "16h")
ANTIBIOTICOS = ("Genta", "Genta + Peni", "Ceftiofur", "Marbofloxacina")
EDEMA = ("0", "+", "++", "+++")
LIQUIDO = ("0", "<2 cm", "+", "++", "+++")
CERVIX = ("1 · fechado", "2 · intermédio", "3 · aberto")
# Tarefas de hoje que obrigam a responder no registo (o registo fecha-as).
TAREFAS_OVULACAO = ("verificar_ovulacao",)
TAREFAS_DG = ("diagnostico_gestacao", "confirmacao_gestacao", "segunda_confirmacao")


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _texto(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


# ── Modelos (a mesma forma que o ecrã usa) ────────────────────────────────

class Foliculo(BaseModel):
    tamanho: int = Field(ge=9, le=61)  # 9 = "<10", 61 = ">60"
    achados: list[Literal["NS", "OV", "FH", "MF", "CL"]] = []


class Ovario(BaseModel):
    foliculos: list[Foliculo] = []
    comentario: str | None = None

    @field_validator("comentario", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class Utero(BaseModel):
    edema: int = Field(ge=0, le=len(EDEMA) - 1)
    liquido: int = Field(ge=0, le=len(LIQUIDO) - 1)
    comentario: str | None = None

    @field_validator("comentario", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class Cervix(BaseModel):
    grau: int = Field(ge=1, le=3)
    comentario: str | None = None

    @field_validator("comentario", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class Ocitocina(BaseModel):
    vezes: int = Field(ge=1, le=4)
    hora: Literal["8h", "10h", "12h", "14h", "16h"]


class Infusao(BaseModel):
    ab: list[str] = []
    abOutro: str | None = None
    mucolitico: bool = False
    outro: str | None = None

    @field_validator("abOutro", "outro", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class Inducao(BaseModel):
    data: datetime
    produto: str | None = None

    @field_validator("produto", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class Marcar(BaseModel):
    dias: Literal["1", "2", "3", "agenda"]
    data: date | None = None  # quando dias = "agenda"


class Tratamento(BaseModel):
    ocitocina: Ocitocina | None = None
    pg: int = Field(default=0, ge=0, le=4)
    p4: bool = False
    infusao: Infusao | None = None
    zaragatoa: bool = False
    lavagem: int = Field(default=0, ge=0, le=4)
    inducao: Inducao | None = None
    marcar: Marcar | None = None


SimNao = Literal["sim", "nao", "nao_avaliado"]


class Ovulacao(BaseModel):
    """Exame de confirmação de ovulação (D+1): "não avaliado" é diferente
    de "não"."""
    ovulacao: SimNao
    fh: SimNao  # folículo hemorrágico anovulatório


class Dados(BaseModel):
    OE: Ovario | None = None
    OD: Ovario | None = None
    UT: Utero | None = None
    CER: Cervix | None = None
    TX: Tratamento | None = None
    OVU: Ovulacao | None = None
    DG: Literal["Positivo", "Negativo", "Inconclusivo", "Sem exame"] | None = None


class RegistoIn(BaseModel):
    data_registo: datetime
    dados: Dados
    prioritario: bool = False


# ── Textos curtos (tarefas e histórico) ───────────────────────────────────

def _mm(n: int) -> str:
    return "<10" if n <= 9 else ">60" if n >= 61 else str(n)


def resumo_tx(t: Tratamento) -> str:
    inf = t.infusao
    partes = [
        t.ocitocina and f"Ocitocina {t.ocitocina.vezes}× {t.ocitocina.hora}",
        t.pg and f"PG {t.pg}×",
        t.p4 and "P4",
        inf and "Infusão " + " + ".join(x for x in [*inf.ab, inf.abOutro, "Mucolítico" if inf.mucolitico else None, inf.outro] if x),
        t.zaragatoa and "Zaragatoa",
        t.lavagem and f"Lavagem {t.lavagem}×",
        t.inducao and f"Indução {t.inducao.produto + ' ' if t.inducao.produto else ''}{t.inducao.data:%d/%m %H:%M}",
    ]
    return " · ".join(p for p in partes if p)


# ── Leitura ───────────────────────────────────────────────────────────────

def _egua(animal_id: int) -> dict:
    a = _carregar_animal(animal_id)
    if not a:
        raise _erro(404, "web.animal.error.not_found")
    # O diário clínico é só para éguas e receptoras.
    if a["tipo"] == "garanhao":
        raise _erro(409, "web.animal.error.no_diary_stallion")
    return a


def _contexto(animal_id: int, a: dict) -> dict:
    """Cliente, local (box da estadia aberta) e garanhão (da estadia de inseminação)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT nome FROM dono WHERE id = %s", (a.get("dono_id"),))
            dono = cur.fetchone()
            cur.execute(
                """
                SELECT al.nome, e.garanhao FROM estadias e
                LEFT JOIN alojamentos al ON al.id = e.alojamento_id
                WHERE e.animal_id = %s AND e.data_saida IS NULL
                ORDER BY e.data_entrada DESC, e.id DESC LIMIT 1
                """,
                (animal_id,),
            )
            est = cur.fetchone()
    return {"cliente": dono[0] if dono else None, "local": est[0] if est else None, "garanhao": est[1] if est else None}


def _novos(animal_id: int, limite: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, data_registo, dados, prioritario, utilizador FROM registo_clinico
                WHERE animal_id = %s ORDER BY data_registo DESC, id DESC LIMIT %s
                """,
                (animal_id, limite),
            )
            rows = cur.fetchall()
    return [
        {"id": r[0], "data_registo": valor(r[1]), "dados": r[2] or {}, "prioritario": r[3], "utilizador": r[4], "antigo": False}
        for r in rows
    ]


def _antigos(animal_id: int, limite: int = 10) -> list[dict]:
    """Registos do diário antigo, convertidos para o mesmo formato (só leitura)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, data_registo, foliculo_mm, edema_grau, fluido_uterino, tratamentos, observacoes, utilizador, created_at
                FROM diario_clinico WHERE animal_id = %s ORDER BY data_registo DESC, id DESC LIMIT %s
                """,
                (animal_id, limite),
            )
            rows = cur.fetchall()
    lista = []
    for rid, dia, fol, edema, fluido, trat, obs, utilizador, criado in rows:
        quando = datetime.combine(dia, (criado or datetime.min).time()) if dia else criado
        lista.append(
            {
                "id": rid,
                "data_registo": valor(quando),
                "utilizador": utilizador,
                "prioritario": False,
                "antigo": True,
                # O registo antigo não diz o ovário: o folículo vai num texto à parte.
                "texto": " · ".join(
                    x for x in [
                        fol and f"Folículo {fol} mm",
                        edema is not None and f"Edema {edema}",
                        fluido and "Fluido uterino",
                        trat and f"TX: {trat}",
                        obs,
                    ] if x
                ),
                "dados": {},
            }
        )
    return lista


@router.get("/{animal_id:int}/registos")
def listar(animal_id: int, _user: dict = Depends(get_current_user)):
    a = _egua(animal_id)
    historico = sorted(_novos(animal_id) + _antigos(animal_id), key=lambda r: r["data_registo"] or "", reverse=True)[:10]
    tratamentos = [
        {"data_registo": r["data_registo"], "texto": resumo_tx(Tratamento(**r["dados"]["TX"]))}
        for r in _novos(animal_id, 30)
        if r["dados"].get("TX")
    ][:5]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT categoria, valor FROM opcoes_clinicas ORDER BY LOWER(valor)")
            extra = cur.fetchall()
    return {
        **_contexto(animal_id, a),
        "estadia_ativa": _obter_estadia_activa(animal_id) is not None,
        "historico": historico,
        "pede": _pede(animal_id),
        "tratamentos_anteriores": tratamentos,
        "antibioticos": [*ANTIBIOTICOS, *(v for c, v in extra if c == "antibiotico" and v not in ANTIBIOTICOS)],
        "infusoes": [v for c, v in extra if c == "infusao"],
    }


def _pede(animal_id: int) -> dict:
    """O que o registo de hoje tem de dizer, pelas tarefas por fazer hoje:
    a ovulação (tarefa D+1) e/ou o diagnóstico de gestação. Assim "não
    avaliado"/"sem exame" fica escrito, em vez de ficar em branco."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # A ovulação também se a tarefa D+1 ficou em atraso (o registo
            # fecha-a); o DG só no dia (fecha com o resultado).
            cur.execute(
                """
                SELECT DISTINCT tipo FROM trabalho_diario
                WHERE animal_id = %s AND concluida = FALSE
                  AND (data_tarefa = CURRENT_DATE OR (data_tarefa < CURRENT_DATE AND tipo = ANY(%s)))
                """,
                (animal_id, list(TAREFAS_OVULACAO)),
            )
            tipos = {r[0] for r in cur.fetchall()}
    return {"ovulacao": bool(tipos & set(TAREFAS_OVULACAO)), "dg": bool(tipos & set(TAREFAS_DG))}


# ── Gravar ────────────────────────────────────────────────────────────────

def _guardar_opcoes(cur, t: Tratamento | None):
    """"Outro" antibiótico / outras infusões ficam na lista para a próxima vez."""
    if not t or not t.infusao:
        return
    for categoria, v in (("antibiotico", t.infusao.abOutro), ("infusao", t.infusao.outro)):
        if v:
            cur.execute(
                """
                INSERT INTO opcoes_clinicas (categoria, valor) VALUES (%s, %s)
                ON CONFLICT (categoria, LOWER(valor)) DO NOTHING
                """,
                (categoria, v[:80]),
            )


def _urgencia(dia: date) -> str:
    falta = (dia - date.today()).days
    return "hoje" if falta <= 0 else "amanha" if falta == 1 else "observacao"


def _tarefa(cur, animal_id: int, estadia_id: int, dia: date, motivo: str, utilizador: str) -> int:
    cur.execute(
        """
        INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, tipo, motivo, urgencia, criado_automaticamente, utilizador)
        VALUES (%s, %s, %s, 'tratamento', %s, %s, FALSE, %s) RETURNING id
        """,
        (animal_id, estadia_id, dia, motivo[:500], _urgencia(dia), utilizador[:50]),
    )
    return cur.fetchone()[0]


def _resultado_dg(animal_id: int, dg: str, data_exame: datetime, utilizador: str, registo_id: int) -> str | None:
    """Guarda o DG na etapa certa (D+14/D+28/D+45) da inseminação mais
    recente da égua, com a data e hora do exame. Positivo/negativo também
    atualizam o resultado da inseminação (tarefas seguintes, como antes)."""
    from backend.routers.animais import _como_data, _etapa, _etapas_feitas, reprodutivo

    dia = data_exame.date()
    ops = [
        r for r in reprodutivo(animal_id)["inseminacoes"]
        # Só inseminações ainda em aberto (pendente ou positiva à espera das
        # confirmações): um DG nunca reescreve uma inseminação já fechada.
        if r["pode_resultado"] and _como_data(r["data_inseminacao"]) <= dia
    ]
    if not ops:
        return "sem_inseminacao"
    alvo = max(ops, key=lambda r: _como_data(r["data_inseminacao"]))
    tipo, _ = _etapa(_como_data(alvo["data_inseminacao"]), alvo["resultado"], _etapas_feitas(animal_id).get(alvo["op_key"], ()), dia)
    try:
        registar_diagnostico(
            animal_id=animal_id,
            operation_id=alvo["op_key"],
            tipo_tarefa=tipo,
            resultado={"Positivo": "positivo", "Negativo": "negativo", "Inconclusivo": "inconclusivo"}.get(dg, "sem_exame"),
            data_exame=data_exame,
            utilizador=utilizador,
            registo_clinico_id=registo_id,
        )
        if dg in ("Positivo", "Negativo"):
            registar_resultado(
                operation_id=alvo["op_key"],
                resultado="positivo" if dg == "Positivo" else "negativo",
                tipo_tarefa=tipo,
                data=dia,
                utilizador=utilizador,
            )
    except InseminacaoError as e:
        raise _erro(409, "web.animal.error.result_failed", detalhe=str(e)) from e
    return "registado"


@router.post("/{animal_id:int}/registos", status_code=201)
def criar(animal_id: int, d: RegistoIn, user: dict = Depends(get_current_user)):
    _egua(animal_id)
    estadia_id = _obter_estadia_activa(animal_id)
    if estadia_id is None:
        raise _erro(409, "web.animal.error.no_active_stay")
    dados = d.dados
    if not any([dados.OE, dados.OD, dados.UT, dados.CER, dados.TX, dados.OVU, dados.DG]):
        raise _erro(422, "web.registo.error.empty")
    pede = _pede(animal_id)
    if pede["ovulacao"] and not dados.OVU:
        raise _erro(422, "web.registo.error.ovulation_required")
    if pede["dg"] and not dados.DG:
        raise _erro(422, "web.registo.error.dg_required")
    if dados.TX and dados.TX.marcar and dados.TX.marcar.dias == "agenda" and not dados.TX.marcar.data:
        raise _erro(422, "web.registo.error.agenda_date")

    criadas: list[int] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO registo_clinico (animal_id, estadia_id, data_registo, dados, prioritario, utilizador)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s) RETURNING id
                    """,
                    (animal_id, estadia_id, d.data_registo, json.dumps(dados.model_dump(mode="json", exclude_none=True)), d.prioritario, user["username"][:50]),
                )
                rid = cur.fetchone()[0]
                _guardar_opcoes(cur, dados.TX)
                t = dados.TX
                if t and t.marcar:
                    # Repetir o tratamento: as mesmas vezes (na ocitocina, as mesmas horas).
                    motivo = f"Tratamento: {resumo_tx(t.model_copy(update={'inducao': None}))}"
                    dias = (
                        [t.marcar.data]
                        if t.marcar.dias == "agenda"
                        else [date.today() + timedelta(days=i) for i in range(1, int(t.marcar.dias) + 1)]
                    )
                    for dia in dias:
                        criadas.append(_tarefa(cur, animal_id, estadia_id, dia, motivo, user["username"]))
                if t and t.inducao:
                    produto = f" ({t.inducao.produto})" if t.inducao.produto else ""
                    criadas.append(
                        _tarefa(cur, animal_id, estadia_id, t.inducao.data.date(), f"Indução{produto} às {t.inducao.data:%H:%M}", user["username"])
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    concluidas = _concluir_tarefas_animal_hoje(animal_id, user["username"])
    resultado = _resultado_dg(animal_id, dados.DG, d.data_registo, user["username"], rid) if dados.DG else None
    if d.prioritario:
        # A próxima tarefa por fazer desta égua passa a urgente.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trabalho_diario SET urgencia = 'urgente'
                    WHERE id = (SELECT id FROM trabalho_diario WHERE animal_id = %s AND concluida = FALSE AND data_tarefa >= CURRENT_DATE
                                ORDER BY data_tarefa, id LIMIT 1)
                    """,
                    (animal_id,),
                )
            conn.commit()
    return {"id": rid, "tarefas_concluidas": concluidas, "tarefas_criadas": len(criadas), "resultado": resultado}


def _do_animal(animal_id: int, rid: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM registo_clinico WHERE id = %s AND animal_id = %s", (rid, animal_id))
            if not cur.fetchone():
                raise _erro(404, "web.animal.error.record_not_found")


@router.put("/{animal_id:int}/registos/{rid:int}")
def editar(animal_id: int, rid: int, d: RegistoIn, _user: dict = Depends(get_current_user)):
    """Corrigir um registo: só os dados (não volta a criar tarefas nem a
    registar resultados — isso acontece uma vez, ao gravar)."""
    _egua(animal_id)
    _do_animal(animal_id, rid)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE registo_clinico SET data_registo = %s, dados = %s::jsonb, prioritario = %s, updated_at = NOW() WHERE id = %s",
                (d.data_registo, json.dumps(d.dados.model_dump(mode="json", exclude_none=True)), d.prioritario, rid),
            )
            _guardar_opcoes(cur, d.dados.TX)
        conn.commit()
    return {"ok": True}


@router.delete("/{animal_id:int}/registos/{rid:int}")
def apagar(animal_id: int, rid: int, _user: dict = Depends(get_current_user)):
    _do_animal(animal_id, rid)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM registo_clinico WHERE id = %s", (rid,))
        conn.commit()
    return {"ok": True}
