"""Dra. Sofia — diretora clínica e sócia. Gere a clínica pela app.

Rotina:
- Manhãs (falha ~20 %, ~35 % em junho/julho; férias na 2.ª semana de agosto;
  domingos raramente): Dashboard + Trabalho diário. Tarefas em atraso:
  decide com critério (DG nunca é cancelado sem perceber porquê).
- Segunda: ponto da semana (internadas, gestações, inseminações, stock a
  acabar) + controlo de qualidade dos dados das éguas internadas.
- Início do mês: Relatórios/Exportar (stock, inseminações por garanhão),
  taxa de gestação e palhetas por gestação, proprietários duplicados,
  lotes externos sem motilidade.
- Às vezes um dono importante liga: abre o historial da égua na app.

Hábitos humanos: às vezes cancela em lote tarefas antigas de observação
(e, com pressa, também uma "verificar ovulação" antiga sem ver o diário);
deixa passar dias; só regista cada achado uma vez.
"""

from __future__ import annotations

import random
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta

from simcore import HOJE_REAL, Pessoa

TIPOS_DG = {"diagnostico_gestacao", "confirmacao_gestacao", "segunda_confirmacao"}
TIPOS_OBS = {"primeira_observacao", "observacao_clinica", "observacao"}


def _d(v) -> date | None:
    if not v:
        return None
    return date.fromisoformat(str(v)[:10])


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.replace("—", " ").replace("-", " ").replace(".", " ").split())


