# EquiCore — app nova (React + FastAPI)

Migração da app Streamlit, página a página. Enquanto não estiver completa,
a app Streamlit (`app.py`) continua a ser a que os clientes usam — nada
aqui é usado pelo deploy atual no Render (`start.sh`).

## Correr localmente

Dois terminais, a partir da raiz do projeto:

```bash
# 1. API (porta 8000) — liga-se sempre à base de TESTE (TEST_DATABASE_URL)
venv/bin/pip install -r backend/requirements.txt   # só na primeira vez
venv/bin/uvicorn backend.main:app --reload --reload-dir backend --reload-dir modules --port 8000

# 2. Frontend (porta 5180)
cd frontend && npm install && npm run dev
```

Abrir <http://localhost:5180>. As contas são as mesmas da app Streamlit.

## Estrutura

- `backend/` — FastAPI. Reutiliza `modules/repositories` e
  `modules/services`, por isso a lógica é a mesma das duas apps.
- `frontend/src/pages/` — uma pasta/ficheiro por página.
- Traduções: vêm de `modules/i18n.py` + `backend/i18n_web.py` (textos só da app nova).

## Estado da migração

| Página | Estado |
|---|---|
| Login + alterar credenciais | ✅ |
| Definições › Proprietários | ✅ (com paginação e pesquisa) |
| Stock de sémen › Lotes, Garanhões, Adicionar lote | ✅ |
| Stock de sémen › Transferências, Mapa, Importar | ⏳ |
| Restantes | ⏳ ainda na app Streamlit |

Todas as páginas são feitas e verificadas em telemóvel (~375px), tablet
(~820px) e computador.

## Produção (mais tarde)

`npm run build` gera `frontend/dist`; a API serve-o automaticamente, por
isso basta um serviço: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
