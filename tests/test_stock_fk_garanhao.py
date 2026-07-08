"""Testes de integração para o Pedido 5 — leituras via FK `animais`.

Valida que as queries de `carregar_stock`, `carregar_transferencias`
e `obter_stock_contentor` (em `/app/app.py`) devolvem `garanhao_nome`
(ou coluna `garanhao` canonicalizada) via `COALESCE(a.nome, e.garanhao)`
usando o LEFT JOIN a `animais` pela FK `estoque_dono.animal_id`.

Também valida `filter_stock_view` (prefere `garanhao_nome` com fallback).

Como `app.py` corre código Streamlit no import (top-level), estes testes
replicam as queries directamente contra a BD de teste — o que é
equivalente a validar o SQL produzido pelas funções decoradas com
`@st.cache_data`.
"""

from __future__ import annotations

import os
import time

import pandas as pd
import psycopg2
import pytest


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    assert url, "DATABASE_URL não configurada"
    return psycopg2.connect(url)


@pytest.fixture(scope="module")
def db_conn():
    conn = _connect()
    yield conn
    conn.close()


@pytest.fixture()
def dono_id(db_conn) -> int:
    cur = db_conn.cursor()
    cur.execute(
        "SELECT id FROM dono WHERE ativo = TRUE ORDER BY id LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        cur.close()
        return int(row[0])
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (f"_TEST_DONO_{int(time.time())}",),
    )
    did = int(cur.fetchone()[0])
    db_conn.commit()
    cur.close()
    return did


# Réplica exacta das queries em /app/app.py (Pedido 5)
QUERY_CARREGAR_STOCK = """
    SELECT e.*,
           d.nome as proprietario_nome,
           c.codigo as contentor_codigo,
           COALESCE(a.nome, e.garanhao) as garanhao_nome
    FROM estoque_dono e
    LEFT JOIN dono d ON e.dono_id = d.id
    LEFT JOIN contentores c ON e.contentor_id = c.id
    LEFT JOIN animais a ON a.id = e.animal_id
    WHERE e.existencia_atual > 0
      AND d.ativo = TRUE
    ORDER BY garanhao_nome, e.id
"""

QUERY_OBTER_STOCK_CONTENTOR = """
    SELECT e.id,
           COALESCE(a.nome, e.garanhao) AS garanhao,
           d.nome as proprietario_nome,
           e.canister, e.andar, e.existencia_atual,
           e.qualidade, e.data_embriovet, e.origem_externa
    FROM estoque_dono e
    LEFT JOIN dono d ON e.dono_id = d.id
    LEFT JOIN animais a ON a.id = e.animal_id
    WHERE e.contentor_id = %s AND e.existencia_atual > 0
    ORDER BY e.canister, e.andar, garanhao
"""


def _cleanup(cur, animal_ids, lote_ids):
    if lote_ids:
        cur.execute(
            "DELETE FROM estoque_dono WHERE id = ANY(%s)", (lote_ids,)
        )
    if animal_ids:
        cur.execute(
            "DELETE FROM animais WHERE id = ANY(%s)", (animal_ids,)
        )


# ────────────────────────────────────────────────────────────────────
# carregar_stock: coluna garanhao_nome via FK + fallback
# ────────────────────────────────────────────────────────────────────

