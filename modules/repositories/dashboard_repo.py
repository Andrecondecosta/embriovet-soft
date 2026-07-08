"""Repository do Dashboard — 100% leitura.

Concentra todas as queries que alimentam a "visão do dia" do dashboard
(KPIs de stock + clínicos, Hoje na clínica, Stock a precisar de atenção,
atividade recente agrupada por `operation_id`).

Todas as queries usam FKs canónicas (`animais`, `dono`, `contentores`,
`estadias`, `trabalho_diario`) e nunca comparações por texto do garanhão.

Este ficheiro não contém nenhum UPDATE/DELETE/INSERT — validado por
`tests/test_dashboard_repo.py::test_repo_e_read_only`.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from modules.db import get_connection


# ─── KPIs de stock ────────────────────────────────────────────────────
def carregar_kpis_stock() -> dict:
    """Devolve os KPIs de stock (leitura pura)."""
    sql = """
        SELECT
            COALESCE(SUM(existencia_atual), 0) AS total_palhetas,
            COUNT(*) FILTER (WHERE existencia_atual > 0) AS lotes_ativos,
            COUNT(*) FILTER (WHERE existencia_atual > 0 AND existencia_atual <= 5) AS stock_critico
        FROM estoque_dono
        WHERE existencia_atual > 0
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        cur.close()
    return {
        "total_palhetas": int(row[0] or 0),
        "lotes_ativos": int(row[1] or 0),
        "stock_critico": int(row[2] or 0),
    }


# ─── KPIs clínicos ────────────────────────────────────────────────────
def carregar_kpis_clinicos() -> dict:
    """KPIs clínicos: estadias activas, tarefas de hoje (com urgentes),
    gestações confirmadas em curso e inseminações do mês (operações
    distintas).

    Deve bater com as páginas de origem:
    - `estadias_active` = mesmo count que `estadias_page._carregar_estadias(True)`
    - `tarefas_hoje` = mesmo count que `trabalho_diario_page` para hoje
    - `insem_mes_operacoes` conta DISTINCT operation_id (não linhas)
    """
    # Estadias activas
    sql_estadias = """
        SELECT COUNT(*) FROM estadias e
        WHERE e.data_saida IS NULL
    """
    # Tarefas de hoje (não concluídas) + subset urgentes
    sql_tarefas = """
        SELECT
            COUNT(*) FILTER (WHERE concluida = FALSE) AS total,
            COUNT(*) FILTER (WHERE concluida = FALSE AND urgencia IN ('urgente', 'hoje')) AS urgentes
        FROM trabalho_diario
        WHERE data_tarefa = CURRENT_DATE
    """
    # Gestações confirmadas em curso: acompanhamentos com resultado
    # 'gestacao_confirmada' cuja estadia ainda está aberta.
    sql_gestacoes = """
        SELECT COUNT(*) FROM acompanhamento_inseminacao ai
        JOIN estadias e ON e.id = ai.estadia_id
        WHERE ai.resultado = 'gestacao_confirmada'
          AND e.data_saida IS NULL
    """
    # Inseminações do mês corrente — DISTINCT operation_id.
    # NULL operation_id conta como 1 operação por linha (backwards compat).
    sql_insem_mes = """
        SELECT COUNT(*) FROM (
            SELECT DISTINCT COALESCE(operation_id::text, 'solo_' || id::text) AS op
            FROM inseminacoes
            WHERE date_trunc('month', data_inseminacao)
                = date_trunc('month', CURRENT_DATE)
        ) t
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql_estadias)
        estadias_ativas = int(cur.fetchone()[0] or 0)
        cur.execute(sql_tarefas)
        row_t = cur.fetchone()
        tarefas_hoje = int(row_t[0] or 0)
        tarefas_urgentes = int(row_t[1] or 0)
        cur.execute(sql_gestacoes)
        gestacoes = int(cur.fetchone()[0] or 0)
        cur.execute(sql_insem_mes)
        insem_mes_ops = int(cur.fetchone()[0] or 0)
        cur.close()
    return {
        "estadias_ativas": estadias_ativas,
        "tarefas_hoje": tarefas_hoje,
        "tarefas_urgentes": tarefas_urgentes,
        "gestacoes_confirmadas": gestacoes,
        "insem_mes_operacoes": insem_mes_ops,
    }


# ─── Gráficos de distribuição ─────────────────────────────────────────
def carregar_stock_por_contentor(limit: int = 10) -> pd.DataFrame:
    sql = """
        SELECT c.codigo AS "Contentor",
               COALESCE(SUM(e.existencia_atual), 0) AS "Palhetas"
        FROM contentores c
        LEFT JOIN estoque_dono e
            ON c.id = e.contentor_id AND e.existencia_atual > 0
        GROUP BY c.codigo
        ORDER BY "Palhetas" DESC
        LIMIT %s
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(int(limit),))


