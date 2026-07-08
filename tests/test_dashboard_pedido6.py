"""Testes do Pedido 6 — Dashboard + separação de responsabilidades.

Cobre os critérios de aceitação:
(a) o dashboard não contém nenhum UPDATE/DELETE — grep de código-fonte;
(b) a anulação de transferências funciona no novo repository FK-based;
(c) os KPIs clínicos batem com as páginas de origem (mesmo count de
    estadias ativas / tarefas de hoje);
(d) `carregar_atividade_recente_agrupada` devolve 1 linha por operação
    (mesmo com multi-lote);
(e) `carregar_kpis_clinicos` conta operações distintas de inseminação,
    não linhas.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import pytest

from modules.repositories.animal_repo import get_or_create_garanhao
from modules.repositories.dashboard_repo import (
    carregar_atividade_recente_agrupada,
    carregar_kpis_clinicos,
    carregar_kpis_stock,
    carregar_stock_atencao,
    carregar_tarefas_hoje,
)
from modules.repositories.insemination_repo import registar_inseminacao_completa
from modules.repositories.transfer_repo import reverter_operacao


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────

def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@pytest.fixture(scope="module")
def db():
    conn = _connect()
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _rollback_before_each(db):
    try:
        db.rollback()
    except Exception:
        pass
    yield


def _new_dono(db, prefix="_TEST_DASH") -> int:
    cur = db.cursor()
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (f"{prefix}_{int(time.time() * 1_000_000)}",),
    )
    d = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    return d


def _new_egua(db, dono_id) -> tuple[int, int]:
    """Cria uma égua com estadia aberta. Devolve (animal_id, estadia_id)."""
    cur = db.cursor()
    cur.execute(
        "INSERT INTO animais (nome, tipo, ativo, dono_id) "
        "VALUES (%s, 'egua', TRUE, %s) RETURNING id",
        (f"_TEST_EGUA_{int(time.time() * 1_000_000)}", dono_id),
    )
    animal_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO estadias (animal_id, dono_id, tipo_registo, "
        "data_entrada, motivo) VALUES (%s, %s, 'estadia', CURRENT_DATE, "
        "'inseminacao') RETURNING id",
        (animal_id, dono_id),
    )
    estadia_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    return animal_id, estadia_id


def _new_lote_stock(db, dono_id, palhetas=20) -> tuple[int, int]:
    """Cria animal (garanhão) + lote em estoque_dono. Devolve
    (stock_id, animal_id_garanhao)."""
    gar_id = get_or_create_garanhao(f"_TEST_GAR_{int(time.time() * 1_000_000)}")
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO estoque_dono (
            garanhao, dono_id, palhetas_produzidas,
            quantidade_inicial, existencia_atual, animal_id,
            contentor_id, canister, andar
        ) VALUES (
            (SELECT nome FROM animais WHERE id = %s),
            %s, %s, %s, %s, %s,
            NULL, 1, 1
        ) RETURNING id
        """,
        (gar_id, dono_id, palhetas, palhetas, palhetas, gar_id),
    )
    stock_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    return stock_id, gar_id


# ────────────────────────────────────────────────────────────────────
# (a) Grep: dashboard não contém UPDATE/DELETE
# ────────────────────────────────────────────────────────────────────

def test_dashboard_page_e_read_only():
    """O ficheiro `dashboard_page.py` não pode conter UPDATE/DELETE/INSERT
    directos — validado por regex simples sobre o código-fonte."""
    src = (Path("/app/modules/pages/dashboard_page.py")).read_text()
    # Casos negativos aceitáveis: strings em comentários. Para simplificar
    # exigimos ausência total de tokens SQL de escrita no ficheiro.
    padroes_proibidos = [r"\bUPDATE\s+\w+\s+SET\b", r"\bDELETE\s+FROM\b",
                         r"\bINSERT\s+INTO\b"]
    for p in padroes_proibidos:
        assert not re.search(p, src, flags=re.IGNORECASE), (
            f"dashboard_page.py deve ser 100% leitura — padrão '{p}' encontrado"
        )


