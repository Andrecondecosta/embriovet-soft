"""Conversão de dados do pandas (tabelas dos repositórios) para JSON."""

from __future__ import annotations

import math
from datetime import date, datetime


def valor(v):
    """Datas em ISO, NaN/NaT → null, tipos do numpy → Python."""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, float) and math.isnan(v):
        return None
    if type(v).__name__ == "NaTType":
        return None
    if hasattr(v, "item"):  # numpy int64/float64
        v = v.item()
        return None if isinstance(v, float) and math.isnan(v) else v
    if hasattr(v, "isoformat"):  # pandas Timestamp
        return v.isoformat()
    return v


def registos(df, colunas: dict[str, str] | list[str]) -> list[dict]:
    """DataFrame → lista de dicionários. `colunas` pode renomear
    ({antiga: nova}); colunas em falta ficam a null."""
    if isinstance(colunas, list):
        colunas = {c: c for c in colunas}
    if df is None or df.empty:
        return []
    return [{novo: valor(r[antigo]) if antigo in df.columns else None for antigo, novo in colunas.items()} for _, r in df.iterrows()]


def anexo(nome: str) -> dict[str, str]:
    """Cabeçalho de descarga que aceita acentos no nome do ficheiro
    ("garanhao_Falcão.pdf"): versão ASCII para browsers antigos e a
    versão UTF-8 (RFC 6266/5987) para os outros."""
    import unicodedata
    from urllib.parse import quote

    ascii_ = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().replace('"', "")
    return {"Content-Disposition": f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nome)}"}
