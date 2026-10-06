"""Troca o ecrã de carregamento do Streamlit (traços cinzentos a imitar
uma página) por um símbolo a rodar + "A carregar…".

Esse ecrã é desenhado pelo Streamlit antes de a app correr — o CSS da
app só chega depois, por isso não o consegue alterar. A única forma é
acrescentar o CSS à página base (`streamlit/static/index.html`). Corre
em cada arranque (`start.sh`), por isso sobrevive a reinstalações.

Seguro de repetir (substitui o bloco anterior). Se uma versão futura do
Streamlit mudar o ecrã de carregamento, o CSS simplesmente deixa de
apanhar nada e volta a ver-se o ecrã original — nunca parte a app.

Uso: python scripts/personalizar_carregamento.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INICIO = "<!-- embriovet:carregamento:inicio -->"
FIM = "<!-- embriovet:carregamento:fim -->"
COR_POR_OMISSAO = "#E85D4A"


def _cor_primaria(config_toml: Path) -> str:
    """`primaryColor` de .streamlit/config.toml (a mesma da app)."""
    try:
        m = re.search(r'^\s*primaryColor\s*=\s*"(#[0-9a-fA-F]{3,8})"', config_toml.read_text(), re.M)
        return m.group(1) if m else COR_POR_OMISSAO
    except OSError:
        return COR_POR_OMISSAO


def bloco_css(cor: str) -> str:
    # `stAppSkeleton` só é desenhado pelo Streamlit se o carregamento
    # passar de ~0,5 s — o símbolo herda esse atraso (carregamentos
    # rápidos não mostram nada).
    return f"""{INICIO}
    <style>
      [data-testid="stAppSkeleton"] > * {{ display: none !important; }}
      [data-testid="stAppSkeleton"] {{
        min-height: 60vh;
        display: flex !important;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 14px;
      }}
      [data-testid="stAppSkeleton"]::before {{
        content: "";
        width: 36px;
        height: 36px;
        border-radius: 50%;
        border: 3px solid rgba(148, 163, 184, 0.25);
        border-top-color: {cor};
        animation: embriovet-carregar 0.8s linear infinite;
      }}
      [data-testid="stAppSkeleton"]::after {{
        content: "A carregar…";
        color: #64748b;
        font-family: "Source Sans", "Source Sans Pro", sans-serif;
        font-size: 0.9rem;
      }}
      @keyframes embriovet-carregar {{ to {{ transform: rotate(360deg); }} }}
    </style>
    {FIM}"""


def aplicar(index_html: Path, cor: str = COR_POR_OMISSAO) -> bool:
    """Insere/actualiza o bloco antes de `</head>`. Devolve True se o
    ficheiro mudou."""
    original = index_html.read_text(encoding="utf-8")
    sem_bloco = re.sub(re.escape(INICIO) + r".*?" + re.escape(FIM) + r"\s*", "", original, flags=re.S)
    if "</head>" not in sem_bloco:
        return False
    novo = sem_bloco.replace("</head>", bloco_css(cor) + "\n  </head>", 1)
    if novo == original:
        return False
    index_html.write_text(novo, encoding="utf-8")
    return True


def main() -> int:
    try:
        import streamlit
    except ImportError:
        print("Streamlit não instalado — nada a fazer.")
        return 0
    index_html = Path(streamlit.__file__).parent / "static" / "index.html"
    if not index_html.exists():
        print(f"Não encontrei {index_html} — nada a fazer.")
        return 0
    raiz = Path(__file__).resolve().parent.parent
    cor = _cor_primaria(raiz / ".streamlit" / "config.toml")
    try:
        mudou = aplicar(index_html, cor)
    except OSError as e:  # ex.: sem permissão de escrita — a app arranca na mesma
        print(f"Não foi possível personalizar o carregamento: {e}")
        return 0
    print("Ecrã de carregamento personalizado." if mudou else "Ecrã de carregamento já personalizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
