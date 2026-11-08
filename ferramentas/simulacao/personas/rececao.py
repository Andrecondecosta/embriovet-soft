"""Carla — rececionista/administrativa há 6 anos.

Segunda a sábado, 8h-17h. Ao domingo ninguém está na receção: o que chega
fica à porta e é registado na segunda (com a data verdadeira ou, às vezes,
com a de segunda); o que sai ao domingo também só se regista na segunda.

Dá entrada às éguas (proprietário, estadia, box/paddock), regista saídas e
atende os donos que ligam a perguntar se a égua já está gestante. Decide as
saídas pelo que a app mostra + o que o dono combinou (`perfil_dono`).

Hábitos humanos (aleatórios mas reprodutíveis):
- às vezes escreve o nome do dono à sua maneira (sem acentos, "Coud.",
  "Soc. Agrícola"...) em vez de o escolher na lista → proprietário duplicado;
- às vezes atrasa o registo da saída 1-2 dias e mete a data real;
- em dias de muitas chegadas despacha: observações vazias, sem data de
  nascimento, sem garanhão na ficha;
- a ocupação das boxes vai no caderno (a app não tem mapa de boxes); à
  segunda confere o caderno com a lista de internadas.
"""

from __future__ import annotations

import random
import unicodedata
from datetime import date, timedelta

from simcore import Pessoa

ETAPA_SEGUINTE = {"D+14": "D+28", "D+28": "D+45"}
# Dias mínimos depois da inseminação para um DG positivo contar como dessa etapa.
DIAS_ETAPA = {"D+14": 12, "D+28": 25, "D+45": 40}


def sem_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normal(s: str) -> str:
    return " ".join(sem_acentos(s or "").lower().replace(".", " ").split())


def como_data(v) -> date | None:
    if not v:
        return None
    return date.fromisoformat(str(v)[:10])


