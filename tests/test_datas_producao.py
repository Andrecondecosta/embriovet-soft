"""Leitura da data de produção (texto livre) para o filtro por período."""

from datetime import date

import pytest

from modules.datas_producao import dentro_do_periodo, periodo_producao

D = date


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("2021-01-12", (D(2021, 1, 12), D(2021, 1, 12))),
        ("12-01-2021", (D(2021, 1, 12), D(2021, 1, 12))),
        ("12/01/2021", (D(2021, 1, 12), D(2021, 1, 12))),
        ("2019.12.03", (D(2019, 12, 3), D(2019, 12, 3))),
        ("2021.01.31HC", (D(2021, 1, 31), D(2021, 1, 31))),
        ("07.03.2019B", (D(2019, 3, 7), D(2019, 3, 7))),
        ("2026-05", (D(2026, 5, 1), D(2026, 5, 31))),
        ("05/2026", (D(2026, 5, 1), D(2026, 5, 31))),
        ("Agosto 2017", (D(2017, 8, 1), D(2017, 8, 31))),
        ("fev 2024", (D(2024, 2, 1), D(2024, 2, 29))),
        ("2014", (D(2014, 1, 1), D(2014, 12, 31))),
        (" 2014 ", (D(2014, 1, 1), D(2014, 12, 31))),
        ("Várias", None),
        ("—", None),
        ("", None),
        (None, None),
        ("2021-13-45", None),
    ],
)
def test_periodo_producao(texto, esperado):
    assert periodo_producao(texto) == esperado


def test_dentro_do_periodo():
    jan_mar = (D(2021, 1, 1), D(2021, 3, 31))
    assert dentro_do_periodo("2021-01-12", *jan_mar)
    assert not dentro_do_periodo("2021-04-01", *jan_mar)
    assert dentro_do_periodo("2021", *jan_mar)  # o ano toca no período
    assert not dentro_do_periodo("Várias", *jan_mar)
    assert dentro_do_periodo("Várias", None, None)  # sem período: tudo
    assert dentro_do_periodo("2020-12-31", None, D(2021, 1, 1))
    assert not dentro_do_periodo("2020-12-31", D(2021, 1, 1), None)
