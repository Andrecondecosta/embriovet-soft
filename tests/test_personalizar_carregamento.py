"""Ecrã de carregamento (símbolo a rodar em vez dos traços cinzentos):
o script que acrescenta o CSS à página base do Streamlit."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from personalizar_carregamento import FIM, INICIO, _cor_primaria, aplicar  # noqa: E402

HTML = "<html>\n  <head>\n    <title>x</title>\n  </head>\n  <body></body>\n</html>\n"


def test_insere_antes_do_head_e_e_idempotente(tmp_path):
    f = tmp_path / "index.html"
    f.write_text(HTML)
    assert aplicar(f, "#123456") is True
    texto = f.read_text()
    assert texto.count(INICIO) == 1 and texto.count(FIM) == 1
    assert texto.index(FIM) < texto.index("</head>")
    assert "stAppSkeleton" in texto and "#123456" in texto

    assert aplicar(f, "#123456") is False  # repetir não duplica nem muda
    assert f.read_text() == texto


def test_mudar_cor_substitui_o_bloco(tmp_path):
    f = tmp_path / "index.html"
    f.write_text(HTML)
    aplicar(f, "#111111")
    assert aplicar(f, "#222222") is True
    texto = f.read_text()
    assert texto.count(INICIO) == 1
    assert "#222222" in texto and "#111111" not in texto


def test_sem_head_nao_mexe(tmp_path):
    f = tmp_path / "index.html"
    f.write_text("<div></div>")
    assert aplicar(f) is False
    assert f.read_text() == "<div></div>"


def test_cor_do_config_toml(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[theme]\nprimaryColor = "#E85D4A"\n')
    assert _cor_primaria(cfg) == "#E85D4A"
    assert _cor_primaria(tmp_path / "nao_existe.toml") == "#E85D4A"
