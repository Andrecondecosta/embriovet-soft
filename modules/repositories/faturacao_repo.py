"""Faturação: o que há a faturar de estadias (dias) e de armazenamento de
sémen (palhetas × dias), descontando o que já foi faturado.

A app não emite faturas nem tem preços: conta as quantidades e guarda o
número/data da fatura feita no programa de faturação (`faturacao_linhas`).

Regras de contagem:
- Estadia: contam o dia de entrada e o de saída (entra a 1, sai a 3 = 3
  dias). "Externo" não conta (o animal não está no centro). Estadia em
  aberto conta até hoje.
- Armazenamento: cada dia conta as palhetas que o lote tinha no início
  desse dia, por isso o dia em que saem (inseminação, transferência,
  venda, devolução) ainda conta. Os níveis reconstroem-se para trás a
  partir da existência atual, com as saídas datadas — bate sempre certo
  com o stock de hoje. Uma transferência para outro dono cria um lote
  novo desse dono: cada dono paga só os seus dias.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from modules.db import get_connection

TIPOS = ("estadia", "armazenamento")


def _menos(intervalo: tuple[date, date], cobertos: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Partes de `intervalo` que nenhum dos `cobertos` cobre."""
    livres = [intervalo]
    for ci, cf in cobertos:
        novos = []
        for a, b in livres:
            if cf < a or ci > b:
                novos.append((a, b))
                continue
            if ci > a:
                novos.append((a, ci - timedelta(days=1)))
            if cf < b:
                novos.append((cf + timedelta(days=1), b))
        livres = novos
    return livres


def _faturados(cur, tipo: str, refs: list[int]) -> dict[int, list[tuple[date, date]]]:
    if not refs:
        return {}
    cur.execute(
        "SELECT ref_id, inicio, fim FROM faturacao_linhas WHERE tipo = %s AND ref_id = ANY(%s) AND NOT anulada",
        (tipo, refs),
    )
    out: dict[int, list] = defaultdict(list)
    for ref, a, b in cur.fetchall():
        out[ref].append((a, b))
    return out


# ── Estadias ──────────────────────────────────────────────────────────────

def _estadias(cur, inicio: date, fim: date, dono_id: int | None, ids: list[int] | None = None) -> list[dict]:
    hoje = date.today()
    cur.execute(
        """
        SELECT e.id, e.dono_id, d.nome, a.nome, a.tipo, e.tipo_registo, al.nome,
               e.data_entrada, e.data_saida
        FROM estadias e
        JOIN animais a ON a.id = e.animal_id
        LEFT JOIN dono d ON d.id = e.dono_id
        LEFT JOIN alojamentos al ON al.id = e.alojamento_id
        WHERE e.tipo_registo <> 'externo'
          AND e.data_entrada <= %(fim)s
          AND (e.data_saida IS NULL OR e.data_saida >= %(inicio)s)
          AND (%(dono)s::int IS NULL OR e.dono_id = %(dono)s)
          AND (%(ids)s::int[] IS NULL OR e.id = ANY(%(ids)s))
        ORDER BY d.nome, a.nome, e.data_entrada
        """,
        {"inicio": inicio, "fim": fim, "dono": dono_id, "ids": ids},
    )
    itens = []
    for eid, dono, dono_nome, animal, tipo_animal, tipo_registo, aloj, entrada, saida in cur.fetchall():
        a, b = max(entrada, inicio), min(saida or hoje, fim)
        if a > b:
            continue
        itens.append({
            "tipo": "estadia", "ref_id": eid, "dono_id": dono, "dono_nome": dono_nome,
            "descricao": " · ".join(x for x in (animal, aloj) if x),
            "animal": animal, "tipo_animal": tipo_animal, "tipo_registo": tipo_registo, "alojamento": aloj,
            "entrada": entrada, "saida": saida, "limite": (a, b),
        })
    return itens


def _qtd_estadia(_item: dict, a: date, b: date) -> int:
    return (b - a).days + 1


# ── Armazenamento de sémen ───────────────────────────────────────────────