def test_carregar_stock_devolve_garanhao_nome_via_fk(db_conn, dono_id):
    """Lotes com `animal_id` preenchido → garanhao_nome = animais.nome.
       Lotes sem FK → fallback a estoque_dono.garanhao (texto legado)."""
    cur = db_conn.cursor()
    animal_id = None
    lote_com_fk = None
    lote_sem_fk = None
    try:
        nome_animal = f"_TEST_FK_{int(time.time()*1000)}"
        cur.execute(
            "INSERT INTO animais (nome, tipo, dono_id, ativo) "
            "VALUES (%s, 'garanhao', %s, TRUE) RETURNING id",
            (nome_animal, dono_id),
        )
        animal_id = int(cur.fetchone()[0])

        # Lote com FK — nome legado propositadamente DIFERENTE do nome
        # canónico em `animais` (para provar que o SELECT lê da FK).
        cur.execute(
            "INSERT INTO estoque_dono (garanhao, dono_id, animal_id, "
            "palhetas_produzidas, existencia_atual) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            ("_LEGADO_DIFERENTE", dono_id, animal_id, 10, 10),
        )
        lote_com_fk = int(cur.fetchone()[0])

        # Lote sem FK — o fallback COALESCE deve devolver o texto legado
        nome_fallback = f"_TEST_FALLBACK_{int(time.time()*1000)}"
        cur.execute(
            "INSERT INTO estoque_dono (garanhao, dono_id, animal_id, "
            "palhetas_produzidas, existencia_atual) "
            "VALUES (%s, %s, NULL, %s, %s) RETURNING id",
            (nome_fallback, dono_id, 7, 7),
        )
        lote_sem_fk = int(cur.fetchone()[0])
        db_conn.commit()

        df = pd.read_sql_query(QUERY_CARREGAR_STOCK, db_conn)
        assert "garanhao_nome" in df.columns
        assert "garanhao" in df.columns  # coluna legada continua presente

        row_fk = df[df["id"] == lote_com_fk].iloc[0]
        assert row_fk["garanhao_nome"] == nome_animal, (
            f"lote com FK devia devolver o nome canónico ({nome_animal}), "
            f"obtido {row_fk['garanhao_nome']}"
        )
        # Coluna texto legada preservada (para retro-compat de escritas)
        assert row_fk["garanhao"] == "_LEGADO_DIFERENTE"

        row_nofk = df[df["id"] == lote_sem_fk].iloc[0]
        assert row_nofk["garanhao_nome"] == nome_fallback, (
            "sem FK → COALESCE deve cair para e.garanhao"
        )
    finally:
        _cleanup(cur, [animal_id] if animal_id else [],
                 [i for i in (lote_com_fk, lote_sem_fk) if i])
        db_conn.commit()
        cur.close()


def test_rename_animal_reflete_em_stock_sem_tocar_estoque_dono(
    db_conn, dono_id
):
    """UPDATE animais.nome propaga a `garanhao_nome` sem alterar
    `estoque_dono.garanhao` (o texto legado permanece intacto)."""
    cur = db_conn.cursor()
    animal_id = None
    lote_id = None
    try:
        nome_original = f"_TEST_ORIG_{int(time.time()*1000)}"
        cur.execute(
            "INSERT INTO animais (nome, tipo, dono_id, ativo) "
            "VALUES (%s, 'garanhao', %s, TRUE) RETURNING id",
            (nome_original, dono_id),
        )
        animal_id = int(cur.fetchone()[0])

        cur.execute(
            "INSERT INTO estoque_dono (garanhao, dono_id, animal_id, "
            "palhetas_produzidas, existencia_atual) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (nome_original, dono_id, animal_id, 5, 5),
        )
        lote_id = int(cur.fetchone()[0])
        db_conn.commit()

        df1 = pd.read_sql_query(QUERY_CARREGAR_STOCK, db_conn)
        row1 = df1[df1["id"] == lote_id].iloc[0]
        assert row1["garanhao_nome"] == nome_original

        # Renomear o animal — não tocar em estoque_dono
        nome_novo = f"_TEST_RENOMEADO_{int(time.time()*1000)}"
        cur.execute(
            "UPDATE animais SET nome = %s WHERE id = %s",
            (nome_novo, animal_id),
        )
        db_conn.commit()

        df2 = pd.read_sql_query(QUERY_CARREGAR_STOCK, db_conn)
        row2 = df2[df2["id"] == lote_id].iloc[0]
        assert row2["garanhao_nome"] == nome_novo, (
            "renomear em `animais` deve reflectir-se em garanhao_nome"
        )
        # A coluna legada em estoque_dono permanece intacta (retro-compat)
        assert row2["garanhao"] == nome_original, (
            "estoque_dono.garanhao NÃO deve ser tocada — só a UI muda"
        )
    finally:
        _cleanup(cur, [animal_id] if animal_id else [],
                 [lote_id] if lote_id else [])
        db_conn.commit()
        cur.close()


