"""Próxima consulta obrigatória (ficha da égua e Trabalho diário).

Depois de gravar uma consulta no Diário clínico marca-se a seguinte — uma
tarefa 'observacao_clinica' no Trabalho diário, só uma por égua (marcar de
novo muda a data) — ou terminam-se as consultas da égua (só Gestor ou
Administrador, escrevendo TERMINAR). Terminar fecha só as consultas: DG,
confirmações e tratamentos continuam. Um exame novo recomeça o ciclo.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.deps import get_current_user, require_nivel
from modules.db import get_connection
from modules.pages.animal_page import _obter_estadia_activa

router = APIRouter(prefix="/api/animais", tags=["consultas"])

TIPOS_CONSULTA = ("observacao_clinica", "primeira_observacao")
PALAVRA_TERMINAR = "TERMINAR"


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _urgencia(dia: date) -> str:
    falta = (dia - date.today()).days
    return "hoje" if falta <= 0 else "amanha" if falta == 1 else "observacao"


def _egua(cur, animal_id: int) -> tuple:
    cur.execute(
        "SELECT falta_proxima_consulta, consultas_terminadas_em FROM animais WHERE id = %s AND tipo IN ('egua', 'receptora')",
        (animal_id,),
    )
    row = cur.fetchone()
    if not row:
        raise _erro(404, "web.stays.error.animal_not_found")
    return row


def _marcada(cur, animal_id: int):
    """A próxima consulta por fazer (hoje ou à frente), se houver."""
    cur.execute(
        """
        SELECT id, data_tarefa, motivo FROM trabalho_diario
        WHERE animal_id = %s AND concluida = FALSE AND tipo = 'observacao_clinica' AND data_tarefa >= CURRENT_DATE
        ORDER BY data_tarefa, id LIMIT 1
        """,
        (animal_id,),
    )
    return cur.fetchone()


def _inseminar(cur, animal_id: int):
    """A tarefa "Inseminar" por fazer (hoje ou à frente), se houver."""
    cur.execute(
        """SELECT id, data_tarefa, motivo FROM trabalho_diario
           WHERE animal_id = %s AND NOT concluida AND tipo = 'inseminar' AND data_tarefa >= CURRENT_DATE
           ORDER BY data_tarefa, id LIMIT 1""",
        (animal_id,),
    )
    return cur.fetchone()


def _observacoes(motivo: str | None) -> str:
    """O motivo guarda "Próxima consulta" ou "Próxima consulta: <obs>"."""
    return (motivo or "").partition(": ")[2] if (motivo or "").startswith("Próxima consulta") else ""


def gravou_consulta(cur, animal_id: int) -> None:
    """Chamado ao gravar uma consulta nova: falta marcar a próxima e, se as
    consultas estavam terminadas, recomeçam."""
    cur.execute(
        "UPDATE animais SET falta_proxima_consulta = TRUE, consultas_terminadas_em = NULL, consultas_terminadas_por = NULL WHERE id = %s",
        (animal_id,),
    )


@router.get("/{animal_id:int}/proxima-consulta")
def estado(animal_id: int, user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            falta, terminadas = _egua(cur, animal_id)
            m = _marcada(cur, animal_id)
            # O que já está marcado (DG, tratamentos, inseminar…), para não
            # repetirem uma consulta no mesmo dia.
            cur.execute(
                """
                SELECT tipo, data_tarefa, motivo FROM trabalho_diario
                WHERE animal_id = %s AND concluida = FALSE AND data_tarefa >= CURRENT_DATE AND tipo NOT IN %s
                ORDER BY data_tarefa, id LIMIT 10
                """,
                (animal_id, TIPOS_CONSULTA),
            )
            outras = [{"tipo": t, "data": d.isoformat(), "motivo": mo} for t, d, mo in cur.fetchall()]
            ins = _inseminar(cur, animal_id)
    return {
        # Já há uma marcada (ex.: viu-se a égua antes do dia): não falta.
        "falta": bool(falta) and not m,
        "terminadas": terminadas is not None,
        "marcada": {"id": m[0], "data": m[1].isoformat(), "observacoes": _observacoes(m[2])} if m else None,
        "outras": outras,
        # Inseminação marcada (da indução): pode ser a próxima consulta.
        "inseminar": {"id": ins[0], "data": ins[1].isoformat(), "motivo": ins[2]} if ins else None,
        "pode_terminar": user["nivel"] in ("Gestor", "Administrador"),
    }


class MarcarIn(BaseModel):
    data: date
    observacoes: str | None = Field(default=None, max_length=300)


@router.put("/{animal_id:int}/proxima-consulta")
def marcar(animal_id: int, d: MarcarIn, user: dict = Depends(get_current_user)):
    if d.data <= date.today():
        raise _erro(422, "web.next_visit.error.future")
    obs = (d.observacoes or "").strip()
    motivo = f"Próxima consulta: {obs}" if obs else "Próxima consulta"
    with get_connection() as conn:
        with conn.cursor() as cur:
            _egua(cur, animal_id)
            m = _marcada(cur, animal_id)
            if m:
                # Só uma consulta marcada por égua: marcar de novo muda-a.
                cur.execute(
                    "UPDATE trabalho_diario SET data_tarefa = %s, motivo = %s, urgencia = %s, utilizador = %s WHERE id = %s",
                    (d.data, motivo, _urgencia(d.data), user["username"][:50], m[0]),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, tipo, motivo, urgencia, criado_automaticamente, utilizador)
                    VALUES (%s, %s, %s, 'observacao_clinica', %s, %s, FALSE, %s)
                    """,
                    (animal_id, _obter_estadia_activa(animal_id), d.data, motivo, _urgencia(d.data), user["username"][:50]),
                )
            cur.execute(
                "UPDATE animais SET falta_proxima_consulta = FALSE, consultas_terminadas_em = NULL, consultas_terminadas_por = NULL WHERE id = %s",
                (animal_id,),
            )
        conn.commit()
    return {"ok": True}