def _lotes(cur, inicio: date, fim: date, dono_id: int | None, ids: list[int] | None = None) -> list[dict]:
    hoje = date.today()
    cur.execute(
        """
        SELECT l.id, l.dono_id, d.nome, COALESCE(a.nome, l.garanhao), l.data_criacao::date,
               l.existencia_atual, l.origem_externa, l.data_embriovet, c.codigo, l.canister, l.andar
        FROM estoque_dono l
        LEFT JOIN dono d ON d.id = l.dono_id
        LEFT JOIN animais a ON a.id = l.animal_id
        LEFT JOIN contentores c ON c.id = l.contentor_id
        WHERE l.data_criacao::date <= %(fim)s
          AND (%(dono)s::int IS NULL OR l.dono_id = %(dono)s)
          AND (%(ids)s::int[] IS NULL OR l.id = ANY(%(ids)s))
        ORDER BY d.nome, 4, l.id
        """,
        {"fim": fim, "dono": dono_id, "ids": ids},
    )
    lotes = cur.fetchall()
    if not lotes:
        return []
    refs = [r[0] for r in lotes]
    # Saídas datadas de cada lote a partir do início do período (as de
    # antes não mudam o nível dentro dele).
    cur.execute(
        """
        SELECT estoque_id, dia, SUM(q)::int FROM (
            SELECT estoque_id, data_inseminacao AS dia, palhetas_gastas AS q FROM inseminacoes
            UNION ALL
            SELECT estoque_id, data_transferencia::date, quantidade FROM transferencias
            UNION ALL
            SELECT estoque_id, data_transferencia::date, quantidade FROM transferencias_externas
        ) s
        WHERE estoque_id = ANY(%s) AND dia >= %s AND q > 0
        GROUP BY 1, 2
        """,
        (refs, inicio),
    )
    saidas: dict[int, list[tuple[date, int]]] = defaultdict(list)
    for ref, dia, q in cur.fetchall():
        saidas[ref].append((dia, q))
    itens = []
    for lid, dono, dono_nome, garanhao, criado, atual, origem, data_prod, cont, can, andar in lotes:
        a, b = max(criado, inicio), min(hoje, fim)
        if a > b:
            continue
        item = {
            "tipo": "armazenamento", "ref_id": lid, "dono_id": dono, "dono_nome": dono_nome,
            "descricao": f"{garanhao} · lote {lid}",
            "garanhao": garanhao, "origem": origem, "data_producao": data_prod,
            "local": f"{cont} · C{can} · A{andar}" if cont else None,
            "atual": max(atual or 0, 0), "saidas": saidas.get(lid, []), "limite": (a, b),
        }
        if _qtd_lote(item, a, b):
            itens.append(item)
    return itens


def _nivel(item: dict, dia: date) -> int:
    """Palhetas no início de `dia`."""
    return item["atual"] + sum(q for d, q in item["saidas"] if d >= dia)


def _qtd_lote(item: dict, a: date, b: date) -> int:
    dias = (b - a).days + 1
    return item["atual"] * dias + sum(q * max(0, (min(d, b) - a).days + 1) for d, q in item["saidas"])


_QTD = {"estadia": _qtd_estadia, "armazenamento": _qtd_lote}


def _tracos(item: dict, a: date, b: date):
    """Parte [a, b] onde o número de palhetas do lote é sempre o mesmo
    (muda no dia a seguir a cada saída): (início, fim, palhetas)."""
    cortes = sorted({d for d, _ in item["saidas"] if a <= d < b})
    inicio = a
    for d in cortes + [b]:
        yield inicio, d, _nivel(item, inicio)
        inicio = d + timedelta(days=1)


def _linhas(itens: list[dict], faturados: dict[int, list], tipo: str) -> list[dict]:
    """Linhas por faturar. No sémen, uma por cada troço com o mesmo número
    de palhetas ("10 palhetas, 4 dias" + "6 palhetas, 5 dias")."""
    out = []
    for it in itens:
        base = {k: v for k, v in it.items() if k not in ("limite", "saidas", "atual")}
        for a, b in _menos(it["limite"], faturados.get(it["ref_id"], [])):
            tracos = _tracos(it, a, b) if tipo == "armazenamento" else [(a, b, None)]
            for ta, tb, palhetas in tracos:
                dias = (tb - ta).days + 1
                if palhetas == 0:
                    continue
                out.append({**base, "inicio": ta, "fim": tb, "dias": dias, "palhetas": palhetas,
                            "quantidade": dias * palhetas if palhetas else dias})
    return out