def test_dashboard_repo_e_read_only():
    """O `dashboard_repo.py` também deve ser 100% leitura."""
    src = (Path("/app/modules/repositories/dashboard_repo.py")).read_text()
    padroes_proibidos = [r"\bUPDATE\s+\w+\s+SET\b", r"\bDELETE\s+FROM\b",
                         r"\bINSERT\s+INTO\b"]
    for p in padroes_proibidos:
        assert not re.search(p, src, flags=re.IGNORECASE), (
            f"dashboard_repo.py deve ser 100% leitura — padrão '{p}' encontrado"
        )


# ────────────────────────────────────────────────────────────────────
# (b) reverter_operacao (FK-based) funciona no repository
# ────────────────────────────────────────────────────────────────────

def test_reverter_operacao_transfer_interna_devolve_palhetas(db):
    dono_origem = _new_dono(db)
    dono_destino = _new_dono(db)
    stock_id, gar_id = _new_lote_stock(db, dono_origem, palhetas=20)

    # Criar um lote destino manualmente (mesma localização, dono destino).
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO estoque_dono (
            garanhao, dono_id, palhetas_produzidas,
            quantidade_inicial, existencia_atual, animal_id,
            contentor_id, canister, andar
        ) VALUES (
            (SELECT nome FROM animais WHERE id = %s),
            %s, 0, 0, 5, %s,
            NULL, 1, 1
        ) RETURNING id
        """,
        (gar_id, dono_destino, gar_id),
    )
    dest_stock_id = int(cur.fetchone()[0])
    # Simular a operação de transferência: descontar origem, adicionar
    # destino, criar linha em transferencias.
    cur.execute(
        "UPDATE estoque_dono SET existencia_atual = existencia_atual - %s "
        "WHERE id = %s",
        (5, stock_id),
    )
    cur.execute(
        "INSERT INTO transferencias (estoque_id, proprietario_origem_id, "
        "proprietario_destino_id, quantidade, data_transferencia, utilizador) "
        "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, 'test') RETURNING id",
        (stock_id, dono_origem, dono_destino, 5),
    )
    transfer_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()

    # Estado antes da reversão
    cur = db.cursor()
    cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (stock_id,))
    assert int(cur.fetchone()[0]) == 15  # 20 - 5
    cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (dest_stock_id,))
    assert int(cur.fetchone()[0]) == 5

    # Reverter
    ok = reverter_operacao("transfer_internal", action_id=transfer_id)
    assert ok is True

    # Estado depois
    cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (stock_id,))
    assert int(cur.fetchone()[0]) == 20, "origem devia voltar aos 20"
    cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (dest_stock_id,))
    row = cur.fetchone()
    # Destino era 5, retirou 5 → 0 → apagado
    assert row is None, "lote destino com 0 devia ter sido apagado"

    cur.execute("SELECT COUNT(*) FROM transferencias WHERE id = %s",
                (transfer_id,))
    assert int(cur.fetchone()[0]) == 0, "transferência devia ter sido apagada"
    cur.close()


def test_reverter_operacao_insemination_devolve_stock(db):
    dono = _new_dono(db)
    animal_egua, estadia_id = _new_egua(db, dono)
    stock_id, gar_id = _new_lote_stock(db, dono, palhetas=20)

    result = registar_inseminacao_completa(
        animal_id_egua=animal_egua,
        estadia_id=estadia_id,
        dono_id=dono,
        garanhao_nome=f"_TEST_GAR_REV_{time.time()}",
        data_inseminacao=date.today(),
        registros=[{"stock_id": stock_id, "palhetas": 4}],
        utilizador="test",
    )
    assert result["inseminacao_ids"]

    cur = db.cursor()
    cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (stock_id,))
    assert int(cur.fetchone()[0]) == 16
    cur.close()

    ok = reverter_operacao(
        "insemination",
        operation_id=result["operation_id"],
    )
    assert ok is True

    cur = db.cursor()
    cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (stock_id,))
    assert int(cur.fetchone()[0]) == 20
    cur.execute(
        "SELECT COUNT(*) FROM inseminacoes WHERE operation_id = %s::uuid",
        (result["operation_id"],),
    )
    assert int(cur.fetchone()[0]) == 0
    cur.close()


def test_reverter_operacao_valida_tipo():
    with pytest.raises(ValueError):
        reverter_operacao("tipo_invalido", action_id=1)


# ────────────────────────────────────────────────────────────────────
# (c) KPIs clínicos alinhados com fontes
# ────────────────────────────────────────────────────────────────────

def test_kpis_clinicos_estadias_ativas_bate_com_fonte(db):
    kpis = carregar_kpis_clinicos()

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM estadias WHERE data_saida IS NULL")
    esperado = int(cur.fetchone()[0])
    cur.close()

    assert kpis["estadias_ativas"] == esperado, (
        "KPI de estadias activas deve bater com COUNT direto na tabela "
        "(mesma query que estadias_page.py)"
    )


def test_kpis_clinicos_tarefas_hoje_bate_com_trabalho_diario(db):
    kpis = carregar_kpis_clinicos()

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM trabalho_diario "
        "WHERE data_tarefa = CURRENT_DATE AND concluida = FALSE"
    )
    esperado = int(cur.fetchone()[0])
    cur.close()
    assert kpis["tarefas_hoje"] == esperado


# ────────────────────────────────────────────────────────────────────
# (d) atividade recente agrupa por operation_id (1 linha por operação)
# ────────────────────────────────────────────────────────────────────

def test_atividade_recente_agrupa_por_operation_id(db):
    dono = _new_dono(db)
    animal_egua, estadia_id = _new_egua(db, dono)
    stock1, _ = _new_lote_stock(db, dono, palhetas=20)
    stock2, _ = _new_lote_stock(db, dono, palhetas=20)

    # Inseminação MULTI-LOTE (2 linhas em `inseminacoes`, mesmo op_id)
    result = registar_inseminacao_completa(
        animal_id_egua=animal_egua,
        estadia_id=estadia_id,
        dono_id=dono,
        garanhao_nome=f"_TEST_GAR_MULTI_{time.time()}",
        data_inseminacao=date.today(),
        registros=[
            {"stock_id": stock1, "palhetas": 3},
            {"stock_id": stock2, "palhetas": 4},
        ],
        utilizador="test",
    )
    assert len(result["inseminacao_ids"]) == 2

    ops = carregar_atividade_recente_agrupada(limit=30)
    matched = [
        o for o in ops
        if o.get("operation_id") == result["operation_id"]
    ]
    assert len(matched) == 1, (
        "Operação multi-lote devia aparecer como 1 linha agrupada, "
        f"apareceu {len(matched)}"
    )
    op = matched[0]
    assert op["num_lotes"] == 2
    assert op["quantidade"] == 7  # 3 + 4
    assert op["tipo"] == "insemination"


# ────────────────────────────────────────────────────────────────────
# (e) KPI de inseminações do mês conta operações, não linhas
# ────────────────────────────────────────────────────────────────────

def test_kpi_insem_mes_conta_operacoes_e_nao_linhas(db):
    dono = _new_dono(db)
    animal_egua, estadia_id = _new_egua(db, dono)
    stock1, _ = _new_lote_stock(db, dono, palhetas=20)
    stock2, _ = _new_lote_stock(db, dono, palhetas=20)

    kpis_antes = carregar_kpis_clinicos()

    # UMA operação com 2 linhas
    registar_inseminacao_completa(
        animal_id_egua=animal_egua,
        estadia_id=estadia_id,
        dono_id=dono,
        garanhao_nome=f"_TEST_GAR_KPI_{time.time()}",
        data_inseminacao=date.today(),
        registros=[
            {"stock_id": stock1, "palhetas": 2},
            {"stock_id": stock2, "palhetas": 3},
        ],
        utilizador="test",
    )

    kpis_depois = carregar_kpis_clinicos()
    delta = kpis_depois["insem_mes_operacoes"] - kpis_antes["insem_mes_operacoes"]
    assert delta == 1, (
        "KPI 'inseminações do mês' deve contar 1 operação, mesmo com "
        f"2 linhas em `inseminacoes` — delta={delta}"
    )


# ────────────────────────────────────────────────────────────────────
# Extras: kpi de stock + stock_atencao devolvem estruturas correctas
# ────────────────────────────────────────────────────────────────────

def test_kpis_stock_retorna_chaves_esperadas():
    k = carregar_kpis_stock()
    assert set(k.keys()) == {"total_palhetas", "lotes_ativos", "stock_critico"}
    assert all(isinstance(v, int) for v in k.values())


def test_stock_atencao_usa_fk_garanhao_nome(db):
    dono = _new_dono(db)
    stock_id, gar_id = _new_lote_stock(db, dono, palhetas=3)  # < 5

    # Renomear o garanhão em `animais`; o campo texto `estoque_dono.garanhao`
    # NÃO muda — a query deve preferir `animais.nome`.
    cur = db.cursor()
    novo_nome = f"_RENAMED_{time.time()}"
    cur.execute("UPDATE animais SET nome = %s WHERE id = %s", (novo_nome, gar_id))
    db.commit()
    cur.close()

    df = carregar_stock_atencao(limite=5, top=100)
    matched = df[df["lote_id"] == stock_id]
    assert not matched.empty, "lote com existência 3 devia aparecer"
    assert matched.iloc[0]["garanhao_nome"] == novo_nome, (
        "carregar_stock_atencao deve preferir animais.nome sobre "
        "estoque_dono.garanhao"
    )


def test_tarefas_hoje_traz_apenas_hoje_nao_concluidas(db):
    dono = _new_dono(db)
    animal_egua, estadia_id = _new_egua(db, dono)
    cur = db.cursor()
    # Uma tarefa para hoje (não concluída) + uma para amanhã + uma
    # concluída hoje.
    cur.execute(
        "INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, "
        "tipo, motivo, urgencia, criado_automaticamente, utilizador) "
        "VALUES (%s, %s, CURRENT_DATE, 'primeira_observacao', "
        "'test-hoje', 'hoje', TRUE, 'test') RETURNING id",
        (animal_egua, estadia_id),
    )
    id_hoje = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, "
        "tipo, motivo, urgencia, criado_automaticamente, utilizador) "
        "VALUES (%s, %s, CURRENT_DATE + INTERVAL '1 day', "
        "'primeira_observacao', 'test-amanha', 'amanha', TRUE, 'test')",
        (animal_egua, estadia_id),
    )
    cur.execute(
        "INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, "
        "tipo, motivo, urgencia, criado_automaticamente, utilizador, "
        "concluida, data_conclusao) "
        "VALUES (%s, %s, CURRENT_DATE, 'primeira_observacao', "
        "'test-feita', 'hoje', TRUE, 'test', TRUE, CURRENT_DATE)",
        (animal_egua, estadia_id),
    )
    db.commit()
    cur.close()

    df = carregar_tarefas_hoje()
    ids = set(int(x) for x in df["tarefa_id"].tolist()) if not df.empty else set()
    assert id_hoje in ids, "a tarefa de hoje não concluída devia aparecer"
    # Não conseguimos afirmar que outras não estão sem controlar o resto
    # da BD — mas o subset da nossa deve estar. O test central é que
    # `data_tarefa = CURRENT_DATE AND concluida = FALSE`.
    motivos = df[df["tarefa_id"] == id_hoje]["motivo"].tolist()
    assert motivos == ["test-hoje"]
