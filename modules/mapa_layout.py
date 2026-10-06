"""Posições dos contentores no Mapa — cálculo puro, sem BD nem Streamlit.

Tudo nas unidades "virtuais" do mapa (as mesmas dos `x`/`y` gravados em
`contentores`), iguais em todos os ecrãs — ver `VIRTUAL_W`/`VIRTUAL_H`/
`BOX` no JS de `map_page.py`, que têm de bater com estas constantes.
"""

from __future__ import annotations

import re

MAPA_VIRTUAL_W = 900
MAPA_VIRTUAL_H = 550
CONTENTOR_LADO_VIRTUAL = 70

# Grelha usada para organizar e para colocar contentores novos: caixa de
# 70 + 20 de espaço entre caixas, com margem de 10 à volta.
GRELHA_MARGEM = 10
GRELHA_PASSO = 90
GRELHA_X_MAX = MAPA_VIRTUAL_W - CONTENTOR_LADO_VIRTUAL
GRELHA_Y_MAX = MAPA_VIRTUAL_H - CONTENTOR_LADO_VIRTUAL


def _slots_grelha():
    """Posições da grelha, linha a linha, da esquerda para a direita."""
    y = GRELHA_MARGEM
    while y <= GRELHA_Y_MAX:
        x = GRELHA_MARGEM
        while x <= GRELHA_X_MAX:
            yield x, y
            x += GRELHA_PASSO
        y += GRELHA_PASSO


def chave_natural(codigo) -> tuple:
    """Ordena "2" antes de "10" e os códigos só numéricos antes dos de
    texto (ex.: 1, 2, …, 14, Equogestão, Luis Bastos, TEMPORÁRIO)."""
    texto = str(codigo or "").strip()
    if texto.isdigit():
        return (0, int(texto), "")
    partes = [int(p) if p.isdigit() else p.casefold() for p in re.split(r"(\d+)", texto) if p]
    return (1, 0, tuple(str(p).zfill(10) if isinstance(p, int) else p for p in partes))


def posicoes_em_grelha(contentores) -> dict:
    """Arruma os contentores numa grelha, por ordem natural do código.

    `contentores`: iterável de `(id, codigo)`. Devolve `{id: (x, y)}`.
    Se houver mais contentores do que lugares na grelha, os excedentes
    ficam no último lugar (sobrepostos) — com 10 × 6 = 60 lugares não é
    um caso realista.
    """
    ordenados = sorted(contentores, key=lambda c: chave_natural(c[1]))
    slots = list(_slots_grelha())
    return {
        cid: slots[min(i, len(slots) - 1)]
        for i, (cid, _codigo) in enumerate(ordenados)
    }


def _sobrepoe(x, y, ocupadas) -> bool:
    lado = CONTENTOR_LADO_VIRTUAL
    return any(abs(x - ox) < lado and abs(y - oy) < lado for ox, oy in ocupadas)


def proxima_posicao(ocupadas, ultima=None) -> tuple:
    """Posição para um contentor novo: logo à direita do último criado
    (`ultima`, `(x, y)` ou None), passando para a linha de baixo quando
    chega ao fim; salta lugares já ocupados por outro contentor.

    `ocupadas`: posições `(x, y)` dos contentores existentes.
    """
    ocupadas = list(ocupadas)
    if ultima is not None:
        x, y = int(ultima[0]) + GRELHA_PASSO, int(ultima[1])
        while y <= GRELHA_Y_MAX:
            if x > GRELHA_X_MAX:
                x, y = GRELHA_MARGEM, y + GRELHA_PASSO
                continue
            if not _sobrepoe(x, y, ocupadas):
                return x, y
            x += GRELHA_PASSO
    # Sem último, ou a seguir a ele já não há espaço: primeiro lugar
    # livre da grelha a partir do canto superior esquerdo.
    for x, y in _slots_grelha():
        if not _sobrepoe(x, y, ocupadas):
            return x, y
    return GRELHA_MARGEM, GRELHA_MARGEM
