"""Testes para o bug: lotes sem proprietário desapareciam do separador
"Lotes" (Stock de sémen) depois da importação passar a permitir
`dono_id = NULL`.

Causa: `carregar_stock(apenas_ativos=True)` (stock_repo.py) filtrava
com `WHERE ... AND d.ativo = TRUE`, sobre um `LEFT JOIN dono d ON
e.dono_id = d.id`. Para um lote sem dono, o LEFT JOIN produz `d.ativo
= NULL`, e `NULL = TRUE` nunca é verdadeiro em SQL (lógica a três
valores) — a linha desaparecia da lista por completo, apesar de
continuar a existir na BD. Corrigido para `AND (d.ativo = TRUE OR
e.dono_id IS NULL)`: um lote sem proprietário não está ligado ao
estado activo/inactivo de nenhum dono, por isso não devia ser afectado
por este filtro.

Cobre também `summarize_stock_by_owner` (stock_reporting.py) — o
`groupby` do pandas ignora por omissão chaves NaN, o que escondia
esses lotes do resumo "Total Palhetas por Proprietário" mesmo depois
da correcção acima (a linha aparece na lista, mas ficava de fora deste
resumo específico).

Segue o mesmo padrão de `test_stock_fk_garanhao.py`: liga directamente
à BD de teste e replica a query (em vez de chamar `carregar_stock`
directamente, que tem `@st.cache_data` — evita depender do
comportamento da cache fora de um script Streamlit real).
"""

from __future__ import annotations

import os
import time

import pandas as pd
import psycopg2
import pytest

from modules.stock_reporting import summarize_stock_by_owner

# Réplica exacta da query corrigida em stock_repo.carregar_stock (apenas_ativos=True)
QUERY_CARREGAR_STOCK_ATIVOS = """
    SELECT e.*,
           d.nome as proprietario_nome,
           c.codigo as contentor_codigo,
           COALESCE(a.nome, e.garanhao) as garanhao_nome
    FROM estoque_dono e
    LEFT JOIN dono d ON e.dono_id = d.id
    LEFT JOIN contentores c ON e.contentor_id = c.id
    LEFT JOIN animais a ON a.id = e.animal_id
    WHERE e.existencia_atual > 0
      AND (d.ativo = TRUE OR e.dono_id IS NULL)
    ORDER BY garanhao_nome, e.id
"""


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    assert url, "DATABASE_URL não configurada"
    return psycopg2.connect(url)


@pytest.fixture(scope="module")
def db_conn():
    conn = _connect()
    yield conn
    conn.close()


def test_lote_sem_proprietario_aparece_com_apenas_ativos(db_conn):
    """Um lote com `dono_id = NULL` tem de aparecer em
    `carregar_stock(apenas_ativos=True)` — é o filtro por omissão do
    separador "Lotes", o mesmo que escondia estas linhas antes da
    correcção."""
    nome = f"_TEST_SEMDONO_{int(time.time() * 1_000_000)}"
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO estoque_dono (garanhao, dono_id, existencia_atual) "
        "VALUES (%s, NULL, %s) RETURNING id",
        (nome, 5),
    )
    lote_id = int(cur.fetchone()[0])
    db_conn.commit()
    cur.close()

    try:
        df = pd.read_sql_query(QUERY_CARREGAR_STOCK_ATIVOS, db_conn)
        assert lote_id in df["id"].values
        linha = df[df["id"] == lote_id].iloc[0]
        assert pd.isna(linha["proprietario_nome"])
    finally:
        cur = db_conn.cursor()
        cur.execute("DELETE FROM estoque_dono WHERE id = %s", (lote_id,))
        db_conn.commit()
        cur.close()


def test_resumo_por_proprietario_inclui_sem_proprietario():
    df = pd.DataFrame({
        "proprietario_nome": ["Dono A", None, "Dono A"],
        "existencia_atual": [10, 5, 3],
    })
    resumo = summarize_stock_by_owner(df)
    assert set(resumo["Proprietário"]) == {"Dono A", "Sem proprietário"}
    total_sem_dono = resumo.loc[resumo["Proprietário"] == "Sem proprietário", "Total Palhetas"].iloc[0]
    assert total_sem_dono == 5
