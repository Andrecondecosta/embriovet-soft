"""Localização das éguas externas (na entrada "externo"): onde está a égua,
em texto e, se se quiser, o ponto no mapa — e o link "Abrir no mapa".

Ao criar a entrada externa vem preenchida com a morada do proprietário; pode
mudar-se na ficha ("Usar a minha localização" no telemóvel, ou colar um link
do Google Maps). Sem nada, o mapa abre na morada do proprietário.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.deps import get_current_user
from modules.db import get_connection

router = APIRouter(prefix="/api/estadias", tags=["localizacao"])

COORDS = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


def morada_do_dono(cur, dono_id: int | None) -> str | None:
    if not dono_id:
        return None
    cur.execute("SELECT morada, codigo_postal, cidade FROM dono WHERE id = %s", (dono_id,))
    r = cur.fetchone()
    if not r:
        return None
    morada, cp, cidade = r
    texto = ", ".join(x for x in [(morada or "").strip(), " ".join(x for x in [(cp or "").strip(), (cidade or "").strip()] if x)] if x)
    return texto or None


def link_mapa(texto: str | None, mapa: str | None, morada: str | None = None) -> str | None:
    """Link para o caminho no Google Maps (abre a app de mapas no telemóvel)."""
    if mapa:
        m = COORDS.match(mapa)
        if m:
            return f"https://www.google.com/maps/dir/?api=1&destination={m.group(1)},{m.group(2)}"
        if mapa.startswith(("http://", "https://")):
            return mapa
    destino = (texto or "").strip() or (morada or "").strip()
    return f"https://www.google.com/maps/dir/?api=1&destination={quote(destino)}" if destino else None


def preencher_da_morada(cur, estadia_id: int) -> None:
    """Entrada externa sem localização: fica com a morada do proprietário."""
    cur.execute("SELECT tipo_registo, dono_id, localizacao FROM estadias WHERE id = %s", (estadia_id,))
    r = cur.fetchone()
    if r and r[0] == "externo" and not (r[2] or "").strip():
        cur.execute("UPDATE estadias SET localizacao = %s WHERE id = %s", (morada_do_dono(cur, r[1]), estadia_id))


def da_entrada(cur, animal_id: int) -> dict | None:
    """Localização da entrada externa em aberto do animal (para a ficha)."""
    cur.execute(
        """SELECT id, tipo_registo, localizacao, localizacao_mapa, dono_id FROM estadias
           WHERE animal_id = %s AND data_saida IS NULL ORDER BY data_entrada DESC, id DESC LIMIT 1""",
        (animal_id,),
    )
    r = cur.fetchone()
    if not r or r[1] != "externo":
        return None
    eid, _, texto, mapa, dono = r
    return {"estadia_id": eid, "texto": texto, "mapa": mapa, "link": link_mapa(texto, mapa, morada_do_dono(cur, dono))}


class LocalizacaoIn(BaseModel):
    texto: str | None = Field(default=None, max_length=300)
    mapa: str | None = Field(default=None, max_length=1000)

    @field_validator("texto", "mapa", mode="before")
    @classmethod
    def _limpar(cls, v):
        return (v.strip() or None) if isinstance(v, str) else v

    @field_validator("mapa")
    @classmethod
    def _mapa(cls, v):
        if v and not (COORDS.match(v) or v.startswith(("http://", "https://"))):
            raise HTTPException(422, {"code": "web.location.error.map", "params": {}})
        return v


@router.put("/{estadia_id:int}/localizacao")
def guardar(estadia_id: int, d: LocalizacaoIn, _user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tipo_registo FROM estadias WHERE id = %s", (estadia_id,))
            r = cur.fetchone()
            if not r:
                raise HTTPException(404, {"code": "web.stays.error.not_found", "params": {}})
            cur.execute("UPDATE estadias SET localizacao = %s, localizacao_mapa = %s WHERE id = %s", (d.texto, d.mapa, estadia_id))
        conn.commit()
    return {"ok": True}
