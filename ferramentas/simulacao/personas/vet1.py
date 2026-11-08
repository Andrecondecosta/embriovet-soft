"""Dra. Marta — veterinária sénior de reprodução (vet1).

15 anos de experiência, meticulosa. Segunda a sexta, 8h-13h (de tarde e ao
fim de semana é o colega júnior). Começa pelo Trabalho diário e pela lista
de internadas, abre a ficha de cada égua (registo clínico + reprodutivo) e
decide pelo que a app mostra e pelo que vê na ecografia.

Hábitos humanos:
- dia cheio (muitas ecografias): deixa parte dos registos para o fim da
  manhã; muitas vezes fica a hora a que escreve, não a do exame;
- ≈2 %: regista o exame na ficha da égua da box ao lado;
- só tem a manhã: não consegue ver de 12 em 12 h perto da ovulação;
- se a manhã não chega, as éguas de rotina ficam para amanhã.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from simcore import LOG, Pessoa, Relogio

TAREFAS_DG = {"diagnostico_gestacao", "confirmacao_gestacao", "segunda_confirmacao"}
MIN_EXAME = 8  # minutos por ecografia (com a deslocação entre boxes)
MIN_INSEM = 20  # descongelar + inseminar
FIM_MANHA = 13 * 60


def _dt(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", ""))
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(str(s)[:10]), time(0))
        except ValueError:
            return None


class Marta(Pessoa):
    papel = "vet1"
    nome = "marta"
    ordem = 3

    def __init__(self, mundo):
        super().__init__(mundo)
        self.rng = random.Random(1508)
        self.notas_feitas: set[str] = set()

    # ── utilidades ───────────────────────────────────────────────────────
    def nota1(self, chave, texto, **extra):
        """Nota que a pessoa só faria uma vez (queixa recorrente)."""
        if chave not in self.notas_feitas:
            self.notas_feitas.add(chave)
            self.nota(texto, **extra)

    def _sim(self, rel: Relogio, dt_real: datetime | None) -> datetime | None:
        if dt_real is None:
            return None
        return datetime.combine(rel.simulado(dt_real.date()), dt_real.time())

    def _real(self, rel: Relogio, dt_sim: datetime) -> datetime:
        return datetime.combine(rel.real(dt_sim.date()), dt_sim.time())

    @staticmethod
    def _maior(dados: dict) -> int:
        fs = [f.get("tamanho", 0) for k in ("OE", "OD") for f in (dados.get(k) or {}).get("foliculos", [])]
        return max(fs + [0])

    # ── o dia ────────────────────────────────────────────────────────────
    def dia(self, rel):
        if rel.hoje.weekday() >= 5:
            return  # fim de semana é o colega
        self.minuto = 8 * 60
        self.adiados: list[tuple] = []
        # 1) Trabalho diário (o ecrã gera as 1.as observações ao abrir).
        self.api("POST", "/trabalho/gerar")
        s, trab = self.api("GET", "/trabalho")
        trab = trab if s == 200 else {}
        tarefas: dict[int, list[dict]] = {}
        for t in trab.get("por_fazer", []) + trab.get("atrasadas", []):
            tarefas.setdefault(t["animal_id"], []).append(t)
        # 2) Internadas.
        s, r = self.api("GET", "/estadias/internadas")
        internadas = (r or {}).get("itens", []) if s == 200 else []
        eguas = [x for x in internadas if x.get("animal_tipo") == "egua"]
        eguas.sort(key=lambda x: (x.get("alojamento_nome") or "zzz", x.get("animal") or ""))
        if any(x.get("animal_tipo") == "receptora" for x in internadas):
            self.nota1("receptoras", "Tenho receptoras internadas mas nada no Trabalho diário me diz o que fazer com elas (sincronização com dadoras?).")

        # 3) Abre a ficha de cada égua e decide quem vê hoje.
        plano = []
        for i, x in enumerate(eguas):
            aid = x["animal_id"]
            s, reg = self.api("GET", f"/animais/{aid}/registos")
            if s != 200:
                continue
            s, rep = self.api("GET", f"/animais/{aid}/reprodutivo")
            rep = rep if s == 200 else {"inseminacoes": []}
            info = self._ler_ficha(rel, x, reg, rep, tarefas.get(aid, []))
            info["vizinha"] = eguas[i + 1] if i + 1 < len(eguas) else (eguas[i - 1] if i else None)
            pri = self._prioridade(rel, info)
            if pri is not None:
                plano.append((pri, i, info))
        plano.sort(key=lambda p: (p[0], p[1]))

        dia_cheio = len(plano) >= 18
        nao_vistas = []
        for pri, _, info in plano:
            if self.minuto + MIN_EXAME > FIM_MANHA - (15 if dia_cheio else 0):
                if pri >= 3:
                    nao_vistas.append(info["nome"])
                    continue
                # Tarefas e éguas em cio vê-as mesmo que passe da hora.
            self._examinar(rel, info, dia_cheio)
        if nao_vistas:
            self.nota(f"Não deu tempo para {len(nao_vistas)} éguas de rotina (ficam para amanhã).", eguas=nao_vistas[:10])

        # 4) Fim da manhã: os registos que ficaram por passar.
        self.minuto = max(self.minuto, 12 * 60 + 30)
        for aid, dados, hora_exame, prioritario, nome in self.adiados:
            hora_escrita = datetime.combine(rel.hoje, time(min(self.minuto // 60, 13), self.minuto % 60))
            # Na maior parte das vezes fica a hora a que está a escrever (o ecrã sugere "agora").
            quando = hora_escrita if self.rng.random() < 0.7 else hora_exame
            self._gravar(rel, aid, dados, quando, prioritario, nome)
            self.minuto += 3

        # 5) Tarefas em atraso que o registo não fecha (ex.: indução já feita).
        s, trab = self.api("GET", "/trabalho")
        for t in (trab or {}).get("atrasadas", []) if s == 200 else []:
            if t["tipo"] == "tratamento" and (t.get("motivo") or "").startswith("Indução"):
                self.api("POST", f"/trabalho/{t['tarefa_id']}/concluir", json={"observacoes": "Indução feita no dia"})

    # ── leitura da ficha ─────────────────────────────────────────────────
    def _ler_ficha(self, rel, x, reg, rep, tarefas):
        hist = [h for h in reg.get("historico", []) if not h.get("antigo")]
        ultimo = hist[0] if hist else None
        ult_dt = self._sim(rel, _dt(ultimo["data_registo"])) if ultimo else None
        # Última indução escrita no registo (minha ou do colega).
        inducao = None
        for h in hist:
            ind = ((h.get("dados") or {}).get("TX") or {}).get("inducao")
            if ind:
                # Dia = o do registo (o campo da indução é texto dentro do registo); hora = a escrita na indução.
                d_reg, d_ind = self._sim(rel, _dt(h["data_registo"])), _dt(ind.get("data"))
                if d_reg and d_ind:
                    inducao = datetime.combine(d_reg.date(), d_ind.time())
                break
        ins = [i for i in rep.get("inseminacoes", []) if i.get("data_inseminacao")]
        ins.sort(key=lambda i: str(i["data_inseminacao"]), reverse=True)
        ult_ins = ins[0] if ins else None
        ult_ins_dia = rel.simulado(date.fromisoformat(str(ult_ins["data_inseminacao"])[:10])) if ult_ins else None
        # Edema do registo anterior com edema >= 2 (para ver a descida antes da ovulação).
        edema_ant = max([((h.get("dados") or {}).get("UT") or {}).get("edema", 0) for h in hist[:2]] + [0])
        return {
            "aid": x["animal_id"], "nome": x.get("animal"), "box": x.get("alojamento_nome"),
            "tarefas": tarefas, "tipos": {t["tipo"] for t in tarefas}, "pede": reg.get("pede") or {},
            "garanhao_app": reg.get("garanhao"), "ultimo": ultimo, "ult_dt": ult_dt,
            "ult_maior": self._maior((ultimo or {}).get("dados") or {}),
            "ult_edema": (((ultimo or {}).get("dados") or {}).get("UT") or {}).get("edema", 0),
            "edema_ant": edema_ant, "inducao": inducao, "ult_ins": ult_ins, "ult_ins_dia": ult_ins_dia,
        }

    def _prioridade(self, rel, f):
        """0 = urgente/tarefa, 1 = indução recente, 2 = cio, 3 = rotina; None = hoje não."""
        hoje = rel.hoje
        agora = datetime.combine(hoje, time(8))
        ins, dia_ins = f["ult_ins"], f["ult_ins_dia"]
        if f["tarefas"]:
            return 0
        if f["inducao"] and timedelta(0) < agora - f["inducao"] <= timedelta(hours=50) and not (dia_ins and dia_ins >= f["inducao"].date()):
            return 1
        if ins and ins["resultado"] == "pendente":
            d = (hoje - dia_ins).days
            # Inseminada: deixo-a em paz até ao DG (D+14); se a tarefa se perdeu, faço-o na mesma.
            return 0 if d >= 14 else None
        if ins and ins["resultado"] == "gestacao_confirmada":
            d = (hoje - dia_ins).days
            etapa = ins.get("etapa")
            if (etapa == "D+28" and d >= 29) or (etapa == "D+45" and 46 <= d <= 60):
                return 0  # a confirmação devia ter aparecido no Trabalho diário
            return None
        if not f["ultimo"]:
            return 0
        dias = (hoje - f["ult_dt"].date()).days
        if f["ult_maior"] >= 30 or f["ult_edema"] >= 2:
            return 2 if dias >= 1 else None
        intervalo = 2 if f["ult_maior"] >= 25 else self.rng.choice([2, 3, 3])
        return 3 if dias >= intervalo else None

    # ── exame ────────────────────────────────────────────────────────────
    def _examinar(self, rel, f, dia_cheio):
        aid, wid = f["aid"], self.mundo.wid_por_nome(f["nome"])
        if wid is None or wid not in self.mundo.eguas:
            return
        hora_exame = datetime.combine(rel.hoje, time(self.minuto // 60, self.minuto % 60))
        self.minuto += MIN_EXAME
        ex = self.mundo.exame(wid, hora_exame)
        maior = max(ex["foliculos"]["OE"] + ex["foliculos"]["OD"] + [0])

        def ovario(lst, lado):
            return {"foliculos": [{"tamanho": max(9, min(61, n))} for n in lst]}

        dados = {
            "OE": ovario(ex["foliculos"]["OE"], "OE"),
            "OD": ovario(ex["foliculos"]["OD"], "OD"),
            "UT": {"edema": ex["edema"], "liquido": min(ex["liquido"], 4)},
            "CER": {"grau": ex["cervix"]},
        }
        if ex["corpo_luteo"]:
            dados["OD" if self.rng.random() < 0.5 else "OE"]["comentario"] = "CL"
        tx: dict = {}

        # Ovulação: o D+1 pede-a; e escrevo-a sempre que a vejo.
        if f["pede"].get("ovulacao") or "verificar_ovulacao" in f["tipos"] or ex["ovulou"] or ex["folic_hemorragico"]:
            dados["OVU"] = {"ovulacao": "sim" if ex["ovulou"] else "nao", "fh": "sim" if ex["folic_hemorragico"] else "nao"}

        # DG: tarefa do dia, ou inseminação pendente/positiva cuja etapa já chegou.
        ins = f["ult_ins"]
        quer_dg = bool(f["tipos"] & TAREFAS_DG) or f["pede"].get("dg")
        if ins and ins["resultado"] in ("pendente", "gestacao_confirmada") and (rel.hoje - f["ult_ins_dia"]).days >= 14:
            quer_dg = quer_dg or ins["resultado"] == "pendente" or (rel.hoje - f["ult_ins_dia"]).days in range(27, 61)
        if quer_dg and not (ins and (rel.hoje - f["ult_ins_dia"]).days >= 12):
            quer_dg = bool(f["pede"].get("dg"))  # tarefa sem inseminação que se veja: respondo o que vejo
        dg = None
        if quer_dg:
            v = ex["vesicula_embrionaria"]
            dg = "Inconclusivo" if v is None else "Positivo" if v else "Negativo"
            dados["DG"] = dg
            if dg == "Negativo":
                tx["pg"] = 1  # encurtar o diestro para voltar ao cio

        # Indução: folículo >= 35 mm com edema, sem CL, e ainda não induzida neste ciclo.
        prioritario = False
        ja_induzida = f["inducao"] and (hora_exame - f["inducao"]) < timedelta(days=5)
        ja_inseminada = f["ult_ins_dia"] and (rel.hoje - f["ult_ins_dia"]).days < 5
        if maior >= 35 and ex["edema"] >= 2 and not ex["corpo_luteo"] and not ex["ovulou"] and not ja_induzida and not ja_inseminada and dg is None:
            produto = "Deslorelina" if self.memoria.get(("hcg", aid), 0) >= 2 else "hCG"
            self.memoria[("hcg", aid)] = self.memoria.get(("hcg", aid), 0) + (produto == "hCG")
            tx["inducao"] = {"data": self._real(rel, hora_exame).isoformat(), "produto": produto}
            self.mundo.induzir(wid, hora_exame)
            if rel.hoje.weekday() == 4:
                prioritario = True
                self.nota1(
                    "sexta",
                    "Induzi à sexta: a inseminação é amanhã e é o colega. Não há forma de deixar na app uma tarefa "
                    "'inseminar amanhã às X h' — só marco '!' e espero que ele leia o registo.",
                    egua=f["nome"],
                )
        if tx:
            dados["TX"] = tx

        # Inseminação.
        inseminar, pos_ov = False, False
        if not ja_inseminada and dg is None:
            if f["inducao"] and not ja_induzida_hoje(tx):
                h = (hora_exame - f["inducao"]).total_seconds() / 3600
                if 14 <= h <= 48 and not ex["corpo_luteo"] and not ex["ovulou"]:
                    inseminar = True
                elif ex["ovulou"] and 30 <= h <= 44:
                    inseminar, pos_ov = True, True
            # Sem indução (ou indução que falhou): folículo grande e o edema a cair = ovulação iminente.
            if not inseminar and "inducao" not in tx and maior >= 38 and ex["edema"] <= 1 and f["edema_ant"] >= 2 and not ex["corpo_luteo"] and not ex["ovulou"]:
                inseminar = True
        if ex["ovulou"] and not ja_inseminada and not inseminar and f["inducao"] and (hora_exame - f["inducao"]) < timedelta(days=4):
            self.nota(f"{f['nome']}: já ovulou e ninguém inseminou depois da indução — ciclo perdido.", egua=f["nome"])
        if pos_ov:
            self.nota1("posov", "Inseminei depois da ovulação (dentro das 6-12 h?) — a app não me diz a que horas foi a indução do colega nem quem a fez, tive de ir ao registo.")

        # Gravar (ou deixar para o fim da manhã).
        alvo, alvo_nome = aid, f["nome"]
        if self.rng.random() < 0.02 and f.get("vizinha"):
            alvo, alvo_nome = f["vizinha"]["animal_id"], f["vizinha"]["animal"]
            LOG("verdade", evento="registo_egua_trocada", pessoa=self.nome, examinada=f["nome"], registada=alvo_nome)
            s, rv = self.api("GET", f"/animais/{alvo}/registos")
            pede_v = (rv or {}).get("pede", {}) if s == 200 else {}
            # O ecrã da outra égua pede o que ela precisa; respondo com o que vi.
            if pede_v.get("ovulacao") and "OVU" not in dados:
                dados["OVU"] = {"ovulacao": "sim" if ex["ovulou"] or ex["corpo_luteo"] else "nao", "fh": "nao"}
            if pede_v.get("dg") and "DG" not in dados:
                v = ex["vesicula_embrionaria"]
                dados["DG"] = "Sem exame" if v is None else "Positivo" if v else "Negativo"
                self.nota("O ecrã pediu um DG a uma égua que eu achava não estar para DG; pus o que vi.", egua=alvo_nome)
        else:
            # Ecrã da própria égua: se pedir algo que não tenho, respondo.
            if f["pede"].get("ovulacao") and "OVU" not in dados:
                dados["OVU"] = {"ovulacao": "nao_avaliado", "fh": "nao_avaliado"}
            if f["pede"].get("dg") and "DG" not in dados:
                dados["DG"] = "Sem exame"
                self.nota("A app obrigou-me a responder DG ('Sem exame') a uma égua sem inseminação visível para DG.", egua=f["nome"])

        if inseminar:
            # A inseminação regista-se logo (as palhetas saem do contentor agora).
            self._inseminar(rel, f, wid, hora_exame + timedelta(minutes=MIN_EXAME + 5))
        if dia_cheio and "TX" not in dados and "DG" not in dados and self.rng.random() < 0.35:
            self.adiados.append((alvo, dados, hora_exame, prioritario, alvo_nome))
        else:
            self._gravar(rel, alvo, dados, hora_exame, prioritario, alvo_nome)

    def _gravar(self, rel, aid, dados, quando_sim, prioritario, nome):
        s, r = self.api("POST", f"/animais/{aid}/registos", json={
            "data_registo": self._real(rel, quando_sim).isoformat(), "dados": dados, "prioritario": prioritario,
        })
        if s == 422 and isinstance(r, dict):
            code = (r.get("detail") or {}).get("code", "") if isinstance(r.get("detail"), dict) else ""
            if "ovulation_required" in code:
                dados["OVU"] = {"ovulacao": "nao_avaliado", "fh": "nao_avaliado"}
            elif "dg_required" in code:
                dados["DG"] = "Sem exame"
            else:
                return
            self.nota("Registo recusado: a app pediu um campo que eu não tinha preenchido (registo atrasado, a tarefa mudou entretanto).", egua=nome, code=code)
            self.api("POST", f"/animais/{aid}/registos", json={
                "data_registo": self._real(rel, quando_sim).isoformat(), "dados": dados, "prioritario": prioritario,
            })

    # ── inseminação ──────────────────────────────────────────────────────
    def _garanhao(self, f, wid):
        g = f.get("garanhao_app")
        if g:
            return g
        cache = self.memoria.setdefault("garanhao", {})
        if f["aid"] not in cache:
            # Não está na app: telefono ao dono (ou vou à folha da receção).
            cache[f["aid"]] = self.mundo.perfil_dono(wid)["garanhao"]
            self.nota1(
                "garanhao",
                "A ficha/registo da égua não mostra o garanhão pedido pelo dono (a receção escreveu-o nas observações "
                "de entrada, que eu não vejo). Tive de ligar ao dono.",
            )
        return cache[f["aid"]]

    def _inseminar(self, rel, f, wid, quando_sim):
        garanhao = self._garanhao(f, wid)
        s, r = self.api("GET", "/stock/lotes", params={"garanhao": garanhao, "min_palhetas": 2})
        lotes = (r or {}).get("items", []) if s == 200 else []
        if not lotes:
            self.nota(f"Sem sémen de {garanhao} com 2 palhetas para {f['nome']} — égua pronta e não insemino.", egua=f["nome"])
            return

        def mot(l):
            try:
                return float(str(l.get("motilidade") or 0).replace(",", "."))
            except ValueError:
                return 0.0

        lote = max(lotes, key=mot)
        if not mot(lote):
            self.nota1("sem_mot", f"Lotes de {garanhao} sem motilidade registada: escolho às cegas.")
        if not lote.get("observacoes"):
            s, ficha = self.api("GET", f"/stock/lotes/{lote['id']}")
            lote = {**lote, **(ficha if s == 200 and isinstance(ficha, dict) else {})}
        codigo = next((t.strip(".,;") for t in str(lote.get("observacoes") or "").split() if t.startswith("LT-")), None)
        self.minuto += MIN_INSEM
        self.mundo.inseminar(wid, quando_sim, codigo)
        hora_digitada = quando_sim if self.rng.random() < 0.9 else quando_sim + timedelta(minutes=self.rng.choice([30, 60, 90]))
        s, _ = self.api("POST", "/inseminacoes", json={
            "animal_id_egua": f["aid"], "garanhao": garanhao,
            "data_inseminacao": rel.real(quando_sim.date()).isoformat(),
            "hora_inseminacao": hora_digitada.strftime("%H:%M"),
            "linhas": [{"stock_id": lote["id"], "palhetas": 2}],
        })
        if s != 201:
            self.nota(f"Não consegui registar a inseminação de {f['nome']} (HTTP {s}); fica no papel.", egua=f["nome"])
        self.nota1(
            "ficha_ins",
            "No reprodutivo da égua vejo a data da inseminação mas não a hora nem quem inseminou — para decidir a "
            "repetição tenho de perguntar ao colega.",
        )


def ja_induzida_hoje(tx: dict) -> bool:
    return "inducao" in tx
