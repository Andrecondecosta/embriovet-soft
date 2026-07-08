"""Repository de transferências — funções de escrita que envolvem
reversão / desfazer operações.

Este módulo concentra a lógica antes espalhada em `dashboard_page.py`
(`reverter_acao`), que era read-only-friendly mas fazia UPDATE/DELETE
no meio da renderização e usava comparações por texto do garanhão
(`WHERE garanhao = (SELECT garanhao FROM estoque_dono...)`) para
localizar o lote destino.

A nova versão:
- Faz reversão FK-based: o lote destino é localizado por
  `animal_id + dono_id + localização (contentor_id, canister, andar)`,
  nunca por texto.
- Devolve `bool` (True/False) sem escrever no `st` — retornos limpos
  para o chamador decidir mensagens.
- Invalida o `st.cache_data` no fim (via `invalidate_data_cache`).

Todos os writes correm dentro de uma única transacção — em caso de
falha faz-se rollback e devolve-se False.
"""

from __future__ import annotations

import logging
from typing import Optional

from modules.db import get_connection, invalidate_data_cache

logger = logging.getLogger(__name__)


TIPOS_VALIDOS = {"transfer_internal", "transfer_external", "insemination"}


def reverter_operacao(
    tipo: str,
    action_id: Optional[int] = None,
    operation_id: Optional[str] = None,
) -> bool:
    """Reverte uma operação e elimina o(s) seu(s) registo(s).

    Regras:
    - Se `operation_id` for passado, reverte **TODOS** os lotes da
      operação (multi-lote). Caso contrário, reverte só a linha
      identificada por `action_id`.
    - `tipo` deve estar em `TIPOS_VALIDOS`.

    Efeitos por tipo:
    - `insemination`: devolve `palhetas_gastas` a `estoque_dono` (por
      `estoque_id`, quando existir) e apaga as linhas em `inseminacoes`.
    - `transfer_internal`: devolve `quantidade` ao lote de origem
      (`estoque_id`) e retira do lote destino localizado por
      `(animal_id, dono_id, contentor_id, canister, andar)` — nada de
      texto. Apaga a linha em `transferencias`.
    - `transfer_external`: devolve `quantidade` ao lote de origem
      (`estoque_id`) e apaga a linha em `transferencias_externas`.
    """
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: {tipo!r}")
    if not operation_id and not action_id:
        raise ValueError("é preciso passar operation_id OU action_id")

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            try:
                if tipo == "transfer_internal":
                    _reverter_transfer_internal(cur, action_id, operation_id)
                elif tipo == "transfer_external":
                    _reverter_transfer_external(cur, action_id, operation_id)
                else:  # insemination
                    _reverter_insemination(cur, action_id, operation_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
    except Exception as e:
        logger.error(f"reverter_operacao falhou (tipo={tipo}): {e}")
        return False

    invalidate_data_cache()
    return True


# ────────────────────────────────────────────────────────────────────
# Helpers internos — todos assumem que estão dentro de uma transacção
# ────────────────────────────────────────────────────────────────────

def _reverter_transfer_internal(cur, action_id, operation_id) -> None:
    """Reverte transferência(s) interna(s) — devolve palhetas ao lote
    origem e retira do lote destino (FK-based, sem texto)."""
    if operation_id:
        cur.execute(
            "SELECT id, estoque_id, quantidade, proprietario_destino_id "
            "FROM transferencias WHERE operation_id = %s::uuid",
            (operation_id,),
        )
    else:
        cur.execute(
            "SELECT id, estoque_id, quantidade, proprietario_destino_id "
            "FROM transferencias WHERE id = %s",
            (int(action_id),),
        )
    rows = cur.fetchall()

    for row_id, e_id, qtd, dest_id in rows:
        qtd = int(qtd or 0)
        if not e_id:
            continue

        # Devolve palhetas ao lote origem.
        cur.execute(
            "UPDATE estoque_dono SET existencia_atual = existencia_atual + %s "
            "WHERE id = %s",
            (qtd, e_id),
        )

        # Localiza lote destino via FK (animal_id + dono_id + localização
        # exacta), NUNCA por nome do garanhão.
        cur.execute(
            """
            SELECT dest.id, dest.existencia_atual
            FROM estoque_dono src
            JOIN estoque_dono dest ON
                dest.animal_id = src.animal_id AND
                dest.dono_id   = %s AND
                COALESCE(dest.contentor_id, 0) = COALESCE(src.contentor_id, 0) AND
                COALESCE(dest.canister,     0) = COALESCE(src.canister,     0) AND
                COALESCE(dest.andar,        0) = COALESCE(src.andar,        0)
            WHERE src.id = %s
            ORDER BY dest.existencia_atual DESC
            LIMIT 1
            """,
            (dest_id, e_id),
        )
        lote_dest = cur.fetchone()
        if lote_dest:
            dest_id_row, dest_exist = int(lote_dest[0]), int(lote_dest[1] or 0)
            nova = dest_exist - qtd
            if nova <= 0:
                cur.execute("DELETE FROM estoque_dono WHERE id = %s", (dest_id_row,))
            else:
                cur.execute(
                    "UPDATE estoque_dono SET existencia_atual = %s WHERE id = %s",
                    (nova, dest_id_row),
                )

    if operation_id:
        cur.execute(
            "DELETE FROM transferencias WHERE operation_id = %s::uuid",
            (operation_id,),
        )
    else:
        cur.execute("DELETE FROM transferencias WHERE id = %s", (int(action_id),))


def _reverter_transfer_external(cur, action_id, operation_id) -> None:
    """Reverte transferência(s) externa(s) — devolve palhetas ao lote
    origem. Não há lote destino no sistema."""
    if operation_id:
        cur.execute(
            "SELECT id, estoque_id, quantidade "
            "FROM transferencias_externas WHERE operation_id = %s::uuid",
            (operation_id,),
        )
    else:
        cur.execute(
            "SELECT id, estoque_id, quantidade "
            "FROM transferencias_externas WHERE id = %s",
            (int(action_id),),
        )
    rows = cur.fetchall()

    for row_id, e_id, qtd in rows:
        if not e_id:
            continue
        cur.execute(
            "UPDATE estoque_dono SET existencia_atual = existencia_atual + %s "
            "WHERE id = %s",
            (int(qtd or 0), e_id),
        )

    if operation_id:
        cur.execute(
            "DELETE FROM transferencias_externas WHERE operation_id = %s::uuid",
            (operation_id,),
        )
    else:
        cur.execute(
            "DELETE FROM transferencias_externas WHERE id = %s",
            (int(action_id),),
        )


def _reverter_insemination(cur, action_id, operation_id) -> None:
    """Reverte inseminação(ões) — devolve palhetas ao stock e apaga
    as linhas em `inseminacoes`. Não mexe em tarefas de trabalho diário
    nem em acompanhamentos (mantém comportamento anterior)."""
    if operation_id:
        cur.execute(
            "SELECT id, estoque_id, palhetas_gastas "
            "FROM inseminacoes WHERE operation_id = %s::uuid",
            (operation_id,),
        )
    else:
        cur.execute(
            "SELECT id, estoque_id, palhetas_gastas "
            "FROM inseminacoes WHERE id = %s",
            (int(action_id),),
        )
    rows = cur.fetchall()

    for row_id, e_id, pals in rows:
        if e_id:
            cur.execute(
                "UPDATE estoque_dono SET existencia_atual = existencia_atual + %s "
                "WHERE id = %s",
                (int(pals or 0), e_id),
            )

    if operation_id:
        cur.execute(
            "DELETE FROM inseminacoes WHERE operation_id = %s::uuid",
            (operation_id,),
        )
    else:
        cur.execute("DELETE FROM inseminacoes WHERE id = %s", (int(action_id),))
