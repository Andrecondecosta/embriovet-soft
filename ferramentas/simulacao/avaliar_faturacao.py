"""Verifica a faturação no fim de uma época simulada.

    python avaliar_faturacao.py [--db embriovet_sim] [--dias 365]

Compara o que a app tem faturado (faturacao_linhas) com o que está
registado (estadias, lotes, saídas) e com a verdade do mundo (sémen de
clientes: desde quando estava guardado e quando levantaram palhetas).
Também resume os erros da API, os tempos e as notas das pessoas.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import psycopg2

ap = argparse.ArgumentParser()
ap.add_argument("--db", default="embriovet_sim")
ap.add_argument("--dias", type=int, default=365)
a = ap.parse_args()

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[1]
url = next(l.split("=", 1)[1].strip() for l in (REPO / ".env").read_text().splitlines() if l.startswith("TEST_DATABASE_URL="))
url = url.replace("/embriovet_test?", f"/{a.db}?")
assert "localhost" in url
SAIDA = AQUI / "saida" / a.db
INICIO = date(2027, 2, 1)
HOJE_REAL = date.today()
FIM_SIM = INICIO + timedelta(days=a.dias)  # "hoje" simulado no fim


def sim(d: date) -> date:
    """Data da base (real) → data simulada."""
    return FIM_SIM + (d - HOJE_REAL)


conn = psycopg2.connect(url)
cur = conn.cursor()


def q(sql, p=()):
    cur.execute(sql, p)
    return cur.fetchall()


def ler(nome):
    f = SAIDA / f"{nome}.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


achados: list[tuple[str, str]] = []  # (gravidade, texto)


def achado(grav, texto):
    achados.append((grav, texto))


linhas = q("""SELECT id, tipo, ref_id, dono_id, dono_nome, inicio, fim, quantidade, palhetas, fatura_numero,
                     fatura_data, anulada, motivo_anulacao, criado_por FROM faturacao_linhas""")
ativas = [l for l in linhas if not l[11]]
print(f"Linhas faturadas: {len(linhas)} ({len(linhas) - len(ativas)} anuladas); faturas: {len({l[9] for l in ativas})}")

# 1. Dias faturados duas vezes.
por_ref = defaultdict(list)
for l in ativas:
    por_ref[(l[1], l[2])].append((l[5], l[6], l[9]))
duplos = []
for k, ints in por_ref.items():
    ints.sort()
    for (a1, b1, n1), (a2, b2, n2) in zip(ints, ints[1:]):
        if a2 <= b1:
            duplos.append((k, n1, n2, (min(b1, b2) - a2).days + 1))
if duplos:
    achado("GRAVE", f"{len(duplos)} casos de dias faturados duas vezes (ex.: {duplos[:3]}).")
else:
    print("OK  Nenhum dia faturado duas vezes.")

# 2. Estadias: faturado fora do período registado (ex.: saída registada depois, com data anterior).
estadias = {e[0]: e for e in q("SELECT id, data_entrada, data_saida, dono_id, tipo_registo FROM estadias")}
fora = []
for l in ativas:
    if l[1] != "estadia":
        continue
    e = estadias.get(l[2])
    if not e:
        fora.append((l[2], "estadia apagada", l[9]))
        continue
    ini, sai = e[1], e[2] or HOJE_REAL
    if l[5] < ini or l[6] > sai:
        dias_a_mais = max(0, (ini - l[5]).days) + max(0, (l[6] - sai).days)
        fora.append((l[2], dias_a_mais, l[9]))
if fora:
    total = sum(x[1] for x in fora if isinstance(x[1], int))
    achado("GRAVE", f"{len(fora)} linhas de estadia faturadas para lá da saída registada ({total} dias cobrados a mais). "
           "Causa provável: faturou-se até ao fim do mês com a égua ainda internada e a saída foi registada depois com "
           f"uma data anterior; a app não avisa que esses dias já estavam faturados. Ex.: {fora[:3]}")
else:
    print("OK  Nenhuma estadia faturada fora das datas registadas.")

# 3. Estadias: dias por faturar até ao último corte (o que ficou esquecido).
corte_est = max((l[6] for l in ativas if l[1] == "estadia"), default=None)
if corte_est:
    esquecidos = []
    for eid, ini, sai, dono, tipo in estadias.values():
        if tipo == "externo":
            continue
        b = min(sai or HOJE_REAL, corte_est)
        if ini > b:
            continue
        cobertos = set()
        for a1, b1, _ in por_ref.get(("estadia", eid), []):
            cobertos.update(range(a1.toordinal(), b1.toordinal() + 1))
        falta = sum(1 for d in range(ini.toordinal(), b.toordinal() + 1) if d not in cobertos)
        if falta:
            esquecidos.append((eid, falta))
    if esquecidos:
        achado("MÉDIO", f"{len(esquecidos)} estadias com {sum(f for _, f in esquecidos)} dias ainda por faturar até ao último corte "
               f"({sim(corte_est)} simulado) — ficaram para trás. Ex.: {esquecidos[:5]}")
    else:
        print(f"OK  Todas as estadias faturadas até ao último corte ({sim(corte_est)}).")


# 4. Sémen: o faturado bate com as palhetas registadas hoje? (mudanças depois de faturar)
def nivel_inicio(lote, dia):
    atual, saidas = lote
    return atual + sum(qq for dd, qq in saidas if dd >= dia)


lotes = {}
for lid, atual, criado, obs, dono in q("SELECT id, existencia_atual, data_criacao::date, observacoes, dono_id FROM estoque_dono"):
    lotes[lid] = [max(atual or 0, 0), [], criado, obs or "", dono]
for lid, dia, qq in q("""SELECT estoque_id, dia, SUM(q) FROM (
        SELECT estoque_id, data_inseminacao AS dia, palhetas_gastas AS q FROM inseminacoes
        UNION ALL SELECT estoque_id, data_transferencia::date, quantidade FROM transferencias
        UNION ALL SELECT estoque_id, data_transferencia::date, quantidade FROM transferencias_externas) s
        WHERE estoque_id IS NOT NULL AND q > 0 GROUP BY 1, 2"""):
    if lid in lotes:
        lotes[lid][1].append((dia, int(qq)))
dif_app = []
for l in ativas:
    if l[1] != "armazenamento" or l[2] not in lotes:
        continue
    lo = lotes[l[2]]
    agora = sum(nivel_inicio((lo[0], lo[1]), date.fromordinal(d)) for d in range(l[5].toordinal(), l[6].toordinal() + 1))
    if agora != l[7]:
        dif_app.append((l[2], l[9], l[7], agora))
if dif_app:
    achado("MÉDIO", f"{len(dif_app)} linhas de sémen cujo total (palhetas × dias) já não bate com o stock de hoje: "
           f"registos feitos depois de faturar com datas para trás. Ex. (lote, fatura, faturado, agora): {dif_app[:3]}")
else:
    print("OK  Sémen faturado continua a bater com o stock registado.")

# 5. Sémen de clientes: faturado vs verdade do mundo.
verdade = [v for v in ler("verdade") if v.get("evento") == "lote_cliente"]
politica = next((v["politica"] for v in ler("verdade") if v.get("evento") == "politica_faturacao"), {})
cod_lote = {o.split(" ")[0]: lid for lid, (_, _, _, o, _) in lotes.items() if o.startswith("CL-")}
dif_mundo, sem_registo, inicio_errado = [], [], []
for v in verdade:
    lid = cod_lote.get(v["codigo"])
    if not lid:
        sem_registo.append(v["codigo"])
        continue
    desde = date.fromisoformat(v["guardado_desde"])
    lev = sorted((date.fromisoformat(d), qq) for d, qq, _ in v["levantamentos"])

    def verdade_dia(d):  # palhetas guardadas no início do dia d (simulado); o dia em que saem conta
        if d < desde:
            return 0
        return v["palhetas"] - sum(qq for dd, qq in lev if dd < d)

    for l in ativas:
        if l[1] == "armazenamento" and l[2] == lid:
            a1, b1 = sim(l[5]), sim(l[6])
            certo = sum(verdade_dia(date.fromordinal(d)) for d in range(a1.toordinal(), b1.toordinal() + 1))
            if certo != l[7]:
                dif_mundo.append((v["codigo"], l[9], l[7], certo))
    primeiras = [sim(l[5]) for l in ativas if l[1] == "armazenamento" and l[2] == lid]
    if primeiras and min(primeiras) != desde:
        inicio_errado.append((v["codigo"], str(min(primeiras)), str(desde)))
if sem_registo:
    achado("MÉDIO", f"{len(sem_registo)} lotes de clientes que nunca chegaram a ser registados na app: {sem_registo[:8]}")
if dif_mundo:
    mais = sum(f - c for _, _, f, c in dif_mundo if f > c)
    menos = sum(c - f for _, _, f, c in dif_mundo if f < c)
    achado("MÉDIO", f"{len(dif_mundo)} faturas de sémen diferentes da realidade: +{mais} palhetas × dia cobradas a mais, "
           f"-{menos} a menos. Causa: levantamentos registados dias depois (fins de semana) — a app grava a saída com a data "
           f"em que se escreve, sem deixar pôr a data verdadeira. Ex. (lote, fatura, faturado, real): {dif_mundo[:4]}")
else:
    print("OK  Sémen de clientes faturado igual à realidade.")
if inicio_errado:
    achado("BAIXO", f"{len(inicio_errado)} lotes de clientes cuja primeira fatura não começa no dia em que o sémen começou a "
           f"estar guardado (lote, faturado desde, real): {inicio_errado[:4]}")

# 5b. Palhetas de clientes usadas: cada uso faturado ao dono da égua e ao dono do sémen?
usos = q("""SELECT i.id, i.data_inseminacao, ds.id, COALESCE(e.dono_id, a.dono_id)
            FROM inseminacoes i JOIN estoque_dono l ON l.id = i.estoque_id JOIN dono ds ON ds.id = l.dono_id
            LEFT JOIN estadias e ON e.id = i.estadia_id LEFT JOIN animais a ON a.id = i.animal_id_egua
            WHERE NOT ds.da_clinica AND i.palhetas_gastas > 0""")
corte_p = max((l[6] for l in ativas if l[1].startswith("palhetas")), default=None)
if usos:
    faltam = [u for u in usos if corte_p and u[1] <= corte_p and not por_ref.get(("palhetas_gastas", u[0]))]
    print(f"INFO {len(usos)} inseminações com sémen de clientes; sem 'palhetas gastas' faturadas até ao corte: {len(faltam)}")
    if faltam:
        achado("MÉDIO", f"{len(faltam)} usos de sémen de clientes ainda por faturar ao dono do sémen até ao último corte.")

# 5c. Estadias que ficaram abertas com a égua já fora (saída recusada).
abertas_presas = [e for e in erros_saida] if (erros_saida := [x for x in ler("erros") if str(x.get("caminho", "")).endswith("/saida") and x.get("status") in (409, 422)]) else []
if abertas_presas:
    ids = {x["caminho"].split("/")[2] for x in abertas_presas}
    ainda = q("SELECT count(*) FROM estadias WHERE id = ANY(%s) AND data_saida IS NULL", ([int(i) for i in ids],))[0][0]
    if ainda:
        achado("GRAVE", f"{ainda} estadias continuam abertas depois de a receção tentar registar a saída ({len(abertas_presas)} tentativas recusadas).")
    else:
        print(f"OK  Saídas com aviso ({len(ids)} estadias) todas registadas depois de confirmar.")

# 6. Sémen da clínica no "Em atraso" / por faturar.
clinica = q("SELECT id FROM dono WHERE nome LIKE 'Clínica — %%' AND NOT da_clinica")
if clinica:
    n = q("SELECT count(*) FROM estoque_dono WHERE dono_id = ANY(%s)", ([c[0] for c in clinica],))[0][0]
    achado("MÉDIO", f"O sémen da própria clínica ({n} lotes) aparece em 'Por faturar' e 'Em atraso' para sempre: não há forma "
           "de marcar um proprietário como 'não se fatura'. O 'Em atraso' e o aviso do Dashboard ficam sempre vermelhos.")

# 7. Números de fatura repetidos entre proprietários.
nums = defaultdict(set)
for l in ativas:
    nums[l[9]].add(l[3])
rep = {n: len(d) for n, d in nums.items() if len(d) > 1}
if rep:
    achado("BAIXO", f"{len(rep)} números de fatura usados para mais de um proprietário (aviso ignorado): {list(rep)[:5]}")
anul = [l for l in linhas if l[11]]
if anul:
    print(f"INFO {len(anul)} linhas anuladas: {Counter(l[12] for l in anul).most_common(3)}")

# 8. Erros da API, exceções, tempos.
erros = ler("erros")
exc = [e for e in erros if "excecao" in e]
st = Counter((e.get("pessoa"), e.get("caminho", "").split("?")[0], e.get("status")) for e in erros if "status" in e)
print("\nErros da API (pessoa, caminho, estado):")
for k, n in st.most_common(15):
    print(f"  {n:5d}  {k}")
cinco = [e for e in erros if str(e.get("status", "")).startswith("5")]
if cinco:
    achado("GRAVE", f"{len(cinco)} erros 500 da API. Ex.: {[(e['pessoa'], e['caminho']) for e in cinco[:4]]}")
if exc:
    tipos = Counter(e["excecao"][:90] for e in exc)
    achado("GRAVE", f"{len(exc)} exceções nas pessoas (o programa rebentou ao trabalhar): {tipos.most_common(4)}")

acoes = ler("acoes")
tempos = defaultdict(list)
for x in acoes:
    c = x["caminho"]
    chave = "/" + "/".join(p if not p.isdigit() else "{id}" for p in c.strip("/").split("/"))
    tempos[chave].append(x["ms"])
print("\nPedidos mais lentos (p95 / máx, ms):")
lentos = sorted(((statistics.quantiles(v, n=20)[-1] if len(v) > 20 else max(v), max(v), k, len(v)) for k, v in tempos.items()), reverse=True)[:12]
for p95, mx, k, n in lentos:
    print(f"  {int(p95):7d} {mx:7d}  {k}  ({n}×)")
for p95, mx, k, n in lentos:
    if k.startswith("/faturacao") and mx > 3000:
        achado("MÉDIO", f"{k} é lento: até {mx / 1000:.1f} s (p95 {p95 / 1000:.1f} s, {n} pedidos) — cresce com o histórico.")

# 9. Notas das pessoas sobre a faturação.
notas = [n for n in ler("notas") if n.get("pessoa") == "teresa" or "fatur" in n.get("texto", "").lower()]
print(f"\nNotas sobre faturação: {len(notas)}")
for n in Counter(n["texto"][:160] for n in notas).most_common(12):
    print(f"  {n[1]:3d}× {n[0]}")

print("\n=== ACHADOS ===")
for g, t in sorted(achados, key=lambda x: ["GRAVE", "MÉDIO", "BAIXO"].index(x[0])):
    print(f"[{g}] {t}\n")
