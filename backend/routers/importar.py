"""Importar sémen — equivalente a `modules/pages/import_page.py`.

O assistente da app atual guarda o estado na sessão do Streamlit; aqui
cada passo é um pedido e o ecrã guarda as linhas:

1. `POST /ler` — lê o ficheiro (CSV/Excel, enviado em base64) com o mesmo
   mapa de colunas e devolve as linhas;
2. `POST /entidades` — proprietários/contentores que não existem;
   `POST /proprietario` e `POST /contentor` criam-nos (ou o ecrã mapeia um
   proprietário para um existente);
3. `POST /validar` — as mesmas regras (`_validate_import_df`);
4. `POST /executar` — valida outra vez e grava tudo numa transação.
"""

from __future__ import annotations

import base64
import binascii
import datetime
from io import BytesIO
from unittest.mock import patch

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator

from backend.deps import get_current_user
from backend.serial import anexo, valor
from modules.db import get_connection, invalidate_data_cache, to_py
from modules.pages import import_page
from modules.pages.import_page import (
    ALIAS_MAP,
    REQUIRED_COLS,
    _gerar_template_csv,
    _gerar_template_xlsx,
    _is_empty,
    _normalizar_coluna,
)
from modules.repositories.container_repo import adicionar_contentor, obter_ou_criar_contentor_temporario
from modules.repositories.owner_repo import adicionar_proprietario
from modules.repositories.stock_repo import carregar_contentores, carregar_proprietarios

router = APIRouter(prefix="/api/importar", tags=["importar"])