def por_faturar(inicio: date, fim: date, dono_id: int | None = None, tipo: str | None = None) -> list[dict]:
    """Linhas ainda por faturar no período (uma estadia ou lote pode dar
    várias, se parte do período já foi faturada)."""
    out: list[dict] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            if tipo in (None, "estadia"):
                itens = _estadias(cur, inicio, fim, dono_id)
                out += _linhas(itens, _faturados(cur, "estadia", [i["ref_id"] for i in itens]), "estadia")
            if tipo in (None, "armazenamento"):
                itens = _lotes(cur, inicio, fim, dono_id)
                out += _linhas(itens, _faturados(cur, "armazenamento", [i["ref_id"] for i in itens]), "armazenamento")
    return out


class JaFaturado(Exception):
    pass


def _palhetas_fixas(item: dict, a: date, b: date) -> int | None:
    """Palhetas do troço, se forem as mesmas em todos os dias (o ecrã manda
    sempre troços assim); senão None (fica só o total palhetas × dia)."""
    tracos = list(_tracos(item, a, b))
    return tracos[0][2] if len(tracos) == 1 else None


class OutroDono(Exception):
    pass


def faturar(faturas: list[dict], utilizador: str) -> int:
    """Marca como faturadas as linhas de cada fatura ({dono_id, fatura_numero,
    fatura_data, acerto_inicial, observacoes, linhas: [{tipo, ref_id, inicio,
    fim}]}). Uma fatura é de um só proprietário. As quantidades recalculam-se
    aqui (não se confia no ecrã) e tudo fica numa só transação: se alguma
    parte já estiver faturada (por exemplo, outra pessoa ao mesmo tempo),
    nada é gravado."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Uma marcação de cada vez (evita faturar o mesmo dia duas vezes).
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('faturacao_linhas'))")
            n = 0
            for f in faturas:
                for l in f["linhas"]:
                    a, b = l["inicio"], l["fim"]
                    busca = _estadias if l["tipo"] == "estadia" else _lotes
                    itens = busca(cur, a, b, None, [l["ref_id"]])
                    if not itens or itens[0]["limite"] != (a, b):
                        # Fora das datas da estadia/lote (ou ainda no futuro).
                        raise JaFaturado()
                    it = itens[0]
                    if it["dono_id"] != f["dono_id"]:
                        raise OutroDono()
                    if _menos((a, b), _faturados(cur, l["tipo"], [l["ref_id"]]).get(l["ref_id"], [])) != [(a, b)]:
                        raise JaFaturado()
                    cur.execute(
                        """
                        INSERT INTO faturacao_linhas
                            (tipo, ref_id, dono_id, dono_nome, descricao, inicio, fim, quantidade, palhetas,
                             fatura_numero, fatura_data, acerto_inicial, observacoes, criado_por)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (l["tipo"], l["ref_id"], it["dono_id"], it["dono_nome"], it["descricao"], a, b,
                         _QTD[l["tipo"]](it, a, b), _palhetas_fixas(it, a, b) if l["tipo"] == "armazenamento" else None,
                         f["fatura_numero"] or "", f["fatura_data"], bool(f.get("acerto_inicial")),
                         f.get("observacoes"), (utilizador or "—")[:50]),
                    )
                    n += 1
        conn.commit()
    return n


def movimentos(lotes: list[dict]) -> list[dict]:
    """Saídas de palhetas de cada lote no período ({ref_id, inicio, fim}),
    com o porquê — para o resumo explicar cada mudança de palhetas."""
    out: list[dict] = []
    if not lotes:
        return out
    with get_connection() as conn:
        with conn.cursor() as cur:
            for l in lotes:
                cur.execute(
                    """
                    SELECT dia, q, tipo, detalhe FROM (
                        SELECT data_inseminacao AS dia, palhetas_gastas AS q, 'inseminacao' AS tipo,
                               COALESCE(a.nome, i.egua) AS detalhe
                        FROM inseminacoes i LEFT JOIN animais a ON a.id = i.animal_id_egua
                        WHERE i.estoque_id = %(id)s
                        UNION ALL
                        SELECT t.data_transferencia::date, t.quantidade, 'transferencia', d.nome
                        FROM transferencias t LEFT JOIN dono d ON d.id = t.proprietario_destino_id
                        WHERE t.estoque_id = %(id)s
                        UNION ALL
                        SELECT x.data_transferencia::date, x.quantidade, 'externa',
                               concat_ws(' — ', x.tipo, x.destinatario_externo)
                        FROM transferencias_externas x WHERE x.estoque_id = %(id)s
                    ) m
                    WHERE q > 0 AND dia BETWEEN %(a)s AND %(b)s
                    ORDER BY dia
                    """,
                    {"id": l["ref_id"], "a": l["inicio"], "b": l["fim"]},
                )
                out += [{"ref_id": l["ref_id"], "data": d, "quantidade": q, "tipo": t, "detalhe": x}
                        for d, q, t, x in cur.fetchall()]
            return out


