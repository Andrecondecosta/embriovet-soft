# PRD — Embriovet / EquiCore — Gestão de Sémen Veterinário

## Última Atualização
**Mar 2026** — Operações multi-lote (transferências + inseminações agrupadas por `operation_id`) totalmente implementadas e testadas. Bug P0 "Editar Transferência não carregava todos os lotes" corrigido. Persistência de sessão via DB implementada. Melhorias de UX mobile concluídas.

## Problema Original
Software modular de gestão veterinária de sémen (congelado/fresco) para equinos. Precisa de: mapa visual de contentores, gestão de stock, transferências, inseminações, relatórios, design premium SaaS, suporte multi-idioma, white-labeling, migrações de base de dados automáticas, e importação inteligente com criação automática de entidades.

## Arquitetura
- **Framework:** Streamlit (Python) + PostgreSQL (psycopg2)
- **Entrada:** `/app/app.py` — Router central, lógica de sessão, menus
- **Módulos core:**
  - `modules/ui_kit.py` — Sistema de design, CSS global, sidebar, header
  - `modules/i18n.py` — Sistema de internacionalização (t() function)
  - `modules/migration_runner.py` — Migrações automáticas SQL
  - `modules/pages/` — Uma página por ficheiro (incluindo import_page.py)
- **DB Migrations:** `/app/migrations/*.sql`

## Funcionalidades Implementadas

### Mapa dos Contentores (`map_page.py`) — Corrigido Feb 2026
- **Contentores não apareciam**: CSS `html,body { height: 100% }` em falta no iframe; `#mapa-wrapper` passou de `height: 100%` para `height: 100vh`
- **Propriedades JavaScript erradas**: `c.pos_x` → `c.x`, `c.pos_y` → `c.y`, `c.total_palhetas` → `c.palhetas`, `lote.palhetas` → `lote.quantidade`
- **Botões com chaves i18n em bruto**: adicionadas chaves `btn.cancel = "Cancelar"` e `btn.create_container = "Criar Contentor"` para PT-PT e EN

### Importação Inteligente (`import_page.py`) — NOVO Feb 2026
- **Wizard de 4 passos**: Ficheiro → Entidades → Validar → Relatório
- **Passo 1:** Upload CSV/XLSX com download de template, pré-visualização
- **Passo 2:** Detecção automática de proprietários/contentores desconhecidos; criação imediata no fluxo (sem sair da página) ou mapeamento para existentes
- **Passo 3:** `st.data_editor` editável com erros destacados; KPIs de validação (linhas/válidas/erros)
- **Ajuste histórico de data:** `data_criacao` definida como 1 Jan do ano do documento (não data de importação)
- **Relatório:** Download CSV do resultado; botão "Nova Importação"
- Testado com 100% de sucesso (iteration_22)

### Autenticação & Sessão
- Login com username/password (hash bcrypt)
- Sessão persistente via query param `?session=TOKEN`
- Forçar alteração de password no 1º login
- Fluxo de onboarding para nova base de dados

### Mapa dos Contentores (`map_page.py`)
- Mapa visual interactivo com grid HTML/CSS
- Drag-and-drop para editar posições (modo edição)
- Modal de inventário ao clicar num contentor
- KPI bar (nº contentores, total palhetas)
- Header premium com subtítulo
- Estado vazio melhorado com botão de onboarding
- Adição e edição de contentores

### Dashboard (`dashboard_page.py`)
- KPI cards: Total Straws, Active Lots, Inseminations Today, Critical Stock
- **Gráficos Altair**: Palhetas por Contentor + Palhetas por Proprietário
- Tabela de actividade recente (transferências + inseminações)
- Quick Actions (Nova Inseminação, Nova Transferência, Import, Ver Mapa)
- **Gestão de Logs (Admin)** — Março 2026:
  - Botão ✏️ junto a "ATIVIDADE RECENTE" abre modal de gestão
  - Modal lista todos os logs com botões ✏️ (editar) e 🗑️ (eliminar/reverter)
  - Eliminar: confirma e reverte dados (devolve palhetas ao stock)
  - Editar: navega para formulário com dados pré-preenchidos
  - Registos editados exibem prefixo "✏️" na coluna "Ação"
  - **Painel de Auditoria** — Março 2026:
    - Layout [4.5 | 5 | 0.5 | 0.5] no modal: col2 mostra histórico de edição
    - Campos alterados mostrados com valor anterior (riscado vermelho) → novo (verde)
    - Inseminações: captura Égua, Garanhão, Palhetas, Data, Protocolo, Proprietário
    - Transferências: captura Quantidade, Destino / Destinatário, Tipo
    - Indica utilizador e data da edição
    - Baseado na tabela `historico_edicoes` (migration 008)
  - **Campo Observações nas Inseminações** — Março 2026:
    - Textarea "Observações" adicionada ao formulário de inseminação
    - Observações aparecem no Detalhe da ATIVIDADE RECENTE e no audit
    - Pré-preenchidas em modo de edição
  - **Utilizador nos Logs** — Março 2026:
    - Colunas `utilizador` adicionadas a `inseminacoes`, `transferencias`, `transferencias_externas` (migration 010)
    - Novos registos guardam o nome do utilizador autenticado
    - Bug corrigido: `st.session_state.get('user',{}).get('username')` em 8 locais

