"""Testes para o posicionamento automático dos contentores no Mapa:
botão "Organizar" (`posicoes_em_grelha`) e contentores novos ao lado do
último criado (`proxima_posicao`, usado por `adicionar_contentor`).
"""

from __future__ import annotations

import os
import time

import psycopg2

from modules.mapa_layout import (
    CONTENTOR_LADO_VIRTUAL,
    GRELHA_MARGEM,
    GRELHA_PASSO,
    GRELHA_X_MAX,
    GRELHA_Y_MAX,
    posicoes_em_grelha,
    proxima_posicao,
)


def _sem_sobreposicoes(posicoes):
    pts = list(posicoes)
    for i, (x1, y1) in enumerate(pts):
        for x2, y2 in pts[i + 1:]:
            assert abs(x1 - x2) >= CONTENTOR_LADO_VIRTUAL or abs(y1 - y2) >= CONTENTOR_LADO_VIRTUAL


def test_grelha_ordem_natural_e_sem_sobreposicoes():
    codigos = ["TEMPORÁRIO", "10", "2", "Luis Bastos", "1", "14", "Equogestão", "3"]
    contentores = list(enumerate(codigos, start=100))
    pos = posicoes_em_grelha(contentores)

    por_codigo = {codigos[cid - 100]: xy for cid, xy in pos.items()}
    ordem = sorted(por_codigo, key=lambda c: (por_codigo[c][1], por_codigo[c][0]))
    assert ordem == ["1", "2", "3", "10", "14", "Equogestão", "Luis Bastos", "TEMPORÁRIO"]
    assert por_codigo["1"] == (GRELHA_MARGEM, GRELHA_MARGEM)
    _sem_sobreposicoes(pos.values())
    for x, y in pos.values():
        assert 0 <= x <= GRELHA_X_MAX and 0 <= y <= GRELHA_Y_MAX


def test_grelha_muda_de_linha():
    pos = posicoes_em_grelha([(i, str(i)) for i in range(1, 19)])
    assert pos[1][1] == GRELHA_MARGEM
    assert pos[18][1] == GRELHA_MARGEM + GRELHA_PASSO


def test_proxima_ao_lado_do_ultimo():
    assert proxima_posicao([(10, 10), (100, 10)], ultima=(100, 10)) == (190, 10)


def test_proxima_salta_lugar_ocupado():
    ocupadas = [(10, 10), (100, 10), (190, 10)]
    assert proxima_posicao(ocupadas, ultima=(100, 10)) == (280, 10)


def test_proxima_muda_de_linha_no_fim():
    ultima = (GRELHA_X_MAX - 10, 10)
    assert proxima_posicao([ultima], ultima=ultima) == (GRELHA_MARGEM, 10 + GRELHA_PASSO)


def test_proxima_sem_contentores():
    assert proxima_posicao([], ultima=None) == (GRELHA_MARGEM, GRELHA_MARGEM)


def test_proxima_ultimo_fora_da_grelha_nao_sobrepoe():
    # Posições antigas, fora da grelha (ex.: arrastadas à mão).
    ocupadas = [(0, 0), (83, 2), (172, 7)]
    x, y = proxima_posicao(ocupadas, ultima=(172, 7))
    _sem_sobreposicoes(ocupadas + [(x, y)])


def test_adicionar_contentor_fica_ao_lado_do_ultimo():
    """Sem x/y, `adicionar_contentor` grava a posição de `proxima_posicao`
    calculada a partir dos contentores activos (último = maior id)."""
    from modules.repositories.container_repo import adicionar_contentor

    conn = psycopg2.connect(os.getenv("DATABASE_URL", "").strip())
    cur = conn.cursor()
    cur.execute("SELECT x, y FROM contentores WHERE ativo = TRUE ORDER BY id")
    ocupadas = [(int(x or 0), int(y or 0)) for x, y in cur.fetchall()]
    esperado = proxima_posicao(ocupadas, ocupadas[-1] if ocupadas else None)

    cid = adicionar_contentor({"codigo": f"_TEST_MAPA_{int(time.time() * 1_000_000)}", "descricao": ""})
    try:
        assert cid
        cur.execute("SELECT x, y FROM contentores WHERE id = %s", (cid,))
        assert cur.fetchone() == esperado
        # Só o novo vs os existentes (estes podem já sobrepor-se entre si).
        for ox, oy in ocupadas:
            assert abs(esperado[0] - ox) >= CONTENTOR_LADO_VIRTUAL or abs(esperado[1] - oy) >= CONTENTOR_LADO_VIRTUAL
    finally:
        cur.execute("DELETE FROM contentores WHERE id = %s", (cid,))
        conn.commit()
        cur.close()
        conn.close()
