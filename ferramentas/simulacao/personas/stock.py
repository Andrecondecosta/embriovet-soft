"""Hugo — técnico de laboratório, responsável pelo banco de sémen.

Trabalha de segunda a sexta (uma semana de férias em agosto). Recebe os
lotes que chegam, guarda-os no azoto e regista-os na app. Vigia o stock por
garanhão e encomenda quando está baixo. Uma vez por mês faz a "contagem" dos
lotes e compara com o que a app mostra.

Hábitos humanos (reprodutíveis, `random.Random(4242)`):
- lotes que chegam à sexta à tarde ou ao fim de semana ficam no contentor de
  quarentena e só são registados na segunda (ou no 1.º dia útil);
- ~7 % das vezes esquece-se de escrever o código LT nas observações;
- ~8 % das vezes regista o canister errado (troca com o do lado);
- lote externo sem motilidade/concentração: deixa 0 (a app avisa, mas grava);
  quando o fornecedor manda o certificado (nem sempre), tenta corrigir o lote;
- ~10 % dos dias úteis não chega a olhar para o stock (dia corrido);
- contagem mensal no 1.º dia útil do mês.
"""

from __future__ import annotations

import random
from datetime import timedelta

from mundo import GARANHOES
from simcore import Pessoa

DONO_INTERNO = "Clínica — sémen próprio"
DONO_EXTERNO = "Clínica — sémen comprado"
LIMIAR = 10  # palhetas por garanhão abaixo das quais encomenda
FERIAS = (210, 214)  # dias simulados (≈ 30 ago – 3 set 2027), seg–sex


