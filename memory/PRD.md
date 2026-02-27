# PRD — Embriovet Gestor (Mapa dos Contentores)

## Problema original
Substituir localização em texto livre por estrutura física com `contentores`, `canister` e `andar`, incluindo mapa visual com arrastar/soltar e persistência de posição.

## Arquitetura atual
- App monolítica em `app.py` (Streamlit + PostgreSQL via psycopg2)
- Tabelas relevantes: `contentores`, `estoque_dono`
- Página principal: **Mapa dos Contentores**

## Implementado (2026-02-27)
- Redesign profissional/técnico da página **Mapa dos Contentores** (mapa como elemento principal + layout contextual)
- Correção de persistência do drag-and-drop com `streamlit_js_eval` + `localStorage`
- Melhorias de interação solicitadas:
  - Clique no contentor abre painel/modal de inventário no próprio mapa (sem navegar)
  - Dois modos de uso: **normal** (bloqueado) e **editar mapa** (arrastável)
  - Botão **Salvar layout** persiste posições e retorna ao modo normal
  - Layout desktop: descrição à esquerda e mapa à direita
  - Layout mobile: empilhado vertical, painel de inventário adaptado e botões de toque
- Resiliência adicionada: fallback amigável quando `streamlit-js-eval` não estiver instalado
- Dependência: `streamlit-js-eval==1.0.0`
- Ajuste de prioridade visual do mapa:
  - toolbar compacta (ações principais) junto ao topo da área do mapa
  - indicadores discretos de `contentores` e `palhetas` em estilo técnico (inline, sem cards grandes)
  - redução de espaço vertical acima do mapa
  - layout desktop com maior área para o mapa (`[1,5]`) e mobile empilhado
- Higiene técnica: removido bloco morto/duplicado do mapa após `st.stop()` no `app.py`

## Testes e validação
- Teste automatizado anterior (iteration_3): **PASS 100% frontend** para persistência base
- Novos ciclos (iteration_4 e iteration_5): validação funcional bloqueada por ambiente sem PostgreSQL (`localhost:5432` indisponível), mas code review confirmou implementação das melhorias de interação e organização visual
- Evidências: `/app/test_reports/iteration_3.json`, `/app/test_reports/iteration_4.json`, `/app/test_reports/iteration_5.json`

## Backlog priorizado
### P0
- Concluído: persistência de posição do mapa

### P1
- Aplicar filtro de data (data única/período) nas consultas dos relatórios

### P2
- Teste aprofundado da regra de segurança de exclusão de contentor com stock > 0
- Refatorar `app.py` em módulos menores (DB/UI/relatórios)
