"""API da app nova (FastAPI).

Local:   venv/bin/uvicorn backend.main:app --reload --port 8000
         (o frontend em desenvolvimento corre à parte, ver frontend/README.md)

Em produção a mesma app serve também o frontend já compilado
(`frontend/dist`), por isso basta um serviço.
"""

from __future__ import annotations

from backend import config  # noqa: F401 — tem de vir antes de `modules.*`

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIST, IS_RENDER
from backend.deps import pode_escrever
from backend.routers import animais, auth, registo_clinico, dashboard, definicoes, estadias, faturacao, importar, inseminacoes, relatorios, trabalho, mapa, opcoes, owners, public, stock, transferencias

# A documentação da API só fora do Render (em produção não fica pública).
_DOCS = not IS_RENDER
app = FastAPI(
    title="EquiCore API",
    docs_url="/api/docs" if _DOCS else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if _DOCS else None,
)


@app.middleware("http")
async def cabecalhos_seguranca(request: Request, call_next):
    """Cabeçalhos de segurança em todas as respostas (a app só usa recursos
    da própria origem; imagens em data: são o logótipo)."""
    r = await call_next(request)
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("X-Frame-Options", "DENY")
    r.headers.setdefault("Referrer-Policy", "same-origin")
    r.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    if IS_RENDER:
        r.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return r


# Escrever/apagar exige Gestor em tudo menos login e público (backend/deps.py).
ESCRITA = [Depends(pode_escrever)]
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(owners.router, dependencies=ESCRITA)
app.include_router(opcoes.router, dependencies=ESCRITA)
app.include_router(stock.router, dependencies=ESCRITA)
app.include_router(transferencias.router, dependencies=ESCRITA)
app.include_router(mapa.router, dependencies=ESCRITA)
app.include_router(definicoes.router, dependencies=ESCRITA)
app.include_router(dashboard.router, dependencies=ESCRITA)
app.include_router(relatorios.router, dependencies=ESCRITA)
app.include_router(estadias.router, dependencies=ESCRITA)
app.include_router(trabalho.router, dependencies=ESCRITA)
app.include_router(animais.router, dependencies=ESCRITA)
app.include_router(registo_clinico.router, dependencies=ESCRITA)
app.include_router(inseminacoes.router, dependencies=ESCRITA)
app.include_router(importar.router, dependencies=ESCRITA)
# Faturação: autorização própria (não o nível) — ver `acesso_faturacao`.
app.include_router(faturacao.router)


@app.get("/api/health")
def health():
    return {"ok": True}


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # Qualquer rota que não seja da API devolve a app React, que trata
        # da navegação no browser.
        ficheiro = FRONTEND_DIST / path
        if path and ficheiro.is_file() and FRONTEND_DIST in ficheiro.resolve().parents:
            return FileResponse(ficheiro)
        return FileResponse(FRONTEND_DIST / "index.html")
