"""Estadias e visitas — equivalente a `modules/pages/estadias_page.py`
(e à criação rápida de animal de `modules/components/modal_animal.py`).

Separadores: Internadas agora, Movimentos da semana (entram/saem nos
próximos 7 dias) e Histórico (passagens de um mês). Ações: nova estadia /
visita / externo (com um animal existente ou criando-o na hora, numa só
transação, como o modal da app atual) e registar saída.

As regras da tabela `estadias` que a app atual mexe em tempo de execução
(`_ensure_*_constraints`) são chamadas nos mesmos momentos, para as duas
apps se comportarem igual enquanto coexistem.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator

from backend.deps import get_current_user
from backend.serial import registos
from modules.db import get_connection
from modules.pages.estadias_page import (
    _carregar_estadias,
    _ensure_externo_constraints,
    _ensure_saida_constraints,
)

router = APIRouter(prefix="/api", tags=["estadias"])

TipoRegisto = Literal["estadia", "visita", "externo"]
Motivo = Literal["inseminacao", "colheita", "diagnostico", "tratamento", "embriao"]
TipoAnimal = Literal["egua", "garanhao", "receptora"]
EstadoSaida = Literal["gestante", "alta", "sem_resultado", "transferido"]
# Janela de "esta semana": 7 dias, hoje incluído (como a app atual).
JANELA_MOVIMENTOS = 6

COLUNAS = ["id", "animal_id", "animal", "tipo", "animal_tipo", "proprietario", "motivo", "estado",
           "data_entrada", "data_saida", "alojamento_nome", "dias_internado"]


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _texto(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _lista(where: str, params: tuple, tipo_animal: TipoAnimal | None) -> list[dict]:
    df = _carregar_estadias(where, params)
    if tipo_animal:
        df = df[df["animal_tipo"] == tipo_animal]
    return registos(df, COLUNAS)


# ── Pesquisa de animais (Estadias e Trabalho diário) ──────────────────────

@router.get("/animais/pesquisa")
def pesquisar_animais(
    q: str = "",
    tipo: TipoAnimal | None = None,
    _user: dict = Depends(get_current_user),
):
    """Por nome, como `search_animal`: só ativos, até 50, com o dono e se
    tem estadia/visita em aberto."""
    sql = """
        SELECT a.id, a.nome, a.tipo, a.dono_id, d.nome AS proprietario,
               (SELECT e.tipo_registo FROM estadias e
                 WHERE e.animal_id = a.id AND e.data_saida IS NULL
                 ORDER BY e.data_entrada DESC, e.id DESC LIMIT 1) AS em_aberto
        FROM animais a
        LEFT JOIN dono d ON d.id = a.dono_id
        WHERE a.ativo = TRUE AND LOWER(a.nome) LIKE LOWER(%s)
    """
    params: list = [f"%{q.strip()}%"]
    if tipo:
        sql += " AND a.tipo = %s"
        params.append(tipo)
    sql += " ORDER BY LOWER(a.nome) LIMIT 50"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = ["id", "nome", "tipo", "dono_id", "proprietario", "em_aberto"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


# ── Listas ────────────────────────────────────────────────────────────────

@router.get("/estadias/internadas")
def internadas(tipo_animal: TipoAnimal | None = None, _user: dict = Depends(get_current_user)):
    total = _lista("e.data_saida IS NULL", (), None)
    itens = [r for r in total if not tipo_animal or r["animal_tipo"] == tipo_animal]
    return {"total": len(total), "itens": itens}


@router.get("/estadias/movimentos")
def movimentos(_user: dict = Depends(get_current_user)):
    hoje = date.today()
    fim = hoje + timedelta(days=JANELA_MOVIMENTOS)
    entram = _lista("e.data_entrada BETWEEN %s AND %s", (hoje, fim), None)
    saem = _lista("e.data_saida IS NOT NULL AND e.data_saida BETWEEN %s AND %s", (hoje, fim), None)
    return {
        "inicio": hoje.isoformat(),
        "fim": fim.isoformat(),
        "entram": sorted(entram, key=lambda r: r["data_entrada"] or ""),
        "saem": sorted(saem, key=lambda r: r["data_saida"] or ""),
    }


@router.get("/estadias/historico")
def historico(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    tipo_animal: TipoAnimal | None = None,
    _user: dict = Depends(get_current_user),
):
    """Todas as passagens que tocam o mês (inclui as já encerradas)."""
    primeiro = date(ano, mes, 1)
    ultimo = date(ano, mes, calendar.monthrange(ano, mes)[1])
    total = _lista("e.data_entrada <= %s AND (e.data_saida IS NULL OR e.data_saida >= %s)", (ultimo, primeiro), None)
    itens = [r for r in total if not tipo_animal or r["animal_tipo"] == tipo_animal]
    return {"total": len(total), "itens": sorted(itens, key=lambda r: r["data_entrada"] or "", reverse=True)}


@router.get("/estadias/opcoes")
def opcoes(_user: dict = Depends(get_current_user)):
    """Donos ativos e alojamentos ativos para o formulário."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM dono WHERE ativo = TRUE ORDER BY LOWER(nome)")
            donos = [{"id": r[0], "nome": r[1]} for r in cur.fetchall()]
            cur.execute("SELECT id, nome, tipo, capacidade FROM alojamentos WHERE ativo = TRUE ORDER BY tipo, LOWER(nome)")
            aloj = [{"id": r[0], "nome": r[1], "tipo": r[2], "capacidade": r[3]} for r in cur.fetchall()]
    return {"donos": donos, "alojamentos": aloj, "motivos_por_tipo": MOTIVOS_POR_TIPO}


