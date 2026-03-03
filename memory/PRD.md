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
- Fase 2 de modularização concluída (router + páginas extraídas):
  - Router central em `app.py` delega para módulos de página (`map_page`, `stock_page`, `reports_page`) e interrompe fluxo com `st.stop()`.
  - Páginas extraídas para `/app/modules/pages/`.
  - Bug crítico de escopo no `exec()` corrigido em todos os módulos de página (`exec(PAGE_CODE, local_ctx, local_ctx)`).
- Módulo **Registrar Inseminação** redesenhado (UX técnica, sem mudar lógica de negócio central):
  - Seleção de lotes em **modal** com filtros prévios por garanhão e proprietário
  - Lista densa por lote (ref/data, localização, motilidade, dose, disponível, qty com `- / +`)
  - Botão **Usar** recolhe lotes com qty > 0, soma duplicados automaticamente e atualiza página principal
  - Área **Linhas da inseminação** com edição por `- / +` + input numérico e remoção por linha
  - Regra de qty zero: remoção automática da linha
  - Validação de stock no UI e no backend
  - Novo fluxo transacional `registrar_inseminacao_multiplas` com `SELECT ... FOR UPDATE` para consistência
  - Correção do incremento/decremento nas linhas: estado unificado em `st.session_state`, keys únicas e sincronização com input numérico
  - Resumo rápido da inseminação (status bar compacta com total de palhetas e nº de lotes antes de registrar)
  - Modal de seleção simplificado: checkbox por lote, filtros compactos, confirmação adiciona lotes com qty=1 e mantém seleção entre aberturas
  - Nova página **Importar Sémen**: template XLSX/CSV (com fallback se openpyxl não estiver disponível), upload, preview com colunas reordenadas + sticky à esquerda + toggle compacta/completa, edição via `st.data_editor` com validação inline (células a vermelho + tooltip) e scroll automático para o primeiro erro, importação transacional e relatório de importação
- Redesign técnico do bloco **Transferir Palhetas** no Ver Stock: cabeçalho operacional compacto, controlo horizontal do tipo de operação, grelha de execução com stepper, avisos discretos e micro-resumo dinâmico
- Componente de **stepper** padronizado (render_stepper) com keys únicas e estado controlado por `st.session_state` aplicado em transferência e linhas de inseminação
  - Stepper estilizado com símbolos visíveis (− / +), tamanho mínimo e aria-labels/tooltip para acessibilidade
  - CSS do stepper reforçado para garantir visibilidade dos símbolos em todos os contextos (desktop/mobile)
  - CSS do stepper simplificado para alinhar visual ao fluxo de Inseminação
  - CSS de radio do Ver Stock agora escopado para evitar alterações no menu lateral
  - CSS base (stock/reports/stepper) aplicado globalmente após `set_page_config` para consistência
  - Stepper padronizado com layout **valor → − → +** e botões com `width="stretch"` para consistência entre Transferências e Inseminação
  - Fix no Ver Stock: índices de canister/andar convertidos para int para evitar erro de selectbox
  - Transferências corrigidas para usar coluna `estoque_id` (não `stock_id`)
  - Linhas do consumo/inseminação ajustadas para layout técnico: Ref | Localização | Disponível | Quantidade (stepper) | Remover
  - Página Registrar Inseminação modularizada em `/modules/pages/insemination_page.py` com modal de seleção por checkbox
  - Sistema de migrations SQL (sem SQLAlchemy) com `schema_migrations` e advisory lock
  - Migrations automáticas via `/app/migration_runner.py` com app_settings, onboarding e compatibilidade de transferencias
  - White-label por DB (company_name/logo/cor) + wizard inicial e forçar troca de credenciais no 1º login
  - Runner de migrations com logs (apply/skip/finished) e caminho dinâmico por `Path(__file__)`
  - Nova página “🏠 Dashboard” (clínico minimalista) com KPIs, alertas, atividade recente e ações rápidas
- Next Action concluído: **Fase 3 da modularização**
  - `map_page.py` e `stock_page.py` migrados para funções tipadas (sem `exec`).
  - Router consolidado no `app.py` para Mapa / Ver Stock / Relatórios.
  - Limpeza de código morto remanescente no `app.py`.