class TerminarIn(BaseModel):
    confirmacao: str


@router.post("/{animal_id:int}/terminar-consultas")
def terminar(animal_id: int, d: TerminarIn, user: dict = Depends(require_nivel("Gestor"))):
    if d.confirmacao.strip().upper() != PALAVRA_TERMINAR:
        raise _erro(422, "web.next_visit.error.word")
    with get_connection() as conn:
        with conn.cursor() as cur:
            _egua(cur, animal_id)
            cur.execute(
                """
                UPDATE trabalho_diario
                SET concluida = TRUE, cancelada = TRUE, data_conclusao = CURRENT_DATE, concluida_por = %s,
                    observacoes_conclusao = 'Consultas terminadas'
                WHERE animal_id = %s AND concluida = FALSE AND tipo IN %s
                """,
                (user["username"][:50], animal_id, TIPOS_CONSULTA),
            )
            fechadas = cur.rowcount
            cur.execute(
                """UPDATE animais SET falta_proxima_consulta = FALSE, consultas_terminadas_em = NOW(), consultas_terminadas_por = %s
                   WHERE id = %s""",
                (user["username"][:50], animal_id),
            )
        conn.commit()
    return {"ok": True, "fechadas": fechadas}


def sem_proxima() -> list[dict]:
    """Éguas com consulta gravada e sem a próxima marcada (Trabalho diário)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.nome, a.tipo, d.nome FROM animais a LEFT JOIN dono d ON d.id = a.dono_id
                WHERE a.falta_proxima_consulta AND a.ativo IS NOT FALSE
                  AND NOT EXISTS (
                      SELECT 1 FROM trabalho_diario t
                      WHERE t.animal_id = a.id AND t.concluida = FALSE AND t.tipo = 'observacao_clinica' AND t.data_tarefa >= CURRENT_DATE
                  )
                ORDER BY LOWER(a.nome)
                """
            )
            return [{"animal_id": i, "animal": n, "tipo": t, "dono": dn} for i, n, t, dn in cur.fetchall()]


class InseminacaoIn(BaseModel):
    data: date


@router.put("/{animal_id:int}/proxima-consulta/inseminacao")
def inseminacao_como_proxima(animal_id: int, d: InseminacaoIn, _user: dict = Depends(get_current_user)):
    """A inseminação marcada é a próxima consulta: muda-se o dia dela (se
    for preciso) e não se marca outra consulta."""
    if d.data < date.today():
        raise _erro(422, "web.next_visit.error.past")
    with get_connection() as conn:
        with conn.cursor() as cur:
            _egua(cur, animal_id)
            ins = _inseminar(cur, animal_id)
            if not ins:
                raise _erro(409, "web.next_visit.error.no_insemination")
            cur.execute("UPDATE trabalho_diario SET data_tarefa = %s WHERE id = %s", (d.data, ins[0]))
            cur.execute(
                "UPDATE animais SET falta_proxima_consulta = FALSE, consultas_terminadas_em = NULL, consultas_terminadas_por = NULL WHERE id = %s",
                (animal_id,),
            )
        conn.commit()
    return {"ok": True}