COLUNAS = [
    "garanhao", "data_embriovet/ref", "existencia_atual", "dose", "motilidade", "qualidade", "concentracao", "cor",
    "proprietario_nome", "contentor_codigo", "canister", "andar", "observacoes", "certificado",
]
FICHEIRO_MAX = 5_000_000


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _celula(v):
    """Célula → texto (vazio para NaN), como o ecrã a mostra e edita."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (datetime.date, datetime.datetime, pd.Timestamp)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


@router.get("/modelo")
def modelo(formato: str = "xlsx", _user: dict = Depends(get_current_user)):
    if formato == "csv":
        return Response(_gerar_template_csv(), media_type="text/csv", headers=anexo("template_importar_semen.csv"))
    return Response(
        _gerar_template_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=anexo("template_importar_semen.xlsx"),
    )


class FicheiroIn(BaseModel):
    nome: str
    conteudo: str  # base64


@router.post("/ler")
def ler(f: FicheiroIn, _user: dict = Depends(get_current_user)):
    try:
        dados = base64.b64decode(f.conteudo, validate=True)
    except (binascii.Error, ValueError) as e:
        raise _erro(422, "web.import.error.bad_file") from e
    if len(dados) > FICHEIRO_MAX:
        raise _erro(413, "web.import.error.too_big", mb=FICHEIRO_MAX // 1_000_000)
    try:
        if f.nome.lower().endswith(".csv"):
            raw = pd.read_csv(BytesIO(dados))
        elif f.nome.lower().endswith((".xlsx", ".xls")):
            raw = pd.read_excel(BytesIO(dados))
        else:
            raise _erro(422, "web.import.error.bad_type")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — ficheiro ilegível
        raise _erro(422, "import.read_error", error=str(e)) from e
    if raw.empty:
        raise _erro(422, "import.file_empty")
    # O mesmo mapa de colunas (aceita "palhetas", "dono", "contentor"…).
    col_map: dict[str, str] = {}
    for col in raw.columns:
        k = ALIAS_MAP.get(_normalizar_coluna(col))
        if k and k not in col_map:
            col_map[k] = col
    falta = [c for c in REQUIRED_COLS if c not in col_map]
    if falta:
        raise _erro(422, "import.missing_columns", cols=", ".join(falta))
    linhas = []
    for i, r in raw.iterrows():
        linha = {c: "" for c in COLUNAS}
        for k, col in col_map.items():
            linha["data_embriovet/ref" if k == "data_ref" else k] = _celula(r[col])
        linha["__row"] = int(i) + 2
        linhas.append(linha)
    return {"linhas": linhas}


class LinhasIn(BaseModel):
    linhas: list[dict]
    # Proprietários da folha mapeados para um existente: {nome em minúsculas: id}.
    mapa_donos: dict[str, int] = {}

    @field_validator("linhas")
    @classmethod
    def _nao_vazio(cls, v):
        if not v:
            raise ValueError("import.file_empty")
        return v


def _df(linhas: list[dict]) -> tuple[pd.DataFrame, list[int]]:
    df = pd.DataFrame([{c: l.get(c, "") for c in COLUNAS} for l in linhas])
    return df, [int(l.get("__row") or i + 2) for i, l in enumerate(linhas)]


@router.post("/entidades")
def entidades(d: LinhasIn, _user: dict = Depends(get_current_user)):
    """Proprietários e contentores da folha que ainda não existem."""
    props = carregar_proprietarios(apenas_ativos=False)
    conts = carregar_contentores(apenas_ativos=False)
    donos = {str(n).strip().lower() for n in props.get("nome", [])}
    codigos = {str(c).strip().upper() for c in conts.get("codigo", [])}
    novos_donos, novos_conts = [], []
    for l in d.linhas:
        p = str(l.get("proprietario_nome") or "").strip()
        if p and not _is_empty(p) and p.lower() not in donos and p.lower() not in d.mapa_donos and p not in novos_donos:
            novos_donos.append(p)
        c = str(l.get("contentor_codigo") or "").strip()
        if c and not _is_empty(c) and c.upper() not in codigos and c not in novos_conts:
            novos_conts.append(c)
    return {
        "proprietarios": novos_donos,
        "contentores": novos_conts,
        "existentes": [{"id": int(i), "nome": n} for i, n in zip(props.get("id", []), props.get("nome", []))],
    }


class NomeIn(BaseModel):
    nome: str


@router.post("/proprietario", status_code=201)
def criar_proprietario(d: NomeIn, _user: dict = Depends(get_current_user)):
    nome = d.nome.strip()
    if not nome:
        raise _erro(422, "error.name_required")
    pid = adicionar_proprietario(
        {"nome": nome, "email": None, "telemovel": None, "nome_completo": None, "nif": None, "morada": None, "codigo_postal": None, "cidade": None}
    )
    if not pid:
        raise _erro(409, "web.import.error.owner_create")
    return {"id": int(pid)}


class ContentorIn(BaseModel):
    codigo: str
    descricao: str | None = None


@router.post("/contentor", status_code=201)
def criar_contentor(d: ContentorIn, _user: dict = Depends(get_current_user)):
    codigo = d.codigo.strip()
    if not codigo:
        raise _erro(422, "map.container_code_required_error")
    cid = adicionar_contentor({"codigo": codigo, "descricao": (d.descricao or "").strip(), "x": 100, "y": 100, "w": 150, "h": 150})
    if not cid:
        raise _erro(409, "web.import.error.container_create")
    return {"id": int(cid)}


def _validar(d: LinhasIn):
    """As mesmas regras da app atual. As mensagens saem como chaves de
    tradução (o ecrã traduz) em vez do texto em português."""
    df, nums = _df(d.linhas)
    props = carregar_proprietarios(apenas_ativos=False)
    conts = carregar_contentores(apenas_ativos=False)
    prop_map = {str(n).strip().lower(): int(i) for i, n in zip(props.get("id", []), props.get("nome", []))}
    prop_map.update({k.lower(): v for k, v in d.mapa_donos.items()})
    cont_map = {str(c).strip().upper(): int(i) for c, i in zip(conts.get("codigo", []), conts.get("id", []))}
    # Contentor "TEMPORÁRIO" só se alguma linha vier sem contentor (como a app atual).
    temp = obter_ou_criar_contentor_temporario() if df["contentor_codigo"].apply(lambda v: _is_empty(str(v).strip())).any() else None
    with patch.object(import_page, "t", lambda chave, **_: chave):
        erros, erros_df, validas = import_page._validate_import_df(df, nums, cont_map, prop_map, temp)
    lista = [{"linha": int(r["linha"]), "coluna": r["coluna"], "erro": r["erro"]} for _, r in erros_df.iterrows()] if not erros_df.empty else []
    return lista, validas


@router.post("/validar")
def validar(d: LinhasIn, _user: dict = Depends(get_current_user)):
    erros, validas = _validar(d)
    com_data = sum(1 for l in d.linhas if not _is_empty(l.get("data_embriovet/ref")))
    return {"total": len(d.linhas), "validas": len(d.linhas) - len({e["linha"] for e in erros}), "erros": erros, "com_data": com_data}


@router.post("/executar")
def executar(d: LinhasIn, user: dict = Depends(get_current_user)):
    erros, linhas = _validar(d)
    if erros or not linhas:
        raise _erro(422, "import.validation_errors")
    from modules.repositories.animal_repo import get_or_create_garanhao

    # Um animal por garanhão distinto, antes da ligação principal (como a app atual).
    animais = {g: get_or_create_garanhao(g) for g in {l["garanhao"] for l in linhas}}
    relatorio = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                for l in linhas:
                    de = l.get("data_embriovet")
                    # data_criacao = 1 de janeiro do ano do documento (não a data da importação).
                    if de and hasattr(de, "year"):
                        criacao = datetime.date(de.year, 1, 1)
                        nota = f"{criacao.isoformat()}"
                    else:
                        criacao, nota = datetime.date.today(), ""
                    cur.execute(
                        """
                        INSERT INTO estoque_dono (
                            garanhao, dono_id, data_embriovet, origem_externa, palhetas_produzidas, qualidade,
                            concentracao, motilidade, certificado, dose, observacoes, quantidade_inicial,
                            existencia_atual, contentor_id, canister, andar, cor, criado_por, data_criacao, animal_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        tuple(
                            to_py(v)
                            for v in (
                                l["garanhao"], l.get("prop_id"), de, l.get("origem_externa"), l["existencia_atual"],
                                l.get("qualidade"), l.get("concentracao"), l.get("motilidade"), l.get("certificado"),
                                l.get("dose"), l.get("observacoes"), l["existencia_atual"], l["existencia_atual"],
                                l.get("contentor_id"), l.get("canister"), l.get("andar"), l.get("cor"),
                                user["username"], criacao, animais.get(l["garanhao"]),
                            )
                        ),
                    )
                    relatorio.append(
                        {
                            "linha": l["linha"],
                            "garanhao": l["garanhao"],
                            "proprietario": l.get("proprietario_nome") or "",
                            "palhetas": l["existencia_atual"],
                            "stock_id": cur.fetchone()[0],
                            "data_ajustada": nota,
                        }
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise _erro(500, "import.failed", error=str(e)) from e
    invalidate_data_cache()
    return {"importados": len(relatorio), "relatorio": [{k: valor(v) for k, v in r.items()} for r in relatorio]}
