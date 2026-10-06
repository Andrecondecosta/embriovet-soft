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

# Iniciar Streamlit
echo "🎯 Iniciando Streamlit..."
streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=true