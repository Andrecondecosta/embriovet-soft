"""Testes do widget "Partos previstos — próximos 30 dias"
(secção "Hoje na clínica" do Dashboard).

Critérios de aceitação:
(a) mostra as éguas com gestação confirmada e parto previsto na janela;
(b) exclui gestações falhadas;
(c) contagem de dias correta;
(d) só mostra estadias ainda abertas;
(e) ordenado do mais próximo para o mais distante.
"""

from __future__ import annotations

import os
import time
from datetime import date, timedelta

import psycopg2
import pytest

from modules.repositories.dashboard_repo import carregar_partos_previstos


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


def _seed_egua_com_gestacao(
    db,
    *,
    dias_ate_parto: int,
    resultado: str = "gestacao_confirmada",
    estadia_aberta: bool = True,
) -> dict:
    """Cria dono + égua + estadia + acompanhamento com data_parto_previsto
    = hoje + `dias_ate_parto`. Devolve dict com ids."""
    cur = db.cursor()
    ts = int(time.time() * 1_000_000)
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (f"_TEST_DONO_PARTO_{ts}",),
    )
    dono_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO animais (nome, tipo, ativo, dono_id) "
        "VALUES (%s, 'egua', TRUE, %s) RETURNING id",
        (f"_TEST_EGUA_PARTO_{ts}", dono_id),
    )
    animal_id = int(cur.fetchone()[0])
    data_saida = None if estadia_aberta else date.today()
    cur.execute(
        "INSERT INTO estadias (animal_id, dono_id, tipo_registo, "
        "data_entrada, data_saida, motivo) "
        "VALUES (%s, %s, 'estadia', CURRENT_DATE, %s, 'inseminacao') "
        "RETURNING id",
        (animal_id, dono_id, data_saida),
    )
    estadia_id = int(cur.fetchone()[0])

    data_parto = date.today() + timedelta(days=dias_ate_parto)
    cur.execute(
        "INSERT INTO acompanhamento_inseminacao "
        "(estadia_id, animal_id, data_inseminacao, data_parto_previsto, "
        " resultado) VALUES (%s, %s, CURRENT_DATE - INTERVAL '60 days', "
        "%s, %s) RETURNING id",
        (estadia_id, animal_id, data_parto, resultado),
    )
    ai_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    return {
        "dono_id": dono_id,
        "animal_id": animal_id,
        "estadia_id": estadia_id,
        "acompanhamento_id": ai_id,
        "data_parto_previsto": data_parto,
        "egua_nome": f"_TEST_EGUA_PARTO_{ts}",
    }


def test_widget_mostra_egua_com_gestacao_confirmada(db):
    ctx = _seed_egua_com_gestacao(db, dias_ate_parto=10)
    df = carregar_partos_previstos(dias=30)
    row = df[df["estadia_id"] == ctx["estadia_id"]]
    assert not row.empty, "égua com gestação confirmada devia aparecer"
    assert row.iloc[0]["egua"] == ctx["egua_nome"]
    assert row.iloc[0]["dias_restantes"] == 10
    assert row.iloc[0]["data_parto_previsto"] == ctx["data_parto_previsto"]


def test_widget_exclui_gestacao_falhada(db):
    ctx = _seed_egua_com_gestacao(
        db, dias_ate_parto=15, resultado="falhou"
    )
    df = carregar_partos_previstos(dias=30)
    ids = set(int(x) for x in df["estadia_id"].tolist()) if not df.empty else set()
    assert ctx["estadia_id"] not in ids, (
        "gestação falhada NÃO pode aparecer no widget"
    )


def test_widget_exclui_gestacao_sem_resultado(db):
    """`resultado IS NULL` (ainda pendente) também é excluído."""
    ctx = _seed_egua_com_gestacao(db, dias_ate_parto=20, resultado=None)
    df = carregar_partos_previstos(dias=30)
    ids = set(int(x) for x in df["estadia_id"].tolist()) if not df.empty else set()
    assert ctx["estadia_id"] not in ids


def test_widget_exclui_estadia_encerrada(db):
    ctx = _seed_egua_com_gestacao(
        db, dias_ate_parto=5, estadia_aberta=False
    )
    df = carregar_partos_previstos(dias=30)
    ids = set(int(x) for x in df["estadia_id"].tolist()) if not df.empty else set()
    assert ctx["estadia_id"] not in ids, (
        "estadia fechada não deve aparecer nos partos previstos"
    )


def test_widget_exclui_partos_fora_da_janela(db):
    """Parto previsto para daqui a 60 dias não deve aparecer com dias=30."""
    ctx = _seed_egua_com_gestacao(db, dias_ate_parto=60)
    df = carregar_partos_previstos(dias=30)
    ids = set(int(x) for x in df["estadia_id"].tolist()) if not df.empty else set()
    assert ctx["estadia_id"] not in ids


def test_widget_inclui_parto_no_limite_da_janela(db):
    """Parto no exato dia+30 deve estar incluído (BETWEEN inclusivo)."""
    ctx = _seed_egua_com_gestacao(db, dias_ate_parto=30)
    df = carregar_partos_previstos(dias=30)
    ids = set(int(x) for x in df["estadia_id"].tolist()) if not df.empty else set()
    assert ctx["estadia_id"] in ids


def test_widget_ordenacao_do_mais_proximo_para_o_mais_distante(db):
    a = _seed_egua_com_gestacao(db, dias_ate_parto=25)
    b = _seed_egua_com_gestacao(db, dias_ate_parto=5)
    c = _seed_egua_com_gestacao(db, dias_ate_parto=15)

    df = carregar_partos_previstos(dias=30)
    # Filtrar só as nossas éguas
    ours = df[df["estadia_id"].isin(
        [a["estadia_id"], b["estadia_id"], c["estadia_id"]]
    )].reset_index(drop=True)
    dias_ordem = ours["dias_restantes"].tolist()
    assert dias_ordem == sorted(dias_ordem), (
        f"esperado ordenação crescente por dias_restantes, obtido {dias_ordem}"
    )
    # 1º = 5 dias, 2º = 15, 3º = 25
    assert dias_ordem[0] == 5


def test_widget_parto_no_passado_nao_aparece(db):
    """Parto previsto no passado (data já ficou para trás) — não deve
    aparecer. Ex.: dias_ate_parto=-3."""
    ctx = _seed_egua_com_gestacao(db, dias_ate_parto=-3)
    df = carregar_partos_previstos(dias=30)
    ids = set(int(x) for x in df["estadia_id"].tolist()) if not df.empty else set()
    assert ctx["estadia_id"] not in ids


def test_widget_devolve_colunas_esperadas(db):
    _seed_egua_com_gestacao(db, dias_ate_parto=7)
    df = carregar_partos_previstos(dias=30)
    assert not df.empty
    esperado = {"egua", "data_parto_previsto", "dias_restantes",
                "estadia_id", "animal_id"}
    assert esperado.issubset(set(df.columns))
