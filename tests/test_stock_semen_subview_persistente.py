"""Regressão: a sub-vista "Adicionar lote"/"Importar" do Stock de sémen
não pode perder-se a meio do preenchimento.

Bug original (existia desde 2026-07-08, commit 7269dc32, sem deteção):
`run_stock_semen_page` lia a flag `stock_semen_view` com `.pop()` — ou
seja, consumia-a logo no primeiro rerun após clicar "Adicionar lote".
Qualquer interação seguinte que disparasse outro rerun (escolher um
garanhão/proprietário nos selectbox fora do `st.form`, ou a própria
submissão do form via "Guardar") já não encontrava a flag, caía no
ramo da vista padrão (separadores) e a gravação nunca chegava a
correr — impossível registar um lote.

Corrigido trocando `.pop()` por `.get()` (a flag sobrevive a todos os
reruns dentro da sub-vista) e limpando-a explicitamente só nos pontos
de saída reais: "← Voltar ao Stock de sémen" (add_stock e import) e a
gravação com sucesso do lote.

Este teste usa `AppTest` (streamlit.testing.v1) para exercitar o fluxo
real através de múltiplos reruns — não apenas inspeção de código-fonte
— porque foi exactamente a ausência de um teste do fluxo completo (só
a função de query isolada estava coberta) que deixou o bug escondido
durante meses.
"""

from __future__ import annotations

import os
import time

import psycopg2
import pytest
from streamlit.testing.v1 import AppTest

from modules.i18n import t
from modules.repositories.animal_repo import get_or_create_garanhao

APP_TIMEOUT = 30


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@pytest.fixture()
def db():
    conn = _connect()
    yield conn
    conn.close()


@pytest.fixture()
def seed(db):
    """Dono, dois garanhões e um contentor — próprios do teste, para não
    depender da ordem/estado de dados pré-existentes na BD de teste."""
    ts = int(time.time() * 1_000_000)
    cur = db.cursor()

    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (f"_TEST_SUBVIEW_DONO_{ts}",),
    )
    dono_id = int(cur.fetchone()[0])
    db.commit()

    gar_a = get_or_create_garanhao(f"_TEST_SUBVIEW_GAR_A_{ts}")
    gar_b = get_or_create_garanhao(f"_TEST_SUBVIEW_GAR_B_{ts}")

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
            (f"_TEST_SUBVIEW_CTR_{ts}",),
        )
        contentor_id = int(cur.fetchone()[0])
        contentor_criado = True
        db.commit()

    cur.close()

    yield {
        "dono_id": dono_id,
        "garanhao_a_id": gar_a,
        "garanhao_b_id": gar_b,
        "contentor_id": contentor_id,
    }

    cur = db.cursor()
    cur.execute(
        "DELETE FROM estoque_dono WHERE animal_id = ANY(%s)",
        ([gar_a, gar_b],),
    )
    cur.execute(
        "DELETE FROM animais WHERE id = ANY(%s)", ([gar_a, gar_b],)
    )
    cur.execute("DELETE FROM dono WHERE id = %s", (dono_id,))
    if contentor_criado:
        cur.execute(
            "DELETE FROM contentores WHERE id = %s", (contentor_id,)
        )
    db.commit()
    cur.close()


def _ss(at: AppTest, key: str, default=None):
    """`at.session_state` não expõe `.get()` (proxy do Streamlit só
    implementa `__getattr__`/`__getitem__`) — acesso seguro por chave."""
    return at.session_state[key] if key in at.session_state else default


def _run_stock_semen_page_script():
    import streamlit as st  # noqa: F401
    from modules.pages.stock_semen_page import run_stock_semen_page

    run_stock_semen_page({})


def _abrir_add_stock(at: AppTest) -> AppTest:
    """Simula o clique em "Adicionar lote" — a flag é definida e a
    página corre pela 1ª vez dentro da sub-vista, tal como o botão real
    faz (`st.session_state["stock_semen_view"] = "add_stock"` seguido
    de rerun)."""
    at.session_state["stock_semen_view"] = "add_stock"
    at.run(timeout=APP_TIMEOUT)
    return at


def test_escolher_proprietario_nao_expulsa_do_formulario(seed):
    """(a) Trocar o proprietário seleccionado dispara um rerun (o
    selectbox está fora do `st.form`, tal como o do garanhão) — a
    sub-vista "Adicionar lote" tem de continuar aberta depois disso,
    não voltar aos separadores.

    Usa o selectbox "Proprietário do Sémen" em vez do "Garanhão" para
    accionar o rerun: o do garanhão usa `format_func` sobre um id
    inteiro, o que esbarra numa limitação própria do `AppTest` do
    Streamlit (perde a correspondência id→label ao trocar de opção,
    independente de haver ou não bug na aplicação). O do proprietário
    usa strings simples e é mecanicamente idêntico do ponto de vista
    do bug em causa: um widget fora do form que dispara um rerun.
    """
    at = AppTest.from_function(_run_stock_semen_page_script)
    _abrir_add_stock(at)

    assert not at.exception, f"erro ao abrir Adicionar lote: {at.exception}"
    assert at.selectbox(key="add_stock_garanhao_select") is not None, (
        "formulário 'Adicionar lote' devia estar visível após o 1º rerun"
    )
    prop_select = at.selectbox(key="add_stock_prop_select")
    assert prop_select is not None
    assert len(prop_select.options) >= 2, (
        "precisa de pelo menos 2 proprietários para trocar a selecção"
    )

    # Escolher outra opção — dispara rerun imediato (fora do form).
    outro_index = 1 if prop_select.index == 0 else 0
    prop_select.select_index(outro_index).run(timeout=APP_TIMEOUT)

    assert not at.exception, f"erro após trocar proprietário: {at.exception}"
    assert _ss(at, "stock_semen_view") == "add_stock", (
        "a flag 'stock_semen_view' não pode perder-se só por trocar o "
        "proprietário — é exactamente o bug original"
    )
    assert at.selectbox(key="add_stock_garanhao_select") is not None, (
        "o formulário 'Adicionar lote' saiu do ecrã ao trocar de "
        "proprietário — regressão do bug de sub-vista de utilização única"
    )


