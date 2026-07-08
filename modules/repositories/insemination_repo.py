"""Repository de inseminações — função unificada `registar_inseminacao_completa`.

Substitui as duas implementações que existiam antes:
- `app.py::registrar_inseminacao_multiplas` (menu "Registar Inseminação")
- `modules/pages/animal_page.py::_upsert_acompanhamento` (ficha da égua)

Uma única transacção cobre:
1. Resolução do `animal_id_garanhao` via `get_or_create_garanhao` (com
   normalização acentos + espaços).
2. Fetch dos nomes canónicos em `animais` para preencher as colunas de
   texto legado (`egua`, `garanhao`) — mantidas para relatórios/importação.
3. INSERTs em `inseminacoes` (uma linha por lote), com FKs preenchidas.
4. UPSERT em `acompanhamento_inseminacao` com as datas automáticas:
   D+14 (1º diagnóstico), D+28 (confirmação), D+45 (2ª confirmação).
5. INSERT idempotente em `trabalho_diario` para a data D+14 (para a
   égua aparecer na agenda semanal).
6. Desconto das palhetas em `estoque_dono`.

Todos os passos partilham a mesma conexão/cursor — em caso de falha
qualquer alteração é revertida (rollback).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import date, timedelta
from typing import Optional

from modules.db import get_connection
from modules.repositories.animal_repo import get_or_create_garanhao


# Offsets D+1 / D+14 / D+28 / D+45 (fixos por decisão de produto).
DIAS_VER_OVULACAO = 1
DIAS_1O_DIAGNOSTICO = 14
DIAS_CONFIRMACAO = 28
DIAS_2A_CONFIRMACAO = 45
DIAS_PARTO_PREVISTO = 340  # ~11 meses de gestação em equinos


class InseminacaoError(Exception):
    """Erro de validação/negócio da função `registar_inseminacao_completa`."""


def _normalizar_nome(nome: Optional[str]) -> str:
    """Remove acentos, faz strip e colapsa espaços internos."""
    if not nome:
        return ""
    txt = unicodedata.normalize("NFKD", str(nome))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip()


def _fetch_nome_canonico(cur, animal_id: int) -> Optional[str]:
    cur.execute("SELECT nome FROM animais WHERE id = %s", (int(animal_id),))
    row = cur.fetchone()
    return str(row[0]) if row and row[0] else None


def upsert_acompanhamento_datas(
    *,
    estadia_id: int,
    animal_id: int,
    data_inseminacao: Optional[date],
    data_1o_diagnostico: Optional[date] = None,
    data_confirmacao: Optional[date] = None,
    data_2a_confirmacao: Optional[date] = None,
    data_parto_previsto: Optional[date] = None,
    cur=None,
) -> int:
    """UPSERT das datas em `acompanhamento_inseminacao` (uma linha por estadia).

    Implementação partilhada por:
    - `registar_inseminacao_completa` (fluxo de criação a partir do menu)
    - Ficha da égua (`animal_page._render_seccao_acompanhamento`, edição manual)

    Se `cur` for fornecido usa esse cursor (fica na transacção do chamador);
    caso contrário abre uma conexão nova e faz commit isolado.
    """
    sql = """
        INSERT INTO acompanhamento_inseminacao (
            estadia_id, animal_id, data_inseminacao,
            data_1o_diagnostico, data_confirmacao,
            data_2a_confirmacao, data_parto_previsto
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (estadia_id) DO UPDATE SET
            data_inseminacao    = EXCLUDED.data_inseminacao,
            data_1o_diagnostico = EXCLUDED.data_1o_diagnostico,
            data_confirmacao    = EXCLUDED.data_confirmacao,
            data_2a_confirmacao = EXCLUDED.data_2a_confirmacao,
            data_parto_previsto = EXCLUDED.data_parto_previsto
        RETURNING id
    """
    params = (
        int(estadia_id), int(animal_id), data_inseminacao,
        data_1o_diagnostico, data_confirmacao, data_2a_confirmacao,
        data_parto_previsto,
    )
    if cur is not None:
        cur.execute(sql, params)
        return int(cur.fetchone()[0])

    with get_connection() as conn:
        _cur = conn.cursor()
        _cur.execute(sql, params)
        new_id = int(_cur.fetchone()[0])
        conn.commit()
        _cur.close()
        return new_id


def registar_inseminacao_completa(
    *,
    animal_id_egua: int,
    estadia_id: int,
    dono_id: int,
    garanhao_nome: str,
    data_inseminacao: date,
    registros: list[dict],
    observacoes: Optional[str] = None,
    utilizador: str = "—",
    operation_id: Optional[str] = None,
    criar_tarefa_d1: bool = True,
) -> dict:
    """Regista uma inseminação completa numa única transacção.

    Parâmetros
    ----------
    animal_id_egua : int
        FK para `animais.id` (a égua já tem que existir).
    estadia_id : int
        FK para `estadias.id` — a estadia activa da égua com
        `motivo='inseminacao'`. Usada para criar o acompanhamento e a
        tarefa em `trabalho_diario`.
    dono_id : int
        FK para `dono.id` — proprietário da égua.
    garanhao_nome : str
        Nome do garanhão. Resolvido via `get_or_create_garanhao` (que
        aplica normalização acentos + espaços).
    data_inseminacao : date
        Data em que a inseminação foi feita. As datas D+14/D+28/D+45
        são calculadas a partir dela.
    registros : list[dict]
        Lista de lotes usados. Cada item deve conter:
            - `stock_id` (int): `estoque_dono.id`
            - `palhetas` (int > 0): quantidade descontada deste lote
            - `protocolo` (str, opcional)
            - `garanhao` (str, opcional): nome do lote (usado apenas
              para a coluna texto se `garanhao_nome` não estiver
              disponível).
    observacoes : str | None
    utilizador : str
        Username para auditoria (`inseminacoes.utilizador`).
    operation_id : str | None
        UUID que agrupa lotes da mesma operação. Gerado se `None`.

    Devolve
    -------
    dict com:
        - `inseminacao_ids`: list[int]
        - `acompanhamento_id`: int
        - `trabalho_diario_id`: int | None (None se já existir)
        - `operation_id`: str

    Raises
    ------
    InseminacaoError
        Se validações falharem (sem lotes, stock insuficiente, etc.).
    """
    # ── Validações ────────────────────────────────────────────────────
    if not registros:
        raise InseminacaoError("Sem lotes seleccionados.")
    if not garanhao_nome or not garanhao_nome.strip():
        raise InseminacaoError("Nome do garanhão obrigatório.")
    if not isinstance(data_inseminacao, date):
        raise InseminacaoError("`data_inseminacao` tem que ser um date.")

    total_palhetas = 0
    for reg in registros:
        p = int(reg.get("palhetas", 0) or 0)
        if p <= 0:
            raise InseminacaoError(
                f"Palhetas inválidas no lote {reg.get('stock_id')}: {p}"
            )
        if not reg.get("stock_id"):
            raise InseminacaoError("`stock_id` em falta num lote.")
        total_palhetas += p

    if operation_id is None:
        operation_id = str(uuid.uuid4())

    # Datas automáticas D+1/D+14/D+28/D+45 + parto previsto.
    data_d1 = data_inseminacao + timedelta(days=DIAS_VER_OVULACAO)
    data_1o = data_inseminacao + timedelta(days=DIAS_1O_DIAGNOSTICO)
    data_conf = data_inseminacao + timedelta(days=DIAS_CONFIRMACAO)
    data_2a = data_inseminacao + timedelta(days=DIAS_2A_CONFIRMACAO)
    data_parto = data_inseminacao + timedelta(days=DIAS_PARTO_PREVISTO)

    # Resolução do garanhão (fora do bloco with — get_or_create abre
    # a sua própria conexão e faz commit isolado, o que é aceitável).
    animal_id_garanhao = get_or_create_garanhao(garanhao_nome)
    if animal_id_garanhao is None:
        raise InseminacaoError(
            f"Não foi possível resolver garanhão '{garanhao_nome}'."
        )

    inseminacao_ids: list[int] = []

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            # 0. Canonicalização da estadia — REUTILIZA sempre a estadia
            #    aberta MAIS ANTIGA da égua (menor id), mesmo que o
            #    chamador tenha passado outra. Isto previne o bug em
            #    que duas estadias abertas em simultâneo faziam a
            #    inseminação e as tarefas ficarem numa estadia
            #    diferente da que já tinha, por exemplo, a tarefa
            #    `primeira_observacao`.
            cur.execute(
                """
                SELECT id
                FROM estadias
                WHERE animal_id = %s AND data_saida IS NULL
                ORDER BY id ASC
                LIMIT 1
                """,
                (int(animal_id_egua),),
            )
            row_est = cur.fetchone()
            if not row_est:
                raise InseminacaoError(
                    f"Égua id={animal_id_egua} não tem estadia activa. "
                    f"Crie primeiro uma estadia."
                )
            estadia_id = int(row_est[0])
            # Nomes canónicos (a partir de `animais`) para os campos texto.
            egua_nome = _fetch_nome_canonico(cur, animal_id_egua)
            gar_nome = _fetch_nome_canonico(cur, animal_id_garanhao)
            if egua_nome is None:
                raise InseminacaoError(
                    f"Égua id={animal_id_egua} não existe em `animais`."
                )
            if gar_nome is None:
                raise InseminacaoError(
                    f"Garanhão id={animal_id_garanhao} não existe."
                )

            # 1. Validar stock e INSERT `inseminacoes` (uma linha por lote).
            for reg in registros:
                stock_id = int(reg["stock_id"])
                palhetas = int(reg["palhetas"])

                cur.execute(
                    "SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                    (stock_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise InseminacaoError(
                        f"Lote {stock_id} não encontrado."
                    )
                exist = int(row[0] or 0)
                if exist < palhetas:
                    raise InseminacaoError(
                        f"Stock insuficiente no lote {stock_id}: "
                        f"disponível={exist}, pedido={palhetas}."
                    )

                cur.execute(
                    """
                    INSERT INTO inseminacoes (
                        garanhao, dono_id, data_inseminacao, egua,
                        protocolo, palhetas_gastas, observacoes, utilizador,
                        estoque_id, operation_id,
                        animal_id_egua, animal_id_garanhao, estadia_id
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s::uuid,
                        %s, %s, %s
                    ) RETURNING id
                    """,
                    (
                        gar_nome, dono_id, data_inseminacao, egua_nome,
                        reg.get("protocolo"), palhetas, observacoes, utilizador,
                        stock_id, operation_id,
                        int(animal_id_egua), int(animal_id_garanhao),
                        int(estadia_id),
                    ),
                )
                inseminacao_ids.append(int(cur.fetchone()[0]))

                # 2. Desconto do stock (dentro da mesma transacção).
                cur.execute(
                    "UPDATE estoque_dono "
                    "SET existencia_atual = existencia_atual - %s "
                    "WHERE id = %s",
                    (palhetas, stock_id),
                )

            # 3. UPSERT acompanhamento (uma linha por estadia) — mesma
            #    implementação partilhada usada pela ficha da égua.
            acompanhamento_id = upsert_acompanhamento_datas(
                estadia_id=int(estadia_id),
                animal_id=int(animal_id_egua),
                data_inseminacao=data_inseminacao,
                data_1o_diagnostico=data_1o,
                data_confirmacao=data_conf,
                data_2a_confirmacao=data_2a,
                data_parto_previsto=data_parto,
                cur=cur,
            )

            # 4. Actualiza a coluna `garanhao` da estadia (compat legado).
            cur.execute(
                "UPDATE estadias SET garanhao = %s, updated_at = NOW() "
                "WHERE id = %s",
                (gar_nome, int(estadia_id)),
            )

            # 5. Tarefa em `trabalho_diario` para D+14 (idempotente).
            cur.execute(
                """
                INSERT INTO trabalho_diario (
                    animal_id, estadia_id, data_tarefa, tipo, motivo,
                    urgencia, criado_automaticamente, utilizador
                )
                SELECT %s, %s, %s, 'diagnostico_gestacao', %s,
                       'hoje', TRUE, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM trabalho_diario
                    WHERE animal_id = %s AND estadia_id = %s
                      AND data_tarefa = %s
                      AND tipo = 'diagnostico_gestacao'
                )
                RETURNING id
                """,
                (
                    int(animal_id_egua), int(estadia_id), data_1o,
                    f"1º diagnóstico de gestação — inseminação {data_inseminacao.strftime('%d/%m/%Y')}",
                    utilizador,
                    int(animal_id_egua), int(estadia_id), data_1o,
                ),
            )
            td_row = cur.fetchone()
            trabalho_diario_id = int(td_row[0]) if td_row else None

            # 6. Tarefa opcional D+1 — verificação de ovulação (idempotente).
            verificar_ovulacao_id: Optional[int] = None
            if criar_tarefa_d1:
                cur.execute(
                    """
                    INSERT INTO trabalho_diario (
                        animal_id, estadia_id, data_tarefa, tipo, motivo,
                        urgencia, criado_automaticamente, utilizador
                    )
                    SELECT %s, %s, %s, 'verificar_ovulacao', %s,
                           'hoje', TRUE, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM trabalho_diario
                        WHERE animal_id = %s AND estadia_id = %s
                          AND data_tarefa = %s
                          AND tipo = 'verificar_ovulacao'
                    )
                    RETURNING id
                    """,
                    (
                        int(animal_id_egua), int(estadia_id), data_d1,
                        f"Verificar ovulação (D+1) — inseminação {data_inseminacao.strftime('%d/%m/%Y')}",
                        utilizador,
                        int(animal_id_egua), int(estadia_id), data_d1,
                    ),
                )
                td1_row = cur.fetchone()
                verificar_ovulacao_id = int(td1_row[0]) if td1_row else None

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    return {
        "inseminacao_ids": inseminacao_ids,
        "acompanhamento_id": acompanhamento_id,
        "trabalho_diario_id": trabalho_diario_id,
        "verificar_ovulacao_id": verificar_ovulacao_id,
        "operation_id": operation_id,
        "animal_id_egua": int(animal_id_egua),
        "animal_id_garanhao": int(animal_id_garanhao),
        "estadia_id": int(estadia_id),
        "data_inseminacao": data_inseminacao,
        "data_ver_ovulacao": data_d1,
        "data_1o_diagnostico": data_1o,
        "data_confirmacao": data_conf,
        "data_2a_confirmacao": data_2a,
        "data_parto_previsto": data_parto,
        "total_palhetas": total_palhetas,
    }


def listar_eguas_com_estadia_ativa() -> list[dict]:
    """Devolve as éguas com estadia aberta (`data_saida IS NULL`).

    Uma égua com **múltiplas** estadias abertas devolve **uma só linha**
    (a estadia aberta mais antiga) para evitar duplicação no selectbox
    do menu e garantir que o registo cai sempre na mesma estadia.

    Usada pelo selectbox do menu "Registar Inseminação" — não permite
    inseminações fora de estadias registadas.

    Cada dict contém:
        - `animal_id`, `nome`
        - `estadia_id`, `data_entrada`, `motivo`
        - `alojamento_id`, `alojamento_nome`, `alojamento_tipo`
        - `dono_id`, `dono_nome`
    """
    sql = """
        SELECT DISTINCT ON (a.id)
               a.id AS animal_id, a.nome,
               e.id AS estadia_id, e.data_entrada, e.motivo,
               e.alojamento_id, al.nome AS alojamento_nome,
               al.tipo AS alojamento_tipo,
               e.dono_id, d.nome AS dono_nome
        FROM animais a
        JOIN estadias e     ON e.animal_id = a.id
        LEFT JOIN alojamentos al ON al.id = e.alojamento_id
        LEFT JOIN dono d         ON d.id = e.dono_id
        WHERE a.tipo IN ('egua', 'receptora')
          AND a.ativo = TRUE
          AND e.data_saida IS NULL
          AND e.tipo_registo IN ('estadia', 'visita')
        ORDER BY a.id, e.data_entrada ASC, e.id ASC
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        cur.close()
    # Re-ordenar por nome (o DISTINCT ON forçou ORDER BY a.id primeiro)
    result = [dict(zip(cols, r)) for r in rows]
    result.sort(key=lambda x: (x["nome"] or "").lower())
    return result
