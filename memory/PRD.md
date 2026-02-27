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
- Reestruturação UX completa da página **Relatórios** (mantendo lógica):
  - Navegação principal compacta por rádio horizontal (`Garanhão | Proprietário | Histórico Geral`)
  - Estrutura explícita em 3 zonas: **seleção**, **filtros** (colapsados por defeito), **resultados**
  - Exportações (CSV/PDF) posicionadas no topo da zona de resultados
  - Métricas em faixa técnica discreta (sem visual de dashboard)
  - Tabelas mais densas e consistentes para foco em análise
  - Base pronta para expansão de relatórios por contentor/localização/ocupação
- Next action concluído: UX técnica no módulo **Ver Stock**
  - Estrutura em 3 zonas (seleção/filtros/resultados)
  - Filtros colapsáveis compactos (proprietário, mínimo de palhetas, incluir lotes vazios)
  - Indicadores técnicos compactos + resumo por proprietário em tabela densa
  - Histórico técnico de transferências por garanhão + export CSV (internas/externas)
  - Histórico técnico por lote dentro de cada expander de lote
- Future/backlog concluído (Fase 1 de modularização sem alterar lógica):
  - Novo módulo `/app/modules/ui_kit.py` para CSS/helper UI reutilizáveis
  - Novo módulo `/app/modules/stock_reporting.py` para filtros/sumarização de stock e histórico técnico
  - `app.py` atualizado para consumir helpers modulares (base para fase 2)
- Continuação executada (next action + future/backlog):
  - Regra de segurança de exclusão de contentor reforçada na UI: botão “Apagar” desativado quando há stock > 0 + tooltip/caption explicativos, mantendo validação SQL no backend.
  - Novos relatórios adicionados em **Relatórios → Contentor / Localização** com:
    - filtros por garanhão, proprietário, canister e andar
    - KPIs técnicos de ocupação/contexto
    - tabela densa de lotes por localização física
    - histórico físico do sémen (entradas + transferências internas/externas quando disponíveis)
    - exportação CSV no topo da zona de resultados
  - Modularização avançada com novo módulo `/app/modules/stock_reporting.py` aplicado no `Ver Stock` (filtros, KPIs e histórico técnico)

## Testes e validação
- Teste automatizado anterior (iteration_3): **PASS 100% frontend** para persistência base
- Novos ciclos (iteration_4 e iteration_5): validação funcional bloqueada por ambiente sem PostgreSQL (`localhost:5432` indisponível), mas code review confirmou implementação das melhorias de interação e organização visual
- Evidências: `/app/test_reports/iteration_3.json`, `/app/test_reports/iteration_4.json`, `/app/test_reports/iteration_5.json`
- Reestruturação UX de Relatórios validada com **PASS 100% frontend**: `/app/test_reports/iteration_10.json`
- Ver Stock UX + modularização fase 1 validados com **PASS 100% frontend**: `/app/test_reports/iteration_11.json`
- Iteração seguinte (novas features) validada por code review do testing agent com app bloqueada por BD indisponível no ambiente de teste: `/app/test_reports/iteration_12.json`

## Backlog priorizado
### P0
- Concluído: persistência de posição do mapa

### P1
- Aplicar filtro de data (data única/período) nas consultas dos relatórios

### P2
- Teste aprofundado da regra de segurança de exclusão de contentor com stock > 0
- Refatorar `app.py` em módulos menores (DB/UI/relatórios) — **Fase 1 concluída**, pendente Fase 2 (extração de páginas completas)
- Concluir Fase 2: extrair páginas completas (Mapa, Ver Stock, Relatórios) para módulos dedicados com roteamento enxuto no `app.py`