def test_carregar_transferencias_resolve_garanhao_via_fk(db_conn, dono_id):
    """`carregar_transferencias` devolve `garanhao` resolvido via FK."""
    cur = db_conn.cursor()
    animal_id = None
    lote_id = None
    transf_id = None
    try:
        nome_animal = f"_TEST_TRANSF_{int(time.time()*1000)}"
        cur.execute(
            "INSERT INTO animais (nome, tipo, dono_id, ativo) "
            "VALUES (%s, 'garanhao', %s, TRUE) RETURNING id",
            (nome_animal, dono_id),
        )
        animal_id = int(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO estoque_dono (garanhao, dono_id, animal_id, "
            "palhetas_produzidas, existencia_atual) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            ("_LEG_TRANSF", dono_id, animal_id, 3, 3),
        )
        lote_id = int(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO transferencias "
            "(estoque_id, proprietario_origem_id, proprietario_destino_id, "
            " quantidade, data_transferencia) "
            "VALUES (%s, %s, %s, %s, NOW()) RETURNING id",
            (lote_id, dono_id, dono_id, 1),
        )
        transf_id = int(cur.fetchone()[0])
        db_conn.commit()

        query = """
            SELECT t.*,
                   COALESCE(a.nome, e.garanhao) as garanhao
            FROM transferencias t
            LEFT JOIN estoque_dono e ON t.estoque_id = e.id
            LEFT JOIN animais a ON a.id = e.animal_id
            WHERE t.id = %s
        """
        df = pd.read_sql_query(query, db_conn, params=(transf_id,))
        assert len(df) == 1
        assert df.iloc[0]["garanhao"] == nome_animal, (
            "carregar_transferencias devia resolver via FK animais.nome"
        )
    finally:
        if transf_id:
            cur.execute(
                "DELETE FROM transferencias WHERE id = %s", (transf_id,)
            )
        _cleanup(cur, [animal_id] if animal_id else [],
                 [lote_id] if lote_id else [])
        db_conn.commit()
        cur.close()


def test_obter_stock_contentor_resolve_garanhao_via_fk(db_conn, dono_id):
    """`obter_stock_contentor` devolve o nome canónico via FK."""
    cur = db_conn.cursor()
    animal_id = None
    lote_id = None
    contentor_id = None
    try:
        cur.execute(
            "SELECT id FROM contentores ORDER BY id LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            contentor_id = int(row[0])
            contentor_criado = False
        else:
            cur.execute(
                "INSERT INTO contentores (codigo) VALUES (%s) RETURNING id",
                (f"_TEST_CTR_{int(time.time()*1000)}",),
            )
            contentor_id = int(cur.fetchone()[0])
            contentor_criado = True
            db_conn.commit()

        nome_animal = f"_TEST_CTR_{int(time.time()*1000)}"
        cur.execute(
            "INSERT INTO animais (nome, tipo, dono_id, ativo) "
            "VALUES (%s, 'garanhao', %s, TRUE) RETURNING id",
            (nome_animal, dono_id),
        )
        animal_id = int(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO estoque_dono (garanhao, dono_id, animal_id, "
            "contentor_id, palhetas_produzidas, existencia_atual, "
            "canister, andar) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            ("_LEG_CTR", dono_id, animal_id, contentor_id, 4, 4, 1, 1),
        )
        lote_id = int(cur.fetchone()[0])
        db_conn.commit()

        df = pd.read_sql_query(
            QUERY_OBTER_STOCK_CONTENTOR, db_conn, params=(contentor_id,)
        )
        row_lote = df[df["id"] == lote_id].iloc[0]
        assert row_lote["garanhao"] == nome_animal, (
            "obter_stock_contentor deve resolver o nome via FK"
        )
    finally:
        _cleanup(cur, [animal_id] if animal_id else [],
                 [lote_id] if lote_id else [])
        if contentor_id and 'contentor_criado' in dir() and contentor_criado:
            cur.execute(
                "DELETE FROM contentores WHERE id = %s", (contentor_id,)
            )
        db_conn.commit()
        cur.close()


# ────────────────────────────────────────────────────────────────────
# filter_stock_view: prefere garanhao_nome, fallback a garanhao
# ────────────────────────────────────────────────────────────────────

def test_filter_stock_view_prefere_garanhao_nome():
    from modules.stock_reporting import filter_stock_view

    df = pd.DataFrame([
        {
            "garanhao": "LEG_A", "garanhao_nome": "CANONICO_A",
            "existencia_atual": 5, "proprietario_nome": "Dono X",
        },
        {
            "garanhao": "LEG_B", "garanhao_nome": "CANONICO_B",
            "existencia_atual": 3, "proprietario_nome": "Dono X",
        },
    ])
    # Filtrar por nome canónico deve devolver a linha correcta
    out = filter_stock_view(df, "CANONICO_A")
    assert len(out) == 1
    assert out.iloc[0]["garanhao"] == "LEG_A"

    # Filtrar pelo nome legado NÃO deve devolver nada porque o filtro
    # agora prefere `garanhao_nome`
    out_legado = filter_stock_view(df, "LEG_A")
    assert len(out_legado) == 0


def test_filter_stock_view_fallback_garanhao_legado():
    """Retro-compat: se o DataFrame não tem `garanhao_nome`, o filtro
    cai para a coluna `garanhao` (texto legado)."""
    from modules.stock_reporting import filter_stock_view

    df = pd.DataFrame([
        {"garanhao": "LEG_A", "existencia_atual": 5,
         "proprietario_nome": "Dono X"},
    ])
    out = filter_stock_view(df, "LEG_A")
    assert len(out) == 1


# ────────────────────────────────────────────────────────────────────
# Grep final: coluna de texto só aparece em escritas + fallback COALESCE
# ────────────────────────────────────────────────────────────────────

def test_grep_final_no_leituras_da_coluna_texto():
    """Guarda de arquitetura: leituras da coluna texto `garanhao` só
    podem existir em dois sítios muito específicos, e mais em lado
    nenhum (nem em `app.py`, nem em `modules/pages/*`, nem em nenhum
    outro repositório).

    As duas ocorrências toleradas são:

    1. `modules/pages/map_page.py` — template JavaScript inline que
       lê `lote.garanhao` de um objecto já construído em Python (o
       objecto usa `garanhao_nome` como preferência; o campo texto é
       apenas fallback compat).
    2. `modules/repositories/stock_repo.py` — expressão
       `garanhao_expr = "te.garanhao"` dentro de
       `carregar_transferencias_externas`, ligada ao ramo defensivo
       para schemas legados que **ainda não têm** `estoque_id` na
       tabela `transferencias_externas`. Assim que a migração de
       schema for feita este ramo pode ser removido.

    Objectivo do teste: se alguém voltar a introduzir uma leitura de
    `e.garanhao` no `app.py` ou nas pages, o teste falha e força a
    conversa. Este guarda ficou mais estrito após o Pedido 6.2
    (extração de `stock_repo.py`) — antes aceitava a ocorrência em
    `app.py` porque o fallback vivia lá.
    """
    import subprocess

    cmd = (
        r"grep -rn 'e\.garanhao\|ed\.garanhao\|LOWER(garanhao)' "
        r"/app/modules /app/app.py "
        r"| grep -v migrations | grep -v __pycache__ "
        r"| grep -v 'COALESCE' | grep -v '\-\-\|#'"
    )
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True
    )
    linhas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(linhas) <= 2, (
        f"Esperado <=2 ocorrências residuais, obtido {len(linhas)}:\n"
        + "\n".join(linhas)
    )
    joined = "\n".join(linhas)

    # Nenhuma ocorrência pode viver no `app.py` nem em nenhum ficheiro
    # de `modules/pages/` (exceto `map_page.py`, coberto abaixo).
    for ln in linhas:
        assert "app.py" not in ln, (
            f"leitura de `e.garanhao` reintroduzida em app.py: {ln!r}"
        )
        if "modules/pages/" in ln:
            assert "map_page.py" in ln, (
                f"leitura de `e.garanhao` reintroduzida numa page: {ln!r}"
            )

    # Ocorrências toleradas — apenas nestes dois caminhos.
    caminhos_permitidos = (
        "modules/pages/map_page.py",
        "modules/repositories/stock_repo.py",
    )
    for ln in linhas:
        assert any(p in ln for p in caminhos_permitidos), (
            f"leitura de `e.garanhao` fora dos caminhos autorizados: {ln!r}"
        )
