"""Versões base (simples e corretas) das 5 pessoas. Cada agente substitui
uma por uma pessoa "real" em personas/<papel>.py, com o mesmo `papel`.

Regras para todas:
- Só se sabe o que a app mostra (API) + o que a pessoa vê/ouve no mundo
  (exame, chegadas, donos) + a sua memória privada. Nada de ler a base.
- Datas para a app: `rel.real(dia_simulado)`. Datas do mundo: simuladas.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from simcore import Pessoa, Relogio


def hora(rel: Relogio, h: int, m: int = 0, real=True) -> datetime:
    d = rel.real(rel.hoje) if real else rel.hoje
    return datetime.combine(d, time(h, m))


class Rececao(Pessoa):
    papel = "rececao"
    nome = "rececao_base"
    ordem = 1

    def _dono(self, nome):
        cache = self.memoria.setdefault("donos", {})
        if nome not in cache:
            s, r = self.api("GET", "/owners", params={"q": nome, "por_pagina": 50})
            achado = next((o for o in (r or {}).get("itens", []) if o.get("nome") == nome), None) if s == 200 else None
            if achado:
                cache[nome] = achado["id"]
            else:
                s, r = self.api("POST", "/owners", json={"nome": nome})
                cache[nome] = r.get("id") if s == 201 else None
        return cache[nome]

    def _lugar(self):
        """Box livre (a app não mostra a ocupação: a receção sabe de cabeça)."""
        if "alojamentos" not in self.memoria:
            s, r = self.api("GET", "/estadias/opcoes")
            self.memoria["alojamentos"] = {a["id"]: a["capacidade"] or 1 for a in (r or {}).get("alojamentos", [])}
            self.memoria["ocupacao"] = {}
        oc = self.memoria["ocupacao"]
        for aid, cap in self.memoria["alojamentos"].items():
            if oc.get(aid, 0) < cap:
                oc[aid] = oc.get(aid, 0) + 1
                return aid
        return None

    def dia(self, rel):
        m = self.mundo
        for e in m.chegadas(rel.hoje):
            lugar = self._lugar()
            idade = date(rel.real(rel.hoje).year - e.idade, 5, 1)
            corpo = {
                "animal": {"nome": e.nome, "tipo": e.tipo, "data_nascimento": idade.isoformat()},
                "tipo_registo": "estadia",
                "motivo": "embriao" if e.tipo == "receptora" else "inseminacao",
                "dono_id": self._dono(e.dono),
                "data_entrada": rel.real(rel.hoje).isoformat(),
                "alojamento_id": lugar,
                "observacoes": f"Garanhão pedido: {e.garanhao}",
            }
            s, r = self.api("POST", "/estadias", json=corpo)
            if s in (200, 201):
                self.memoria.setdefault("eguas", {})[e.wid] = {"animal_id": r.get("animal_id"), "estadia_id": r.get("id") or r.get("estadia_id"), "lugar": lugar}
        # Donos que vêm buscar sem aviso.
        for e in m.saidas_imprevistas(rel.hoje):
            self._saida(rel, e.wid, "alta", "Dono levou a égua")
        # Regras dos donos: gestante na etapa combinada, ou ciclos esgotados.
        for wid, x in list(self.memoria.get("eguas", {}).items()):
            if x.get("saiu") or not x.get("animal_id"):
                continue
            s, rep = self.api("GET", f"/animais/{x['animal_id']}/reprodutivo")
            if s != 200:
                continue
            ins = rep.get("inseminacoes", [])
            perfil = m.perfil_dono(wid)
            if ins and ins[0]["resultado"] == "gestacao_confirmada":
                feito = {"D+14": "D+28", "D+28": "D+45", "D+45": "fim"}  # etapa seguinte => a combinada já foi feita
                if ins[0]["etapa"] == feito[perfil["leva_para_casa_gestante_em"]] or (ins[0]["etapa"] == "D+45" and perfil["leva_para_casa_gestante_em"] == "D+45" and x.get("d45_visto")):
                    self._saida(rel, wid, "gestante", None)
                if ins[0]["etapa"] == "D+45":
                    x["d45_visto"] = True
            falhadas = sum(1 for i in ins if i["resultado"] == "falhou")
            if falhadas >= perfil["max_ciclos"] and (not ins or ins[0]["resultado"] != "pendente"):
                self._saida(rel, wid, "sem_resultado", f"{falhadas} ciclos sem gestação")

    def _saida(self, rel, wid, estado, obs):
        x = self.memoria.get("eguas", {}).get(wid)
        if not x or x.get("saiu"):
            return
        s, est = self.api("GET", f"/animais/{x['animal_id']}/estadias")
        aberta = next((e for e in (est or {}).get("estadias", est if isinstance(est, list) else []) if not e.get("data_saida")), None) if s == 200 else None
        eid = (aberta or {}).get("id") or x.get("estadia_id")
        s, _ = self.api("POST", f"/estadias/{eid}/saida", json={"data_saida": rel.real(rel.hoje).isoformat(), "estado": estado, "observacoes": obs})
        if s == 200:
            x["saiu"] = True
            if x.get("lugar"):
                self.memoria["ocupacao"][x["lugar"]] -= 1


class Stock(Pessoa):
    papel = "stock"
    nome = "stock_base"
    ordem = 2

    def dia(self, rel):
        if "dono" not in self.memoria:
            s, r = self.api("POST", "/owners", json={"nome": "Clínica — sémen próprio"})
            self.memoria["dono"] = r.get("id")
            s, cont = self.api("GET", "/opcoes/contentores")
            self.memoria["contentor"] = (cont or [{}])[0].get("id") if s == 200 else None
        for l in self.mundo.semen_chega(rel.hoje):
            corpo = {
                "garanhao": l.garanhao, "dono_id": self.memoria["dono"], "palhetas": l.palhetas,
                "data_embriovet": rel.real(l.data_producao).isoformat() if l.interno else None,
                "origem_externa": l.origem or None, "motilidade": l.motilidade_rotulo or 0,
                "concentracao": l.concentracao_rotulo or 0, "contentor_id": self.memoria["contentor"],
                "canister": 1, "andar": 1, "observacoes": l.codigo,
            }
            self.api("POST", "/stock/lotes", json=corpo)
        # Pedidos de sémen em falta, deixados pelos veterinários na memória partilhada? Não: cada
        # pessoa só sabe o que a app mostra. Verifica stock por garanhão uma vez por semana.
        if rel.d % 7 == 0:
            s, lotes = self.api("GET", "/inseminacoes/lotes")
            por = {}
            for l in lotes or []:
                por[l.get("garanhao_nome") or l.get("garanhao")] = por.get(l.get("garanhao_nome") or l.get("garanhao"), 0) + int(l.get("existencia_atual") or 0)
            from mundo import GARANHOES
            for g, *_ in GARANHOES:
                if por.get(g, 0) < 6:
                    self.mundo.pedir_semen(rel.hoje, g)


class Veterinario(Pessoa):
    papel = "vet1"
    nome = "vet_base"
    ordem = 3
    hora_inicio = 9

    def _eguas(self):
        s, r = self.api("GET", "/estadias/internadas")
        return [x for x in (r or {}).get("itens", []) if x.get("animal_tipo") in ("egua",)] if s == 200 else []

    def dia(self, rel):
        # Base: vet1 trabalha de segunda a sexta; o vet2 ao fim de semana.
        if rel.hoje.weekday() < 5:
            self._trabalhar(rel)

    def _trabalhar(self, rel):
        s, trab = self.api("GET", "/trabalho")
        tarefas = {}
        for t in (trab or {}).get("por_fazer", []) + (trab or {}).get("atrasadas", []):
            tarefas.setdefault(t["animal_id"], []).append(t["tipo"])
        mem = self.memoria.setdefault("ultimo", {})
        for i, x in enumerate(self._eguas()):
            aid = x.get("animal_id")
            wid = self.mundo.wid_por_nome(x.get("animal"))
            if wid is None or wid not in self.mundo.eguas:
                continue
            ult = mem.get(aid, {"dia": -99, "maior": 0})
            if not (aid in tarefas or rel.d - ult["dia"] >= 2 or ult["maior"] >= 30):
                continue
            h = self.hora_inicio + i // 6
            quando_sim = datetime.combine(rel.hoje, time(min(h, 18), (i * 7) % 60))
            ex = self.mundo.exame(wid, quando_sim)
            maior = max(ex["foliculos"]["OE"] + ex["foliculos"]["OD"] + [0])
            dados = {
                "OE": {"foliculos": [{"tamanho": max(9, min(61, f))} for f in ex["foliculos"]["OE"]]},
                "OD": {"foliculos": [{"tamanho": max(9, min(61, f))} for f in ex["foliculos"]["OD"]]},
                "UT": {"edema": ex["edema"], "liquido": ex["liquido"]},
                "CER": {"grau": ex["cervix"]},
            }
            if "verificar_ovulacao" in tarefas.get(aid, []) or ex["ovulou"] or ex["folic_hemorragico"]:
                dados["OVU"] = {"ovulacao": "sim" if ex["ovulou"] else "nao", "fh": "sim" if ex["folic_hemorragico"] else "nao"}
            dg_tarefa = {"diagnostico_gestacao", "confirmacao_gestacao", "segunda_confirmacao"} & set(tarefas.get(aid, []))
            if dg_tarefa or ex["vesicula_embrionaria"] is not None and ult.get("insem"):
                v = ex["vesicula_embrionaria"]
                dados["DG"] = "Sem exame" if v is None else "Positivo" if v else "Negativo"
            real = rel.real(rel.hoje)
            induz = maior >= 35 and ex["edema"] >= 2 and not ex["corpo_luteo"]
            if induz:
                dados["TX"] = {"inducao": {"data": datetime.combine(real, quando_sim.time()).isoformat(), "produto": "hCG"}}
                self.mundo.induzir(wid, quando_sim)
            self.api("POST", f"/animais/{aid}/registos", json={"data_registo": datetime.combine(real, quando_sim.time()).isoformat(), "dados": dados})
            mem[aid] = {**ult, "dia": rel.d, "maior": maior}
            # Insemina no dia seguinte à indução (≈24 h antes da ovulação).
            if ult.get("induzida") == rel.d - 1 and not ex["corpo_luteo"]:
                self._inseminar(rel, aid, wid, x, quando_sim)
            if induz:
                mem[aid]["induzida"] = rel.d

    def _inseminar(self, rel, aid, wid, x, quando_sim):
        garanhao = self.mundo.perfil_dono(wid)["garanhao"]
        s, lotes = self.api("GET", "/inseminacoes/lotes")
        cands = [l for l in (lotes or []) if (l.get("garanhao_nome") or l.get("garanhao")) == garanhao and int(l.get("existencia_atual") or 0) >= 2]
        if not cands:
            self.nota(f"Sem sémen de {garanhao} para {x.get('animal')}")
            return
        lote = max(cands, key=lambda l: int(l.get("motilidade") or 0))
        quando = quando_sim + timedelta(minutes=30)
        # O código LT está nas observações do lote (ficha do lote); a lista não o traz.
        s, ficha = self.api("GET", f"/stock/lotes/{lote['id']}")
        obs = (ficha or {}).get("observacoes") or ""
        codigo = next((p for p in obs.replace(",", " ").split() if p.startswith("LT-")), None)
        self.mundo.inseminar(wid, quando, codigo)
        s, r = self.api("POST", "/inseminacoes", json={
            "animal_id_egua": aid, "garanhao": garanhao, "data_inseminacao": rel.real(rel.hoje).isoformat(),
            "hora_inseminacao": quando.strftime("%H:%M"), "linhas": [{"stock_id": lote["id"], "palhetas": 2}],
        })
        self.memoria["ultimo"][aid]["insem"] = rel.d


class Veterinario2(Veterinario):
    papel = "vet2"
    nome = "vet2_base"
    ordem = 4
    hora_inicio = 14

    def dia(self, rel):
        # Base: só trabalha ao fim de semana (dias 5 e 6 da semana); o vet1 folga.
        if rel.hoje.weekday() >= 5:
            self._trabalhar(rel)


class Direcao(Pessoa):
    papel = "direcao"
    nome = "direcao_base"
    ordem = 5
    nivel = "Administrador"

    def dia(self, rel):
        s, trab = self.api("GET", "/trabalho")
        for t in (trab or {}).get("atrasadas", []):
            if t["dias_atraso"] >= 7:
                self.api("POST", f"/trabalho/{t['tarefa_id']}/cancelar")
        if rel.hoje.weekday() == 0:
            self.api("GET", "/dashboard")