def test_guardar_lote_grava_na_bd_e_sai_da_subvista(seed, db):
    """(b) Preencher o formulário completo e clicar "Guardar" tem de
    gravar mesmo o lote em `estoque_dono` — o próprio submit do form
    dispara um rerun que, com o bug original, também perdia a flag
    antes de o código de gravação chegar a correr."""
    cur = db.cursor()
    cur.execute("SELECT count(*) FROM estoque_dono")
    antes = cur.fetchone()[0]
    cur.close()

    at = AppTest.from_function(_run_stock_semen_page_script)
    _abrir_add_stock(at)
    assert not at.exception, f"erro ao abrir Adicionar lote: {at.exception}"

    # Preencher "Palhetas Produzidas" (único campo com validação
    # obrigatória > 0) — os restantes ficam nos valores por omissão,
    # tal como no caminho mais simples que um utilizador tentaria.
    straws = [
        ni for ni in at.number_input
        if t("stock.straws_produced") in (ni.label or "")
    ]
    assert straws, "campo 'Palhetas Produzidas' não encontrado no form"
    straws[0].set_value(12)

    guardar = [
        b for b in at.button if (b.label or "") == t("btn.save")
    ]
    assert guardar, "botão 'Guardar' não encontrado"
    guardar[0].click().run(timeout=APP_TIMEOUT)

    assert not at.exception, f"erro ao gravar: {at.exception}"

    cur = db.cursor()
    cur.execute("SELECT count(*) FROM estoque_dono")
    depois = cur.fetchone()[0]
    cur.close()

    assert depois == antes + 1, (
        "o lote não foi gravado — o rerun do próprio 'Guardar' perdeu "
        "a sub-vista antes de `inserir_stock` correr (bug original)"
    )

    # Redirect pós-gravação: sai da sub-vista, aterra em Lotes. O
    # AppTest segue automaticamente o `st.rerun()` dentro do próprio
    # `.run()`, por isso `stock_semen_tab` já foi consumido por
    # `_resolver_aba_ativa()` e transformado em `stock_semen_active_tab`
    # (esse sim, o estado persistente do separador activo).
    assert _ss(at, "stock_semen_view") is None, (
        "'stock_semen_view' devia ser limpo ao gravar com sucesso"
    )
    assert _ss(at, "stock_semen_active_tab") == "Lotes"


def test_voltar_do_add_stock_limpa_a_subvista(seed):
    """O botão "← Voltar ao Stock de sémen" tem de limpar a flag — caso
    contrário a próxima navegação para "Stock de sémen" reabriria
    sempre directamente em "Adicionar lote"."""
    at = AppTest.from_function(_run_stock_semen_page_script)
    _abrir_add_stock(at)
    assert not at.exception

    voltar = [
        b for b in at.button
        if "Voltar ao Stock de sémen" in (b.label or "")
    ]
    assert voltar, "botão 'Voltar ao Stock de sémen' não encontrado"
    voltar[0].click().run(timeout=APP_TIMEOUT)

    assert not at.exception, f"erro ao voltar: {at.exception}"
    assert _ss(at, "stock_semen_view") is None


def test_importar_sobrevive_a_rerun_dentro_da_subvista(seed):
    """Mesma classe de bug na vista "Importar" — qualquer rerun dentro
    dela (aqui simulado directamente, já que o 1º widget é um
    file_uploader difícil de accionar via AppTest) não pode perder a
    flag antes do utilizador sair deliberadamente."""
    at = AppTest.from_function(_run_stock_semen_page_script)
    at.session_state["stock_semen_view"] = "import"
    at.run(timeout=APP_TIMEOUT)
    assert not at.exception, f"erro ao abrir Importar: {at.exception}"
    assert _ss(at, "stock_semen_view") == "import"

    # Rerun adicional dentro da mesma sub-vista (equivalente a qualquer
    # widget do wizard de importação disparar um script rerun).
    at.run(timeout=APP_TIMEOUT)
    assert not at.exception
    assert _ss(at, "stock_semen_view") == "import", (
        "a vista 'Importar' perdeu a sub-vista num rerun interno — "
        "mesma classe de bug do 'Adicionar lote'"
    )
