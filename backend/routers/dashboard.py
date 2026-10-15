"""Dashboard — visão do dia, só leitura. Equivalente a
`modules/pages/dashboard_page.py`, com as mesmas consultas
(`modules/repositories/dashboard_repo.py`), num só pedido."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import get_current_user
from backend.serial import registos
from modules.repositories.dashboard_repo import (
    carregar_atividade_recente_agrupada,
    carregar_kpis_clinicos,
    carregar_kpis_stock,
    carregar_partos_previstos,
    carregar_stock_atencao,
    carregar_stock_por_contentor,
    carregar_stock_por_proprietario,
    carregar_tarefas_hoje,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Mesmos valores fixos da página atual.
DIAS_PARTOS = 30
LIMITE_STOCK_ATENCAO = 5


@router.get("")
def dashboard(_user: dict = Depends(get_current_user)):
    return {
        "stock": carregar_kpis_stock(),
        "clinica": carregar_kpis_clinicos(),
        "hoje": registos(
            carregar_tarefas_hoje(),
            {"tarefa_id": "id", "animal": "animal", "dono": "dono", "tipo": "tipo", "urgencia": "urgencia"},
        ),
        "atividade": [
            {
                "ts": o["ts"].isoformat() if o.get("ts") else None,
                "usuario": o.get("usuario"),
                "acao": o.get("acao"),
                "detalhe": o.get("detalhe"),
                "num_lotes": o.get("num_lotes"),
            }
            for o in carregar_atividade_recente_agrupada(limit=10)
        ],
        "partos": {
            "dias": DIAS_PARTOS,
            "itens": registos(
                carregar_partos_previstos(dias=DIAS_PARTOS),
                {"egua": "egua", "data_parto_previsto": "data", "dias_restantes": "dias"},
            ),
        },
        "atencao": {
            "limite": LIMITE_STOCK_ATENCAO,
            "itens": registos(
                carregar_stock_atencao(limite=LIMITE_STOCK_ATENCAO, top=10),
                {
                    "lote_id": "id",
                    "garanhao_nome": "garanhao",
                    "proprietario": "proprietario",
                    "contentor": "contentor",
                    "canister": "canister",
                    "andar": "andar",
                    "existencia_atual": "palhetas",
                },
            ),
        },
        "por_contentor": [
            r for r in registos(carregar_stock_por_contentor(limit=10), {"Contentor": "nome", "Palhetas": "palhetas"}) if r["palhetas"]
        ],
        "por_proprietario": [
            r
            for r in registos(carregar_stock_por_proprietario(limit=8), {"Proprietário": "nome", "Palhetas": "palhetas"})
            if r["palhetas"]
        ],
    }
