"""Testes do Pedido 7 — Reorganização da navegação (13 → 6).

Cobre os critérios de aceitação:
(a) menu com exactamente 6 itens, sem emojis, sem "Mais opções";
(b) os 13 antigos labels de menu resolvem para um dos 6 novos destinos;
(c) o repo `_carregar_garanhoes_com_stock` devolve os garanhões com
    stock (base do novo separador "Garanhões");
(d) os pontos de entrada da inseminação continuam a activar o flag
    `insem_flow_active` — testado por inspecção do código-fonte;
(e) o separador "Utilizadores" é filtrado por permissão (`is_admin`);
(f) toda a suite passa (63 baseline + estes novos).

Estes testes não iniciam o Streamlit — validam contratos de código
e queries SQL directamente.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import psycopg2
import pytest

from modules.pages.stock_semen_page import _carregar_garanhoes_com_stock
from modules.repositories.animal_repo import get_or_create_garanhao


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


# ────────────────────────────────────────────────────────────────────
# (a) Menu tem 6 itens, sem emojis, sem "Mais opções"
# ────────────────────────────────────────────────────────────────────

def test_menu_lateral_tem_seis_itens_sem_emoji():
    """`app.py` deve definir `menu_principal` com exactamente os 6
    labels novos (Dashboard/Estadias/.../Definições) e nenhum emoji.
    `menu_secundario` deve ser lista vazia."""
    src = Path("/app/app.py").read_text()

    # Extrair menu_principal
    m = re.search(
        r"menu_principal\s*=\s*\[(?P<items>.*?)\]",
        src,
        flags=re.DOTALL,
    )
    assert m is not None, "menu_principal não encontrado em app.py"
    items = m.group("items")

    # Validar 6 nomes literais nas constantes NAV_*
    esperados = [
        "NAV_DASHBOARD", "NAV_ESTADIAS", "NAV_TRABALHO_DIARIO",
        "NAV_STOCK_SEMEN", "NAV_RELATORIOS", "NAV_DEFINICOES",
    ]
    for nome in esperados:
        assert nome in items, f"{nome} ausente do menu_principal"

    # Validar strings dos NAV_* (sem emoji)
    for label in [
        '"Dashboard"', '"Estadias"', '"Trabalho diário"',
        '"Stock de sémen"', '"Relatórios"', '"Definições"',
    ]:
        assert label in src, f"label esperado {label} ausente em app.py"

    # Sem emojis nas constantes NAV_*
    emoji_pattern = re.compile(
        r"NAV_\w+\s*=\s*\"[^\"]*"
        r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"
    )
    assert not emoji_pattern.search(src), (
        "NAV_* labels não podem conter emojis"
    )

    # menu_secundario vazio
    m2 = re.search(r"menu_secundario\s*=\s*\[(?P<items>.*?)\]", src)
    assert m2 is not None
    assert not m2.group("items").strip(), (
        "menu_secundario deve ser [] no Pedido 7 (sem 'Mais opções')"
    )


# ────────────────────────────────────────────────────────────────────
# (b) Todos os 13 antigos labels resolvem para um dos 6 novos
# ────────────────────────────────────────────────────────────────────

def test_mapeamento_13_para_6_esta_completo():
    """O `_LEGACY_NAV_MAP` em `app.py` deve cobrir os 12 antigos labels
    (menu.dashboard, menu.stock, menu.map, menu.transfers, menu.reports,
    menu.add_stock, menu.import, menu.register_insemination, menu.owners,
    menu.users, menu.settings + literal 'Estadias e Visitas' e
    'Trabalho diário')."""
    src = Path("/app/app.py").read_text()
    m = re.search(
        r"_LEGACY_NAV_MAP\s*=\s*\{(?P<body>.*?)\n\}",
        src,
        flags=re.DOTALL,
    )
    assert m is not None, "_LEGACY_NAV_MAP não encontrado"
    body = m.group("body")

    for k in [
        "menu.dashboard", "menu.stock", "menu.map", "menu.transfers",
        "menu.reports", "menu.add_stock", "menu.import",
        "menu.register_insemination", "menu.owners", "menu.users",
        "menu.settings",
    ]:
        assert f'"{k}"' in body, f"mapeamento de {k!r} ausente"
    assert '"Estadias e Visitas"' in body
    assert '"Trabalho diário"' in body


# ────────────────────────────────────────────────────────────────────
# (c) Tab "Garanhões": query devolve garanhões com stock
# ────────────────────────────────────────────────────────────────────

def test_carregar_garanhoes_com_stock_devolve_garanhao_com_lote(db):
    # Seed: dono + garanhão + lote em estoque_dono
    ts = int(time.time() * 1_000_000)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (f"_TEST_P7_DONO_{ts}",),
    )
    dono_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()

    gar_nome = f"_TEST_P7_GAR_{ts}"
    gar_id = get_or_create_garanhao(gar_nome)

    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO estoque_dono (
            garanhao, dono_id, palhetas_produzidas,
            quantidade_inicial, existencia_atual, animal_id
        ) VALUES (
            (SELECT nome FROM animais WHERE id = %s),
            %s, 10, 10, 10, %s
        )
        """,
        (gar_id, dono_id, gar_id),
    )
    db.commit()
    cur.close()

    rows = _carregar_garanhoes_com_stock()
    matched = [r for r in rows if r[0] == gar_id]
    assert matched, "garanhão criado devia aparecer no separador"
    assert matched[0][1] == gar_nome
    assert int(matched[0][2]) >= 10  # palhetas
    assert int(matched[0][3]) >= 1   # lotes