# ── Nova estadia / visita / externo ───────────────────────────────────────

class AnimalNovo(BaseModel):
    """Campos da criação rápida de animal (`modal_animal`)."""

    nome: str | None = None
    tipo: TipoAnimal = "egua"
    raca: str | None = None
    pelagem: str | None = None
    data_nascimento: date | None = None
    numero_registo: str | None = None
    chip: str | None = None
    altura: float | None = None
    peso: float | None = None
    pai: str | None = None
    mae: str | None = None
    avo_paterno: str | None = None
    avo_materno: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class EstadiaIn(BaseModel):
    animal_id: int | None = None
    animal: AnimalNovo | None = None
    tipo_registo: TipoRegisto | None = None  # obrigatório (validado em `criar`)
    motivo: Motivo = "inseminacao"
    dono_id: int | None = None
    data_entrada: date
    alojamento_id: int | None = None
    observacoes: str | None = None

    @field_validator("observacoes", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


ESTADO_INICIAL = {"estadia": "internado", "visita": "visitante", "externo": "externo"}

# Motivos possíveis por tipo de animal: a égua não faz colheita; a receptora
# só recebe embriões (e pode ter diagnóstico); o garanhão só faz colheita e
# tratamento.
MOTIVOS_POR_TIPO = {
    "egua": ("inseminacao", "diagnostico", "tratamento", "embriao"),
    "receptora": ("embriao", "diagnostico"),
    "garanhao": ("colheita", "tratamento"),
}


def _validar_motivo(tipo_animal: str, motivo: str):
    if motivo not in MOTIVOS_POR_TIPO.get(tipo_animal, ()):
        raise _erro(422, "web.stays.error.reason_not_allowed")


@router.post("/estadias", status_code=201)
def criar(d: EstadiaIn, user: dict = Depends(get_current_user)):
    if (d.animal_id is None) == (d.animal is None):
        raise _erro(422, "web.stays.error.animal_required")
    if not d.tipo_registo:
        raise _erro(422, "web.stays.error.kind_required")
    if not d.dono_id:
        raise _erro(422, "web.stays.error.owner_required")
    if d.tipo_registo == "estadia" and not d.alojamento_id:
        raise _erro(422, "web.stays.error.housing_required")
    if d.tipo_registo == "externo":
        _ensure_externo_constraints()

    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                if d.animal is not None:
                    a = d.animal
                    if not a.nome:
                        raise _erro(422, "web.stays.error.animal_name_required")
                    _validar_motivo(a.tipo, d.motivo)
                    # Só bloqueia o mesmo nome com o MESMO dono (como a app atual).
                    cur.execute(
                        "SELECT 1 FROM animais WHERE LOWER(nome) = LOWER(%s) AND dono_id = %s LIMIT 1",
                        (a.nome, d.dono_id),
                    )
                    if cur.fetchone():
                        raise _erro(409, "web.stays.error.animal_exists", name=a.nome)
                    cur.execute(
                        """
                        INSERT INTO animais (
                            nome, tipo, raca, pelagem, data_nascimento, numero_registo, chip,
                            altura, peso, dono_id, pai, mae, avo_paterno, avo_materno,
                            observacoes, is_receptora, ativo
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                        RETURNING id
                        """,
                        (
                            a.nome, a.tipo, a.raca, a.pelagem, a.data_nascimento, a.numero_registo, a.chip,
                            a.altura if a.altura and a.altura > 0 else None,
                            a.peso if a.peso and a.peso > 0 else None,
                            d.dono_id, a.pai, a.mae, a.avo_paterno, a.avo_materno,
                            d.observacoes, a.tipo == "receptora",
                        ),
                    )
                    animal_id = cur.fetchone()[0]
                else:
                    animal_id = d.animal_id
                    cur.execute("SELECT tipo FROM animais WHERE id = %s", (animal_id,))
                    row = cur.fetchone()
                    if not row:
                        raise _erro(404, "web.stays.error.animal_not_found")
                    _validar_motivo(row[0], d.motivo)
                    # Uma só estadia em aberto por animal (a BD também o impede).
                    cur.execute("SELECT id FROM estadias WHERE animal_id = %s AND data_saida IS NULL LIMIT 1", (animal_id,))
                    if cur.fetchone():
                        raise _erro(409, "web.stays.error.already_open")
                cur.execute(
                    """
                    INSERT INTO estadias (
                        tipo_registo, animal_id, alojamento_id, dono_id, data_entrada, data_saida,
                        motivo, estado, observacoes_entrada, criado_por
                    ) VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        d.tipo_registo, animal_id,
                        d.alojamento_id if d.tipo_registo != "externo" else None,
                        d.dono_id, d.data_entrada, d.motivo, ESTADO_INICIAL[d.tipo_registo],
                        d.observacoes, user["username"],
                    ),
                )
                estadia_id = cur.fetchone()[0]
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    return {"id": estadia_id, "animal_id": animal_id}


# ── Registar saída ────────────────────────────────────────────────────────

class SaidaIn(BaseModel):
    data_saida: date
    estado: EstadoSaida
    observacoes: str | None = None

    @field_validator("observacoes", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


@router.post("/estadias/{estadia_id}/saida")
def registar_saida(estadia_id: int, d: SaidaIn, _user: dict = Depends(get_current_user)):
    # "Outro" exige descrição, como na app atual.
    if d.estado == "sem_resultado" and not d.observacoes:
        raise _erro(422, "web.stays.error.exit_notes_required")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data_entrada, data_saida FROM estadias WHERE id = %s", (estadia_id,))
            row = cur.fetchone()
    if not row:
        raise _erro(404, "web.stays.error.not_found")
    if row[1] is not None:
        raise _erro(409, "web.stays.error.already_closed")
    if d.data_saida < row[0]:
        raise _erro(422, "web.stays.error.exit_before_entry")
    _ensure_saida_constraints()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE estadias SET data_saida = %s, estado = %s, observacoes_saida = %s WHERE id = %s",
                (d.data_saida, d.estado, d.observacoes, estadia_id),
            )
        conn.commit()
    return {"ok": True}