def donos(ids: list[int]) -> list[dict]:
    """Dados do proprietário para o cabeçalho do resumo (PDF)."""
    if not ids:
        return []
    cols = ["id", "nome", "nome_completo", "nif", "morada", "codigo_postal", "cidade", "email", "telemovel"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(cols)} FROM dono WHERE id = ANY(%s)", (ids,))
            return [dict(zip(cols, r)) for r in cur.fetchall()]


_COLS = ["id", "tipo", "ref_id", "dono_id", "dono_nome", "descricao", "inicio", "fim", "quantidade", "palhetas",
         "fatura_numero", "fatura_data", "acerto_inicial", "observacoes", "criado_por", "created_at",
         "anulada", "anulada_por", "anulada_em", "motivo_anulacao"]


def faturado(inicio: date, fim: date, dono_id: int | None = None, fatura: str | None = None,
             incluir_anuladas: bool = False) -> list[dict]:
    """Linhas faturadas cujo período toca em [inicio, fim]."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {", ".join(_COLS)} FROM faturacao_linhas
                WHERE inicio <= %(fim)s AND fim >= %(inicio)s
                  AND (%(dono)s::int IS NULL OR dono_id = %(dono)s)
                  AND (%(fatura)s::text IS NULL OR fatura_numero ILIKE '%%' || %(fatura)s || '%%')
                  AND (%(anuladas)s OR NOT anulada)
                ORDER BY fatura_data DESC, fatura_numero, dono_nome, inicio
                """,
                {"inicio": inicio, "fim": fim, "dono": dono_id, "fatura": fatura or None, "anuladas": incluir_anuladas},
            )
            return [dict(zip(_COLS, r)) for r in cur.fetchall()]


def anular(linha_id: int, motivo: str, utilizador: str) -> bool:
    """Anula uma linha faturada (fica guardada, marcada como anulada): esses
    dias voltam a aparecer por faturar."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE faturacao_linhas SET anulada = TRUE, anulada_por = %s, anulada_em = NOW(), motivo_anulacao = %s
                   WHERE id = %s AND NOT anulada""",
                ((utilizador or "—")[:50], motivo, linha_id),
            )
            ok = cur.rowcount == 1
        conn.commit()
    return ok


# ── Quadro por ano (proprietário × ano) ──────────────────────────────────────

INICIO_HISTORICO = date(1990, 1, 1)


def _por_ano(a: date, b: date):
    """Parte [a, b] pelos anos civis."""
    while a <= b:
        fim_ano = date(a.year, 12, 31)
        yield a.year, a, min(b, fim_ano)
        a = fim_ano + timedelta(days=1)


