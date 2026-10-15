"""Dashboard — visão do dia, só leitura. Equivalente a
`modules/pages/dashboard_page.py`, com as mesmas consultas
(`modules/repositories/dashboard_repo.py`), num só pedido."""

from __future__ import annotations

import math
from datetime import date, datetime

from fastapi import APIRouter, Depends

from backend.deps import get_current_user
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


def _valor(v):
    """Valores do pandas → JSON (datas em ISO, NaN → null, numpy → Python)."""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):  # numpy int64/float64
        v = v.item()
        return None if isinstance(v, float) and math.isnan(v) else v
    if hasattr(v, "isoformat"):  # pandas Timestamp
        return v.isoformat()
    return v


def _registos(df, colunas: dict[str, str]) -> list[dict]:
    """DataFrame → lista de dicionários, com as colunas renomeadas."""
    return [{novo: _valor(r[antigo]) for antigo, novo in colunas.items()} for _, r in df.iterrows()]


@router.get("")
def dashboard(_user: dict = Depends(get_current_user)):
    return {
        "stock": carregar_kpis_stock(),
        "clinica": carregar_kpis_clinicos(),
        "hoje": _registos(
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
            "itens": _registos(
                carregar_partos_previstos(dias=DIAS_PARTOS),
                {"egua": "egua", "data_parto_previsto": "data", "dias_restantes": "dias"},
            ),
        },
        "atencao": {
            "limite": LIMITE_STOCK_ATENCAO,
            "itens": _registos(
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
            r for r in _registos(carregar_stock_por_contentor(limit=10), {"Contentor": "nome", "Palhetas": "palhetas"}) if r["palhetas"]
        ],
        "por_proprietario": [
            r
            for r in _registos(carregar_stock_por_proprietario(limit=8), {"Proprietário": "nome", "Palhetas": "palhetas"})
            if r["palhetas"]
        ],
    }
