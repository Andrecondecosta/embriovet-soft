"""Repositório de Colheitas (Pedido 8).

Domínio novo — colheitas agendadas do garanhão. Não misturamos com
`stock_repo` (as colheitas geram lotes só na conclusão, via
`inserir_stock`) nem com `insemination_repo` (semanticamente é o lado
oposto: as éguas recebem, o garanhão produz).

Contrato:
- `agendar_colheita(animal_id, data, utilizador, motivo=None) -> int`
- `listar_colheitas_futuras(animal_id) -> pd.DataFrame` (colheitas
  ainda não concluídas com `data_tarefa >= CURRENT_DATE`)
- `cancelar_colheita(tarefa_id) -> bool`
- `concluir_colheita(tarefa_id, utilizador) -> bool`  (chamado quando
  o `inserir_stock` guarda o lote a partir do prefill)

Todos os writes invalidam `st.cache_data` no sucesso.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import pandas as pd

from modules.db import get_connection, invalidate_data_cache

logger = logging.getLogger(__name__)

TIPO_COLHEITA = "colheita"


def _urgencia_pelo_delta(data_tarefa: date) -> str:
    """A colheita usa a mesma escala de urgência das outras tarefas."""
    hoje = date.today()
    if data_tarefa <= hoje:
        return "hoje"
    if data_tarefa == hoje.replace(day=hoje.day):  # segurança extra
        return "hoje"
    delta = (data_tarefa - hoje).days
    if delta <= 0:
        return "hoje"
    if delta == 1:
        return "amanha"
    return "observacao"


def agendar_colheita(
    animal_id: int,
    data_tarefa: date,
    utilizador: str,
    motivo: Optional[str] = None,
) -> int:
    """Agenda uma colheita para o garanhão numa data.

    Não impede duplicados — o veterinário pode marcar várias colheitas
    para o mesmo dia se assim quiser (comportamento pedido: "datas
    soltas, decididas pelo veterinário").

    Devolve o `id` da tarefa criada.
    """
    if animal_id is None:
        raise ValueError("animal_id obrigatório")

    motivo_final = motivo or "Colheita agendada"
    urgencia = _urgencia_pelo_delta(data_tarefa)

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO trabalho_diario (
                    animal_id, estadia_id, data_tarefa, tipo,
                    motivo, urgencia, criado_automaticamente, utilizador
                ) VALUES (%s, NULL, %s, %s, %s, %s, FALSE, %s)
                RETURNING id
                """,
                (
                    int(animal_id), data_tarefa, TIPO_COLHEITA,
                    motivo_final, urgencia, utilizador or "sistema",
                ),
            )
            new_id = int(cur.fetchone()[0])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    invalidate_data_cache()
    logger.info(f"Colheita agendada: garanhao={animal_id} data={data_tarefa} id={new_id}")
    return new_id


def listar_colheitas_futuras(animal_id: int) -> pd.DataFrame:
    """Lista as colheitas ainda por concluir do garanhão, hoje ou no
    futuro. Ordenadas por data ascendente.

    Devolve `id`, `data_tarefa`, `urgencia`, `motivo`, `concluida`.
    """
    sql = """
        SELECT id, data_tarefa, urgencia, motivo, concluida
        FROM trabalho_diario
        WHERE animal_id = %s
          AND tipo = %s
          AND concluida = FALSE
          AND data_tarefa >= CURRENT_DATE
        ORDER BY data_tarefa ASC, id ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(int(animal_id), TIPO_COLHEITA))


def cancelar_colheita(tarefa_id: int) -> bool:
    """Remove uma colheita agendada. Só cancela se estiver por concluir
    (evita "apagar histórico" de colheitas já feitas).

    Devolve True se removeu, False se não encontrada / já concluída.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                DELETE FROM trabalho_diario
                WHERE id = %s
                  AND tipo = %s
                  AND concluida = FALSE
                """,
                (int(tarefa_id), TIPO_COLHEITA),
            )
            n = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    if n > 0:
        invalidate_data_cache()
        logger.info(f"Colheita cancelada: id={tarefa_id}")
        return True
    return False


def concluir_colheita(tarefa_id: int, utilizador: str) -> bool:
    """Marca a colheita como concluída (chamado pelo `inserir_stock`
    quando o lote é guardado com `colheita_garanhao_prefill` activo).

    Devolve True se concluiu; False se não encontrada ou já concluída.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE trabalho_diario
                   SET concluida = TRUE,
                       data_conclusao = CURRENT_DATE,
                       observacoes_conclusao = COALESCE(observacoes_conclusao,
                           'Colheita registada por ' || %s)
                 WHERE id = %s
                   AND tipo = %s
                   AND concluida = FALSE
                """,
                (utilizador or "sistema", int(tarefa_id), TIPO_COLHEITA),
            )
            n = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    if n > 0:
        invalidate_data_cache()
        logger.info(f"Colheita concluída: id={tarefa_id}")
        return True
    return False
