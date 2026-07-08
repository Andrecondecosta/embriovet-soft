"""Repository de acesso à tabela `animais`."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from modules.db import get_connection, invalidate_data_cache


def _normalizar_nome(nome: Optional[str]) -> str:
    """Remove acentos, colapsa espaços internos e faz `strip`.

    Usado para matching case/acento-insensitive contra a UNIQUE INDEX
    `animais_nome_tipo_uniq` (migration 026).
    """
    if not nome:
        return ""
    txt = unicodedata.normalize("NFKD", str(nome))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip()


def get_or_create_garanhao(nome: Optional[str]) -> Optional[int]:
    """Devolve o id do garanhão em `animais` com o nome dado.

    - Faz matching case/acento-insensitive via `unaccent` + normalização
      de espaços internos, para que "Falcao" e "Falcão" nunca criem
      duplicados.
    - Se não existir, cria com `tipo='garanhao'`, `ativo=TRUE` e devolve
      o novo id. O nome guardado é a versão "limpa" (com espaços
      colapsados a um só, mas com acentos preservados).
    - Se `nome` for `None`/vazio, devolve `None`.
    """
    if not nome:
        return None
    nome_clean = re.sub(r"\s+", " ", str(nome)).strip()
    if not nome_clean:
        return None
    nome_norm = _normalizar_nome(nome_clean)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM animais "
            "WHERE tipo = 'garanhao' "
            "  AND LOWER(f_unaccent(TRIM(REGEXP_REPLACE(nome, '\\s+', ' ', 'g')))) "
            "      = LOWER(f_unaccent(%s)) "
            "LIMIT 1",
            (nome_norm,),
        )
        row = cur.fetchone()
        if row:
            cur.close()
            return int(row[0])

        cur.execute(
            "INSERT INTO animais (nome, tipo, ativo, created_at) "
            "VALUES (%s, 'garanhao', TRUE, NOW()) RETURNING id",
            (nome_clean,),
        )
        new_id = int(cur.fetchone()[0])
        conn.commit()
        cur.close()
        invalidate_data_cache()
        return new_id
