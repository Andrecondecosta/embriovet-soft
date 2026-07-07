"""Repository de acesso à tabela `animais`."""

from __future__ import annotations

from typing import Optional

from modules.db import get_connection


def get_or_create_garanhao(nome: Optional[str]) -> Optional[int]:
    """Devolve o id do garanhão em `animais` com o nome dado.

    - Faz `LOWER(TRIM(nome))` para matching case-insensitive.
    - Se não existir, cria com `tipo='garanhao'`, `ativo=TRUE` e devolve o novo id.
    - Se `nome` for `None`/vazio, devolve `None`.
    """
    if not nome:
        return None
    nome_norm = str(nome).strip()
    if not nome_norm:
        return None

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM animais "
            "WHERE tipo = 'garanhao' AND LOWER(nome) = LOWER(%s) LIMIT 1",
            (nome_norm,),
        )
        row = cur.fetchone()
        if row:
            cur.close()
            return int(row[0])

        cur.execute(
            "INSERT INTO animais (nome, tipo, ativo, created_at) "
            "VALUES (%s, 'garanhao', TRUE, NOW()) RETURNING id",
            (nome_norm,),
        )
        new_id = int(cur.fetchone()[0])
        conn.commit()
        cur.close()
        return new_id
