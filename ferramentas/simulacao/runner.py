"""Corre a clínica simulada.

    python runner.py [--dias N] [--db embriovet_simX]

As pessoas vêm de personas/<papel>.py (classe com `papel`); o que faltar
usa a versão base de personas_base.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--dias", type=int, default=273)
ap.add_argument("--db", default="embriovet_sim")
ap.add_argument("--base", nargs="*", default=[], help="papéis a forçar na versão base")
ap.add_argument("--persona", help="usar SÓ este ficheiro de personas/ (o resto fica na versão base)")
a = ap.parse_args()
os.environ["SIM_DB"] = a.db

import simcore  # noqa: E402
from simcore import LOG, RELOGIO, SAIDA, avancar_dia, limpar_base, sql  # noqa: E402

import personas_base  # noqa: E402
from mundo import Mundo  # noqa: E402

PAPEIS = ["rececao", "stock", "vet1", "vet2", "direcao"]


def carregar():
    base = {c.papel: c for c in vars(personas_base).values() if isinstance(c, type) and hasattr(c, "papel") and c.__module__ == "personas_base"}
    escolhidas = dict(base)
    pasta = Path(__file__).parent / "personas"
    ficheiros = [Path(a.persona).resolve()] if a.persona else (sorted(pasta.glob("*.py")) if pasta.exists() else [])
    for f in ficheiros:
        spec = importlib.util.spec_from_file_location(f"personas.{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for c in vars(mod).values():
            if isinstance(c, type) and getattr(c, "papel", None) in PAPEIS and c.__module__ == mod.__name__ and c.papel not in a.base:
                escolhidas[c.papel] = c
    return [escolhidas[p] for p in PAPEIS]


def estado_do_dia():
    (abertas, atraso, atraso7, internadas) = sql(
        """SELECT
             (SELECT count(*) FROM trabalho_diario WHERE NOT concluida AND data_tarefa <= CURRENT_DATE),
             (SELECT count(*) FROM trabalho_diario WHERE NOT concluida AND data_tarefa < CURRENT_DATE),
             (SELECT count(*) FROM trabalho_diario WHERE NOT concluida AND data_tarefa < CURRENT_DATE - 7),
             (SELECT count(*) FROM estadias WHERE data_saida IS NULL)""",
        fetch=True,
    )[0]
    return {"tarefas_abertas": abertas, "em_atraso": atraso, "atraso_7d": atraso7, "internadas": internadas}


def main():
    # A base da simulação fica sempre com o esquema da app atual.
    from migration_runner import run_migrations
    from modules.db import get_connection

    with get_connection() as conn:
        run_migrations(conn, migrations_dir=str(simcore.REPO / "migrations"))
    for f in SAIDA.glob("*.jsonl"):
        f.unlink()
    simcore.LOG.__init__()
    limpar_base()
    mundo = Mundo()  # o mundo é sempre o mesmo (9 meses), mesmo em corridas curtas
    pessoas = [c(mundo) for c in carregar()]
    print("Pessoas:", [f"{p.papel}={p.nome}" for p in pessoas], flush=True)
    t0 = time.time()
    for d in range(a.dias):
        RELOGIO.d = d
        for p in pessoas:
            try:
                p.dia(RELOGIO)
            except Exception as e:  # um erro de uma pessoa não pára a clínica
                LOG("erros", pessoa=p.nome, excecao=repr(e), traceback=traceback.format_exc()[-1500:])
        LOG("notas", pessoa="motor", texto="fim do dia", **estado_do_dia())
        if d % 15 == 0:
            print(f"dia {d} ({RELOGIO.hoje}) {estado_do_dia()} {int(time.time() - t0)}s", flush=True)
        avancar_dia()
    # Fim: verdade do mundo e o estado da app, com datas convertidas para simuladas.
    RELOGIO.d = a.dias  # após o último avanço, "hoje" real = INICIO + dias
    with open(SAIDA / "verdade_final.json", "w") as f:
        json.dump(mundo.verdade_final(), f, default=str, ensure_ascii=False, indent=1)
    print("fim", int(time.time() - t0), "s", flush=True)


main()
