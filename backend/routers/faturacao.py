"""Faturação — estadias (dias) e armazenamento de sémen (palhetas × dias):
o que está por faturar e o que já foi faturado. Contas em
`modules/repositories/faturacao_repo.py`.

Só para quem tem `acesso_faturacao` (independente do nível: pode ser um
Visualizador da contabilidade a marcar faturas)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.deps import acesso_faturacao
from modules.repositories import faturacao_repo

router = APIRouter(prefix="/api/faturacao", tags=["faturacao"], dependencies=[Depends(acesso_faturacao)])

Tipo = Literal["estadia", "armazenamento"]


def _erro(http_status: int, code: str, **params):
    return HTTPException(http_status, {"code": code, "params": params})


def _periodo(inicio: date, fim: date):
    if fim < inicio:
        raise _erro(422, "web.billing.error.bad_period")


@router.get("/por-faturar")
def por_faturar(inicio: date, fim: date, dono_id: int | None = None, tipo: Tipo | None = None):
    _periodo(inicio, fim)
    return faturacao_repo.por_faturar(inicio, fim, dono_id, tipo)


class LinhaIn(BaseModel):
    tipo: Tipo
    ref_id: int
    inicio: date
    fim: date


class FaturarIn(BaseModel):
    fatura_numero: str = Field(max_length=60)
    fatura_data: date
    observacoes: str | None = None
    linhas: list[LinhaIn] = Field(min_length=1, max_length=2000)

    @field_validator("fatura_numero", "observacoes", mode="before")
    @classmethod
    def _limpar(cls, v):
        return v.strip() if isinstance(v, str) else v


@router.post("/faturar")
def faturar(d: FaturarIn, user: dict = Depends(acesso_faturacao)):
    if not d.fatura_numero:
        raise _erro(422, "web.billing.error.invoice_required")
    try:
        n = faturacao_repo.faturar(
            [l.model_dump() for l in d.linhas], d.fatura_numero, d.fatura_data, d.observacoes or None, user["username"]
        )
    except faturacao_repo.JaFaturado:
        raise _erro(409, "web.billing.error.changed")
    return {"linhas": n}


@router.get("/faturado")
def faturado(inicio: date, fim: date, dono_id: int | None = None, fatura: str | None = None, anuladas: bool = False):
    _periodo(inicio, fim)
    return faturacao_repo.faturado(inicio, fim, dono_id, (fatura or "").strip() or None, anuladas)


class AnularIn(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)


@router.post("/linhas/{linha_id}/anular")
def anular(linha_id: int, d: AnularIn, user: dict = Depends(acesso_faturacao)):
    if not d.motivo.strip():
        raise _erro(422, "web.billing.error.reason_required")
    if not faturacao_repo.anular(linha_id, d.motivo.strip(), user["username"]):
        raise _erro(404, "web.billing.error.not_found")
    return {"ok": True}