- Runtime atualizado para ambiente remoto:
  - `DATABASE_URL` ativa com Render PostgreSQL (`sslmode=require`).
  - Pool confirmado em logs: `✅ Pool criado com DATABASE_URL (sslmode=require)`.

## Implementado (2026-03-01)
- Modo QA i18n com pseudo-locale "zz" e diagnóstico de traduções no rodapé
- Toggle de QA i18n em Definições + idioma pseudo-locale disponível
- Map/Logins/Utilizadores/Definições alinhados 100% ao i18n

## Implementado (2026-03-02)
- Design system global aplicado (tipografia base, radius, sombras e espaçamento compacto)
- Header e Sidebar refinados para estilo SaaS premium (layout, alinhamentos e destaque ativo)
- Cards KPI do Dashboard com fundo branco e sombra leve
- Correção de indentação no modal de seleção de lotes (Registrar Inseminação)
- Sidebar forçado a iniciar expandido (evita ficar oculto com header nativo oculto)
- CSS de fallback para reabrir sidebar mesmo quando colapsado (sem toolbar nativa)
- CSS global ajustado para não esconder stHeader/stToolbar (mantém botão do sidebar)
- Correção de variável local `t` em reports_page (UnboundLocalError)
- Remoção do fallback forçado do sidebar para evitar duplicação do botão de recolher
- CSS atualizado para esconder Deploy bar e forçar sidebar sempre visível no topo
- Sidebar voltou ao comportamento nativo do Streamlit (header/toolbar visíveis)
- CSS ajustado para layout mais compacto (topo do conteúdo/sidebar) e header mais baixo; Deploy oculto
- Script/seletores reforçados para ocultar apenas o botão Deploy sem remover header/toolbar
- Persistência de sessão via query param para manter login após refresh
- Fluxo inicial com Welcome Page (EquiCore) antes do Setup e coluna welcome_completed
- CSS global atualizado para espaçamento compacto e ocultar apenas o item Deploy da toolbar
- Lotes agora suportam cor e qualidade em texto (migration 006) + import/template atualizados

## Testes e validação
- Teste automatizado anterior (iteration_3): **PASS 100% frontend** para persistência base
- Novos ciclos (iteration_4 e iteration_5): validação funcional bloqueada por ambiente sem PostgreSQL (`localhost:5432` indisponível), mas code review confirmou implementação das melhorias de interação e organização visual
- Evidências: `/app/test_reports/iteration_3.json`, `/app/test_reports/iteration_4.json`, `/app/test_reports/iteration_5.json`
- Reestruturação UX de Relatórios validada com **PASS 100% frontend**: `/app/test_reports/iteration_10.json`
- Ver Stock UX + modularização fase 1 validados com **PASS 100% frontend**: `/app/test_reports/iteration_11.json`
- Iteração seguinte (novas features) validada por code review do testing agent com app bloqueada por BD indisponível no ambiente de teste: `/app/test_reports/iteration_12.json`
- Verificação da Fase 2 e correção de bug `exec()` confirmadas por code review: `/app/test_reports/iteration_13.json` e `/app/test_reports/iteration_14.json`
- Registrar Inseminação (nova UX) validado por code review completo no testing agent: `/app/test_reports/iteration_15.json` (bloqueado dinamicamente por indisponibilidade de PostgreSQL no ambiente)
- Fase 3 + DATABASE_URL validados dinamicamente com **PASS 100% frontend**: `/app/test_reports/iteration_19.json`

## Backlog priorizado
### P0
- Concluído: persistência de posição do mapa

### P1
- Aplicar filtro de data (data única/período) nas consultas dos relatórios

### P2
- Teste aprofundado da regra de segurança de exclusão de contentor com stock > 0
- Refatorar `app.py` em módulos menores (DB/UI/relatórios) — **Fase 1, Fase 2 e Fase 3 concluídas**
- Próximo passo técnico: extração adicional dos blocos “Adicionar Stock”, “Registrar Inseminação” e “Gestão de Proprietários” para módulos próprios.
