"""Guarda-costas barato contra "nome usado mas nunca importado" — a
classe de bug encontrada em `map_page.py` (chamava `editar_contentor`,
`deletar_contentor`, `mover_lotes_por_andar` e `atualizar_andar_lote`
sem os importar; só rebentava em runtime, ao clicar no botão certo) e
depois também em `owners_view.py` (`time`) e `users_view.py` (`user`).

Usa `pyflakes` (análise estática, sem precisar de importar o módulo —
o que evitaria efeitos secundários de módulos Streamlit a nível de
página) e falha se aparecer um `UndefinedName` num dos ficheiros
verificados. Cobre todo o `modules/pages/` (onde os 3 casos até agora
apareceram) mais `container_repo.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pyflakes_checker = pytest.importorskip("pyflakes.checker")
pyflakes_messages = pytest.importorskip("pyflakes.messages")
Checker = pyflakes_checker.Checker
UndefinedName = pyflakes_messages.UndefinedName

ROOT = Path(__file__).resolve().parent.parent

FICHEIROS_VERIFICADOS = sorted(
    (ROOT / "modules" / "pages").glob("*.py")
) + [
    ROOT / "modules" / "repositories" / "container_repo.py",
]


def _undefined_names(caminho: Path) -> list[str]:
    src = caminho.read_text()
    tree = ast.parse(src, filename=str(caminho))
    checker = Checker(tree, filename=str(caminho))
    return [
        str(msg) for msg in checker.messages if isinstance(msg, UndefinedName)
    ]


@pytest.mark.parametrize("caminho", FICHEIROS_VERIFICADOS, ids=lambda p: p.name)
def test_sem_nomes_por_importar(caminho: Path):
    problemas = _undefined_names(caminho)
    assert not problemas, (
        "Nome(s) usados sem import (ou definição local) — provável "
        "import em falta:\n" + "\n".join(problemas)
    )
