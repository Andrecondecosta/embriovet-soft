"""A "natureza" escondida: ciclos das éguas, ovulação, gestação, sémen, donos.

As pessoas NÃO leem o estado interno. Só veem o que um veterinário veria
(`exame`), o que chega à porta (`chegadas`, `semen_chega`) e o que os donos
pedem (`perfil_dono`, `saidas_imprevistas`). As ações físicas (inseminar,
induzir) também passam por aqui, para a biologia reagir.

Tudo é determinístico (semente fixa) para se poder repetir.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from simcore import INICIO, LOG

NOMES = [
    "Alameda", "Bonança", "Brisa", "Cigana", "Dália", "Estrela", "Faia", "Gaivota", "Harpa", "Íris", "Jóia", "Lua",
    "Magnólia", "Neblina", "Oliva", "Pérola", "Quimera", "Rosa", "Safira", "Tília", "Urze", "Valquíria", "Xana", "Zínia",
]
APELIDOS = ["do Vale", "da Serra", "de Alter", "do Monte", "da Lezíria", "do Sado", "da Ribeira", "de Évora", "do Tejo", "da Beira"]
DONOS = [
    "Coudelaria Vale Verde", "Herdade do Sobral", "Quinta da Lagoa", "Rui Matos", "Ana Ferreira", "Coudelaria Ribeiro",
    "Sociedade Agrícola Monte Alto", "João Pires", "Marta Lopes", "Coudelaria do Sado", "Paulo Nunes", "Herdade da Torre",
    "Inês Carvalho", "Coudelaria Alvarenga", "Tiago Moura", "Quinta do Pinhal", "Sofia Rocha", "Coudelaria Real",
]
GARANHOES = [  # (nome, interno?, motilidade média pós-descongelação, concentração)
    ("Xaquiro", True, 52, 200), ("Nobre", True, 45, 180), ("Embaixador", True, 38, 150), ("Fadista", True, 30, 120),
    ("Rubi Real", True, 55, 220), ("Quixote", True, 41, 160), ("Ulisses", False, 48, 200), ("Hostil", False, 35, 140),
    ("Zeus do Sado", False, 25, 100), ("Bailador", False, 50, 210), ("Opus", False, 44, 170), ("Vendaval", False, 33, 130),
]


@dataclass
class Lote:
    codigo: str  # "LT-007" — a pessoa do stock deve escrevê-lo nas observações do lote
    garanhao: str
    interno: bool
    origem: str  # texto da origem externa ("" se interno)
    data_producao: date
    palhetas: int
    motilidade_real: int
    concentracao_real: int
    motilidade_rotulo: int | None  # o que vem escrito (None = não veio)
    concentracao_rotulo: int | None
    chega: date


@dataclass
class Egua:
    wid: int
    nome: str
    idade: int
    dono: str
    chegada: date
    garanhao: str  # escolhido pelo dono
    tipo: str  # "egua" ou "receptora"
    fertilidade: float
    propensa_liquido: bool
    max_ciclos: int  # quantos ciclos o dono aceita tentar
    leva_para_casa: str  # quando o dono a leva se gestante: "D+14" | "D+28" | "D+45"
    saida_imprevista: date | None = None
    # estado biológico
    estro_inicio: date | None = None
    foliculo_inicial: float = 25.0
    taxa: float = 3.0
    limiar: float = 42.0
    lado: str = "OE"
    hemorragico: bool = False
    ovulacao: datetime | None = None
    induzida: datetime | None = None
    insem: list = field(default_factory=list)  # [(datetime, motilidade_real, codigo_lote)]
    gestante: bool = False
    perda: date | None = None
    ciclos: int = 0
    historia: list = field(default_factory=list)


class Mundo:
    def __init__(self, semente=2027, n_eguas=150, dias=273):
        self.r = random.Random(semente)
        self.dias = dias
        self.lotes: dict[str, Lote] = {}
        self.eguas: dict[int, Egua] = {}
        self._n_lote = 0
        fim_chegadas = dias - 60
        for i in range(1, n_eguas + 1):
            # Mais chegadas na primavera (início da época).
            d = int(min(self.r.betavariate(1.6, 2.6) * fim_chegadas, fim_chegadas))
            nome = f"{self.r.choice(NOMES)} {self.r.choice(APELIDOS)} {i:03d}"
            idade = self.r.choice([3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22])
            receptora = self.r.random() < 0.08
            e = Egua(
                wid=i, nome=nome, idade=idade, dono=self.r.choice(DONOS), chegada=INICIO + timedelta(days=d),
                garanhao=self.r.choice(GARANHOES)[0], tipo="receptora" if receptora else "egua",
                fertilidade=self.r.uniform(0.75, 1.1) * (1.0 if idade <= 12 else 0.85 if idade <= 16 else 0.65),
                propensa_liquido=self.r.random() < 0.12, max_ciclos=self.r.choice([1, 2, 2, 3, 3, 3]),
                leva_para_casa=self.r.choice(["D+14", "D+28", "D+45", "D+45", "D+45"]),
            )
            if self.r.random() < 0.06:
                e.saida_imprevista = e.chegada + timedelta(days=self.r.randint(3, 40))
            self._novo_estro(e, e.chegada + timedelta(days=self.r.randint(-3, 14)))
            self.eguas[i] = e
        # Sémen: stock inicial e entregas mensais.
        self.entregas: dict[date, list[Lote]] = {}
        for nome, interno, mot, conc in GARANHOES:
            for k in range(3):
                self._lote(nome, interno, mot, conc, INICIO + timedelta(days=0 if k == 0 else self.r.randint(20, dias - 80)))
        for e in self.eguas.values():
            LOG("verdade", evento="egua", wid=e.wid, nome=e.nome, idade=e.idade, chegada=e.chegada, garanhao=e.garanhao,
                tipo=e.tipo, max_ciclos=e.max_ciclos, leva_para_casa=e.leva_para_casa, saida_imprevista=e.saida_imprevista)

    # ── sémen ────────────────────────────────────────────────────────────
    def _lote(self, garanhao, interno, mot, conc, chega):
        self._n_lote += 1
        real = max(5, int(self.r.gauss(mot, 7)))
        falta = (not interno) and self.r.random() < 0.3
        l = Lote(
            codigo=f"LT-{self._n_lote:03d}", garanhao=garanhao, interno=interno,
            origem="" if interno else self.r.choice(["Haras de Lusitânia (BR)", "Yeguada Cartuja (ES)", "Stud Hof Kasselmann (DE)", "Coudelaria Alter Real"]),
            data_producao=chega - timedelta(days=self.r.randint(10, 700)), palhetas=self.r.choice([8, 10, 12, 16, 20]),
            motilidade_real=real, concentracao_real=max(30, int(self.r.gauss(conc, 25))),
            motilidade_rotulo=None if falta else min(80, real + self.r.randint(-3, 8)),
            concentracao_rotulo=None if falta else conc, chega=chega,
        )
        self.lotes[l.codigo] = l
        self.entregas.setdefault(chega, []).append(l)
        LOG("verdade", evento="lote", **{k: v for k, v in l.__dict__.items()})

    def semen_chega(self, hoje: date) -> list[Lote]:
        """Lotes que chegam hoje à clínica (a pessoa do stock regista-os)."""
        return self.entregas.get(hoje, [])

    def pedir_semen(self, hoje: date, garanhao: str):
        """Encomenda: chega daqui a 2-5 dias (só garanhões conhecidos)."""
        g = next((g for g in GARANHOES if g[0] == garanhao), None)
        if g:
            self._lote(*g, chega=hoje + timedelta(days=self.r.randint(2, 5)))

    # ── chegadas e donos ─────────────────────────────────────────────────
    def chegadas(self, hoje: date) -> list[Egua]:
        return [e for e in self.eguas.values() if e.chegada == hoje]

    def saidas_imprevistas(self, hoje: date) -> list[Egua]:
        """Donos que vêm buscar a égua hoje sem aviso (doença, venda...)."""
        return [e for e in self.eguas.values() if e.saida_imprevista == hoje]

    def wid_por_nome(self, nome: str | None) -> int | None:
        """A égua física que tem este nome (o que está escrito na box)."""
        return next((e.wid for e in self.eguas.values() if e.nome == nome), None)

    def perfil_dono(self, wid: int) -> dict:
        e = self.eguas[wid]
        return {"garanhao": e.garanhao, "max_ciclos": e.max_ciclos, "leva_para_casa_gestante_em": e.leva_para_casa, "dono": e.dono}

    # ── biologia ─────────────────────────────────────────────────────────
    def _novo_estro(self, e: Egua, inicio: date):
        e.estro_inicio = inicio
        e.foliculo_inicial = self.r.uniform(22, 28)
        e.taxa = self.r.uniform(2.5, 3.8)
        e.limiar = self.r.uniform(38, 48)
        e.lado = self.r.choice(["OE", "OD"])
        e.hemorragico = self.r.random() < 0.04
        dias = (e.limiar - e.foliculo_inicial) / e.taxa
        e.ovulacao = datetime.combine(inicio, time(self.r.randint(0, 23))) + timedelta(days=dias)
        e.induzida = None
        e.insem = []
        e.gestante = False
        e.perda = None

    def _tamanho(self, e: Egua, quando: datetime) -> float | None:
        if e.estro_inicio is None:
            return None
        dias = (quando - datetime.combine(e.estro_inicio, time(0))).total_seconds() / 86400
        if dias < 0:
            return None
        return e.foliculo_inicial + e.taxa * dias

    def _avancar(self, e: Egua, quando: datetime):
        """Fecha os ciclos cuja ovulação já passou (vários, se a égua não
        foi vista durante semanas)."""
        for _ in range(30):
            antes = (e.ovulacao, len(e.historia))
            self._passo(e, quando)
            if (e.ovulacao, len(e.historia)) == antes:
                return

    def _passo(self, e: Egua, quando: datetime):
        fechado = bool(e.historia) and e.historia[-1]["ovulacao"] == e.ovulacao
        if e.ovulacao and quando >= e.ovulacao and not fechado:
            p = 0.0
            for t, mot, cod in e.insem:
                horas = (e.ovulacao - t).total_seconds() / 3600  # >0: inseminou antes de ovular
                janela = 1.0 if -6 <= horas <= 24 else 0.5 if 24 < horas <= 48 else 0.15 if -12 <= horas < -6 else 0.03
                p = max(p, min(0.85, 0.72 * e.fertilidade * min(1.0, mot / 40) * janela))
            gest = (not e.hemorragico) and self.r.random() < p
            perda = None
            if gest and self.r.random() < 0.10:
                perda = e.ovulacao.date() + timedelta(days=self.r.randint(17, 40))
            e.ciclos += 1 if e.insem else 0
            e.historia.append({"ovulacao": e.ovulacao, "insem": list(e.insem), "p": round(p, 2), "gestante": gest, "perda": perda,
                               "hemorragico": e.hemorragico})
            LOG("verdade", evento="ciclo", wid=e.wid, nome=e.nome, ovulacao=e.ovulacao, hemorragico=e.hemorragico,
                insem=[(t, cod) for t, _, cod in e.insem], p=round(p, 2), gestante=gest, perda=perda)
            e.gestante, e.perda = gest, perda
        # Sem gestação (ou perdida): novo estro.
        if e.historia and e.historia[-1]["ovulacao"] == e.ovulacao:
            h = e.historia[-1]
            if not h["gestante"]:
                proximo = e.ovulacao.date() + timedelta(days=self.r.randint(14, 17))
                if quando.date() >= proximo - timedelta(days=1):
                    self._novo_estro(e, proximo)
            elif h["perda"] and quando.date() >= h["perda"] + timedelta(days=4):
                self._novo_estro(e, h["perda"] + timedelta(days=5))

    def exame(self, wid: int, quando: datetime) -> dict:
        """Ecografia: o que o veterinário vê agora (com ruído de medição)."""
        e = self.eguas[wid]
        self._avancar(e, quando)
        r = self.r
        pequenos = lambda: [round(r.uniform(10, 24)) for _ in range(r.randint(0, 3))]  # noqa: E731
        ov = {"OE": pequenos(), "OD": pequenos()}
        h = e.historia[-1] if e.historia and e.historia[-1]["ovulacao"] == e.ovulacao else None
        ovulou_recente = bool(e.ovulacao and e.ovulacao <= quando <= e.ovulacao + timedelta(days=2))
        tam = self._tamanho(e, quando)
        if tam and not h:
            ov[e.lado].append(round(min(tam, e.limiar) + r.uniform(-2, 2)))
        edema = 0
        if tam and not h:
            dias = (quando.date() - e.estro_inicio).days
            edema = 3 if 2 <= dias and quando < e.ovulacao - timedelta(hours=18) else 2 if dias >= 1 else 1
            if quando >= e.ovulacao - timedelta(hours=18):
                edema = 1
        liquido = 0 if not e.propensa_liquido else r.choice([0, 1, 1, 2])
        if ovulou_recente and e.insem:
            liquido = max(liquido, r.choice([0, 0, 1]))
        dg = None
        if h and quando.date() >= e.ovulacao.date() + timedelta(days=12):
            vivo = h["gestante"] and not (h["perda"] and quando.date() >= h["perda"])
            dg = vivo if r.random() > 0.03 else not vivo  # 3% de erro de leitura
        return {
            "foliculos": {k: sorted(v, reverse=True) for k, v in ov.items()},
            "edema": edema,  # 0..3
            "liquido": liquido,  # 0 = sem, 1 = <2 cm, 2 = +
            "cervix": 3 if edema >= 2 else 2 if edema == 1 else 1,
            "ovulou": ovulou_recente and not e.hemorragico,
            "folic_hemorragico": ovulou_recente and e.hemorragico,
            "corpo_luteo": bool(h) and not e.hemorragico,
            "vesicula_embrionaria": dg,  # None = ainda cedo para ver
        }

    def inseminar(self, wid: int, quando: datetime, codigo_lote: str | None):
        """Inseminação física. Sem código, conta motilidade 40%."""
        e = self.eguas[wid]
        self._avancar(e, quando)
        l = self.lotes.get(codigo_lote or "")
        e.insem.append((quando, l.motilidade_real if l else 40, codigo_lote))
        LOG("verdade", evento="inseminacao", wid=wid, quando=quando, lote=codigo_lote)

    def induzir(self, wid: int, quando: datetime):
        """Indutor da ovulação (hCG/deslorelina): ovula 36-42 h depois, se o folículo já tiver >= 33 mm."""
        e = self.eguas[wid]
        tam = self._tamanho(e, quando)
        if tam and tam >= 33 and e.ovulacao > quando + timedelta(hours=42):
            e.ovulacao = quando + timedelta(hours=self.r.uniform(36, 42))
            e.induzida = quando
            LOG("verdade", evento="inducao", wid=wid, quando=quando, ovulacao=e.ovulacao)

    def verdade_final(self) -> list[dict]:
        out = []
        for e in self.eguas.values():
            out.append({"wid": e.wid, "nome": e.nome, "ciclos": [
                {**h, "insem": [(t, c) for t, _, c in h["insem"]]} for h in e.historia if h["insem"]]})
        return out
