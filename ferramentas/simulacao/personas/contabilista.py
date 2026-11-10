"""Teresa — contabilista (part-time, só dias úteis). Fatura pela app o que a
clínica cobra: estadias (dias) e sémen de clientes guardado (palhetas × dias).

Como trabalha:
- No início de cada mês (2.º a 6.º dia útil) olha para "Em atraso" e fatura
  as estadias até ao fim do mês anterior, uma fatura por proprietário.
- O sémen de cada cliente segue o contrato (em papel, `politica_cliente`):
  mensal, trimestral (jan/abr/jul/out) ou anual (janeiro).
- Na primeira fatura de um lote que já cá estava antes da app, o contrato
  diz desde quando: antecipa o início (só na fatura).
- O sémen da própria clínica não se fatura a ninguém.

Erros humanos: às vezes repete o número da fatura anterior (a app avisa:
corrige quase sempre), às vezes fatura até hoje em vez de até ao fim do mês
(percebe depois, anula e refaz), às vezes salta um mês (apanha no seguinte).
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from simcore import Pessoa, sql

DONOS_CLINICA = ("Clínica — sémen próprio", "Clínica — sémen comprado")
FERIAS = (195, 209)  # duas semanas em agosto (dias simulados)


def fim_mes_anterior(d: date) -> date:
    return d.replace(day=1) - timedelta(days=1)


class Teresa(Pessoa):
    papel = "contabilista"
    nome = "teresa"
    nivel = "Visualizador"  # não mexe na clínica, só na faturação
    ordem = 6

    def __init__(self, mundo):
        super().__init__(mundo)
        sql("UPDATE usuarios SET acesso_faturacao = 'editar' WHERE username = %s", (self.username,))
        self.r = random.Random(1717)
        self.seq = 0
        self.ultimo_numero = None

    # ── utilidades ───────────────────────────────────────────────────────
    def _nota_uma_vez(self, chave, texto, **extra):
        vistas = self.memoria.setdefault("notas_feitas", set())
        if chave not in vistas:
            vistas.add(chave)
            self.nota(texto, **extra)

    def _numero(self, rel) -> str:
        """Número da próxima fatura (o programa de faturação dá-o; ela copia)."""
        if self.ultimo_numero and self.r.random() < 0.04:
            return self.ultimo_numero  # engano: copiou o da fatura anterior
        self.seq += 1
        self.ultimo_numero = f"FT {rel.hoje.year}/{self.seq:04d}"
        return self.ultimo_numero

    def _codigo_cliente(self, lote_id) -> str | None:
        """CL-xxx escrito nas observações do lote (o que ela vê na ficha)."""
        cache = self.memoria.setdefault("codigos", {})
        if lote_id not in cache:
            s, l = self.api("GET", f"/stock/lotes/{lote_id}")
            obs = (l or {}).get("observacoes") or "" if s == 200 else ""
            cache[lote_id] = obs.split(" ")[0] if obs.startswith("CL-") else None
        return cache[lote_id]

    def _faturar(self, rel, dono_id, dono_nome, linhas, fim_real) -> bool:
        """Resumo + (às vezes) PDF + número da fatura + marcar. Uma fatura por proprietário."""
        refs = [{"tipo": l["tipo"], "ref_id": l["ref_id"], "inicio": l["inicio"], "fim": min(l["fim"], fim_real)} for l in linhas]
        refs = [x for x in refs if x["inicio"] <= x["fim"]]
        if not refs:
            return False
        s, _ = self.api("POST", "/faturacao/resumo", json={"linhas": refs, "dono_ids": [dono_id] if dono_id else []})
        numero = self._numero(rel)
        s, usados = self.api("GET", "/faturacao/numeros", params={"n": [numero]})
        if s == 200 and any(u["dono_id"] != dono_id for u in usados or []):
            # A app avisa "número repetido". Quase sempre corrige.
            if self.r.random() < 0.8:
                self.seq += 1
                numero = self.ultimo_numero = f"FT {rel.hoje.year}/{self.seq:04d}"
            else:
                self.nota(f"Gravei {numero} para {dono_nome} apesar do aviso de número repetido (pressa).")
        corpo = {"faturas": [{"dono_id": dono_id, "fatura_numero": numero, "fatura_data": rel.real(rel.hoje).isoformat(), "linhas": refs}]}
        s, r = self.api("POST", "/faturacao/faturar", json=corpo)
        if s == 409:
            self.nota(f"Ao faturar {dono_nome}: a app diz que parte já foi faturada ou mudou entretanto ({numero}).")
            return False
        if s != 200:
            self.nota(f"Não consegui faturar {dono_nome}: erro {s}", corpo=r)
            return False
        self.memoria.setdefault("faturas", []).append({"dia": rel.d, "numero": numero, "dono": dono_nome, "linhas": len(refs)})
        return True

    # ── o dia ────────────────────────────────────────────────────────────
    def dia(self, rel):
        hoje = rel.hoje
        if hoje.weekday() >= 5 or FERIAS[0] <= rel.d <= FERIAS[1]:
            return
        self._corrigir_enganos(rel)
        mes = (hoje.year, hoje.month)
        if self.memoria.get("mes_feito") == mes:
            return
        # Começa a faturar entre o 2.º e o 6.º dia do mês (quando tem tempo).
        alvo = self.memoria.setdefault("dia_alvo", {}).setdefault(mes, self.r.randint(2, 6))
        if hoje.day < alvo:
            return
        self.memoria["mes_feito"] = mes
        if rel.d < 25:
            return  # o primeiro mês ainda não fechou
        if self.r.random() < 0.06:
            self.nota(f"Não consegui faturar {hoje.month:02d}/{hoje.year} (fim de mês complicado); fica para o próximo.")
            return
        self.api("GET", "/faturacao/atraso")
        self._estadias(rel)
        self._semen(rel)
        self._palhetas(rel)
        if hoje.month in (1, 4, 7, 10):
            self.api("GET", "/faturacao/anos", params={"desde": 2025})

    def _estadias(self, rel):
        ate_sim = fim_mes_anterior(rel.hoje)
        ate = rel.real(ate_sim).isoformat()
        engano = self.r.random() < 0.03  # fatura até hoje em vez de até ao fim do mês
        if engano:
            ate = rel.real(rel.hoje).isoformat()
        s, linhas = self.api("GET", "/faturacao/por-faturar", params={"inicio": "1990-01-01", "fim": ate, "tipo": "estadia"})
        if s != 200:
            return
        por_dono: dict = {}
        for l in linhas:
            por_dono.setdefault((l["dono_id"], l["dono_nome"]), []).append(l)
        for (dono_id, nome), ls in por_dono.items():
            if self._faturar(rel, dono_id, nome, ls, ate) and engano:
                # Vai perceber daqui a uns dias e corrigir.
                self.memoria.setdefault("a_corrigir", []).append({"dia": rel.d + self.r.randint(2, 8), "dono_id": dono_id, "ate": rel.real(ate_sim).isoformat()})

    def _semen(self, rel):
        hoje = rel.hoje
        politica = self.mundo.politica_cliente
        s, linhas = self.api("GET", "/faturacao/por-faturar", params={"inicio": "1990-01-01", "fim": rel.real(rel.hoje).isoformat(), "tipo": "armazenamento"})
        if s != 200:
            return
        por_dono: dict = {}
        for l in linhas:
            por_dono.setdefault((l["dono_id"], l["dono_nome"]), []).append(l)
        for (dono_id, nome), ls in por_dono.items():
            if nome in DONOS_CLINICA:
                self._nota_uma_vez("clinica", "O sémen da própria clínica aparece em 'Por faturar' (o dono não está marcado como da clínica).")
                continue
            regra = politica.get(nome)
            if regra is None:
                continue
            if regra == "mensal":
                ate_sim = fim_mes_anterior(hoje)
            elif regra == "trimestral":
                if hoje.month not in (1, 4, 7, 10) and not self._atrasado(ls, rel, 100):
                    continue
                q_ini = date(hoje.year, ((hoje.month - 1) // 3) * 3 + 1, 1)
                ate_sim = q_ini - timedelta(days=1)
            else:  # anual
                if hoje.month != 1 and not self._atrasado(ls, rel, 400):
                    continue
                ate_sim = date(hoje.year - 1, 12, 31)
            ate = rel.real(ate_sim).isoformat()
            # Primeira fatura de um lote que já cá estava: o contrato diz desde quando.
            for l in ls:
                if l.get("pode_mudar_inicio") and l["inicio"] == l.get("entrada_app"):
                    cod = self._codigo_cliente(l["ref_id"])
                    lc = self.mundo.lotes_cliente.get(cod) if cod else None
                    if lc and lc.guardado_desde < lc.chega:
                        l["inicio"] = rel.real(lc.guardado_desde).isoformat()
            self._faturar(rel, dono_id, nome, ls, ate)

    def _palhetas(self, rel):
        """Palhetas de sémen de clientes usadas no mês passado: ao dono da égua
        (recebidas) e ao dono do sémen (gastas, para acerto)."""
        ate = rel.real(fim_mes_anterior(rel.hoje)).isoformat()
        s, linhas = self.api("GET", "/faturacao/por-faturar", params={"inicio": "1990-01-01", "fim": ate, "tipo": "palhetas"})
        if s != 200:
            return
        por_dono: dict = {}
        for l in linhas:
            por_dono.setdefault((l["dono_id"], l["dono_nome"]), []).append(l)
        for (dono_id, nome), ls in por_dono.items():
            self._faturar(rel, dono_id, nome, ls, ate)

    def _atrasado(self, linhas, rel, dias) -> bool:
        """Apanha o que ficou para trás (ex.: saltou um trimestre)."""
        mais_antigo = min(l["inicio"] for l in linhas)
        return (rel.real(rel.hoje) - date.fromisoformat(mais_antigo)).days > dias

    def _corrigir_enganos(self, rel):
        """Faturou até hoje em vez de até ao fim do mês: anula e volta a faturar certo."""
        fica = []
        for x in self.memoria.get("a_corrigir", []):
            if x["dia"] > rel.d:
                fica.append(x)
                continue
            s, feitas = self.api("GET", "/faturacao/faturado", params={"inicio": "1990-01-01", "fim": rel.real(rel.hoje).isoformat(), "dono_id": x["dono_id"]})
            erradas = [f for f in (feitas or []) if f["tipo"] == "estadia" and f["fim"] > x["ate"] and not f["anulada"]] if s == 200 else []
            for f in erradas:
                self.api("POST", f"/faturacao/linhas/{f['id']}/anular", json={"motivo": "Faturado além do fim do mês (engano)"})
            if erradas:
                s, linhas = self.api("GET", "/faturacao/por-faturar", params={"inicio": "1990-01-01", "fim": x["ate"], "tipo": "estadia", "dono_id": x["dono_id"]})
                if s == 200 and linhas:
                    self._faturar(rel, x["dono_id"], linhas[0]["dono_nome"], linhas, x["ate"])
                self.nota(f"Corrigi uma fatura de estadias que ia além do fim do mês ({len(erradas)} linha(s) anuladas e refeitas).")
        self.memoria["a_corrigir"] = fica
