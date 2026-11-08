"""Exportação de eventos reprodutivos — corre fora da app (não há botão).

Uma folha por tipo de evento — éguas, exames do diário clínico,
inseminações (uma linha por lote) e diagnósticos de gestação por etapa —
mais uma legenda. Os ciclos montam-se depois na análise, a partir destes
eventos e das datas.

Pseudonimizado: em vez de nomes vão códigos estáveis (E = égua,
G = garanhão, L = lote, I = inseminação, R = registo clínico,
V = veterinário/utilizador). Só a clínica, com a app, consegue voltar
dos códigos aos nomes.

Uso (liga-se à base da `DATABASE_URL`):
    python scripts/exportar_eventos.py [--inicio AAAA-MM-DD] [--fim AAAA-MM-DD] [ficheiro.xlsx]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.db import get_connection  # noqa: E402

EDEMA = ("0", "+", "++", "+++")
LIQUIDO = ("0", "<2 cm", "+", "++", "+++")
DG = {"Positivo": "positivo", "Negativo": "negativo", "Inconclusivo": "inconclusivo", "Sem exame": "sem_exame"}


def _txt(v):
    """Datas e horas em texto ISO (abre igual no Excel, no R e no SPSS)."""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.strftime("%H:%M")
    return v


def _cod(prefixo: str, n) -> str | None:
    return f"{prefixo}{n}" if n is not None else None


def _origem(texto) -> str:
    """Origem do lote: vazio ou "não" = interno; "sim" ou um nome = externo."""
    t = (texto or "").strip().lower()
    return "interno" if t in ("", "não", "nao", "n") else "externo"


def _ovario(ov: dict | None) -> list:
    """N.º de folículos, o maior (mm) e a lista "35 OV; 20"."""
    if ov is None:
        return [None, None, None]
    fol = ov.get("foliculos") or []
    lista = "; ".join(" ".join([str(f.get("tamanho"))] + list(f.get("achados") or [])) for f in fol)
    return [len(fol), max((f.get("tamanho") or 0) for f in fol) if fol else None, lista or None]


def _hora_inducao(d: dict):
    """Data e hora da indução da ovulação escrita no registo (hCG/deslorelina)."""
    v = ((d.get("TX") or {}).get("inducao") or {}).get("data")
    return v.replace("T", " ")[:16] if v else None


def tabelas_eventos(inicio: date | None = None, fim: date | None = None) -> list[tuple]:
    """(nome da folha, cabeçalhos, linhas) para `gerar_excel` / `gerar_csv`."""
    entre = "BETWEEN COALESCE(%s, '-infinity'::date) AND COALESCE(%s, 'infinity'::date)"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username, id FROM usuarios")
            vets = dict(cur.fetchall())

            # Código de cada inseminação (operação): o id da sua primeira linha.
            cur.execute("SELECT operation_id::text, MIN(id) FROM inseminacoes WHERE operation_id IS NOT NULL GROUP BY 1")
            op_cod = {op: f"I{n}" for op, n in cur.fetchall()}

            cur.execute(
                f"""
                SELECT i.id, i.operation_id::text, i.animal_id_egua, i.data_inseminacao, i.hora_inseminacao,
                       i.animal_id_garanhao, i.estoque_id, i.palhetas_gastas, i.resultado, i.utilizador,
                       e.concentracao, e.motilidade, e.origem_externa, e.data_embriovet, e.dose
                FROM inseminacoes i
                LEFT JOIN estoque_dono e ON e.id = i.estoque_id
                WHERE i.animal_id_egua IS NOT NULL AND i.data_inseminacao {entre}
                ORDER BY i.animal_id_egua, i.data_inseminacao, i.hora_inseminacao, i.id
                """,
                (inicio, fim),
            )
            insem = cur.fetchall()

            cur.execute(
                f"""
                SELECT r.id, r.animal_id, r.data_registo, r.dados, r.utilizador
                FROM registo_clinico r JOIN animais a ON a.id = r.animal_id
                WHERE a.tipo <> 'garanhao' AND r.data_registo::date {entre}
                ORDER BY r.animal_id, r.data_registo, r.id
                """,
                (inicio, fim),
            )
            exames = cur.fetchall()

            cur.execute(
                f"""
                SELECT d.id, d.animal_id, d.operation_id::text, d.etapa, d.resultado, d.data_exame,
                       d.registo_clinico_id, d.utilizador
                FROM diagnosticos_gestacao d
                WHERE d.data_exame::date {entre}
                ORDER BY d.animal_id, d.data_exame, d.id
                """,
                (inicio, fim),
            )
            diag = cur.fetchall()

            ids_eguas = sorted({r[2] for r in insem} | {r[1] for r in exames} | {r[1] for r in diag})
            # Estadias (entrada/saída e como saiu): sem isto não se distingue
            # "sem D+45 porque foi para casa" de "sem D+45 por falta de registo".
            cur.execute(
                """SELECT e.animal_id, e.id, e.data_entrada, e.data_saida, e.estado, e.motivo
                   FROM estadias e WHERE e.animal_id = ANY(%s) ORDER BY e.animal_id, e.data_entrada""",
                (ids_eguas,),
            )
            estadias = cur.fetchall()
            cur.execute("SELECT id, tipo, data_nascimento FROM animais WHERE id = ANY(%s) ORDER BY id", (ids_eguas,))
            eguas = cur.fetchall()

    vet = lambda u: _cod("V", vets.get(u)) if u else None  # noqa: E731

    t_eguas = (
        "Éguas",
        ["egua", "tipo", "data_nascimento"],
        [[_cod("E", i), tipo, _txt(nasc)] for i, tipo, nasc in eguas],
    )
    t_exames = (
        "Exames",
        ["egua", "registo", "data_hora", "oe_n_foliculos", "oe_maior_mm", "oe_foliculos", "od_n_foliculos", "od_maior_mm",
         "od_foliculos", "edema", "liquido", "cervix", "ovulacao", "folic_hemorragico", "dg", "inducao", "inducao_produto",
         "veterinario"],
        [
            [
                _cod("E", aid), _cod("R", rid), _txt(quando),
                *_ovario(d.get("OE")), *_ovario(d.get("OD")),
                (d.get("UT") or {}).get("edema"), (d.get("UT") or {}).get("liquido"), (d.get("CER") or {}).get("grau"),
                (d.get("OVU") or {}).get("ovulacao"), (d.get("OVU") or {}).get("fh"), DG.get(d.get("DG")),
                _hora_inducao(d), ((d.get("TX") or {}).get("inducao") or {}).get("produto"), vet(u),
            ]
            for rid, aid, quando, d, u in exames
            for d in [d or {}]
        ],
    )
    t_insem = (
        "Inseminações",
        ["egua", "inseminacao", "data", "hora", "garanhao", "lote", "palhetas", "lote_concentracao", "lote_motilidade",
         "lote_origem", "lote_data_producao", "lote_dose", "resultado_atual", "veterinario"],
        [
            [
                _cod("E", egua), op_cod.get(op) or f"I{iid}", _txt(dia), _txt(hora), _cod("G", gar), _cod("L", lote), palh,
                conc, mot, _origem(origem) if lote else None, prod, dose, res, vet(u),
            ]
            for iid, op, egua, dia, hora, gar, lote, palh, res, u, conc, mot, origem, prod, dose in insem
        ],
    )
    t_diag = (
        "Diagnósticos",
        ["egua", "inseminacao", "etapa", "resultado", "data_hora_exame", "registo", "veterinario"],
        [
            [_cod("E", aid), op_cod.get(op), etapa, res, _txt(quando), _cod("R", reg), vet(u)]
            for _, aid, op, etapa, res, quando, reg, u in diag
        ],
    )
    legenda = (
        "Legenda",
        ["campo", "significado"],
        [
            ["egua / garanhao / lote / inseminacao / registo / estadia / veterinario",
             "Códigos em vez de nomes (E, G, L, I, R, S, V + número interno da app)."],
            ["oe_* / od_*", "Ovário esquerdo / direito. Vazio = ovário não examinado nesse registo; 0 folículos = examinado sem folículos."],
            ["*_maior_mm", "Diâmetro do maior folículo (mm). 9 significa «<10 mm» e 61 significa «>60 mm»."],
            ["*_foliculos", "Cada folículo: tamanho e achados (OV, FH, NS, MF, CL)."],
            ["edema", "0 = 0, 1 = +, 2 = ++, 3 = +++. Vazio = útero não examinado."],
            ["liquido", "0 = 0, 1 = <2 cm, 2 = +, 3 = ++, 4 = +++. Vazio = útero não examinado."],
            ["cervix", "1 = fechado, 2 = intermédio, 3 = aberto."],
            ["ovulacao / folic_hemorragico", "sim / nao / nao_avaliado. Vazio = não registado nesse exame."],
            ["dg (Exames)", "positivo / negativo / inconclusivo / sem_exame, como escrito no registo."],
            ["Diagnósticos", "Um por exame, na etapa D+14 / D+28 / D+45 contada desde a inseminação; não se substituem."],
            ["lote_concentracao / lote_motilidade", "Do lote usado (10⁶/mL e %). Motilidade sempre pós-descongelação. 0 pode querer dizer «não registado»."],
            ["lote_origem", "interno (vazio ou «Não» na origem externa) ou externo."],
            ["resultado_atual", "Estado da inseminação na app hoje (pendente / gestacao_confirmada / falhou)."],
            ["Datas e horas", "AAAA-MM-DD e HH:MM. Inseminações antigas podem não ter hora."],
            ["inducao / inducao_produto", "Indução da ovulação registada nesse exame: data e hora previstas da administração e produto."],
            ["Estadias", "Entrada e saída de cada égua; estado_saida = gestante / alta / sem_resultado / transferido (vazio se ainda está)."],
        ],
    )
    t_estadias = (
        "Estadias",
        ["egua", "estadia", "entrada", "saida", "estado_saida", "motivo"],
        [[_cod("E", aid), _cod("S", eid), _txt(ent), _txt(sai), est if sai else None, mot] for aid, eid, ent, sai, est, mot in estadias],
    )
    return [t_eguas, t_exames, t_insem, t_diag, t_estadias, legenda]


if __name__ == "__main__":
    from modules.relatorio_export import gerar_excel

    ap = argparse.ArgumentParser(description="Exporta os eventos reprodutivos para Excel.")
    ap.add_argument("--inicio", type=date.fromisoformat)
    ap.add_argument("--fim", type=date.fromisoformat)
    ap.add_argument("ficheiro", nargs="?", default=f"eventos_{datetime.now():%Y%m%d}.xlsx")
    a = ap.parse_args()
    Path(a.ficheiro).write_bytes(gerar_excel("EquiCore — eventos reprodutivos", [], tabelas_eventos(a.inicio, a.fim)))
    print(f"✅ {a.ficheiro}")
