"""Faturação — estadias (dias) e armazenamento de sémen (palhetas × dias):
o que está por faturar e o que já foi faturado. Contas em
`modules/repositories/faturacao_repo.py`.

Só para quem tem `acesso_faturacao` (independente do nível: pode ser um
Visualizador da contabilidade a marcar faturas)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
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


class FaturaIn(BaseModel):
    """Uma fatura = um proprietário (`dono_id` None = lotes sem proprietário)."""
    dono_id: int | None
    fatura_numero: str = Field(default="", max_length=60)
    fatura_data: date
    # Primeiro fecho, de antes da app: o número da fatura pode não se saber.
    acerto_inicial: bool = False
    observacoes: str | None = None
    linhas: list[LinhaIn] = Field(min_length=1, max_length=2000)

    @field_validator("fatura_numero", "observacoes", mode="before")
    @classmethod
    def _limpar(cls, v):
        return v.strip() if isinstance(v, str) else v


class FaturarIn(BaseModel):
    faturas: list[FaturaIn] = Field(min_length=1, max_length=500)


@router.post("/faturar")
def faturar(d: FaturarIn, user: dict = Depends(acesso_faturacao)):
    if any(not f.fatura_numero and not f.acerto_inicial for f in d.faturas):
        raise _erro(422, "web.billing.error.invoice_required")
    try:
        n = faturacao_repo.faturar([f.model_dump() for f in d.faturas], user["username"])
    except faturacao_repo.JaFaturado:
        raise _erro(409, "web.billing.error.changed")
    except faturacao_repo.OutroDono:
        raise _erro(422, "web.billing.error.one_owner")
    return {"linhas": n}


class ResumoIn(BaseModel):
    linhas: list[LinhaIn] = Field(min_length=1, max_length=2000)
    dono_ids: list[int] = Field(default_factory=list, max_length=500)


@router.post("/resumo")
def resumo(d: ResumoIn):
    """Para o resumo antes de faturar (e o PDF): o porquê de cada mudança de
    palhetas nos lotes e os dados de cada proprietário."""
    lotes = [l.model_dump() for l in d.linhas if l.tipo == "armazenamento"]
    return {"movimentos": faturacao_repo.movimentos(lotes), "donos": faturacao_repo.donos(d.dono_ids)}


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


# ── Por ano (proprietário × ano) ──────────────────────────────────────────

@router.get("/anos")
def anos(desde: int = Query(2025, ge=1990, le=2100)):
    return faturacao_repo.resumo_anual(min(desde, date.today().year))



@router.get("/atraso")
def atraso():
    """Quem tem estadias/sémen por faturar e desde quando (dashboard)."""
    return faturacao_repo.em_atraso()


@router.get("/numeros")
def numeros(n: list[str] = Query(default=[], max_length=500)):
    """Números de fatura já usados (e para que proprietário)."""
    return faturacao_repo.numeros_usados([x for x in n if x.strip()])

