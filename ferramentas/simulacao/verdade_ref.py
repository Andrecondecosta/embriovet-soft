"""Referência: efeitos reais (da natureza simulada) por ciclo inseminado."""
import json
from datetime import datetime
import pandas as pd

v = [json.loads(l) for l in open("saida/embriovet_sim/verdade.jsonl")]
eg = {x["wid"]: x for x in v if x["evento"] == "egua"}
lotes = {x["codigo"]: x for x in v if x["evento"] == "lote"}
linhas = []
for c in (x for x in v if x["evento"] == "ciclo" and x["insem"]):
    ov = datetime.fromisoformat(c["ovulacao"])
    melhor = None
    for t, cod in c["insem"]:
        h = (ov - datetime.fromisoformat(t)).total_seconds() / 3600
        mot = lotes[cod]["motilidade_real"] if cod in lotes else None
        if melhor is None or abs(h - 12) < abs(melhor[0] - 12):
            melhor = (h, mot)
    h, mot = melhor
    cls = ">48h antes" if h > 48 else "24-48h antes" if h > 24 else "0-24h antes" if h >= 0 else "depois"
    linhas.append({"idade": eg[c["wid"]]["idade"], "horas_antes_ov": h, "classe": cls, "motilidade": mot,
                   "fh": c["hemorragico"], "gestante_d14": c["gestante"], "gestante_d45": c["gestante"] and not c["perda"]})
d = pd.DataFrame(linhas)
d = d[~d.fh]
print("ciclos (sem FH):", len(d), "| gestação D+14:", round(d.gestante_d14.mean() * 100), "% | D+45:", round(d.gestante_d45.mean() * 100), "%")
print("perda embrionária:", round((1 - d.gestante_d45.sum() / d.gestante_d14.sum()) * 100), "% das gestações")
print(d.groupby("classe").gestante_d14.agg(["count", "mean"]).round(2))
d["mot_cl"] = pd.cut(d.motilidade, [0, 30, 40, 50, 100])
print(d.groupby("mot_cl", observed=True).gestante_d14.agg(["count", "mean"]).round(2))
d["idade_cl"] = pd.cut(d.idade, [0, 12, 16, 30])
print(d.groupby("idade_cl", observed=True).gestante_d14.agg(["count", "mean"]).round(2))
