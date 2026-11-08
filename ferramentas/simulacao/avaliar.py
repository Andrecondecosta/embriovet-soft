"""Compara o que a app ficou a saber com o que aconteceu de verdade (mundo).

    python avaliar.py [--db embriovet_sim] [--dias 273]

Escreve saida/<db>/avaliacao.json e imprime um resumo.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import unicodedata
from datetime import date, datetime, timedelta

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="embriovet_sim")
ap.add_argument("--dias", type=int, default=273)
a = ap.parse_args()
os.environ["SIM_DB"] = a.db

from simcore import HOJE_REAL, INICIO, SAIDA, sql  # noqa: E402

# Depois da corrida, "hoje" real corresponde ao dia simulado INICIO + dias.
DESVIO = (INICIO + timedelta(days=a.dias)) - HOJE_REAL


def sim(d):
    if d is None:
        return None
    if isinstance(d, datetime):
        return d + DESVIO
    return d + DESVIO


def ler(n):
    p = SAIDA / f"{n}.jsonl"
    return [json.loads(l) for l in open(p)] if p.exists() else []


verdade = ler("verdade")
eguas_v = {x["nome"]: x for x in verdade if x["evento"] == "egua"}
ciclos = [x for x in verdade if x["evento"] == "ciclo"]
insem_v = [x for x in verdade if x["evento"] == "inseminacao"]
wid_nome = {x["wid"]: x["nome"] for x in eguas_v.values()}
R = {}

# ── Inseminações: físicas vs registadas ──────────────────────────────────
app_ins = sql(
    """SELECT a.nome, i.operation_id::text, MIN(i.data_inseminacao), MIN(i.hora_inseminacao), MAX(i.resultado),
              SUM(i.palhetas_gastas), MAX(i.utilizador), MIN(i.id)
       FROM inseminacoes i JOIN animais a ON a.id = i.animal_id_egua GROUP BY 1, 2""",
    fetch=True,
)
app_por_egua = collections.defaultdict(list)
for nome, op, d, h, res, palh, u, iid in app_ins:
    app_por_egua[nome].append({"op": op, "data": sim(d), "hora": h, "resultado": res, "palhetas": palh, "user": u, "usado": False})
fisicas = collections.defaultdict(list)
for x in insem_v:
    fisicas[wid_nome[x["wid"]]].append(datetime.fromisoformat(x["quando"]))
emparelhadas, sem_registo, erro_hora = 0, [], []
for nome, lst in fisicas.items():
    for q in sorted(lst):
        cand = [r for r in app_por_egua.get(nome, []) if not r["usado"] and abs((r["data"] - q.date()).days) <= 1]
        if not cand:
            sem_registo.append((nome, q.isoformat()))
            continue
        r = min(cand, key=lambda r: abs((r["data"] - q.date()).days))
        r["usado"] = True
        emparelhadas += 1
        if r["hora"]:
            reg = datetime.combine(r["data"], r["hora"])
            erro_hora.append(abs((reg - q).total_seconds()) / 60)
fantasma = [(n, str(r["data"])) for n, l in app_por_egua.items() for r in l if not r["usado"]]
R["inseminacoes"] = {
    "fisicas": sum(len(l) for l in fisicas.values()),
    "registadas_app": len(app_ins),
    "emparelhadas": emparelhadas,
    "feitas_sem_registo_na_app": len(sem_registo),
    "na_app_sem_inseminacao_fisica": len(fantasma),
    "exemplos_sem_registo": sem_registo[:5],
    "exemplos_fantasma": fantasma[:5],
    "erro_hora_min_mediana": sorted(erro_hora)[len(erro_hora) // 2] if erro_hora else None,
    "erro_hora_mais_de_60min": sum(1 for e in erro_hora if e > 60),
    "sem_hora": sum(1 for l in app_por_egua.values() for r in l if r["hora"] is None),
}

# ── Resultado da gestação: verdade vs app ────────────────────────────────
# Para cada ciclo inseminado: a app tem o resultado certo na inseminação desse ciclo?
mat = collections.Counter()
exemplos = collections.defaultdict(list)
FIM = INICIO + timedelta(days=a.dias)
em_curso = 0
for c in ciclos:
    if not c["insem"]:
        continue
    if datetime.fromisoformat(c["ovulacao"]).date() > FIM - timedelta(days=18):
        em_curso += 1  # ainda não chegou ao D+14: não conta
        continue
    nome = c["nome"]
    datas = {datetime.fromisoformat(t).date() for t, _ in c["insem"]}
    regs = [r for r in app_por_egua.get(nome, []) if any(abs((r["data"] - d).days) <= 1 for d in datas)]
    verdade_final = "gestante" if c["gestante"] and not c["perda"] else "perda" if c["gestante"] else "vazia"
    if c.get("hemorragico"):
        verdade_final = "FH"
    if not regs:
        app = "sem_registo"
    else:
        res = {r["resultado"] for r in regs}
        app = "gestacao_confirmada" if "gestacao_confirmada" in res else "falhou" if "falhou" in res else "pendente"
    mat[(verdade_final, app)] += 1
    if len(exemplos[(verdade_final, app)]) < 3:
        exemplos[(verdade_final, app)].append((nome, c["ovulacao"][:10]))
R["gestacao_verdade_vs_app"] = {f"{v} -> {p}": n for (v, p), n in sorted(mat.items())}
R["ciclos_ainda_antes_do_D14_no_fim"] = em_curso
R["gestacao_exemplos"] = {f"{v} -> {p}": e for (v, p), e in exemplos.items()}
R["ciclos_inseminados"] = sum(1 for c in ciclos if c["insem"])
R["gestacoes_reais"] = sum(1 for c in ciclos if c["insem"] and c["gestante"])
R["perdas_embrionarias_reais"] = sum(1 for c in ciclos if c["insem"] and c["gestante"] and c["perda"])

# ── Diagnósticos por etapa ───────────────────────────────────────────────
dg = sql("SELECT etapa, resultado, count(*) FROM diagnosticos_gestacao GROUP BY 1, 2 ORDER BY 1, 2", fetch=True)
R["diagnosticos_por_etapa"] = {f"{e} {r}": n for e, r, n in dg}
ops_sem_dg = sql(
    """SELECT count(DISTINCT i.operation_id) FROM inseminacoes i
       WHERE i.operation_id IS NOT NULL
         AND i.data_inseminacao < CURRENT_DATE - 16
         AND NOT EXISTS (SELECT 1 FROM diagnosticos_gestacao d WHERE d.operation_id = i.operation_id)""",
    fetch=True,
)[0][0]
R["inseminacoes_com_mais_de_16_dias_sem_nenhum_DG"] = ops_sem_dg
R["inseminacoes_pendentes_no_fim"] = sql(
    "SELECT count(DISTINCT operation_id) FROM inseminacoes WHERE resultado = 'pendente' AND data_inseminacao < CURRENT_DATE - 20",
    fetch=True,
)[0][0]

# ── Tarefas ──────────────────────────────────────────────────────────────
t = sql(
    """SELECT tipo,
              count(*) FILTER (WHERE concluida AND NOT cancelada),
              count(*) FILTER (WHERE cancelada),
              count(*) FILTER (WHERE NOT concluida AND data_tarefa < CURRENT_DATE),
              count(*) FILTER (WHERE NOT concluida AND data_tarefa >= CURRENT_DATE)
       FROM trabalho_diario GROUP BY 1 ORDER BY 1""",
    fetch=True,
)
R["tarefas"] = {tipo: {"feitas": f, "canceladas": c, "em_atraso_no_fim": at, "futuras": fu} for tipo, f, c, at, fu in t}
R["tarefas_canceladas_por"] = dict(sql("SELECT coalesce(concluida_por,'?'), count(*) FROM trabalho_diario WHERE cancelada GROUP BY 1", fetch=True))
R["tarefas_concluidas_por"] = dict(sql("SELECT coalesce(concluida_por,'?'), count(*) FROM trabalho_diario WHERE concluida AND NOT cancelada GROUP BY 1", fetch=True))

# ── Estadias, donos, lotes ───────────────────────────────────────────────
R["estadias"] = {
    "total": sql("SELECT count(*) FROM estadias", fetch=True)[0][0],
    "abertas_no_fim": sql("SELECT count(*) FROM estadias WHERE data_saida IS NULL", fetch=True)[0][0],
    "saidas_por_estado": dict(sql("SELECT coalesce(estado,'?'), count(*) FROM estadias WHERE data_saida IS NOT NULL GROUP BY 1", fetch=True)),
    "eguas_reais": len(eguas_v),
    "animais_na_app": sql("SELECT count(*) FROM animais WHERE tipo <> 'garanhao'", fetch=True)[0][0],
}
saidas_gestante = sql(
    """SELECT a.nome FROM estadias e JOIN animais a ON a.id = e.animal_id WHERE e.estado = 'gestante'""", fetch=True)
ult = {}
for c in ciclos:
    if c["insem"]:
        ult[c["nome"]] = c
R["saidas_gestante_mas_vazia_na_verdade"] = [n for (n,) in saidas_gestante if n in ult and not (ult[n]["gestante"] and not ult[n]["perda"])][:20]
R["saidas_gestante_total"] = len(saidas_gestante)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    for a_, b_ in (("coud.", "coudelaria"), ("qta.", "quinta"), ("hdade.", "herdade"), ("soc.", "sociedade")):
        s = s.replace(a_, b_)
    return " ".join(s.replace(".", " ").split())


donos = sql("SELECT nome, ativo FROM dono", fetch=True)
grupos = collections.defaultdict(list)
for n, at in donos:
    grupos[norm(n)].append(n)
R["donos"] = {"total": len(donos), "inativos": sum(1 for _, at in donos if not at),
              "duplicados": {k: v for k, v in grupos.items() if len(v) > 1}}
R["lotes"] = {
    "total": sql("SELECT count(*) FROM estoque_dono", fetch=True)[0][0],
    "externos_motilidade_0": sql("SELECT count(*) FROM estoque_dono WHERE coalesce(motilidade,0) = 0 AND coalesce(origem_externa,'') <> ''", fetch=True)[0][0],
    "sem_codigo_LT": sql("SELECT count(*) FROM estoque_dono WHERE coalesce(observacoes,'') NOT LIKE '%%LT-%%'", fetch=True)[0][0],
    "esgotados": sql("SELECT count(*) FROM estoque_dono WHERE existencia_atual = 0", fetch=True)[0][0],
    "lotes_reais_chegados": sum(1 for x in verdade if x["evento"] == "lote" and date.fromisoformat(x["chega"]) < INICIO + timedelta(days=a.dias)),
}
eguas_sem_insem = sql(
    """SELECT count(*) FROM estadias e JOIN animais a ON a.id = e.animal_id
       WHERE a.tipo = 'egua' AND e.motivo = 'inseminacao'
         AND NOT EXISTS (SELECT 1 FROM inseminacoes i WHERE i.estadia_id = e.id)""",
    fetch=True,
)[0][0]
R["estadias_de_inseminacao_sem_nenhuma_inseminacao"] = eguas_sem_insem

# ── Erros e notas ────────────────────────────────────────────────────────
erros = ler("erros")
R["erros_api"] = collections.Counter(
    f"{e['pessoa']} {e.get('metodo','')} {e.get('caminho','').split('?')[0]} {e.get('status','EXC')} "
    f"{(e.get('corpo') or {}).get('detail', {}).get('code', '') if isinstance(e.get('corpo'), dict) and isinstance((e.get('corpo') or {}).get('detail'), dict) else e.get('excecao','')[:60]}"
    for e in erros).most_common(25)
notas = ler("notas")
R["notas_por_pessoa"] = dict(collections.Counter(n["pessoa"] for n in notas if n["pessoa"] != "motor"))
acoes = ler("acoes")
R["pedidos_por_pessoa"] = dict(collections.Counter(x["pessoa"] for x in acoes))
lento = sorted(acoes, key=lambda x: -x["ms"])[:5]
R["pedidos_mais_lentos_ms"] = [(x["caminho"], x["ms"]) for x in lento]
motor = [n for n in notas if n["pessoa"] == "motor"]
R["atraso_max_tarefas"] = max((n.get("em_atraso", 0) for n in motor), default=0)
R["internadas_max"] = max((n.get("internadas", 0) for n in motor), default=0)

json.dump(R, open(SAIDA / "avaliacao.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(R, ensure_ascii=False, indent=1, default=str)[:12000])
