#!/bin/bash
# Script de inicialização para Render

echo "🚀 Iniciando EquiCore..."

# Configurar banco de dados na primeira execução
if [ ! -f ".db_initialized" ]; then
    echo "📦 Configurando banco de dados pela primeira vez..."
    python setup_database.py
    
    if [ $? -eq 0 ]; then
        touch .db_initialized
        echo "✅ Banco de dados inicializado"
    else
        echo "❌ Erro ao inicializar banco de dados"
        exit 1
    fi
else
    echo "✅ Banco de dados já inicializado"
fi

# Ecrã de carregamento: símbolo a rodar em vez dos traços cinzentos
# (nunca impede o arranque — o script devolve sempre 0)
python scripts/personalizar_carregamento.py || true

# App nova (FastAPI + React) — é a principal. Volta à antiga (Streamlit) se
# EQUICORE_APP=streamlit nas variáveis do Render, ou se o frontend não foi
# compilado (build command antigo, sem `bash render-build.sh`).
if [ "${EQUICORE_APP:-}" != "streamlit" ] && [ -f frontend/dist/index.html ]; then
    echo "📦 A aplicar migrations..."
    python scripts/aplicar_migracoes.py
    echo "🎯 Iniciando EquiCore (app nova)..."
    exec uvicorn backend.main:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}" \
        --proxy-headers \
        --forwarded-allow-ips="*"
fi

# Iniciar Streamlit
echo "🎯 Iniciando Streamlit..."
streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=true