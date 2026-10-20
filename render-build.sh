#!/bin/bash
# Build no Render: dependências Python (app antiga + API nova) e o frontend
# React compilado em frontend/dist (servido pela própria API).
# Se algum passo falhar, o Render não publica e a versão anterior continua.
set -euo pipefail

pip install -r requirements_streamlit.txt -r backend/requirements.txt

cd frontend
npm ci
npm run build