def test_carregar_garanhoes_com_stock_exclui_lotes_zerados(db):
    ts = int(time.time() * 1_000_000)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (f"_TEST_P7_DONO_ZERO_{ts}",),
    )
    dono_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()

    gar_id = get_or_create_garanhao(f"_TEST_P7_GAR_ZERO_{ts}")

    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO estoque_dono (
            garanhao, dono_id, palhetas_produzidas,
            quantidade_inicial, existencia_atual, animal_id
        ) VALUES (
            (SELECT nome FROM animais WHERE id = %s),
            %s, 5, 5, 0, %s
        )
        """,
        (gar_id, dono_id, gar_id),
    )
    db.commit()
    cur.close()

    rows = _carregar_garanhoes_com_stock()
    ids = [r[0] for r in rows]
    assert gar_id not in ids, (
        "garanhão sem stock (existencia_atual=0) não deve aparecer"
    )


# ────────────────────────────────────────────────────────────────────
# (d) Pontos de entrada da inseminação activam `insem_flow_active`
# ────────────────────────────────────────────────────────────────────

def test_estadias_page_seta_insem_flow_active():
    src = Path("/app/modules/pages/estadias_page.py").read_text()
    # No botão "Registar inseminação" (fila de estadia activa) tem de
    # setar o flag.
    assert 'insem_flow_active' in src, (
        "estadias_page.py deve activar `insem_flow_active` no botão "
        "'Registar inseminação'"
    )
    assert '"Trabalho diário"' in src, (
        "estadias_page.py deve redireccionar para 'Trabalho diário'"
    )


def test_animal_page_seta_insem_flow_active():
    src = Path("/app/modules/pages/animal_page.py").read_text()
    assert 'insem_flow_active' in src
    # E o botão só aparece para éguas
    assert 'egua' in src.lower()


def test_trabalho_diario_pivota_para_form_de_inseminacao_com_flag():
    src = Path("/app/modules/pages/trabalho_diario_page.py").read_text()
    # O `run_trabalho_diario_page` deve delegar para `run_insemination_page`
    # quando `insem_flow_active` está setado.
    assert 'insem_flow_active' in src
    assert 'run_insemination_page' in src


def test_insemination_page_limpa_insem_flow_active_no_fim():
    """Nos redirects pós-sucesso (Trabalho Diário / Ficha da égua),
    o `insem_flow_active` deve ser limpo para não ficar preso no fluxo."""
    src = Path("/app/modules/pages/insemination_page.py").read_text()
    assert src.count('pop("insem_flow_active", None)') >= 2, (
        "insemination_page.py deve limpar `insem_flow_active` em ambos "
        "os botões pós-sucesso (Trabalho Diário e Ficha da égua)"
    )


# ────────────────────────────────────────────────────────────────────
# (e) Separador "Utilizadores" é filtrado por permissão
# ────────────────────────────────────────────────────────────────────

def test_definicoes_page_filtra_utilizadores_por_admin():
    src = Path("/app/modules/pages/definicoes_page.py").read_text()
    # Deve haver um check `is_admin` (ou `verificar_permissao('Administrador')`)
    # que controla a existência do separador "Utilizadores".
    assert '"Administrador"' in src or "verificar_permissao" in src, (
        "definicoes_page.py deve consultar permissões"
    )
    assert "Utilizadores" in src
    # E o `is_admin` gates o append de "Utilizadores" e a
    # renderização do respectivo tab.
    assert re.search(r"if\s+is_admin\s*:", src), (
        "deve existir bloco `if is_admin:` em definicoes_page.py"
    )


# ────────────────────────────────────────────────────────────────────
# Extras — estrutura do orquestrador Stock de sémen
# ────────────────────────────────────────────────────────────────────

def test_stock_semen_tem_4_separadores_e_2_botoes_topo():
    src = Path("/app/modules/pages/stock_semen_page.py").read_text()
    # Separadores
    for tab in ["Lotes", "Garanhões", "Mapa dos contentores", "Transferências"]:
        assert f'"{tab}"' in src, f"separador '{tab}' ausente"
    # Botões topo (Adicionar lote e Importar)
    assert '"Adicionar lote"' in src
    # "Importar" pode estar como label do botão
    assert '"Importar"' in src


def test_stock_semen_page_delegates_para_paginas_existentes():
    """O orquestrador não pode reimplementar lógica — tem de invocar
    as pages existentes (`run_stock_page`, `run_map_page`,
    `run_transfer_page`, `run_import_page`)."""
    src = Path("/app/modules/pages/stock_semen_page.py").read_text()
    for fn in [
        "run_stock_page", "run_map_page",
        "run_transfer_page", "run_import_page",
    ]:
        assert fn in src, f"delegação a {fn} ausente"