class Rececao(Pessoa):
    papel = "rececao"
    nome = "carla"
    ordem = 1
    nivel = "Gestor"

    def __init__(self, mundo):
        super().__init__(mundo)
        self.r = random.Random(2027_01)
        m = self.memoria
        m["donos"] = {}  # nome como ela o escreveu → id
        m["eguas"] = {}  # wid → ficha do caderno
        m["porta"] = []  # chegadas de domingo à espera de registo: (wid, dia_sim)
        m["saidas"] = []  # saídas por registar: dict(wid, data_real, registar_em, estado, obs)
        m["ocupacao"] = {}  # caderno: alojamento_id → n.º de éguas
        m["notas_dadas"] = set()

    # ── utilitários ──────────────────────────────────────────────────────
    def nota_uma_vez(self, chave, texto, **extra):
        if chave in self.memoria["notas_dadas"]:
            return
        self.memoria["notas_dadas"].add(chave)
        self.nota(texto, **extra)

    def _alojamentos(self):
        if "alojamentos" not in self.memoria:
            s, r = self.api("GET", "/estadias/opcoes")
            al = {}
            for a in (r or {}).get("alojamentos", []) if s == 200 else []:
                al[a["id"]] = {"nome": a["nome"], "tipo": a.get("tipo"), "cap": a.get("capacidade") or 1}
            self.memoria["alojamentos"] = al
            self.memoria["donos_lista"] = (r or {}).get("donos", []) if s == 200 else []
        return self.memoria["alojamentos"]

    # ── proprietários ────────────────────────────────────────────────────
    def _variante(self, nome: str) -> str:
        """Como a Carla às vezes escreve o nome à pressa."""
        opcoes = []
        if nome.startswith("Coudelaria "):
            opcoes.append(nome.replace("Coudelaria ", "Coud. "))
        if nome.startswith("Sociedade Agrícola "):
            opcoes.append(nome.replace("Sociedade Agrícola ", "Soc. Agrícola "))
        if nome.startswith("Herdade "):
            opcoes.append(nome.replace("Herdade ", "Hdade. "))
        if sem_acentos(nome) != nome:
            opcoes.append(sem_acentos(nome))
        if nome.startswith("Quinta "):
            opcoes.append(nome.replace("Quinta ", "Qta. "))
        opcoes.append(nome.lower() if self.r.random() < 0.3 else nome + " ")  # minúsculas / espaço a mais
        return self.r.choice(opcoes)

    def _dono(self, nome: str, apressada: bool) -> int | None:
        cache = self.memoria["donos"]
        # Normalmente escolhe na lista; às vezes escreve à mão (mais quando está com pressa).
        escrito = nome
        if self.r.random() < (0.12 if apressada else 0.06):
            escrito = self._variante(nome)
        if escrito in cache:
            return cache[escrito]
        termo = escrito.strip()
        s, r = self.api("GET", "/owners", params={"q": termo, "por_pagina": 50})
        itens = (r or {}).get("items", []) if s == 200 else []
        # Reconhece o dono se o nome é "o mesmo" a olho (maiúsculas/acentos/pontos).
        achado = next((o for o in itens if normal(o.get("nome")) == normal(termo)), None)
        if achado:
            cache[escrito] = achado["id"]
            return achado["id"]
        s, r = self.api("POST", "/owners", json={"nome": termo})
        if s == 201:
            cache[escrito] = r.get("id")
            if termo != nome:
                self.memoria.setdefault("duplicados", []).append((nome, termo))
            return cache[escrito]
        if s == 409:
            # A app diz que já existe mas a pesquisa não o mostrou: procura na lista completa.
            s2, r2 = self.api("GET", "/estadias/opcoes")
            # A mensagem da app diz qual é o nome que já existe ("Já existe «X»"): usa esse.
            existente = ((r or {}).get("detail") or {}).get("params", {}).get("name") or termo
            d = next((o for o in (r2 or {}).get("donos", []) if (o["nome"] or "").lower() == existente.lower()), None)
            self.nota_uma_vez("409dono", f"Ao criar o proprietário «{termo}» a app disse que já existe, mas a pesquisa não o mostrou; tive de o procurar na lista.")
            if d:
                cache[escrito] = d["id"]
                return d["id"]
        return None

    # ── boxes (caderno) ──────────────────────────────────────────────────
    def _lugar(self, tipo: str) -> int | None:
        al = self._alojamentos()
        oc = self.memoria["ocupacao"]
        # Receptoras vão para paddock; éguas para box. Se não houver, a outra coisa.
        pref = ("paddock", "box") if tipo == "receptora" else ("box", "paddock")
        for t in pref:
            for aid, a in al.items():
                if (a["tipo"] or "").lower().startswith(t) and oc.get(aid, 0) < a["cap"]:
                    oc[aid] = oc.get(aid, 0) + 1
                    return aid
        for aid, a in al.items():  # tipos com outros nomes
            if oc.get(aid, 0) < a["cap"]:
                oc[aid] = oc.get(aid, 0) + 1
                return aid
        # Tudo cheio: mete no paddock menos cheio e aponta.
        aid = min(al, key=lambda k: oc.get(k, 0) / al[k]["cap"]) if al else None
        if aid is not None:
            oc[aid] = oc.get(aid, 0) + 1
            self.nota("Tudo cheio segundo o meu caderno; meti a égua a mais num alojamento. A app aceitou sem avisar que já estava cheio.", alojamento=al[aid]["nome"])
        return aid

    def _conferir_caderno(self):
        """À segunda: conta as internadas por alojamento e compara com o caderno."""
        s, r = self.api("GET", "/estadias/internadas")
        if s != 200:
            return
        nomes = {a["nome"]: aid for aid, a in self._alojamentos().items()}
        real: dict[int, int] = {}
        for x in r.get("itens", []):
            aid = nomes.get(x.get("alojamento_nome"))
            if aid is not None:
                real[aid] = real.get(aid, 0) + 1
        oc = self.memoria["ocupacao"]
        dif = {self._alojamentos()[k]["nome"]: (oc.get(k, 0), real.get(k, 0)) for k in set(oc) | set(real) if oc.get(k, 0) != real.get(k, 0)}
        self.nota_uma_vez("sem_mapa", "A app não tem vista de ocupação das boxes/paddocks: mantenho um caderno e à segunda conto à mão as internadas por alojamento.")
        if dif:
            self.nota(f"Caderno das boxes não bate com a app em {len(dif)} alojamento(s) (caderno, app): {dif}. Corrigi o caderno pela app.")
        self.memoria["ocupacao"] = {k: v for k, v in real.items()}

    # ── entradas ─────────────────────────────────────────────────────────
    def _entrada(self, rel, e, dia_sim: date, apressada: bool):
        lugar = self._lugar(e.tipo)
        animal = {"nome": e.nome, "tipo": e.tipo}
        if not apressada or self.r.random() < 0.5:
            # O dono diz a idade; ela põe 1 de janeiro desse ano.
            animal["data_nascimento"] = date(rel.real(dia_sim).year - e.idade, 1, 1).isoformat()
        obs = None
        if not (apressada and self.r.random() < 0.6):
            obs = f"Garanhão pedido: {e.garanhao}. Dono: {e.dono}."
        corpo = {
            "animal": animal,
            "tipo_registo": "estadia",
            "motivo": "embriao" if e.tipo == "receptora" else "inseminacao",
            "dono_id": self._dono(e.dono, apressada),
            "data_entrada": rel.real(dia_sim).isoformat(),
            "alojamento_id": lugar,
            "observacoes": obs,
        }
        s, r = self.api("POST", "/estadias", json=corpo)
        if s not in (200, 201):
            if lugar is not None:
                self.memoria["ocupacao"][lugar] -= 1
            self.nota(f"Não consegui dar entrada a {e.nome}: {r}")
            return
        ficha = {
            "animal_id": r.get("animal_id"), "estadia_id": r.get("id"), "lugar": lugar, "nome": e.nome,
            "entrada": dia_sim, "tipo": e.tipo, "saiu": False, "a_sair": False,
            "proxima_chamada": rel.hoje + timedelta(days=self.r.randint(10, 16)),
        }
        self.memoria["eguas"][e.wid] = ficha
        # O formulário de entrada não tem garanhão: se tiver tempo, abre a ficha e põe-no no acompanhamento.
        if e.tipo == "egua" and not apressada and self.r.random() < 0.7:
            self.api("PUT", f"/animais/{ficha['animal_id']}/acompanhamento", json={"garanhao": e.garanhao})
            self.nota_uma_vez("garanhao_form", "O formulário de entrada não tem campo para o garanhão pedido pelo dono; tenho de abrir a ficha da égua depois (ou escrevo nas observações).")

    # ── saídas ───────────────────────────────────────────────────────────
    def _agendar_saida(self, rel, wid, data_real: date, estado: str, obs: str | None):
        x = self.memoria["eguas"].get(wid)
        if not x or x["saiu"] or x["a_sair"]:
            return
        x["a_sair"] = True
        registar = max(data_real, rel.hoje)
        if self.r.random() < 0.18:  # fica para depois (papel em cima da secretária)
            registar = registar + timedelta(days=self.r.randint(1, 2))
        self.memoria["saidas"].append({"wid": wid, "data_real": data_real, "registar_em": registar, "estado": estado, "obs": obs})

    def _estadia_aberta(self, animal_id):
        if self._internadas is None:
            s, r = self.api("GET", "/estadias/internadas")
            self._internadas = r.get("itens", []) if s == 200 else []
        return next((e for e in self._internadas if e.get("animal_id") == animal_id), None)

    def _registar_saidas(self, rel, apressada: bool):
        pendentes = []
        for p in self.memoria["saidas"]:
            if p["registar_em"] > rel.hoje:
                pendentes.append(p)
                continue
            x = self.memoria["eguas"][p["wid"]]
            aberta = self._estadia_aberta(x["animal_id"])
            if not aberta:
                self.nota(f"Ia registar a saída de {x['nome']} mas já não aparece nas internadas (alguém já a fechou?).")
                x["saiu"] = True
                continue
            obs = p["obs"]
            if apressada and p["estado"] != "sem_resultado" and self.r.random() < 0.5:
                obs = None
            corpo = {"data_saida": rel.real(p["data_real"]).isoformat(), "estado": p["estado"], "observacoes": obs}
            if apressada and p["estado"] == "sem_resultado" and self.r.random() < 0.3:
                s, _ = self.api("POST", f"/estadias/{aberta['id']}/saida", json={**corpo, "observacoes": None})
                if s == 422:
                    s, _ = self.api("POST", f"/estadias/{aberta['id']}/saida", json=corpo)
            else:
                s, _ = self.api("POST", f"/estadias/{aberta['id']}/saida", json=corpo)
            if s == 200:
                x["saiu"] = True
                if p["data_real"] < rel.hoje:
                    self.memoria.setdefault("saidas_atrasadas", 0)
                    self.memoria["saidas_atrasadas"] += 1
                if x.get("lugar") is not None:
                    oc = self.memoria["ocupacao"]
                    oc[x["lugar"]] = max(0, oc.get(x["lugar"], 0) - 1)
            else:
                pendentes.append(p)
        self.memoria["saidas"] = pendentes

    # ── telefonemas dos donos ────────────────────────────────────────────
    def _dg_positivo_desde(self, animal_id, insem: date, dias_min: int) -> bool:
        s, r = self.api("GET", f"/animais/{animal_id}/registos")
        if s != 200:
            return False
        for h in r.get("historico", []):
            dg = (h.get("dados") or {}).get("DG")
            d = como_data(h.get("data_registo"))
            if d and str(dg).lower().startswith("positivo") and (d - insem).days >= dias_min:
                return True
        return False

    def _telefonema(self, rel, wid, x):
        """O dono liga: «Então, a égua já está cheia?» A Carla abre a ficha."""
        perfil = self.mundo.perfil_dono(wid)
        aid = x["animal_id"]
        s, rep = self.api("GET", f"/animais/{aid}/reprodutivo")
        if s != 200:
            return
        hoje_real = rel.real(rel.hoje)
        ins = sorted(rep.get("inseminacoes", []), key=lambda i: str(i.get("data_inseminacao") or ""), reverse=True)
        falhadas = sum(1 for i in ins if i.get("resultado") not in ("pendente", "gestacao_confirmada"))
        ult = ins[0] if ins else None
        dias_ins = (hoje_real - como_data(ult["data_inseminacao"])).days if ult and ult.get("data_inseminacao") else None
        x["proxima_chamada"] = rel.hoje + timedelta(days=self.r.randint(3, 7))

        if ult is None:
            dias = (rel.hoje - x["entrada"]).days
            if x.get("tipo") == "receptora":
                return  # receptoras não são inseminadas
            if dias >= 35 and rel.hoje >= x.get("ja_avisei_sem_ins", rel.hoje):
                x["ja_avisei_sem_ins"] = rel.hoje + timedelta(days=30)
                self.nota(f"Dono de {x['nome']} pergunta como vai: está cá há {dias} dias e a app não mostra nenhuma inseminação. Não sei o que lhe dizer.")
            return
        if ult["resultado"] == "gestacao_confirmada":
            quer = perfil["leva_para_casa_gestante_em"]
            etapa = ult.get("etapa")  # etapa do PRÓXIMO diagnóstico
            insem = como_data(ult["data_inseminacao"])
            pronta = False
            if quer == "D+14":
                pronta = True  # o positivo já é o D+14
            elif quer == "D+28":
                if etapa == "D+45" and dias_ins < 45:
                    pronta = True
                elif etapa == "D+45":
                    pronta = self._dg_positivo_desde(aid, insem, DIAS_ETAPA["D+28"])
                    if not pronta:
                        self.nota(f"{x['nome']}: a app diz próxima etapa D+45 mas não encontro o DG de D+28 no histórico; não sei se a confirmação foi feita.")
            else:  # D+45
                if etapa == "D+45" and dias_ins >= 44:
                    pronta = self._dg_positivo_desde(aid, insem, DIAS_ETAPA["D+45"])
                    if not pronta and dias_ins >= 50:
                        self.nota_uma_vez(f"d45_{wid}", f"{x['nome']}: inseminada há {dias_ins} dias, gestante, mas a app não me mostra se a confirmação de D+45 já foi feita. O dono quer levá-la só depois disso.")
            if pronta:
                vem = rel.hoje + timedelta(days=self.r.randint(0, 3))
                self._agendar_saida(rel, wid, vem, "gestante", None if self.r.random() < 0.4 else f"Gestante ({quer}). Garanhão {ult.get('garanhao') or perfil['garanhao']}.")
            return
        if ult["resultado"] == "pendente":
            if dias_ins is not None and dias_ins >= 18:
                self.nota(f"Dono de {x['nome']} perguntou se está gestante: inseminada há {dias_ins} dias e a app ainda diz «pendente». Disse-lhe que ia confirmar com o veterinário.")
            return
        # Última falhou.
        if falhadas >= perfil["max_ciclos"]:
            vem = rel.hoje + timedelta(days=self.r.randint(1, 4))
            self._agendar_saida(rel, wid, vem, "sem_resultado", f"{falhadas} ciclo(s) sem gestação; dono não quer tentar mais.")

    # ── o dia ────────────────────────────────────────────────────────────
    def dia(self, rel):
        m, mem = self.mundo, self.memoria
        self._internadas = None
        hoje = rel.hoje
        if hoje.weekday() == 6:  # domingo: receção fechada
            for e in m.chegadas(hoje):
                mem["porta"].append((e.wid, hoje))
            for e in m.saidas_imprevistas(hoje):
                if e.wid in mem["eguas"]:
                    self._agendar_saida(rel, e.wid, hoje, "alta", "Dono levou a égua ao domingo (sem receção).")
                else:
                    mem.setdefault("levadas_antes_registo", []).append(e.wid)
            return

        if hoje.weekday() == 0 and rel.d > 0:
            self._conferir_caderno()

        # 1. Entradas (as de domingo primeiro).
        chegam = [(e, hoje) for e in m.chegadas(hoje)]
        porta = [(m.eguas[w], d) for w, d in mem["porta"]]
        mem["porta"] = []
        apressada = len(chegam) + len(porta) >= 3
        for e, d in porta:
            if e.wid in mem.get("levadas_antes_registo", []):
                self.nota(f"{e.nome} chegou e saiu no domingo; nunca chegou a ficar registada na app.")
                continue
            # Na maior parte das vezes põe a data verdadeira; às vezes a de hoje.
            dia_reg = d if self.r.random() < 0.7 else hoje
            self._entrada(rel, e, dia_reg, apressada)
            self.nota_uma_vez("domingo", "Chegadas de domingo só entram na app na segunda: durante o domingo os veterinários não as veem na lista de internadas.")
        for e, d in chegam:
            self._entrada(rel, e, d, apressada)

        # 2. Donos que aparecem sem aviso.
        for e in m.saidas_imprevistas(hoje):
            if e.wid in mem["eguas"]:
                self._agendar_saida(rel, e.wid, hoje, "alta", self.r.choice(["Dono levou a égua (venda).", "Dono levou a égua (problema de saúde).", "Dono levou a égua sem aviso.", None]))

        # 3. Telefonemas dos donos (só a quem toca hoje).
        for wid, x in list(mem["eguas"].items()):
            if x["saiu"] or x["a_sair"] or hoje < x["proxima_chamada"]:
                continue
            self._telefonema(rel, wid, x)

        # 4. Registar as saídas de hoje (e as que ficaram para trás).
        self._registar_saidas(rel, apressada)

        # Fim do dia: se o dia foi de correria, fica uma nota de quantos donos ficaram sem resposta.
        if rel.d == 272 or (rel.d % 60 == 59):
            dup = mem.get("duplicados", [])[mem.get("dup_reportados", 0):]
            mem["dup_reportados"] = len(mem.get("duplicados", []))
            if dup:
                self.nota(f"Reparei que há proprietários repetidos com nomes parecidos: {dup}. A app não avisou ao criar.")