def carregar_stock_por_proprietario(limit: int = 8) -> pd.DataFrame:
    sql = """
        SELECT d.nome AS "Proprietário",
               COALESCE(SUM(e.existencia_atual), 0) AS "Palhetas"
        FROM dono d
        JOIN estoque_dono e ON d.id = e.dono_id AND e.existencia_atual > 0
        GROUP BY d.nome
        ORDER BY "Palhetas" DESC
        LIMIT %s
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(int(limit),))


# ─── Hoje na clínica ──────────────────────────────────────────────────
def carregar_tarefas_hoje() -> pd.DataFrame:
    """Tarefas do trabalho diário para hoje (não concluídas).

    Cada linha traz `animal_id`, `estadia_id`, `animal` (via FK),
    `tipo`, `motivo` e `urgencia` — para o card da secção "Hoje na
    clínica" do dashboard.
    """
    sql = """
        SELECT td.id AS tarefa_id,
               td.animal_id, td.estadia_id,
               a.nome AS animal,
               td.tipo, td.motivo, td.urgencia,
               td.data_tarefa
        FROM trabalho_diario td
        JOIN animais a ON a.id = td.animal_id
        WHERE td.data_tarefa = CURRENT_DATE
          AND td.concluida = FALSE
        ORDER BY
            CASE td.urgencia
                WHEN 'urgente' THEN 0
                WHEN 'hoje'    THEN 1
                WHEN 'amanha'  THEN 2
                ELSE 3
            END,
            td.id ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


# ─── Partos previstos ─────────────────────────────────────────────────
def carregar_partos_previstos(dias: int = 30) -> pd.DataFrame:
    """Éguas com parto previsto nos próximos `dias` dias.

    Filtros:
    - `acompanhamento_inseminacao.resultado = 'gestacao_confirmada'`
      (só gestações confirmadas em curso; exclui 'falhou' e NULL)
    - `data_parto_previsto` entre hoje e hoje+`dias` dias
    - `estadias.data_saida IS NULL` (estadia ainda aberta)

    Devolve colunas: `egua`, `data_parto_previsto`, `dias_restantes`,
    `estadia_id`, `animal_id`.
    Ordenado do parto mais próximo para o mais distante.
    """
    sql = """
        SELECT
            a.nome                                   AS egua,
            ai.data_parto_previsto                   AS data_parto_previsto,
            (ai.data_parto_previsto - CURRENT_DATE)::int AS dias_restantes,
            ai.estadia_id,
            a.id                                     AS animal_id
        FROM acompanhamento_inseminacao ai
        JOIN estadias e ON e.id = ai.estadia_id
        JOIN animais a  ON a.id = ai.animal_id
        WHERE ai.resultado = 'gestacao_confirmada'
          AND ai.data_parto_previsto IS NOT NULL
          AND ai.data_parto_previsto BETWEEN CURRENT_DATE
                                          AND CURRENT_DATE + (%s || ' days')::interval
          AND e.data_saida IS NULL
        ORDER BY ai.data_parto_previsto ASC, a.nome ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(int(dias),))


# ─── Stock a precisar de atenção ──────────────────────────────────────
def carregar_stock_atencao(limite: int = 5, top: int = 10) -> pd.DataFrame:
    """Lotes com existência baixa (existencia_atual <= limite), com
    nome do garanhão via FK `animais.nome` (COALESCE ao texto legado).

    Devolve as colunas usadas na UI: `garanhao_nome`, `proprietario`,
    `contentor`, `canister`, `andar`, `existencia_atual`.
    """
    sql = """
        SELECT
            e.id                                    AS lote_id,
            COALESCE(a.nome, e.garanhao)            AS garanhao_nome,
            d.nome                                  AS proprietario,
            c.codigo                                AS contentor,
            e.canister, e.andar,
            e.existencia_atual
        FROM estoque_dono e
        LEFT JOIN animais a      ON a.id = e.animal_id
        LEFT JOIN dono    d      ON d.id = e.dono_id
        LEFT JOIN contentores c  ON c.id = e.contentor_id
        WHERE e.existencia_atual > 0
          AND e.existencia_atual <= %s
        ORDER BY e.existencia_atual ASC, garanhao_nome ASC
        LIMIT %s
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(int(limite), int(top)))