class Hugo(Pessoa):
    papel = "stock"
    nome = "hugo"
    ordem = 2

    def __init__(self, mundo):
        super().__init__(mundo)
        self.r = random.Random(4242)

    # ── utilidades ───────────────────────────────────────────────────────
    def _nota_uma_vez(self, chave, texto, **extra):
        vistas = self.memoria.setdefault("notas_feitas", set())
        if chave not in vistas:
            vistas.add(chave)
            self.nota(texto, **extra)

    def _dono(self, nome):
        donos = self.memoria.setdefault("donos", {})
        if nome not in donos:
            s, r = self.api("GET", "/owners", params={"q": nome, "por_pagina": 50})
            achado = next((o for o in (r or {}).get("itens", []) if o.get("nome") == nome), None) if s == 200 else None
            if achado:
                donos[nome] = achado["id"]
            else:
                s, r = self.api("POST", "/owners", json={"nome": nome})
                donos[nome] = (r or {}).get("id") if s == 201 else None
        return donos[nome]

    def _preparar(self):
        if "contentores" in self.memoria:
            return
        s, cont = self.api("GET", "/opcoes/contentores")
        self.memoria["contentores"] = [c["id"] for c in (cont or [])] if s == 200 else []
        if not self.memoria["contentores"]:
            self.nota("Não há contentores ativos na app: não consigo registar lotes.")
        self.memoria["fisico"] = {}  # codigo LT -> o que ele sabe do lote (onde o pôs, quantas palhetas, id na app)
        self.memoria["por_registar"] = []  # lotes que estão no laboratório mas ainda não na app
        self.memoria["encomendas"] = {}  # garanhão -> dia simulado em que encomendou
        self.memoria["certificados"] = []  # (dia simulado em que chega, codigo)
        self.memoria["esgotados_vistos"] = set()

    def _local(self, garanhao):
        """Arrumação fixa do Hugo: cada garanhão tem o seu canister."""
        conts = self.memoria["contentores"]
        i = [g[0] for g in GARANHOES].index(garanhao) if garanhao in [g[0] for g in GARANHOES] else 0
        return conts[(i // 10) % len(conts)], i % 10 + 1

    # ── o dia ────────────────────────────────────────────────────────────
    def dia(self, rel):
        self._preparar()
        hoje = rel.hoje
        wd = hoje.weekday()
        # O que chega hoje fica no laboratório (alguém assina a guia, mesmo sem o Hugo).
        for l in self.mundo.semen_chega(hoje):
            self.memoria["por_registar"].append(l)
            # Um terço dos externos sem dados: o fornecedor manda o certificado depois (às vezes).
            if not l.interno and l.motilidade_rotulo is None and self.r.random() < 0.6:
                self.memoria["certificados"].append((rel.d + self.r.randint(4, 20), l.codigo))
        if wd >= 5 or FERIAS[0] <= rel.d <= FERIAS[1] or not self.memoria["contentores"]:
            return
        # Sexta à tarde: o que chegou hoje fica para segunda.
        hoje_chegou = {l.codigo for l in self.mundo.semen_chega(hoje)}
        adiar = set()
        if wd == 4:
            adiar = {c for c in hoje_chegou if self.r.random() < 0.5}
        pendentes = self.memoria["por_registar"]
        self.memoria["por_registar"] = [l for l in pendentes if l.codigo in adiar]
        atrasados = [l for l in pendentes if l.codigo not in adiar and l.chega < hoje]
        if len(atrasados) >= 3:
            self._nota_uma_vez(
                "fila", "Segunda de manhã com vários lotes do fim de semana por registar: a app não tem "
                "estado 'recebido, por registar', por isso durante esse tempo os veterinários não os veem.")
        for l in pendentes:
            if l.codigo not in adiar:
                self._registar(rel, l)
        self._certificados(rel)
        # Verificação de stock (às vezes não há tempo).
        if self.r.random() >= 0.10:
            self._vigiar_stock(rel)
        if wd == 0:
            self._esgotados(rel)
        # Contagem mensal: 1.º dia útil do mês.
        if self.memoria.get("ultima_contagem") != (hoje.year, hoje.month):
            self.memoria["ultima_contagem"] = (hoje.year, hoje.month)
            if rel.d > 0:
                self._contagem(rel)

    # ── registo de lotes ─────────────────────────────────────────────────
    def _registar(self, rel, l):
        contentor, canister = self._local(l.garanhao)
        andar = 1 if self.r.random() < 0.6 else 2
        canister_app = canister
        if self.r.random() < 0.08:  # trocou o canister ao escrever
            canister_app = canister + 1 if canister < 10 else canister - 1
        esqueceu_lt = self.r.random() < 0.07
        obs = f"Recebido a {rel.real(l.chega).strftime('%d/%m')}" if esqueceu_lt else l.codigo
        if not l.interno and l.motilidade_rotulo is None:
            obs += " — sem certificado"
        corpo = {
            "garanhao": l.garanhao,
            "dono_id": self._dono(DONO_INTERNO if l.interno else DONO_EXTERNO),
            "palhetas": l.palhetas,
            "data_embriovet": rel.real(l.data_producao).isoformat() if l.interno else None,
            "origem_externa": l.origem or None,
            "motilidade": l.motilidade_rotulo or 0,
            "concentracao": l.concentracao_rotulo or 0,
            "certificado": "Não" if (not l.interno and l.motilidade_rotulo is None) else "Sim",
            "contentor_id": contentor, "canister": canister_app, "andar": andar,
            "observacoes": obs,
        }
        s, r = self.api("POST", "/stock/lotes", json=corpo)
        self.memoria["fisico"][l.codigo] = {
            "garanhao": l.garanhao, "palhetas": l.palhetas, "contentor": contentor, "canister": canister,
            "andar": andar, "id": (r or {}).get("id") if s == 201 else None, "lt_escrito": not esqueceu_lt,
            "registado_dia": rel.d, "chegou_dia": (l.chega - rel.hoje).days + rel.d, "interno": l.interno,
        }
        if s != 201:
            self.nota(f"Não consegui registar o lote {l.codigo} ({l.garanhao}): erro {s}", corpo=r)
            return
        if not l.interno and l.motilidade_rotulo is None:
            self._nota_uma_vez(
                "mot0", "Lote de fora veio sem motilidade/concentração: deixei 0. A app avisa mas grava; "
                "na lista o 0 parece um valor medido, não 'desconhecido'. Faltava poder deixar em branco.")
        if self.memoria.get("encomendas", {}).pop(l.garanhao, None) is not None:
            pass  # encomenda satisfeita

    def _certificados(self, rel):
        """O fornecedor mandou o certificado: tenta pôr a motilidade/concentração no lote."""
        chegaram = [c for d, c in self.memoria["certificados"] if d <= rel.d]
        self.memoria["certificados"] = [(d, c) for d, c in self.memoria["certificados"] if d > rel.d]
        for codigo in chegaram:
            x = self.memoria["fisico"].get(codigo)
            if not x or not x.get("id"):
                continue  # ainda não registado; fica esquecido (o papel perde-se na secretária)
            if self.r.random() < 0.3:
                continue  # deixou o certificado na pasta e nunca mais pegou nele
            l = self.mundo.lotes[codigo]
            s, atual = self.api("GET", f"/stock/lotes/{x['id']}")
            if s != 200:
                continue
            corpo = {k: atual.get(k) for k in ("data_embriovet", "origem_externa", "qualidade", "dose", "cor",
                                               "contentor_id", "canister", "andar", "observacoes", "dono_id",
                                               "palhetas_produzidas", "existencia_atual")}
            corpo.update(
                garanhao=atual.get("garanhao_nome") or l.garanhao,
                motilidade=min(100, l.motilidade_real + self.r.randint(-2, 3)),
                concentracao=l.concentracao_real, certificado="Sim",
                palhetas_produzidas=atual.get("palhetas_produzidas") or 0,
                existencia_atual=atual.get("existencia_atual") or 0,
                canister=atual.get("canister") or 1, andar=atual.get("andar") or 1,
            )
            s, r = self.api("PUT", f"/stock/lotes/{x['id']}", json=corpo)
            if s == 403:
                self._nota_uma_vez(
                    "edit403", "Chegou o certificado do lote de fora mas não consigo corrigir a motilidade: "
                    "só o Administrador pode editar lotes. O lote fica com 0 e tenho de pedir à direção.")
                self.memoria.setdefault("correcoes_por_fazer", []).append(codigo)
            elif s == 200:
                x["corrigido"] = True

    # ── vigilância do stock e encomendas ─────────────────────────────────
    def _vigiar_stock(self, rel):
        s, gars = self.api("GET", "/stock/garanhoes")
        if s != 200:
            return
        por = {g["garanhao"]: int(g.get("palhetas") or 0) for g in gars or []}
        encomendas = self.memoria["encomendas"]
        # Encomendas que nunca vieram (ou que ele não ligou ao lote) caducam ao fim de 10 dias.
        for g, d in list(encomendas.items()):
            if rel.d - d > 10:
                encomendas.pop(g)
        a_caminho = {l.garanhao for l in self.memoria["por_registar"]}
        for g, *_ in GARANHOES:
            n = por.get(g, 0)
            if g not in por:
                self._nota_uma_vez(
                    f"sumiu", "Quando um garanhão fica sem palhetas desaparece da lista de Garanhões do stock: "
                    "tenho de saber de cabeça quais é que trabalhamos para dar pela falta.", garanhao=g)
            if n < LIMIAR and g not in encomendas and g not in a_caminho:
                self.mundo.pedir_semen(rel.hoje, g)
                encomendas[g] = rel.d
                self.memoria.setdefault("n_encomendas", 0)
                self.memoria["n_encomendas"] += 1

    def _esgotados(self, rel):
        """À segunda vê os lotes vazios de cada garanhão (para tirar as raques do azoto)."""
        vistos = self.memoria["esgotados_vistos"]
        novos = []
        for g, *_ in GARANHOES:
            s, r = self.api("GET", "/stock/lotes", params={"garanhao": g, "incluir_vazios": True})
            if s != 200:
                continue
            for l in r.get("items", []):
                if int(l.get("existencia_atual") or 0) == 0 and l["id"] not in vistos:
                    vistos.add(l["id"])
                    novos.append((g, l["id"], (l.get("observacoes") or "").strip()))
        if novos:
            sem_lt = [n for n in novos if not n[2].startswith("LT-")]
            self.nota(f"Segunda: {len(novos)} lote(s) esgotado(s) desde a última vez; retirei-os do contentor.",
                      lotes=[f"{g} #{i} {o}" for g, i, o in novos])
            if sem_lt:
                self._nota_uma_vez(
                    "esg_sem_lt", "Há lotes esgotados sem código LT nas observações: tenho de ir pelo "
                    "contentor/canister para saber qual raque tirar.")
            self._nota_uma_vez(
                "esg_lista", "Para ver lotes esgotados tenho de abrir garanhão a garanhão com 'incluir vazios': "
                "não há uma lista de 'esgotados recentemente'.")

    # ── contagem mensal ──────────────────────────────────────────────────
    def _contagem(self, rel):
        """Compara o que ele sabe (o que guardou e onde) com o que a app mostra."""
        discrep = []
        app_ids = {}
        for g, *_ in GARANHOES:
            s, r = self.api("GET", "/stock/lotes", params={"garanhao": g, "incluir_vazios": True})
            if s == 200:
                for l in r.get("items", []):
                    app_ids[l["id"]] = l
        for codigo, x in self.memoria["fisico"].items():
            l = app_ids.get(x.get("id"))
            if not l:
                discrep.append(f"{codigo} ({x['garanhao']}): guardado no azoto mas não aparece na app")
                continue
            if int(l.get("canister") or 0) != x["canister"]:
                discrep.append(f"{codigo} ({x['garanhao']}): na app está no canister {l.get('canister')}, fisicamente no {x['canister']}")
            if int(l.get("quantidade_inicial") or 0) != x["palhetas"]:
                discrep.append(f"{codigo}: recebi {x['palhetas']} palhetas, a app diz {l.get('quantidade_inicial')} iniciais")
            ex = int(l.get("existencia_atual") or 0)
            if ex < 0 or ex > x["palhetas"]:
                discrep.append(f"{codigo}: existência estranha na app ({ex} de {x['palhetas']})")
            if not x["lt_escrito"] and not x.get("lt_assinalado"):
                x["lt_assinalado"] = True
                discrep.append(f"{codigo} ({x['garanhao']}, lote #{x['id']}): sem código LT nas observações")
            if int(l.get("motilidade") or 0) == 0 and not x["interno"]:
                discrep.append(f"{codigo}: motilidade continua a 0 na app")
        for l in self.memoria["por_registar"]:
            discrep.append(f"{l.codigo} ({l.garanhao}): no laboratório, ainda por registar")
        self.nota(f"Contagem mensal: {len(self.memoria['fisico'])} lotes conferidos, {len(discrep)} discrepância(s).",
                  discrepancias=discrep[:40], encomendas_feitas=self.memoria.get("n_encomendas", 0))
        if any("canister" in d for d in discrep):
            self._nota_uma_vez(
                "canister", "Na contagem encontrei lotes com o canister errado na app e não os consigo corrigir "
                "(editar é só para Administrador).")
