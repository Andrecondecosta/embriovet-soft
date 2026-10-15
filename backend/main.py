"""API da app nova (FastAPI).

Local:   venv/bin/uvicorn backend.main:app --reload --port 8000
         (o frontend em desenvolvimento corre à parte, ver frontend/README.md)

Em produção a mesma app serve também o frontend já compilado
(`frontend/dist`), por isso basta um serviço.
"""

from __future__ import annotations

from backend import config  # noqa: F401 — tem de vir antes de `modules.*`

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIST
from backend.routers import auth, dashboard, definicoes, relatorios, mapa, opcoes, owners, public, stock, transferencias

app = FastAPI(title="EquiCore API", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(owners.router)
app.include_router(opcoes.router)
app.include_router(stock.router)
app.include_router(transferencias.router)
app.include_router(mapa.router)
app.include_router(definicoes.router)
app.include_router(dashboard.router)
app.include_router(relatorios.router)


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
