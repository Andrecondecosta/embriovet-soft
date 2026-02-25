#!/bin/bash
# Script de inicialização para Render

echo "🚀 Iniciando EmbrioVet..."

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

# Iniciar Streamlit
echo "🎯 Iniciando Streamlit..."
streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=true