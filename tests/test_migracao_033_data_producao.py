"""Migração 033 (data de produção → AAAA-MM-DD), corrida numa transação
na base de TESTE e desfeita no fim."""

from pathlib import Path

from modules.db import get_connection

SQL = (Path(__file__).resolve().parents[1] / "migrations" / "033_data_producao_formato_unico.sql").read_text(encoding="utf-8")

CASOS = {
    "12-01-2021": "2021-01-12",
    "12/01/2021": "2021-01-12",
    "2019.12.03": "2019-12-03",
    "2021-1-5": "2021-01-05",
    " 2021-01-12 ": "2021-01-12",
    "2021-01-12": "2021-01-12",
    "2014": "2014",
    "2026-05": "2026-05",
    "Agosto 2017": "Agosto 2017",
    "Várias": "Várias",
    "2021.01.31HC": "2021.01.31HC",
    "07.03.2019B": "07.03.2019B",
    "31-02-2021": "31-02-2021",
}


def test_migracao_converte_so_dias_certos():
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                ids = {}
                for texto in CASOS:
                    cur.execute(
                        "INSERT INTO estoque_dono (garanhao, existencia_atual, quantidade_inicial, data_embriovet)"
                        " VALUES ('__mig033__', 1, 1, %s) RETURNING id",
                        (texto,),
                    )
                    ids[texto] = cur.fetchone()[0]
                cur.execute(SQL)
                for texto, esperado in CASOS.items():
                    cur.execute("SELECT data_embriovet FROM estoque_dono WHERE id = %s", (ids[texto],))
                    assert cur.fetchone()[0].strip() == esperado, texto
        finally:
            conn.rollback()
