"""Dr. Tiago — veterinário júnior (2 anos). Tardes de segunda a sexta
(14h-19h) e fins de semana inteiros. A colega sénior (vet1) faz as manhãs
dos dias úteis: o Tiago depende do que ela deixou na app (Trabalho diário,
ficha da égua, historial reprodutivo) para continuar o trabalho.

Hábitos (reprodutíveis, `random.Random(2402)`):
- às vezes insemina e só regista no fim do turno (hora aproximada) ou no
  dia seguinte;
- por vezes pega no primeiro lote da lista em vez do de melhor motilidade;
- ao fim de semana, com muito trabalho, salta éguas sem tarefa e fecha
  tarefas pelo botão "Concluir" sem registo clínico;
- usa "Não avaliado"/"Sem exame" quando não tem tempo;
- às vezes faz a indução mas esquece-se de a pôr no registo.

Só sabe o que a app mostra, o que vê no exame que ele próprio faz, o que
o dono lhe diz ao telefone e a sua memória (`self.memoria`).
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from simcore import Pessoa

TAREFAS_DG = {"diagnostico_gestacao", "confirmacao_gestacao", "segunda_confirmacao"}


def _dt(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)[:19])
    except ValueError:
        return None


def _d(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


class Tiago(Pessoa):
    papel = "vet2"
    nome = "tiago"
    ordem = 4

    # Probabilidades dos hábitos.
    P_REGISTA_FIM_TURNO = 0.20
    P_REGISTA_DIA_SEGUINTE = 0.08
    P_PRIMEIRO_LOTE = 0.25
    P_ESQUECE_INDUCAO = 0.12
    P_CONCLUIR_SEM_REGISTO = 0.25  # fim de semana, com muito trabalho
    P_SEM_TEMPO_AVALIAR = 0.20  # fim de semana, com muito trabalho

    def __init__(self, mundo):
        super().__init__(mundo)
        self.r = random.Random(2402)

    # ── utilitários ──────────────────────────────────────────────────────
    def _sim_dt(self, rel, s) -> datetime | None:
        """Data/hora real da app → simulada (o que o Tiago pensa como "dia")."""
        x = _dt(s)
        return datetime.combine(rel.simulado(x.date()), x.time()) if x else None

    def _real_dt(self, rel, quando_sim: datetime) -> datetime:
        return datetime.combine(rel.real(quando_sim.date()), quando_sim.time())

    def _egua_mem(self, aid) -> dict:
        return self.memoria.setdefault("eguas", {}).setdefault(aid, {})

    def _ler_ficha(self, rel, aid) -> dict | None:
        """Abre a ficha da égua (registo clínico) e resume o que a colega deixou."""
        s, r = self.api("GET", f"/animais/{aid}/registos")
        if s != 200:
            return None
        hist = r.get("historico", [])
        maior, quando_maior, inducao, ovulou, ultimo = 0, None, None, False, None
        for h in hist:  # do mais recente para o mais antigo
            q = self._sim_dt(rel, h.get("data_registo"))
            if q is None:
                continue
            ultimo = ultimo or q
            if (rel.hoje - q.date()).days > 3:
                continue
            dados = h.get("dados") or {}
            tam = [f.get("tamanho", 0) for lado in ("OE", "OD") for f in (dados.get(lado) or {}).get("foliculos", [])]
            if tam and quando_maior is None:
                maior, quando_maior = max(tam), q
            ind = ((dados.get("TX") or {}).get("inducao") or {}).get("data")
            if ind and inducao is None:
                # Datas dentro do JSON do registo não recuam com o relógio da simulação:
                # usa-se o dia do registo e a hora escrita na indução.
                hi = _dt(ind)
                inducao = datetime.combine(q.date(), hi.time()) if hi else q
            if (dados.get("OVU") or {}).get("ovulacao") == "sim":
                ovulou = True
        return {
            "pede": r.get("pede") or {},
            "garanhao": r.get("garanhao"),
            "maior": maior,
            "quando_maior": quando_maior,
            "inducao": inducao,
            "ovulou": ovulou,
            "ultimo": ultimo,
        }

    def _inseminada_desde(self, rel, aid, desde: date) -> bool:
        if not self.memoria.get("nota_hora"):
            self.memoria["nota_hora"] = True
            self.nota("O historial reprodutivo mostra a data da inseminação mas não a hora: para saber se a colega inseminou antes ou depois da indução/ovulação tenho de adivinhar.")
        s, rep = self.api("GET", f"/animais/{aid}/reprodutivo")
        if s != 200:
            return False
        for i in rep.get("inseminacoes", []):
            d = _d(i.get("data_inseminacao"))
            if d and rel.simulado(d) >= desde:
                return True
        return False

    # ── dia ──────────────────────────────────────────────────────────────
    def dia(self, rel):
        fds = rel.hoje.weekday() >= 5
        self.memoria["turno"] = {"fds": fds, "hora": datetime.combine(rel.hoje, time(9 if fds else 14, 0)), "fim": datetime.combine(rel.hoje, time(19, 0))}
        # O que ficou por registar ontem (inseminações) — regista agora, à chegada.
        self._registar_pendentes(rel, so_de_hoje=False)
        if fds:
            self.api("POST", "/trabalho/gerar")  # o ecrã do Trabalho diário faz isto ao abrir
        s, trab = self.api("GET", "/trabalho")
        trab = trab if s == 200 else {}
        tarefas: dict[int, list[dict]] = {}
        for t in trab.get("por_fazer", []) + trab.get("atrasadas", []):
            tarefas.setdefault(t["animal_id"], []).append(t)
        feitas_hoje = {t["animal_id"]: t for t in trab.get("feitas", [])}
        s, r = self.api("GET", "/estadias/internadas", params={"tipo_animal": "egua"})
        eguas = {x["animal_id"]: x for x in (r or {}).get("itens", [])} if s == 200 else {}
        # Esquece as éguas que já saíram.
        for aid in list(self.memoria.get("eguas", {})):
            if aid not in eguas:
                self.memoria["eguas"].pop(aid)

        if fds:
            fila = self._fila_fim_de_semana(rel, eguas, tarefas)
        else:
            fila = self._fila_tarde(rel, eguas, tarefas, feitas_hoje)

        sobrou = []
        for aid, ficha, motivo in fila:
            turno = self.memoria["turno"]
            if turno["hora"] >= turno["fim"]:
                sobrou.append((aid, motivo))
                continue
            self._ver_egua(rel, aid, eguas[aid], ficha, tarefas.get(aid, []), motivo)
        if sobrou:
            nomes = ", ".join(eguas[a]["animal"] for a, _ in sobrou[:8])
            self.nota(f"Acabou o turno e ficaram {len(sobrou)} éguas por ver ({nomes}…). A app não me diz quais eram mais urgentes além da urgência da tarefa.")
        # Fim do turno: regista as inseminações que deixou para o fim.
        self._registar_pendentes(rel, so_de_hoje=True)

    # ── quem ver ─────────────────────────────────────────────────────────
    def _fila_tarde(self, rel, eguas, tarefas, feitas_hoje):
        """Tarde de dia útil: as que a colega deixou por fazer, as que ela viu
        de manhã com folículo grande/indução, e as que ele próprio está a seguir."""
        fila, vistas = [], set()
        candidatas = []
        for aid in eguas:
            mem = self.memoria.get("eguas", {}).get(aid, {})
            seguir = mem.get("seguir_ate") is not None and mem["seguir_ate"] >= rel.d
            if aid in tarefas or aid in feitas_hoje or seguir:
                candidatas.append(aid)
        for aid in candidatas:
            ficha = self._ler_ficha(rel, aid)
            if ficha is None:
                continue
            mem = self._egua_mem(aid)
            ind = ficha["inducao"] or mem.get("inducao")
            motivo = None
            if aid in tarefas:
                tipos = {t["tipo"] for t in tarefas[aid]}
                # Tarefas de hoje que a manhã não fechou.
                motivo = "tarefa:" + ",".join(sorted(tipos))
            if ind and timedelta(hours=14) <= (datetime.combine(rel.hoje, time(14)) - ind) <= timedelta(hours=40):
                motivo = "inseminar?"  # indução ontem: confirmar se foi inseminada
            elif ind and ind.date() == rel.hoje:
                motivo = motivo or "inducao_hoje"  # só para saber; insemina-se amanhã
            elif ficha["maior"] >= 33 and ficha["quando_maior"] and ficha["quando_maior"].date() == rel.hoje and not ind:
                motivo = motivo or "foliculo_grande"
            elif mem.get("seguir_ate", -1) >= rel.d:
                motivo = motivo or "seguir"
            if ind and ind.date() == rel.hoje and aid not in tarefas:
                # Induzida esta manhã: lembra-se para amanhã à tarde, mas não a vê hoje.
                mem["inducao"] = ind
                mem["seguir_ate"] = rel.d + 1
                continue
            if motivo and aid not in vistas:
                vistas.add(aid)
                fila.append((aid, ficha, motivo))
            # Passagem de turno: a manhã deixou uma égua com folículo grande, sem plano escrito.
            if motivo == "foliculo_grande" and self.r.random() < 0.15:
                self.nota(f"{eguas[aid]['animal']}: a colega viu folículo de {ficha['maior']} mm de manhã e não induziu; a app não diz se é para induzir/inseminar à tarde ou só observar.")
        prio = {"inseminar?": 0, "tarefa": 1, "foliculo_grande": 2, "seguir": 3}
        fila.sort(key=lambda x: prio.get(x[2].split(":")[0], 9))
        return fila

    def _fila_fim_de_semana(self, rel, eguas, tarefas):
        """Fim de semana: faz tudo, mas com muito trabalho salta éguas sem tarefa."""
        fila = []
        muitas = len(tarefas) > 15 or len(eguas) > 45
        for aid, x in eguas.items():
            ficha = self._ler_ficha(rel, aid)
            if ficha is None:
                continue
            mem = self._egua_mem(aid)
            ind = ficha["inducao"] or mem.get("inducao")
            dias_sem = (rel.hoje - ficha["ultimo"].date()).days if ficha["ultimo"] else 99
            if aid in tarefas:
                motivo = "tarefa:" + ",".join(sorted({t["tipo"] for t in tarefas[aid]}))
            elif ind and (datetime.combine(rel.hoje, time(9)) - ind) <= timedelta(hours=44):
                motivo = "inseminar?"
            elif ficha["maior"] >= 28 or mem.get("seguir_ate", -1) >= rel.d:
                motivo = "foliculo"
            elif dias_sem >= 2:
                motivo = "rotina"
            else:
                continue
            if motivo == "rotina" and muitas and self.r.random() < 0.6:
                continue  # sem tarefa e sem nada escrito que preocupe: fica para segunda
            fila.append((aid, ficha, motivo))
        prio = {"inseminar?": 0, "tarefa": 1, "foliculo": 2, "rotina": 3}
        fila.sort(key=lambda x: prio.get(x[2].split(":")[0], 9))
        if muitas:
            self.memoria["turno"]["muito_trabalho"] = True
        return fila

    # ── uma égua ─────────────────────────────────────────────────────────
    def _avancar_hora(self, minutos):
        self.memoria["turno"]["hora"] += timedelta(minutes=minutos)

    def _ver_egua(self, rel, aid, x, ficha, tarefas, motivo):
        turno = self.memoria["turno"]
        nome = x.get("animal")
        wid = self.mundo.wid_por_nome(nome)
        if wid is None or wid not in self.mundo.eguas:
            return
        mem = self._egua_mem(aid)
        tipos = {t["tipo"] for t in tarefas}
        apressado = turno["fds"] and turno.get("muito_trabalho")

        # Fim de semana cheio: tarefa de DG/ovulação fechada no botão, sem registo.
        if apressado and tipos and tipos <= (TAREFAS_DG | {"verificar_ovulacao"}) and motivo != "inseminar?" and self.r.random() < self.P_CONCLUIR_SEM_REGISTO:
            for t in tarefas:
                self.api("POST", f"/trabalho/{t['tarefa_id']}/concluir", json={"observacoes": "visto"})
            self._avancar_hora(3)
            return

        quando = turno["hora"]
        self._avancar_hora(10 if turno["fds"] else 12)
        ex = self.mundo.exame(wid, quando)
        foliculos = {k: [{"tamanho": max(9, min(61, f))} for f in ex["foliculos"][k]] for k in ("OE", "OD")}
        maior = max(ex["foliculos"]["OE"] + ex["foliculos"]["OD"] + [0])
        dados = {
            "OE": {"foliculos": foliculos["OE"]},
            "OD": {"foliculos": foliculos["OD"]},
            "UT": {"edema": ex["edema"], "liquido": ex["liquido"]},
            "CER": {"grau": ex["cervix"]},
        }
        sem_tempo = apressado and self.r.random() < self.P_SEM_TEMPO_AVALIAR
        pede = ficha.get("pede") or {}
        if pede.get("ovulacao") or "verificar_ovulacao" in tipos or ex["ovulou"] or ex["folic_hemorragico"]:
            if sem_tempo and pede.get("ovulacao"):
                dados["OVU"] = {"ovulacao": "nao_avaliado", "fh": "nao_avaliado"}
            else:
                dados["OVU"] = {"ovulacao": "sim" if ex["ovulou"] else "nao", "fh": "sim" if ex["folic_hemorragico"] else "nao"}
        if pede.get("dg") or tipos & TAREFAS_DG:
            v = ex["vesicula_embrionaria"]
            if sem_tempo or v is None:
                dados["DG"] = "Sem exame"
            else:
                dados["DG"] = "Positivo" if v else "Negativo"
            if v is None and not sem_tempo:
                self.nota(f"{nome}: tarefa de DG mas ainda não se vê nada na eco (ovulação recente?); pus 'Sem exame'. A app não me diz a data da ovulação para eu contar os dias.")

        ind = ficha["inducao"] or mem.get("inducao")
        # Inseminar: induzida há ~18-44 h e ainda sem inseminação desde a indução.
        if ind and not ex["corpo_luteo"] and timedelta(hours=14) <= (quando - ind) <= timedelta(hours=44):
            if not self._inseminada_desde(rel, aid, ind.date()) and not mem.get("insem_por_registar"):
                self._inseminar(rel, aid, wid, nome, ficha, quando + timedelta(minutes=20))
            mem.pop("inducao", None)
        elif ex["ovulou"] and not mem.get("insem_dia") in (rel.d, rel.d - 1) and ind and not self._inseminada_desde(rel, aid, ind.date()):
            self.nota(f"{nome}: já ovulou e não encontro inseminação registada desde a indução de {ind:%d/%m %H:%M}. Ou ninguém inseminou, ou foi feita e não está na app.")

        # Induzir: folículo pré-ovulatório com edema, ainda sem indução.
        induzir = maior >= 35 and ex["edema"] >= 2 and not ex["corpo_luteo"] and not (ind and (quando - ind) < timedelta(hours=48))
        if induzir:
            self.mundo.induzir(wid, quando)
            mem["inducao"] = quando
            mem["seguir_ate"] = rel.d + 2
            if self.r.random() < self.P_ESQUECE_INDUCAO:
                mem["inducao_nao_registada"] = rel.d  # fez, mas não ficou na app
            else:
                dados["TX"] = {"inducao": {"data": self._real_dt(rel, quando).isoformat(), "produto": "hCG"}}
        elif maior >= 30:
            mem["seguir_ate"] = rel.d + 1

        s, r = self.api("POST", f"/animais/{aid}/registos", json={"data_registo": self._real_dt(rel, quando).isoformat(), "dados": dados})
        if s == 422 and isinstance(r, dict):
            code = (r.get("detail") or {}).get("code", "")
            if "ovulation_required" in code:
                dados["OVU"] = {"ovulacao": "nao_avaliado", "fh": "nao_avaliado"}
            elif "dg_required" in code:
                dados["DG"] = "Sem exame"
            else:
                return
            self.api("POST", f"/animais/{aid}/registos", json={"data_registo": self._real_dt(rel, quando).isoformat(), "dados": dados})
            self.nota(f"{nome}: o registo pediu ovulação/DG que eu não sabia que estava pendente (a tarefa não estava na minha lista).")
        mem["ultimo_exame"] = rel.d
        mem["maior"] = maior

    # ── inseminação ──────────────────────────────────────────────────────
    def _garanhao(self, rel, wid, nome, ficha):
        g = ficha.get("garanhao")
        if g:
            return g
        cache = self.memoria.setdefault("garanhao_dono", {})
        if wid not in cache:
            cache[wid] = self.mundo.perfil_dono(wid)["garanhao"]  # telefona ao dono
            self.nota(f"{nome}: a ficha não diz o garanhão escolhido; tive de ligar ao dono.")
        return cache[wid]

    def _inseminar(self, rel, aid, wid, nome, ficha, quando):
        garanhao = self._garanhao(rel, wid, nome, ficha)
        s, lotes = self.api("GET", "/inseminacoes/lotes")
        cands = [l for l in (lotes or []) if (l.get("garanhao_nome") or "") == garanhao and int(l.get("existencia_atual") or 0) >= 2] if s == 200 else []
        if not cands:
            self.nota(f"{nome}: induzida e sem sémen de {garanhao} com 2 palhetas no stock — não inseminei. Ninguém me avisou que faltava.")
            return
        if self.r.random() < self.P_PRIMEIRO_LOTE:
            lote = cands[0]  # o primeiro da lista, à pressa
        else:
            lote = max(cands, key=lambda l: float(l.get("motilidade") or 0))
        # O código está na palheta (na app, só nas observações do lote, no Stock).
        s, det = self.api("GET", f"/stock/lotes/{lote['id']}")
        obs = ((det or {}).get("observacoes") or "") if s == 200 else ""
        codigo = next((t.strip(".,;") for t in obs.split() if t.startswith("LT-")), None)
        self.mundo.inseminar(wid, quando, codigo)
        mem = self._egua_mem(aid)
        mem["insem_dia"] = rel.d
        pend = {"aid": aid, "nome": nome, "garanhao": garanhao, "stock_id": lote["id"], "dia_sim": quando.date().isoformat(), "hora": quando.strftime("%H:%M")}
        x = self.r.random()
        if x < self.P_REGISTA_DIA_SEGUINTE:
            pend["registar_em"] = rel.d + 1
        elif x < self.P_REGISTA_DIA_SEGUINTE + self.P_REGISTA_FIM_TURNO:
            pend["registar_em"] = rel.d
        else:
            self._post_inseminacao(rel, pend, exata=True)
            return
        mem["insem_por_registar"] = True
        self.memoria.setdefault("pendentes", []).append(pend)

    def _post_inseminacao(self, rel, p, exata):
        hora = p["hora"]
        if not exata and self.r.random() < 0.5:
            # Já não se lembra bem: arredonda à hora (às vezes erra uma hora).
            h, m = map(int, hora.split(":"))
            h = min(19, max(7, h + (1 if m >= 30 else 0) + self.r.choice([0, 0, -1, 1])))
            hora = f"{h:02d}:00"
        dia_sim = date.fromisoformat(p["dia_sim"])
        s, r = self.api("POST", "/inseminacoes", json={
            "animal_id_egua": p["aid"], "garanhao": p["garanhao"], "data_inseminacao": rel.real(dia_sim).isoformat(),
            "hora_inseminacao": hora, "linhas": [{"stock_id": p["stock_id"], "palhetas": 2}],
        })
        if s >= 400:
            self.nota(f"{p['nome']}: não consegui registar a inseminação de {dia_sim:%d/%m} {hora} (erro {s}).")
        elif dia_sim < self.mundo_hoje(rel):
            self.nota(f"{p['nome']}: registei hoje a inseminação de ontem ({hora}); até agora não estava na app para quem viesse a seguir.")

    def mundo_hoje(self, rel):
        return rel.hoje

    def _registar_pendentes(self, rel, so_de_hoje):
        ficam = []
        for p in self.memoria.get("pendentes", []):
            if p["registar_em"] <= rel.d and (not so_de_hoje or p["registar_em"] == rel.d):
                self._post_inseminacao(rel, p, exata=False)
                self.memoria.get("eguas", {}).get(p["aid"], {}).pop("insem_por_registar", None)
            else:
                ficam.append(p)
        self.memoria["pendentes"] = ficam
