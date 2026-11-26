"""Trabalho diário — equivalente a `modules/pages/trabalho_diario_page.py`.

Lista das tarefas por fazer num dia (com as de dias anteriores à parte,
"em atraso"), as feitas hoje e a barra de cobertura. Ao abrir a página, a
app atual cria tarefas de "1.ª observação" para animais internados sem
registo clínico; aqui isso é um pedido próprio (POST), chamado pelo ecrã
ao abrir, para a leitura não ter efeitos secundários.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from backend.deps import get_current_user
from backend.serial import registos
from modules.db import get_connection
from backend.routers.consultas import sem_proxima
from backend.routers.relatorios import TIPOS as TIPOS_FICHEIRO, _ficheiro, _t
from modules.relatorio_export import gerar_excel, gerar_pdf
from modules.pages.trabalho_diario_page import _gerar_tarefas_primeira_observacao
from modules.repositories.dashboard_repo import (
    carregar_resumo_tarefas_hoje,
    carregar_tarefas_feitas_hoje,
    carregar_tarefas_por_fazer,
)

router = APIRouter(prefix="/api/trabalho", tags=["trabalho"])

URGENCIA_ORDEM = {"urgente": 0, "hoje": 1, "amanha": 2, "observacao": 3}
COLS = ["tarefa_id", "animal_id", "estadia_id", "animal", "dono", "tipo", "motivo", "urgencia", "utilizador", "data_tarefa"]


@router.post("/gerar")
def gerar(_user: dict = Depends(get_current_user)):
    return {"criadas": _gerar_tarefas_primeira_observacao()}


@router.get("")
def trabalho(dia: date | None = None, _user: dict = Depends(get_current_user)):
    dia = dia or date.today()
    tarefas = registos(carregar_tarefas_por_fazer(dia), COLS + ["dias_atraso"])
    normais = sorted(
        (x for x in tarefas if not x["dias_atraso"]),
        key=lambda x: (URGENCIA_ORDEM.get(x["urgencia"], 9), (x["animal"] or "").lower()),
    )
    atrasadas = sorted((x for x in tarefas if x["dias_atraso"]), key=lambda x: -x["dias_atraso"])
    return {
        "dia": dia.isoformat(),
        # Fixo em hoje, como a barra da app atual (não muda com o dia visto).
        "resumo": carregar_resumo_tarefas_hoje(),
        "por_fazer": normais,
        "atrasadas": atrasadas,
        "feitas": registos(carregar_tarefas_feitas_hoje(), COLS + ["concluida_por", "data_conclusao"]),
        # Éguas com consulta gravada e sem a próxima marcada.
        "sem_proxima": sem_proxima(),
    }


# ── Concluir / cancelar à mão (também tarefas em atraso e de estadias já
#    fechadas, que o registo clínico não fecha) ──────────────────────────

class ConcluirIn(BaseModel):
    observacoes: str | None = None


# Estas fecham-se com a resposta (registo clínico, DG ou a inseminação),
# não com "concluir": senão a ovulação / o diagnóstico ficam por saber.
PEDEM_RESPOSTA = ("verificar_ovulacao", "diagnostico_gestacao", "confirmacao_gestacao", "segunda_confirmacao", "inseminar")


@router.post("/{tarefa_id:int}/concluir")
def concluir(tarefa_id: int, d: ConcluirIn, user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tipo FROM trabalho_diario WHERE id = %s", (tarefa_id,))
            row = cur.fetchone()
            if row and row[0] in PEDEM_RESPOSTA:
                raise HTTPException(409, {"code": "web.work.error.needs_answer", "params": {}})
            cur.execute(
                """
                UPDATE trabalho_diario
                SET concluida = TRUE, data_conclusao = CURRENT_DATE, concluida_por = %s, observacoes_conclusao = %s
                WHERE id = %s AND concluida = FALSE
                """,
                (user["username"][:50], (d.observacoes or "").strip() or None, tarefa_id),
            )
            feito = cur.rowcount
        conn.commit()
    if not feito:
        raise HTTPException(404, {"code": "web.work.error.task_not_found", "params": {}})
    return {"ok": True}


@router.post("/{tarefa_id:int}/cancelar")
def cancelar(tarefa_id: int, user: dict = Depends(get_current_user)):
    """Cancela uma tarefa por fazer: sai das listas mas fica registada
    (`cancelada`), e não conta como feita."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE trabalho_diario
                SET concluida = TRUE, cancelada = TRUE, data_conclusao = CURRENT_DATE, concluida_por = %s
                WHERE id = %s AND concluida = FALSE
                """,
                (user["username"][:50], tarefa_id),
            )
            feito = cur.rowcount
        conn.commit()
    if not feito:
        raise HTTPException(404, {"code": "web.work.error.task_not_found", "params": {}})
    return {"ok": True}


# ── Exportar (para dar ao tratador: as éguas de um proprietário a ver nos
#    próximos dias, em PDF ou Excel) ────────────────────────────────────────

# As mesmas cores do ecrã: tratamentos (amarelo), consultas e diagnósticos
# (verde), urgentes (vermelho).
CONSULTAS = ("observacao_clinica", "primeira_observacao", "verificar_ovulacao",
             "diagnostico_gestacao", "confirmacao_gestacao", "segunda_confirmacao")
SEMPRE_URGENTES = ("inseminar", "induzir")
Categoria = Literal["todos", "tratamentos", "consultas", "urgentes"]


def categoria(tipo: str, urgencia: str | None) -> str:
    if urgencia == "urgente" or tipo in SEMPRE_URGENTES:
        return "urgentes"
    return "tratamentos" if tipo == "tratamento" else "consultas" if tipo in CONSULTAS else "outras"


def _rotulo(tipo: str, motivo: str | None) -> str:
    """O que está no retângulo do ecrã: "PG, Ocitocina", "Induzir 20:00", "Consulta"…"""
    m = motivo or ""
    if tipo == "tratamento" and m:
        return ", ".join(p.split(" ")[0] for p in m.removeprefix("Tratamento:").strip().split(" · ") if p)
    nome = _t(f"web.task.{tipo}")
    if tipo == "induzir" and " às " in m:
        return f"{nome} {m.rsplit(' às ', 1)[1]}"
    return nome


def _pormenor(tipo: str, motivo: str | None) -> str:
    if tipo in ("tratamento", "induzir", "inseminar", "observacao_clinica") and motivo:
        return motivo.removeprefix("Tratamento:").strip()
    return ""


@router.get("/exportar")
def exportar(
    inicio: date,
    fim: date,
    formato: Literal["pdf", "xlsx"] = "pdf",
    dono_id: int | None = None,
    tipo: Categoria = "todos",
    _user: dict = Depends(get_current_user),
):
    if fim < inicio:
        raise HTTPException(422, {"code": "web.billing.error.bad_period", "params": {}})
    hoje = date.today()
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Por fazer no período, e as em atraso (para não ficarem esquecidas).
            cur.execute(
                """
                SELECT t.data_tarefa, t.tipo, t.motivo, t.urgencia, a.nome, d.nome, e.tipo_registo, al.nome
                FROM trabalho_diario t
                JOIN animais a ON a.id = t.animal_id
                LEFT JOIN dono d ON d.id = a.dono_id
                LEFT JOIN LATERAL (
                    SELECT tipo_registo, alojamento_id FROM estadias
                    WHERE animal_id = a.id AND data_saida IS NULL ORDER BY data_entrada DESC LIMIT 1
                ) e ON TRUE
                LEFT JOIN alojamentos al ON al.id = e.alojamento_id
                WHERE NOT t.concluida AND t.data_tarefa <= %(fim)s
                  AND (t.data_tarefa >= %(inicio)s OR t.data_tarefa < %(hoje)s)
                  AND (%(dono)s::int IS NULL OR a.dono_id = %(dono)s)
                ORDER BY t.data_tarefa, a.nome
                """,
                {"inicio": inicio, "fim": fim, "hoje": hoje, "dono": dono_id},
            )
            linhas = cur.fetchall()
            nome_dono = None
            if dono_id is not None:
                cur.execute("SELECT nome FROM dono WHERE id = %s", (dono_id,))
                r = cur.fetchone()
                nome_dono = r[0] if r else None

    def local(tipo_registo, alojamento):
        return _t("web.stays.kind.externo") if tipo_registo == "externo" else (alojamento or "—")

    com_dono = dono_id is None
    cab = [_t("web.daily.export.done"), _t("web.dashboard.mare")] + ([_t("web.dashboard.owner")] if com_dono else []) + [
        _t("web.daily.export.where"), _t("web.dashboard.task_type"), _t("web.daily.export.detail")]
    atrasadas, por_dia = [], {}
    for dia, tp, motivo, urg, egua, dono, tipo_registo, aloj in linhas:
        # Um tratamento urgente sai também em "Tratamentos" (e em "Urgentes").
        if tipo != "todos" and not (
            (tipo == "tratamentos" and tp == "tratamento")
            or (tipo == "consultas" and tp in CONSULTAS)
            or (tipo == "urgentes" and categoria(tp, urg) == "urgentes")
        ):
            continue
        linha = ["", egua] + ([dono or "—"] if com_dono else []) + [local(tipo_registo, aloj), _rotulo(tp, motivo), _pormenor(tp, motivo)]
        urgente = categoria(tp, urg) == "urgentes"
        if dia < hoje and dia < inicio:
            atrasadas.append((dia, urgente, linha))
        else:
            por_dia.setdefault(dia, []).append((urgente, linha))

    tabelas = []
    if atrasadas:
        tabelas.append((_t("web.daily.overdue"), cab + [_t("web.daily.export.since")],
                        [l + [d.strftime("%d/%m/%Y")] for d, _, l in sorted(atrasadas, key=lambda x: (not x[1], x[0]))]))
    for dia in sorted(por_dia):
        # Urgentes primeiro; depois por égua.
        filas = [l for _, l in sorted(por_dia[dia], key=lambda x: (not x[0], x[1][1].lower()))]
        tabelas.append((f"{_t(f'web.week.{dia.weekday()}')}, {dia:%d/%m/%Y}", cab, filas))

    titulo = _t("web.daily.export.title") + (f" — {nome_dono}" if nome_dono else "")
    sub = _t("web.daily.export.period", ini=inicio.strftime("%d/%m/%Y"), fim=fim.strftime("%d/%m/%Y"))
    if tipo != "todos":
        sub += f" · {_t(f'web.daily.type.{tipo}')}"
    nome = f"trabalho_{nome_dono or 'todos'}_{inicio:%Y%m%d}-{fim:%Y%m%d}.{formato}".replace(" ", "_").replace("/", "-")
    if formato == "pdf":
        dados = gerar_pdf(titulo, sub, [], tabelas, sem_dados=_t("web.daily.export.empty"), gerado_em=datetime.now())
    else:
        dados = gerar_excel(f"{titulo} · {sub}", [], tabelas)
    return _ficheiro(dados, nome, TIPOS_FICHEIRO[formato])
