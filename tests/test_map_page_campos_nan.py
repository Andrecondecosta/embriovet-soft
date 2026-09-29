"""Testes para `_lote_int`/`_lote_str` (map_page.py) — helpers que
tornam os campos de um lote (concentração, motilidade, qualidade...)
resistentes a `None`/NaN/vazio.

Motivo: o Mapa dos contentores rebentava com `ValueError: cannot
convert float NaN to integer` ao abrir o detalhe de um lote com
`concentracao` vazia — `int(lote['concentracao'] or 0)` não protege
contra NaN porque NaN é "truthy" em Python (`NaN or 0` continua a ser
NaN). Cobre o caso directo (helpers com NaN/None/vazio) e o caso real
de ponta a ponta: um lote gravado na BD com `concentracao = NULL`
chega como NaN via `obter_stock_contentor` (pandas representa NULL
numérico como NaN, não `None`) e o helper tem de sobreviver a isso.

Segue o mesmo padrão de `test_container_repo.py`: liga directamente à
BD de teste (já forçada por `conftest.py` via `TEST_DATABASE_URL`) e
cria/apaga os próprios dados.
"""

from __future__ import annotations

import math
import os
import time

import psycopg2
import pytest

from modules.pages.map_page import _lote_int, _lote_str
from modules.repositories.stock_repo import obter_stock_contentor


# ────────────────────────────────────────────────────────────────────
# Unit — helpers isolados, sem BD
# ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("valor", [float("nan"), None, "", "   "])
def test_lote_int_nao_rebenta_com_nan_none_ou_vazio(valor):
    assert _lote_int(valor) == 0


def test_lote_int_aceita_default_proprio():
    assert _lote_int(float("nan"), default=-1) == -1
    assert _lote_int(None, default=7) == 7


@pytest.mark.parametrize("valor,esperado", [(12, 12), (12.0, 12), ("34", 34)])
def test_lote_int_converte_valores_validos(valor, esperado):
    assert _lote_int(valor) == esperado


@pytest.mark.parametrize("valor", [float("nan"), None, "", "   "])
def test_lote_str_nao_rebenta_com_nan_none_ou_vazio(valor):
    assert _lote_str(valor) == "—"


def test_lote_str_devolve_texto_valido():
    assert _lote_str("Boa") == "Boa"
    assert _lote_str(42) == "42"


# ────────────────────────────────────────────────────────────────────
# Integração — lote real na BD com concentração/motilidade NULL
# ────────────────────────────────────────────────────────────────────
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
def contentor_id(db_conn) -> int:
    cur = db_conn.cursor()
    codigo = f"_TEST_CONT_NAN_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO contentores (codigo, descricao) VALUES (%s, %s) RETURNING id",
        (codigo, "Contentor de teste — campos NaN"),
    )
    cid = int(cur.fetchone()[0])
    db_conn.commit()
    cur.close()
    yield cid

    cur = db_conn.cursor()
    cur.execute("DELETE FROM estoque_dono WHERE contentor_id = %s", (cid,))
    cur.execute("DELETE FROM contentores WHERE id = %s", (cid,))
    db_conn.commit()
    cur.close()


def test_lote_com_concentracao_e_motilidade_nulas_nao_rebenta(db_conn, contentor_id):
    """Reproduz o bug reportado: um lote real sem concentração/
    motilidade preenchidas (comum em lotes antigos ou incompletos)
    tem de sobreviver ao mesmo caminho que `build_canister_info_html`
    percorre — `_lote_int` sobre o valor tal como `obter_stock_contentor`
    o devolve, não um `NaN`/`None` inventado à mão."""
    nome_nan = f"_TEST_GAR_NAN_{int(time.time() * 1_000_000)}"
    nome_ok = f"_TEST_GAR_OK_{int(time.time() * 1_000_000)}"
    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT INTO estoque_dono
            (garanhao, contentor_id, canister, andar, existencia_atual,
             concentracao, motilidade, qualidade)
        VALUES (%s, %s, %s, %s, %s, NULL, NULL, NULL)
        RETURNING id
        """,
        (nome_nan, contentor_id, 1, 1, 5),
    )
    lote_id = int(cur.fetchone()[0])
    # Um segundo lote no MESMO contentor com concentração/motilidade
    # preenchidas — é assim que o bug acontecia de facto: o pandas só
    # representa um NULL numérico como NaN (float) quando a coluna tem
    # outros valores reais a par; com uma única linha toda a NULL, a
    # coluna fica antes a `None` (object) — cenário diferente, ainda
    # coberto pelo helper, mas não o que o traceback original mostrava.
    cur.execute(
        """
        INSERT INTO estoque_dono
            (garanhao, contentor_id, canister, andar, existencia_atual,
             concentracao, motilidade, qualidade)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (nome_ok, contentor_id, 1, 1, 5, 50, 70, "Boa"),
    )
    db_conn.commit()
    cur.close()

    df = obter_stock_contentor(contentor_id)
    linha = df[df["id"] == lote_id].iloc[0]

    # Confirma que a BD devolve mesmo NaN (não None) para o numérico em
    # falta, quando a par de outro lote com valor real — é essa a forma
    # concreta em que o bug acontecia.
    assert math.isnan(linha["concentracao"])
    assert math.isnan(linha["motilidade"])

    # O caminho que rebentava antes da correção:
    assert _lote_int(linha["concentracao"]) == 0
    assert _lote_int(linha["motilidade"]) == 0
    assert _lote_str(linha["qualidade"]) == "—"
