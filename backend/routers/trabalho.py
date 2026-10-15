"""Trabalho diário — equivalente a `modules/pages/trabalho_diario_page.py`.

Lista das tarefas por fazer num dia (com as de dias anteriores à parte,
"em atraso"), as feitas hoje e a barra de cobertura. Ao abrir a página, a
app atual cria tarefas de "1.ª observação" para animais internados sem
registo clínico; aqui isso é um pedido próprio (POST), chamado pelo ecrã
ao abrir, para a leitura não ter efeitos secundários.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from backend.deps import get_current_user
from backend.serial import registos
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
    }
