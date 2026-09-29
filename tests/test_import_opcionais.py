"""Testes para a importação em massa (import_page.py) — proprietário e
contentor/local deixam de ser obrigatórios.

Motivo: uma folha real vinda de fora frequentemente não tem o
proprietário preenchido (o dono ainda não está identificado) nem o
contentor/local exacto (o lote ainda não foi fisicamente arrumado).
Antes, ambos bloqueavam a linha com erro — a única forma de importar
era inventar um proprietário ou um contentor que não existe. Agora:
- Proprietário vazio → importa-se com `dono_id = NULL` ("sem
  proprietário"), atribuível depois na ficha do lote.
- Contentor vazio → vai para um contentor placeholder "TEMPORÁRIO"
  (criado automaticamente na primeira vez que for preciso), visível e
  giríve no Mapa dos contentores, movível depois com "Mover palhetas".
- Canister/andar vazios → assumem 1/1 por omissão.
- Motilidade vazia → fica `NULL` (mesma lógica já aplicada à
  concentração — é uma medida de laboratório, nem sempre feita).
- Um código de contentor PREENCHIDO mas desconhecido continua a ser
  erro (esse caso resolve-se no passo anterior do assistente,
  criar/mapear a entidade — não faz sentido inventar-lhe um local).

Segue o mesmo padrão de `test_container_repo.py` para a parte de BD:
liga directamente à BD de teste (já forçada por `conftest.py` via
`TEST_DATABASE_URL`) e cria/apaga os próprios dados.
"""

from __future__ import annotations

import os
import time

import pandas as pd
import psycopg2
import pytest

from modules.pages.import_page import _validate_import_df
from modules.repositories.container_repo import (
    CONTENTOR_TEMPORARIO_CODIGO,
    obter_ou_criar_contentor_temporario,
)

COLS = [
    "garanhao", "data_embriovet/ref", "existencia_atual", "dose",
    "motilidade", "qualidade", "concentracao", "cor",
    "proprietario_nome", "contentor_codigo", "canister", "andar",
    "observacoes", "certificado",
]


def _linha(**overrides):
    base = {c: "" for c in COLS}
    base.update({
        "garanhao": "Garanhão X",
        "data_embriovet/ref": "2024-01-01",
        "existencia_atual": 10,
        "motilidade": 70,
    })
    base.update(overrides)
    return base


def _df(*linhas):
    return pd.DataFrame(linhas)


# ────────────────────────────────────────────────────────────────────
# Unit — _validate_import_df, sem BD (cont_map/prop_map são só dicts)
# ────────────────────────────────────────────────────────────────────
def test_proprietario_vazio_nao_da_erro_e_fica_sem_dono():
    df = _df(_linha(proprietario_nome=""))
    errors, erros_df, validas = _validate_import_df(df, [2], {}, {})
    assert errors == {}
    assert len(validas) == 1
    assert validas[0]["prop_id"] is None


def test_proprietario_nan_real_fica_vazio_nao_a_string_nan():
    """Uma célula vazia real (como o pandas.read_csv devolve — NaN
    float, não string vazia) não pode acabar como a string literal
    "nan" no relatório final (`str(float('nan')) == 'nan'`)."""
    df = _df(_linha(proprietario_nome=float("nan")))
    errors, erros_df, validas = _validate_import_df(df, [2], {}, {})
    assert errors == {}
    assert validas[0]["proprietario_nome"] == ""


def test_contentor_vazio_nao_da_erro_e_usa_o_temporario():
    df = _df(_linha(contentor_codigo=""))
    errors, erros_df, validas = _validate_import_df(
        df, [2], {}, {}, contentor_temp_id=999,
    )
    assert errors == {}
    assert validas[0]["contentor_id"] == 999


def test_contentor_preenchido_mas_desconhecido_continua_erro():
    df = _df(_linha(contentor_codigo="NAO_EXISTE"))
    errors, erros_df, validas = _validate_import_df(
        df, [2], {"OUTRO": 1}, {}, contentor_temp_id=999,
    )
    assert 0 in errors
    assert errors[0]["contentor_codigo"]


def test_canister_e_andar_vazios_assumem_1_1():
    df = _df(_linha(canister="", andar=""))
    errors, erros_df, validas = _validate_import_df(df, [2], {}, {})
    assert errors == {}
    assert validas[0]["canister"] == 1
    assert validas[0]["andar"] == 1


def test_canister_preenchido_mas_invalido_continua_erro():
    df = _df(_linha(canister=15, andar=1))
    errors, erros_df, validas = _validate_import_df(df, [2], {}, {})
    assert 0 in errors
    assert "canister" in errors[0]


def test_motilidade_vazia_nao_da_erro_e_fica_none():
    df = _df(_linha(motilidade=""))
    errors, erros_df, validas = _validate_import_df(df, [2], {}, {})
    assert errors == {}
    assert validas[0]["motilidade"] is None


def test_motilidade_preenchida_mas_invalida_continua_erro():
    df = _df(_linha(motilidade=150))
    errors, erros_df, validas = _validate_import_df(df, [2], {}, {})
    assert 0 in errors
    assert "motilidade" in errors[0]


def test_linha_so_com_dados_essenciais_fica_totalmente_valida():
    """Garanhão, data e existência continuam obrigatórios — mas nada
    mais precisa de estar preenchido (nem proprietário, contentor,
    canister/andar, motilidade ou concentração)."""
    df = _df(_linha(
        proprietario_nome="", contentor_codigo="", canister="", andar="",
        qualidade="", concentracao="", cor="", dose="", observacoes="",
        certificado="", motilidade="",
    ))
    errors, erros_df, validas = _validate_import_df(
        df, [2], {}, {}, contentor_temp_id=42,
    )
    assert errors == {}
    assert len(validas) == 1
    linha = validas[0]
    assert linha["prop_id"] is None
    assert linha["contentor_id"] == 42
    assert linha["canister"] == 1
    assert linha["andar"] == 1
    assert linha["motilidade"] is None


# ────────────────────────────────────────────────────────────────────
# Integração — contentor placeholder "TEMPORÁRIO" na BD real
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


def test_obter_ou_criar_contentor_temporario_e_idempotente(db_conn):
    """Chamar duas vezes tem de devolver sempre o mesmo id — nunca cria
    um duplicado. Deliberadamente NÃO apaga nada antes/depois: o
    "TEMPORÁRIO" é um contentor real e partilhado (pode já ter stock
    verdadeiro lá dentro, de importações passadas) — um teste que o
    apagasse arriscava destruir dados reais na BD partilhada. Por isso
    o teste verifica idempotência a partir do estado que já lá
    estiver, nunca força um estado "limpo"."""
    id1 = obter_ou_criar_contentor_temporario()
    id2 = obter_ou_criar_contentor_temporario()
    assert id1 is not None
    assert id1 == id2

    cur = db_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM contentores WHERE codigo = %s",
        (CONTENTOR_TEMPORARIO_CODIGO,),
    )
    total = cur.fetchone()[0]
    cur.close()
    assert total == 1