# ─── Atividade recente (agrupada por operation_id) ────────────────────
def carregar_atividade_recente_agrupada(limit: int = 10) -> list[dict]:
    """Devolve as últimas `limit` operações (transferências internas,
    externas e inseminações) já **agrupadas por `operation_id`** — cada
    dict representa UMA operação, mesmo que envolva vários lotes.

    Campos por dict:
    - `ts`: timestamp da operação
    - `usuario`: utilizador que registou
    - `acao`: label ("Inseminação" / "Transferência interna" / ...)
    - `detalhe`: descrição legível (com nº de lotes quando > 1)
    - `tipo`: 'insemination' | 'transfer_internal' | 'transfer_external'
    - `operation_id`: str | None
    - `num_lotes`: int
    - `quantidade`: soma total (palhetas)
    """
    sql = """
        SELECT * FROM (
            SELECT t.data_transferencia AS ts,
                   COALESCE(t.utilizador, '—') AS usuario,
                   CASE WHEN COALESCE(t.atualizado, FALSE)
                        THEN '✏️ Transferência interna'
                        ELSE 'Transferência interna' END AS acao,
                   'transfer_internal' AS tipo,
                   t.id AS action_id,
                   t.quantidade AS qty,
                   t.operation_id::text AS op_id,
                   COALESCE(d1.nome, 'ID ' || t.proprietario_origem_id) AS origem,
                   COALESCE(d2.nome, 'ID ' || t.proprietario_destino_id) AS destino,
                   NULL AS egua, NULL AS garanhao
            FROM transferencias t
            LEFT JOIN dono d1 ON t.proprietario_origem_id = d1.id
            LEFT JOIN dono d2 ON t.proprietario_destino_id = d2.id
            UNION ALL
            SELECT te.data_transferencia AS ts,
                   COALESCE(te.utilizador, '—') AS usuario,
                   CASE WHEN COALESCE(te.atualizado, FALSE)
                        THEN '✏️ Transferência externa'
                        ELSE 'Transferência externa' END AS acao,
                   'transfer_external' AS tipo,
                   te.id AS action_id,
                   te.quantidade AS qty,
                   te.operation_id::text AS op_id,
                   COALESCE(d.nome, 'Origem?') AS origem,
                   te.destinatario_externo AS destino,
                   NULL AS egua, NULL AS garanhao
            FROM transferencias_externas te
            LEFT JOIN dono d ON te.proprietario_origem_id = d.id
            UNION ALL
            SELECT COALESCE(i.created_at, i.data_inseminacao::timestamp + interval '12 hours') AS ts,
                   COALESCE(i.utilizador, '—') AS usuario,
                   CASE WHEN COALESCE(i.atualizado, FALSE)
                        THEN '✏️ Inseminação'
                        ELSE 'Inseminação' END AS acao,
                   'insemination' AS tipo,
                   i.id AS action_id,
                   i.palhetas_gastas AS qty,
                   i.operation_id::text AS op_id,
                   NULL AS origem, NULL AS destino,
                   COALESCE(ae.nome, i.egua)      AS egua,
                   COALESCE(ag.nome, i.garanhao)  AS garanhao
            FROM inseminacoes i
            LEFT JOIN animais ae ON ae.id = i.animal_id_egua
            LEFT JOIN animais ag ON ag.id = i.animal_id_garanhao
        ) AS x
        ORDER BY ts DESC
        LIMIT %s
    """
    # Pedimos até 4x o limite antes de agrupar, para termos margem quando
    # várias linhas partilham operation_id.
    fetch_limit = int(limit) * 4
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (fetch_limit,))
        rows = cur.fetchall()
        cur.close()

    grupos: dict[tuple, dict] = {}
    ordem: list[tuple] = []
    for row in rows:
        (ts, usuario, acao, tipo, action_id, qty, op_id,
         origem, destino, egua, garanhao) = row
        qty_i = int(qty or 0)
        key = (tipo, op_id) if op_id else (tipo, f"solo_{action_id}")

        if key not in grupos:
            if tipo == "insemination":
                detalhe_base = (
                    f"Égua {egua or '—'} · Garanhão {garanhao or '—'}"
                )
            else:
                detalhe_base = f"{origem or '—'} → {destino or '—'}"

            grupos[key] = {
                "ts": ts, "usuario": usuario, "acao": acao,
                "tipo": tipo, "action_id": action_id,
                "operation_id": op_id,
                "quantidade": qty_i, "num_lotes": 1,
                "detalhe_base": detalhe_base,
            }
            ordem.append(key)
        else:
            grupos[key]["quantidade"] += qty_i
            grupos[key]["num_lotes"] += 1

    result: list[dict] = []
    for k in ordem[:limit]:
        g = grupos[k]
        suffix = f"{g['quantidade']} palhetas"
        if g["num_lotes"] > 1:
            suffix += f" ({g['num_lotes']} lotes)"
        g["detalhe"] = f"{g['detalhe_base']} · {suffix}"
        result.append(g)
    return result