def resumo_anual(desde: int) -> dict:
    """Para cada proprietário e ano (os anteriores a `desde` juntos em
    "antes"): se houve estadias/sémen, o que falta faturar (dias e palhetas
    × dia). Só o que está na app (estadias e lotes)."""
    hoje = date.today()
    chaves = ["antes"] + [str(y) for y in range(desde, hoje.year + 1)]
    chave = lambda ano: "antes" if ano < desde else str(ano)  # noqa: E731
    donos: dict = {}

    def celula(dono_id, dono_nome, k):
        d = donos.setdefault(dono_id, {"dono_id": dono_id, "dono_nome": dono_nome, "celulas": {}})
        return d["celulas"].setdefault(k, {"atividade": False, "dias": 0, "dias_semen": 0, "lotes": 0, "pd": 0})

    # Sémen: dias do calendário com algum lote por faturar (vários lotes no
    # mesmo dia contam um dia), e quantos lotes.
    dias_semen: dict = defaultdict(set)
    lotes: dict = defaultdict(set)

    with get_connection() as conn:
        with conn.cursor() as cur:
            for tipo, busca in (("estadia", _estadias), ("armazenamento", _lotes)):
                itens = busca(cur, INICIO_HISTORICO, hoje, None)
                faturados = _faturados(cur, tipo, [i["ref_id"] for i in itens])
                for it in itens:
                    for ano, a, b in _por_ano(*it["limite"]):
                        if _QTD[tipo](it, a, b):
                            celula(it["dono_id"], it["dono_nome"], chave(ano))["atividade"] = True
                    for livre in _menos(it["limite"], faturados.get(it["ref_id"], [])):
                        for ano, a, b in _por_ano(*livre):
                            qtd = _QTD[tipo](it, a, b)
                            if not qtd:
                                continue
                            c = celula(it["dono_id"], it["dono_nome"], chave(ano))
                            if tipo == "estadia":
                                c["dias"] += qtd
                                continue
                            c["pd"] += qtd
                            k = (it["dono_id"], chave(ano))
                            lotes[k].add(it["ref_id"])
                            dias_semen[k].update(
                                ta + timedelta(days=i)
                                for ta, tb, n in _tracos(it, a, b) if n
                                for i in range((tb - ta).days + 1)
                            )
            # Até onde já se faturou cada proprietário (a última data faturada).
            cur.execute("SELECT dono_id, MAX(fim) FROM faturacao_linhas WHERE NOT anulada GROUP BY dono_id")
            ate = dict(cur.fetchall())
    for (dono_id, k), dias in dias_semen.items():
        donos[dono_id]["celulas"][k].update(dias_semen=len(dias), lotes=len(lotes[(dono_id, k)]))
    for d in donos.values():
        d["faturado_ate"] = ate.get(d["dono_id"])
    linhas = sorted(donos.values(), key=lambda d: (d["dono_nome"] is None, (d["dono_nome"] or "").lower()))
    return {"anos": chaves, "linhas": linhas}



# ── Em atraso (há quanto tempo cada proprietário tem dias por faturar) ──────

def em_atraso() -> list[dict]:
    """Por proprietário, estadias e sémen à parte: o dia mais antigo ainda
    por faturar ("desde") e quantos dias faltam (no sémen, dias do
    calendário com algum lote por faturar, e quantos lotes)."""
    hoje = date.today()
    donos: dict = {}
    dias_semen: dict = defaultdict(set)
    for l in por_faturar(INICIO_HISTORICO, hoje):
        d = donos.setdefault(l["dono_id"], {"dono_id": l["dono_id"], "dono_nome": l["dono_nome"],
                                            "estadia": None, "armazenamento": None})
        c = d[l["tipo"]] = d[l["tipo"]] or {"desde": l["inicio"], "dias": 0, "itens": set()}
        c["desde"] = min(c["desde"], l["inicio"])
        c["itens"].add(l["ref_id"])
        if l["tipo"] == "estadia":
            c["dias"] += l["dias"]
        else:
            dias_semen[l["dono_id"]].update(range(l["inicio"].toordinal(), l["fim"].toordinal() + 1))
    for dono_id, dias in dias_semen.items():
        donos[dono_id]["armazenamento"]["dias"] = len(dias)
    for d in donos.values():
        for k in TIPOS:
            if d[k]:
                d[k]["itens"] = len(d[k]["itens"])
    return sorted(donos.values(), key=lambda d: min(d[k]["desde"] for k in TIPOS if d[k]))


def numeros_usados(numeros: list[str]) -> list[dict]:
    """Proprietários a quem cada número de fatura já foi dado (para avisar
    de um provável engano de escrita; não bloqueia)."""
    if not numeros:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT fatura_numero, dono_id, dono_nome FROM faturacao_linhas
                   WHERE NOT anulada AND fatura_numero <> '' AND LOWER(TRIM(fatura_numero)) = ANY(%s)""",
                ([n.strip().lower() for n in numeros],),
            )
            return [{"fatura_numero": a, "dono_id": b, "dono_nome": c} for a, b, c in cur.fetchall()]
