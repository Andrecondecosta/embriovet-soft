"""Ler a "data de produção" de um lote, que é texto livre.

Nos dados reais aparece de muitas formas: "2021-01-12", "12-01-2021",
"2019.12.03", "2021.01.31HC", "07.03.2019B", "2026-05", "Agosto 2017", "2014",
"Várias"… Para filtrar por período, cada uma vira o intervalo de dias
que representa: um dia, um mês inteiro ou um ano inteiro. Texto que não
se percebe dá None (o lote fica de fora quando se filtra por produção).
"""

from __future__ import annotations

import calendar
import re
from datetime import date

_MESES = {
    "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6, "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8, "setembro": 9, "set": 9, "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12,
}

# Ano primeiro (2021-01-12, 2019.12.03, 2021.01.31HC) ou dia primeiro
# (12-01-2021, 07.03.2019B, 12/01/2021). Letras no fim são ignoradas.
_ANO_PRIMEIRO = re.compile(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})")
_DIA_PRIMEIRO = re.compile(r"^(\d{1,2})[-./](\d{1,2})[-./](\d{4})")
_ANO_MES = re.compile(r"^(\d{4})[-./](\d{1,2})$")  # 2026-05
_MES_NUM_ANO = re.compile(r"^(\d{1,2})[-./](\d{4})$")  # 05/2026
_MES_ANO = re.compile(r"^([a-zà-ú]+)\.?\s+(?:de\s+)?(\d{4})$")
_SO_ANO = re.compile(r"^(\d{4})$")


def _mes(ano: int, mes: int) -> tuple[date, date]:
    return date(ano, mes, 1), date(ano, mes, calendar.monthrange(ano, mes)[1])


def periodo_producao(texto) -> tuple[date, date] | None:
    """(primeiro dia, último dia) que o texto representa, ou None."""
    if texto is None:
        return None
    s = str(texto).strip().lower()
    try:
        if m := _ANO_PRIMEIRO.match(s):
            d = date(int(m[1]), int(m[2]), int(m[3]))
            return d, d
        if m := _DIA_PRIMEIRO.match(s):
            d = date(int(m[3]), int(m[2]), int(m[1]))
            return d, d
        if m := _ANO_MES.match(s):
            return _mes(int(m[1]), int(m[2]))
        if m := _MES_NUM_ANO.match(s):
            return _mes(int(m[2]), int(m[1]))
        if (m := _MES_ANO.match(s)) and m[1] in _MESES:
            return _mes(int(m[2]), _MESES[m[1]])
        if m := _SO_ANO.match(s):
            return date(int(m[1]), 1, 1), date(int(m[1]), 12, 31)
    except ValueError:  # ex.: "2021-13-45"
        return None
    return None


def dentro_do_periodo(texto, inicio: date | None, fim: date | None) -> bool:
    """O lote conta se a sua data (ou mês/ano) toca no período escolhido."""
    if inicio is None and fim is None:
        return True
    p = periodo_producao(texto)
    if p is None:
        return False
    return (inicio is None or p[1] >= inicio) and (fim is None or p[0] <= fim)