class Direcao(Pessoa):
    papel = "direcao"
    nome = "sofia"
    ordem = 5
    nivel = "Administrador"

    def __init__(self, mundo):
        super().__init__(mundo)
        self.rng = random.Random(5050)
        self.memoria.update(achados=set(), semana=[], mes={}, cache={})

    # ── utilitários ────────────────────────────────────────────────────
    def _sim(self, v) -> str:
        """Data da app (real) → data simulada, para as notas."""
        d = _d(v)
        return self.rel.simulado(d).strftime("%d/%m/%Y") if d else "?"

    def _achado(self, chave, texto, **extra):
        """Regista um achado só uma vez (a Sofia lembra-se do que já viu)."""
        if chave in self.memoria["achados"]:
            return False
        self.memoria["achados"].add(chave)
        self.nota(texto, **extra)
        return True

    def _get(self, caminho, params=None):
        """Leitura com cache do próprio dia (abrir a mesma ficha duas vezes)."""
        k = (caminho, tuple(sorted((params or {}).items())))
        c = self.memoria["cache"]
        if k not in c:
            s, r = self.api("GET", caminho, params=params)
            c[k] = r if s == 200 else None
        return c[k]

    # ── dia ────────────────────────────────────────────────────────────
    def dia(self, rel):
        self.rel = rel
        self.memoria["cache"] = {}
        hoje = rel.hoje
        if hoje.month == 8 and 9 <= hoje.day <= 15:  # férias
            return
        falha = 0.35 if hoje.month in (6, 7) else 0.20
        if hoje.weekday() == 6:
            falha = 0.85
        segunda = hoje.weekday() == 0
        inicio_mes = hoje.day <= 3 and not self.memoria["mes"].get((hoje.year, hoje.month))
        # À segunda e no fecho do mês é mais difícil faltar (é agenda dela).
        if self.rng.random() < falha and not (segunda and self.rng.random() < 0.7):
            if inicio_mes and hoje.day == 3:
                pass  # o relatório mensal não pode esperar mais
            else:
                return

        self._manha(rel)
        if segunda or (hoje.weekday() == 1 and not self._semana_feita(rel)):
            self._ponto_semana(rel)
        if inicio_mes and hoje.weekday() < 6:
            self._fecho_mes(rel)
        if self.rng.random() < 0.25:
            self._telefonema(rel)

    def _semana_feita(self, rel):
        return rel.hoje.isocalendar()[:2] in self.memoria["semana"]

    # ── manhã ──────────────────────────────────────────────────────────
    def _internadas(self):
        r = self._get("/estadias/internadas") or {}
        return {x["animal_id"]: x for x in r.get("itens", [])}

    def _manha(self, rel):
        dash = self._get("/dashboard") or {}
        cli = dash.get("clinica") or {}
        if cli.get("tarefas_urgentes", 0) > 15:
            self._achado(("muitas_urgentes", rel.hoje.isocalendar()[1]),
                         f"Dashboard com {cli['tarefas_urgentes']} tarefas urgentes hoje ({rel.hoje:%d/%m}); "
                         "não diz quem as vai fazer.")
        trab = self._get("/trabalho") or {}
        atrasadas = trab.get("atrasadas", [])
        if not atrasadas:
            return
        internadas = self._internadas()
        # Dia de "limpeza" em lote (pressa): ~15 % das manhãs.
        em_lote = self.rng.random() < 0.15
        tratadas = 0
        for t in atrasadas:
            if tratadas >= 25:  # não tem a manhã toda
                break
            if t["dias_atraso"] < 2:
                continue
            tratadas += 1
            try:
                self._decidir(rel, t, internadas, em_lote)
            except Exception as e:  # um erro numa tarefa não estraga a manhã
                self.nota(f"(erro ao decidir tarefa {t.get('tarefa_id')}: {e!r})")

    def _decidir(self, rel, t, internadas, em_lote):
        tid, tipo, aid, atraso = t["tarefa_id"], t["tipo"], t["animal_id"], t["dias_atraso"]
        animal = t.get("animal") or f"animal {aid}"
        quando = self._sim(t.get("data_tarefa"))

        # 1) A égua já saiu e a tarefa ficou aberta.
        if aid not in internadas:
            if tipo in TIPOS_DG:
                n = self.memoria["n_saida_dg"] = self.memoria.get("n_saida_dg", 0) + 1
                if n > 3:  # já percebeu o padrão: só conta
                    self.api("POST", f"/trabalho/{tid}/cancelar")
                    return
                self._achado(("saida_dg", tid),
                             f"{animal} saiu da clínica com {tipo} de {quando} por fazer ({atraso} d em atraso). "
                             "A app deixou dar saída sem avisar do DG pendente. Cancelo — fica sem diagnóstico na clínica.",
                             animal=animal, tarefa=tid)
            else:
                self._achado(("saida_tarefa", aid),
                             f"{animal} já saiu mas tinha tarefa '{tipo}' de {quando} aberta no Trabalho diário. "
                             "A saída da estadia não fecha as tarefas.", animal=animal, tarefa=tid)
            self.api("POST", f"/trabalho/{tid}/cancelar")
            return

        # 2) Limpeza em lote: observações antigas fora sem ver.
        if em_lote and tipo in TIPOS_OBS and atraso >= 5:
            self.api("POST", f"/trabalho/{tid}/cancelar")
            return
        if em_lote and tipo == "verificar_ovulacao" and atraso >= 4 and self.rng.random() < 0.5:
            # Com pressa: "isto já passou" (erro humano: não abre o diário).
            self.api("POST", f"/trabalho/{tid}/cancelar")
            return

        # 3) Com critério: abrir a ficha.
        if tipo in TIPOS_DG:
            self._decidir_dg(rel, t, animal, quando)
        elif tipo == "verificar_ovulacao":
            regs = self._registos_desde(aid, t.get("data_tarefa"))
            if any((r["dados"].get("OVU") or {}).get("ovulacao") in ("sim", "nao") for r in regs):
                self.api("POST", f"/trabalho/{tid}/concluir", json={"observacoes": "Ovulação registada no diário (fecho pela direção)"})
                self._achado(("ovu_nao_fechou", aid, quando),
                             f"{animal}: a ovulação está no diário depois de {quando}, mas a tarefa 'verificar ovulação' ficou aberta.")
            elif atraso >= 4:
                self._achado(("ovu_perdida", tid),
                             f"{animal}: 'verificar ovulação' de {quando} nunca foi registada ({atraso} d). "
                             "Já não se pode confirmar; cancelo.", animal=animal)
                self.api("POST", f"/trabalho/{tid}/cancelar")
        elif tipo in TIPOS_OBS:
            regs = self._registos_desde(aid, t.get("data_tarefa"))
            if regs:
                self.api("POST", f"/trabalho/{tid}/concluir", json={"observacoes": "Já observada (há registo clínico)"})
            elif atraso >= 7:
                self.api("POST", f"/trabalho/{tid}/cancelar")
        elif tipo == "tratamento":
            regs = self._registos_desde(aid, t.get("data_tarefa"))
            if any(r["dados"].get("TX") for r in regs):
                self.api("POST", f"/trabalho/{tid}/concluir", json={"observacoes": "Tratamento no diário"})
            elif atraso >= 5:
                self._achado(("tx_sem_registo", tid),
                             f"{animal}: tratamento marcado para {quando} ({t.get('motivo') or '-'}) sem registo; cancelo.")
                self.api("POST", f"/trabalho/{tid}/cancelar")
        else:  # colheitas e outras: deixa estar até ficar mesmo velho
            if atraso >= 14:
                self.api("POST", f"/trabalho/{tid}/cancelar")

    def _registos_desde(self, aid, data_tarefa):
        r = self._get(f"/animais/{aid}/registos") or {}
        desde = _d(data_tarefa)
        return [x for x in r.get("historico", []) if desde and _d(x.get("data_registo")) and _d(x["data_registo"]) >= desde]

    def _decidir_dg(self, rel, t, animal, quando):
        """Nunca cancela um DG sem perceber porquê."""
        tid, aid, atraso = t["tarefa_id"], t["animal_id"], t["dias_atraso"]
        rep = self._get(f"/animais/{aid}/reprodutivo") or {}
        ins = rep.get("inseminacoes", [])
        desde = _d(t.get("data_tarefa"))
        # Inseminação a que este DG se refere: a mais recente antes da data da tarefa.
        antes = [i for i in ins if _d(i.get("data_inseminacao")) and _d(i["data_inseminacao"]) <= desde]
        depois = [i for i in ins if _d(i.get("data_inseminacao")) and _d(i["data_inseminacao"]) > desde]
        alvo = antes[0] if antes else None
        if depois:
            # Já foi reinseminada: o DG antigo deixou de fazer sentido.
            txt = (f"{animal}: DG de {quando} nunca registado e a égua já foi inseminada outra vez em "
                   f"{self._sim(depois[-1]['data_inseminacao'])}. ")
            if alvo and alvo.get("resultado") == "pendente":
                txt += f"A inseminação de {self._sim(alvo['data_inseminacao'])} continua 'pendente' para sempre (conta mal na taxa)."
            self._achado(("dg_reinsem", tid), txt, animal=animal)
            self.api("POST", f"/trabalho/{tid}/cancelar")
            return
        if alvo is None:
            self._achado(("dg_sem_insem", tid), f"{animal}: tarefa {t['tipo']} de {quando} sem inseminação na ficha?")
            return
        etapa_tarefa = {"diagnostico_gestacao": "D+14", "confirmacao_gestacao": "D+28", "segunda_confirmacao": "D+45"}[t["tipo"]]
        res = alvo.get("resultado")
        if res == "falhou" or (res == "gestacao_confirmada" and alvo.get("etapa") != etapa_tarefa):
            # O resultado já está na ficha (por outro caminho); a tarefa é que não fechou.
            self.api("POST", f"/trabalho/{tid}/concluir", json={"observacoes": f"Resultado já na ficha ({res})"})
            self._achado(("dg_nao_fechou", tid),
                         f"{animal}: {t['tipo']} de {quando} aberto mas a ficha já tem resultado '{res}' "
                         f"(insem. {self._sim(alvo['data_inseminacao'])}). Fechei à mão.", animal=animal)
            return
        # Ainda sem resultado: não cancela. Assinala.
        if atraso >= 3:
            self._achado(("dg_atraso", tid),
                         f"{animal}: {t['tipo']} ({etapa_tarefa}) de {quando} por fazer há {atraso} d; insem. "
                         f"{self._sim(alvo['data_inseminacao'])} com {alvo.get('garanhao')}, resultado '{res}'. "
                         "Não cancelo — falta o exame. A app não deixa atribuir a tarefa a um veterinário.",
                         animal=animal)

    # ── ponto da semana + controlo de qualidade ───────────────────────
    def _ponto_semana(self, rel):
        self.memoria["semana"].append(rel.hoje.isocalendar()[:2])
        dash = self._get("/dashboard") or {}
        cli = dash.get("clinica") or {}
        internadas = self._internadas()
        eguas = [x for x in internadas.values() if x.get("animal_tipo") == "egua"]
        hoje_real = HOJE_REAL
        lotes = self._get("/inseminacoes/lotes") or []
        por_g = defaultdict(int)
        for l in lotes:
            por_g[l.get("garanhao_nome")] += int(l.get("existencia_atual") or 0)
        acabar = sorted(g for g, n in por_g.items() if n < 8)
        # Garanhões sem nenhum lote com palhetas (não aparecem na lista).
        gar = [g["nome"] for g in (self._get("/opcoes/garanhoes") or [])]
        sem = sorted(set(gar) - set(por_g))
        resumo = (f"Ponto da semana {rel.hoje:%d/%m}: {len(internadas)} internados ({len(eguas)} éguas), "
                  f"{cli.get('gestacoes_confirmadas')} gestações em curso, {cli.get('insem_mes_operacoes')} insem. este mês; "
                  f"stock a acabar (<8 palhetas): {', '.join(acabar) or 'nenhum'}; sem stock: {', '.join(sem) or 'nenhum'}.")
        self.nota(resumo, tipo="ponto_semana")
        if (dash.get("atencao") or {}).get("itens") and not self.memoria.get("nota_atencao"):
            self.memoria["nota_atencao"] = True
            self.nota("Dashboard 'stock em atenção' é por lote (≤5 palhetas), não por garanhão: "
                      "um garanhão com vários lotes pequenos não aparece como em falta, e um sem stock nenhum também não.")

        # Controlo de qualidade: ficha de cada égua internada (não todas se a semana é pesada).
        amostra = eguas if len(eguas) <= 45 or self.rng.random() < 0.5 else self.rng.sample(eguas, 45)
        for x in amostra:
            try:
                self._qc_egua(rel, x, hoje_real)
            except Exception as e:
                self.nota(f"(erro no controlo da égua {x.get('animal')}: {e!r})")

    def _qc_egua(self, rel, x, hoje_real):
        aid, nome = x["animal_id"], x.get("animal")
        rep = self._get(f"/animais/{aid}/reprodutivo") or {}
        ins = rep.get("inseminacoes", [])
        dias = x.get("dias_internado") or 0
        if not ins and dias >= 30:
            self._achado(("sem_insem", aid, dias // 30),
                         f"{nome} ({x.get('proprietario')}) internada há {dias} d (entrou {self._sim(x.get('data_entrada'))}) "
                         "sem nenhuma inseminação registada.", animal=nome)
        entrada = _d(x.get("data_entrada"))
        regs = None
        for i in ins:
            di = _d(i.get("data_inseminacao"))
            if not di or (entrada and di < entrada):
                continue
            idade = (hoje_real - di).days
            if i.get("resultado") == "pendente" and idade >= 18:
                self._achado(("sem_dg", i.get("op_key")),
                             f"{nome}: inseminada em {self._sim(di)} ({i.get('garanhao')}) e sem DG ao fim de {idade} d "
                             "(D+14 já passou). A app não mostra isto em lado nenhum a não ser na ficha.", animal=nome)
            if i.get("resultado") == "gestacao_confirmada" and i.get("etapa") == "D+28" and idade >= 35:
                self._achado(("sem_d28", i.get("op_key")),
                             f"{nome}: gestação de {self._sim(di)} sem confirmação D+28 ao fim de {idade} d.", animal=nome)
            # Ovulação depois da inseminação (só a última semana: o diário só mostra 10 registos).
            if 3 <= idade <= 9:
                if regs is None:
                    regs = (self._get(f"/animais/{aid}/registos") or {}).get("historico", [])
                janela = [r for r in regs if _d(r.get("data_registo")) and di - timedelta(days=1) <= _d(r["data_registo"]) <= di + timedelta(days=3)]
                if len(regs) >= 10 and regs and _d(regs[-1]["data_registo"]) > di - timedelta(days=1):
                    if not self.memoria.get("nota_10"):
                        self.memoria["nota_10"] = True
                        self.nota(f"Ficha de {nome}: o histórico clínico só mostra os últimos 10 registos; "
                                  "não consigo ver os exames à volta da inseminação de há uma semana.")
                    continue
                ovus = [(r["dados"].get("OVU") or {}).get("ovulacao") for r in janela]
                if "sim" not in ovus:
                    vistos = ", ".join(f"{self._sim(r['data_registo'])}: {o or 'campo vazio'}" for r, o in zip(janela, ovus))
                    self._achado(("sem_ovu", i.get("op_key")),
                                 f"{nome}: inseminada em {self._sim(di)} ({i.get('garanhao')}) e nenhum registo clínico com ovulação "
                                 f"'sim' até {self._sim(di + timedelta(days=3))} (registos: {vistos or 'nenhum'}).", animal=nome)

    # ── fecho do mês ───────────────────────────────────────────────────
    def _fecho_mes(self, rel):
        hoje = rel.hoje
        self.memoria["mes"][(hoje.year, hoje.month)] = True
        if hoje.month == 2 and hoje.year == 2027:
            return  # primeiro mês: nada para fechar
        fim_sim = hoje.replace(day=1) - timedelta(days=1)
        ini_sim = fim_sim.replace(day=1)
        ini, fim = rel.real(ini_sim), rel.real(fim_sim)
        nome_mes = f"{ini_sim:%m/%Y}"

        # Inseminações do mês e acumulado (desde fevereiro).
        def tabela(params):
            r = self._get("/relatorios", params) or {}
            tabs = r.get("tabelas") or [{}]
            return tabs[0].get("linhas", [])

        mes = tabela({"modo": "historico", "hist": "insem", "inicio": ini.isoformat(), "fim": fim.isoformat()})
        tudo = tabela({"modo": "historico", "hist": "insem"})
        s, _ = self.api("GET", "/relatorios/exportar", params={"formato": "xlsx", "modo": "historico", "hist": "insem",
                                                                "inicio": ini.isoformat(), "fim": fim.isoformat()})
        self._resumo_garanhoes(f"mês {nome_mes}", mes)
        self._resumo_garanhoes(f"acumulado até {fim_sim:%d/%m}", tudo)

        # Stock: exportação completa + lotes externos sem dados de qualidade.
        stock = tabela({"modo": "historico", "hist": "stock"})
        self.api("GET", "/relatorios/exportar", params={"formato": "pdf", "modo": "historico", "hist": "stock"})
        for l in stock:
            if l.get("origem_externa") and not l.get("motilidade"):
                self._achado(("lote_sem_mot", l.get("_id")),
                             f"Lote externo {l.get('garanhao_nome')} ({l.get('origem_externa')}, {l.get('observacoes') or 'sem código'}) "
                             f"sem motilidade (mostra {l.get('motilidade')!r}; conc. {l.get('concentracao')!r}). "
                             "Não sei se o 0 é 'não medido' ou 'morto'.", lote=l.get("_id"))
        # Garanhão em PDF para o mais usado do mês (o dono do garanhão pede).
        if mes:
            top = max({l["garanhao_nome"] for l in mes}, key=lambda g: sum(1 for l in mes if l["garanhao_nome"] == g))
            self.api("GET", "/relatorios/exportar", params={"formato": "pdf", "modo": "garanhao", "garanhao": top})

        # Proprietários duplicados.
        s, r = self.api("GET", "/owners", params={"por_pagina": 200})
        grupos = defaultdict(list)
        for o in (r or {}).get("items", []):
            chave = _norm(o["nome"])
            for pre in ("coudelaria ", "herdade ", "quinta ", "sociedade agricola "):
                chave = chave.removeprefix(pre)
            grupos[chave].append(o)
        for k, v in grupos.items():
            if len(v) > 1:
                self._achado(("dono_dup", tuple(sorted(o["id"] for o in v))),
                             "Proprietários duplicados: " + " / ".join(f"'{o['nome']}' (id {o['id']}, {'ativo' if o['ativo'] else 'inativo'})" for o in v)
                             + ". A app aceitou ambos.")
        inativos = [o["nome"] for o in (r or {}).get("items", []) if not o.get("ativo")]
        if inativos:
            internados_donos = {x.get("proprietario") for x in self._internadas().values()}
            com_eguas = sorted(set(inativos) & internados_donos)
            if com_eguas:
                self._achado(("inativo_com_eguas", tuple(com_eguas)),
                             f"Proprietários marcados 'inativo' na lista mas com éguas internadas: {', '.join(com_eguas)}. "
                             "Ninguém os desativou à mão; parece que a app desativa donos sem sémen em stock.")

        # Éguas há muito tempo internadas: saídas do mês e média de dias.
        h = self._get("/estadias/historico", {"ano": fim.year, "mes": fim.month, "tipo_animal": "egua"}) or {}
        longas = [x for x in h.get("itens", []) if (x.get("dias_internado") or 0) >= 45 and not x.get("data_saida")]
        n = self.memoria.pop("n_saida_dg", 0)
        if n > 3:
            self.nota(f"No mês cancelei mais {n - 3} DG/confirmações de éguas que já tinham saído (gestantes levadas pelo dono).")
        self.nota(f"Fecho {nome_mes}: {len(mes)} inseminações (linhas do relatório), {h.get('total')} estadias tocaram o mês, "
                  f"{len(longas)} éguas internadas há ≥45 d.", tipo="fecho_mes")

    def _resumo_garanhoes(self, rotulo, linhas):
        por = defaultdict(lambda: {"ins": 0, "gest": 0, "falh": 0, "pend": 0, "palh": 0})
        for l in linhas:
            g = por[l.get("garanhao_nome")]
            g["ins"] += 1
            g["palh"] += int(l.get("palhetas_gastas") or 0)
            res = l.get("resultado")
            g["gest" if res == "gestacao_confirmada" else "falh" if res == "falhou" else "pend"] += 1
        partes = []
        for nome, g in sorted(por.items(), key=lambda kv: -kv[1]["ins"]):
            fechadas = g["gest"] + g["falh"]
            taxa = f"{round(100 * g['gest'] / fechadas)}%" if fechadas else "-"
            ppg = f"{g['palh'] / g['gest']:.1f}" if g["gest"] else "-"
            partes.append(f"{nome}: {g['ins']} ins, {g['gest']}G/{g['falh']}F/{g['pend']}P, taxa {taxa}, {ppg} palh/gest")
        self.nota(f"Relatório por garanhão ({rotulo}): " + "; ".join(partes), tipo="relatorio_garanhoes")
        pend = sum(g["pend"] for g in por.values())
        if linhas and pend / len(linhas) > 0.4 and "acumulado" in rotulo:
            self._achado(("muitos_pend", rotulo[-5:]),
                         f"{pend} de {len(linhas)} linhas de inseminação ainda 'pendente' no relatório ({rotulo}); "
                         "a taxa de gestação por garanhão fica enganadora. O relatório não tem a taxa feita — calculo à mão.")

    # ── telefonema de um dono ──────────────────────────────────────────
    def _telefonema(self, rel):
        eguas = [x for x in self._internadas().values() if x.get("animal_tipo") == "egua"]
        if not eguas:
            return
        x = self.rng.choice(eguas)
        aid, nome = x["animal_id"], x.get("animal")
        self._get(f"/animais/{aid}")
        rep = self._get(f"/animais/{aid}/reprodutivo") or {}
        est = self._get(f"/animais/{aid}/estadias") or {}
        regs = self._get(f"/animais/{aid}/registos") or {}
        ins = rep.get("inseminacoes", [])
        acomp = est.get("acompanhamento") or {}
        ultima = ins[0] if ins else None
        # A ficha (acompanhamento) e o histórico de inseminações dizem o mesmo?
        if ultima and acomp:
            r_ins = ultima.get("resultado")
            r_acomp = acomp.get("resultado")
            mapa = {"gestacao_confirmada": "gestacao_confirmada", "falhou": "falhou", "pendente": None}
            if r_acomp not in (mapa.get(r_ins), r_ins, None) or (r_ins == "gestacao_confirmada" and r_acomp is None):
                self._achado(("acomp_dif", aid, ultima.get("op_key")),
                             f"Dono de {nome} ({x.get('proprietario')}) ligou: a ficha diz acompanhamento '{r_acomp}' e a "
                             f"última inseminação ({self._sim(ultima.get('data_inseminacao'))}) diz '{r_ins}'. Qual digo ao dono?",
                             animal=nome)
            di_acomp = acomp.get("data_inseminacao")
            if di_acomp and _d(di_acomp) != _d(ultima.get("data_inseminacao")):
                self._achado(("acomp_data", aid, ultima.get("op_key")),
                             f"{nome}: acompanhamento com data de inseminação {self._sim(di_acomp)} mas a última inseminação "
                             f"é de {self._sim(ultima.get('data_inseminacao'))}.", animal=nome)
        ult_reg = (regs.get("historico") or [{}])[0].get("data_registo")
        self.nota(f"Telefonema do dono de {nome} ({x.get('proprietario')}): {len(ins)} inseminações, última "
                  f"{self._sim(ultima.get('data_inseminacao')) if ultima else '-'} '{ultima.get('resultado') if ultima else '-'}', "
                  f"último exame {self._sim(ult_reg) if ult_reg else 'nenhum'}.", tipo="telefonema")