## Navegação — Comportamento Mobile (Março 2026)
- Ao clicar em qualquer item do menu lateral: estado de página limpo (insem_*, edit_*) + scroll ao topo + sidebar fecha em ecrãs < 992px
- Implementado via `_just_navigated` flag + `st.components.v1.html(height=0)` com JS

- Botões (não radio) para ambos os menus
- Menu principal: Dashboard, Add Stock, Register Insemination, Int/Ext Transf., View Stock, Reports
- Menu secundário (expander "Mais opções"): Container Map, Import Semen, Owner Management, User Management, Settings
- `_nav_last_active` tracking + `aba_selecionada` + `st.rerun()` para navegação 100% funcional
- Página default: Container Map

### Gestão de Stock (`stock_page.py`)
- Ver stock com detalhes por lote (local, motilidade, concentração, cor)
- Header informativo por lote

### Transferências (`transfer_page.py`)
- Página dedicada: transferências internas e externas
- Criar novo proprietário durante transferência
- **Modo de Edição Multi-Lote** — Março 2026 (COMPLETO):
  - Ao editar via modal de logs, carrega TODOS os lotes da operação pelo `operation_id`
  - Transferências internas: revert+recreate com suporte a `operation_id`
  - Transferências externas: revert+recreate com suporte a `operation_id` (bug P0 corrigido em Mar 2026)
  - Criação de novas transferências agrupadas por `operation_id` único
  - Testado e verificado — iteration_28: 100% sucesso

### Inseminações (`insemination_page.py`)
- Fluxo sequencial: Cavalo → Proprietário → Lotes → Quantidade
- Detalhes de lote com cor e concentração
- **Modo de Edição** — Março 2026: ao editar via modal de logs, pré-preenche égua, garanhão, proprietário, data, **lote específico (estoque_id) e nº de palhetas**; botão "Atualizar" faz UPDATE no BD com ajuste correto de stock (devolve antigas, desconta novas)
- **Testado e verificado** — iteration_26: 16/16 testes passaram (pré-preenchimento do lote, ajuste de stock, auditoria, utiliz.='admin')

### Migrações DB (`migrations/`)
- `007_add_atualizado_columns.sql`: Adiciona coluna `atualizado BOOLEAN DEFAULT FALSE` a `inseminacoes`, `transferencias` e `transferencias_externas`

### Relatórios (`reports_page.py`)
- Filtros por proprietário, garanhão, datas

### Definições (`settings_page.py`)
- White-labeling: nome, logo, cor primária
- Escolha de idioma (pt-PT, en, fr, de)

### Design System
- CSS global injectado em bloco único
- Spacing reduzido (padding-top: 0.4rem)
- Containers vazios ocultos (anti-spacing fix)
- Tema consistente com variáveis CSS

### i18n
- Suporte completo: pt-PT, en, fr, de
- Todos os textos UI via `t()` function

### Migrações DB
- Sistema automático via `migration_runner.py`
- Ficheiros SQL em `/app/migrations/`

## Estado Actual
- **App:** FUNCIONAL (testes de edição de logs passados — iteration_23.json)
- **Navegação:** Totalmente funcional (botões primários + secundários)
- **Gráficos Dashboard:** Funcionais (Altair v5)
- **Mapa:** Funcional com header premium
- **Gestão de Logs:** Funcional — editar/eliminar transferências e inseminações

## Backlog / Próximas Tarefas

### P0 — CONCLUÍDO (iteration_30 — 90% + fixes aplicadas)
- [x] Edit Transferência Multi-Lote — carregamento, revert+recreate correto (interno e externo)
- [x] Edit Inseminação com Lote de Sémen — pré-preenchimento, ajuste stock, auditoria
- [x] Nome dos lotes "—" em edição → fallback para data ou "Lote #ID"
- [x] Gerir Logs — botões mobile layout fixo
- [x] Histórico de edição ligado ao ID novo (RETURNING id)
- [x] Revert interno: location-matching JOIN em vez de LIMIT 1 sem ordem
- [x] atualizado=TRUE marcado após edit de transferências internas e externas
- [x] Auditoria (historico_edicoes) criada para transferências externas editadas
- [x] operation_id index corrigido: interno=row[11], externo=row[12]

### P1 — Próximas
- [ ] Completar página "Definições": preview do logo em tempo real + painel i18n
- [ ] Verificar salvamento da edição de transferência + reversão (não testado por segurança de DB)

### P2 — Futuro
- [ ] Bug visual dos botões `+/-` do stepper
- [ ] Novos relatórios (por contentor, localização, ocupação)
- [ ] Testar regra de segurança: contentor com stock > 0 não pode ser apagado
- [ ] Extrair "Gestão de Proprietários" de app.py para módulo próprio
- [ ] Extrair "Gestão de Utilizadores" de app.py para módulo próprio
- [ ] Upgrade Altair v5→v6 para compatibilidade Vega-Lite

## Credenciais de Teste
- Admin: `admin` / `admin123`
- DB: Ver `/app/.env` → DATABASE_URL
t Gestor (Mapa dos Contentores)

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
- Remoção do Deploy via JS sem ocultar toolbar (sidebar volta a abrir/fechar)
- Topbar ajustada: removida wrapper HTML que criava blocos vazios (alinha conteúdo para cima)
- Render_header simplificado (sem wrapper de ações) + CSS para ocultar blocos verticais vazios
- Ajuste de espaçamento: margem menor entre elementos (sem ocultar containers)

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
