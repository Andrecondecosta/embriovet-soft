# PRD — Embriovet Gestor (Mapa dos Contentores)

## Problema original
Substituir localização em texto livre por estrutura física com `contentores`, `canister` e `andar`, incluindo mapa visual com arrastar/soltar e persistência de posição.

## Arquitetura atual
- App monolítica em `app.py` (Streamlit + PostgreSQL via psycopg2)
- Tabelas relevantes: `contentores`, `estoque_dono`
- Página principal: **Mapa dos Contentores**

## Implementado (2026-02-27)
- Redesign profissional/técnico da página **Mapa dos Contentores** (visual neutro, sem duplicação na interface ativa)
- Correção do bug crítico de persistência do drag-and-drop:
  - iframe do mapa salva movimento em `parent.localStorage`
  - botão **Sincronizar mapa** dispara rerun
  - Streamlit lê payload via `streamlit_js_eval`, persiste `x,y` em PostgreSQL (`atualizar_posicao_contentor`) e limpa `localStorage`
- Adicionada dependência: `streamlit-js-eval==1.0.0`

## Testes e validação
- Teste automatizado (iteration_3): **PASS 100% frontend**
- Evidências: `/app/test_reports/iteration_3.json`
- Fluxo validado: mover contentor → salvar posição no banco → recarregar página mantendo posição

## Backlog priorizado
### P0
- Concluído: persistência de posição do mapa

### P1
- Aplicar filtro de data (data única/período) nas consultas dos relatórios

### P2
- Teste aprofundado da regra de segurança de exclusão de contentor com stock > 0
- Refatorar `app.py` em módulos menores (DB/UI/relatórios)
