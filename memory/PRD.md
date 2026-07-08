# PRD — Embriovet / EquiCore — Gestão de Sémen Veterinário

## Última Atualização
**Fev 2026** — **Pedido 6 (Dashboard como visão do dia)** concluído. Dashboard 100% leitura: retirada toda a lógica de anulação de transferências (UPDATEs/DELETEs de `reverter_acao`) para o novo `modules/repositories/transfer_repo.py` (FK-based, sem lookup por texto), usada no histórico da `transfer_page.py`. Adicionados 4 KPIs clínicos (estadias ativas, tarefas de hoje com urgentes, gestações confirmadas, inseminações do mês por DISTINCT operation_id), secção "Hoje na clínica" (tarefas do trabalho diário + botão para agenda) e "Stock a precisar de atenção" (existência ≤ 5, via FK garanhao_nome). Atividade recente agora agrupada por operation_id (1 linha por operação). **Total: 55/55 pytest** (43 baseline + 12 novos em `test_dashboard_pedido6.py`, report `/app/test_reports/iteration_37.json`).

## Changelog Recente (Fev 2026 — Pedido 6)
- ✅ **Novo `modules/repositories/dashboard_repo.py`** (100% leitura): `carregar_kpis_stock`, `carregar_kpis_clinicos` (com `insem_mes_operacoes` DISTINCT operation_id), `carregar_tarefas_hoje`, `carregar_stock_atencao(limite=5)` (via FK), `carregar_stock_por_contentor`, `carregar_stock_por_proprietario`, `carregar_atividade_recente_agrupada(limit=10)` (agrupa por operation_id em memória — 1 linha por operação com num_lotes e quantidade somada).
- ✅ **Novo `modules/repositories/transfer_repo.py`** (escrita): `reverter_operacao(tipo, action_id, operation_id)` — uma transacção, rollback em falha, FK-based lookup do lote destino (`animal_id + dono_id + contentor_id + canister + andar` — sem texto), invalida cache no sucesso. Substitui o antigo `reverter_acao` do dashboard.
- ✅ **`dashboard_page.py` reescrito** — decomposto em funções puras (`_render_kpis_stock`, `_render_kpis_clinicos`, `_render_hoje_na_clinica`, `_render_stock_atencao`, `_render_graficos`, `_render_atividade_recente`, `_render_acoes_rapidas`). Zero `UPDATE`/`DELETE`/`INSERT` — validado por grep no teste. Ficha KPI clínica destacada visualmente (verde) para contraste com stock.
- ✅ **`transfer_page.py`** — nova secção "Histórico de operações" no fim (chamada mesmo quando não há stock disponível). Botões editar (transferências → carrega form em modo edição; inseminações → redireciona) e anular (`reverter_operacao` + confirmação inline). Sem `st.dialog` aninhado.
- ✅ **12 novos testes em `test_dashboard_pedido6.py`** cobrindo os 5 critérios:
  - (a) grep de `UPDATE/DELETE/INSERT` em `dashboard_page.py` e `dashboard_repo.py`
  - (b) reversão de transferência interna e inseminação; validação de tipo
  - (c) `estadias_ativas` bate com `COUNT(*) FROM estadias WHERE data_saida IS NULL`; `tarefas_hoje` bate com trabalho_diario
  - (d) inseminação multi-lote → 1 linha em `carregar_atividade_recente_agrupada` com `num_lotes=2` e quantidade somada
  - (e) `insem_mes_operacoes` incrementa +1 mesmo com 2 linhas de mesmo `operation_id`
  - Extras: `stock_atencao` reflecte rename em `animais.nome` sem tocar `estoque_dono.garanhao`; `tarefas_hoje` filtra corretamente

## Changelog Anterior (Fev 2026 — Correção ao Pedido 5)
- ✅ Novo helper `modules.db.invalidate_data_cache()` — chama `st.cache_data.clear()` protegido por try/except (seguro fora de contexto Streamlit).
- ✅ **`app.py`** — 20+ funções de escrita agora chamam `invalidate_data_cache()` após `conn.commit()`: `atualizar_status_proprietarios`, `alternar_status_proprietario`, `editar_proprietario`, `atualizar_proprietario_stock`, `inserir_stock`, `registrar_inseminacao`, `registrar_inseminacao_multiplas` (3 branches: create/edit-op/edit-single), `registrar_inseminacao_linha`, `adicionar_proprietario`, `deletar_proprietario`, `editar_stock`, `deletar_stock`, `adicionar_contentor`, `editar_contentor`, `atualizar_posicao_contentor`, `atualizar_andar_lote`, `mover_lotes_por_andar`, `deletar_contentor`, `transferir_palhetas_parcial`, `transferir_stock_interno_com_localizacao`, `transferir_palhetas_externo`, `atualizar_transferencia_interna`, `atualizar_transferencia_externa`.
- ✅ **`modules/repositories/insemination_repo.py`** — `registar_inseminacao_completa` e `registar_resultado` invalidam cache após commit.
- ✅ **`modules/repositories/animal_repo.py`** — `get_or_create_garanhao` invalida cache apenas quando faz INSERT (SELECT-only não é invalidação).
- ✅ **`modules/pages/dashboard_page.py`** — `reverter_acao` (transferências e inseminações) invalida cache após commit.
- ✅ **`modules/pages/transfer_page.py`** — blocos inline de edição/reversão (interna e externa) invalidam cache após commit.
- ✅ **`modules/pages/import_page.py`** — importação em bulk invalida cache após commit.
- ✅ Substituídas as 2 ocorrências antigas de `try: st.cache_data.clear() except Exception: pass` em `editar_stock`/`deletar_stock` pelo helper unificado.
- ✅ Novo ficheiro **`tests/test_cache_invalidation.py`** com 5 testes (monkeypatch de `invalidate_data_cache` em todos os módulos consumidores + validação em BD real):
  - `test_get_or_create_garanhao_invalida_cache_quando_cria`
  - `test_get_or_create_garanhao_nao_invalida_quando_ja_existe` (SELECT-only não invalida)
  - `test_registar_inseminacao_completa_invalida_cache` (+ sanity do desconto: 20→17)
  - `test_registar_resultado_invalida_cache` (D+14 positivo)
  - `test_invalidate_data_cache_e_no_op_fora_streamlit`
- ✅ **Critério de aceitação do user cumprido**: registar uma inseminação e abrir imediatamente o "Ver Stock" → os números já refletem o desconto (o cache é limpo antes do próximo request).
- ✅ Smoke test: `/_stcore/health` = "ok" (200), `/` = 200.

## Changelog Anterior (Fev 2026 — Pedido 5)
- ✅ **Leituras por FK**:
  - `carregar_stock` — LEFT JOIN animais → nova coluna `garanhao_nome = COALESCE(a.nome, e.garanhao)`.
  - `carregar_transferencias` — LEFT JOIN estoque_dono + animais → `garanhao = COALESCE(...)`.
  - `carregar_transferencias_externas` — mesmo padrão com verificação defensiva de `estoque_id` no schema (fallback ao legado quando o schema é anterior).
  - `obter_stock_contentor` — LEFT JOIN animais.
  - `stock_page.py`, `stock_reporting.py::filter_stock_view`, `transfer_page.py` (selects de lotes + queries de edição), `reports_page.py` (todos os filtros/dataframes), `insemination_page.py` (filtros + queries de edição), `map_page.py` (JSON de lotes), `ui_kit.py` (search) — todos migrados para `garanhao_nome` / `COALESCE`.
- ✅ **Cache de leitura (`@st.cache_data(ttl=60)`)**: aplicado em `carregar_stock`, `carregar_proprietarios`, `carregar_contentores`, `carregar_transferencias`, `carregar_transferencias_externas`.
- ✅ **Invalidação após escritas**: `editar_stock` e `deletar_stock` chamam `st.cache_data.clear()`.
- ✅ **Grep final limpo**: apenas 2 ocorrências restam, ambas expectáveis — `map_page.py:1155` (template JS que lê `lote.garanhao` — mas o build usa `garanhao_nome` como preferência) e `app.py:627` (fallback defensivo em `carregar_transferencias_externas` para schema legado sem `estoque_id`).
- ✅ **Testes**: 7 novos em `tests/test_stock_fk_garanhao.py` (criados pelo testing agent) validam: (a) `garanhao_nome` correcto via COALESCE + fallback quando animal_id é NULL; (b) rename `animais.nome` reflecte em `carregar_stock` sem tocar em `estoque_dono.garanhao`; (c) `carregar_transferencias` resolve via FK; (d) `obter_stock_contentor` idem; (e) `filter_stock_view` prefere `garanhao_nome`.
- **Total: 38 testes pytest, todos passam** (31 anteriores + 7 novos). Migrations em dia com produção Render.

### Observações do testing agent (recomendações para backlog)
- `app.py` já > 3485 linhas — considerar extrair `carregar_*` e `obter_*` para `modules/stock_repo.py` (facilita testes sem contornar top-level Streamlit).
- Testes actuais replicam o SQL das funções decoradas com `@st.cache_data` (não podem importá-las directamente). Extrair queries para constantes de módulo tornaria isto mais robusto.
- Migração pandas → SQLAlchemy engine continua adiada (decisão do utilizador). Warnings persistem, cosméticos.

## Changelog Anterior (Fev 2026 — Pedidos 4b + 4c + item 3)
- ✅ **Circuito de trabalho (4b)**:
  - `insemination_page._render_painel_confirmacao_insem(conf)` — resumo pós-registo (égua × garanhão, total palhetas, num_lotes, data, tarefas automáticas criadas) + 3 botões: primário "📋 Trabalho Diário", secundários "👁 Ver na ficha da égua" e "➕ Registar outra". Substitui o `st.dialog` antigo — mantém o formulário no fluxo principal.
  - `trabalho_diario_page._render_cartao_tarefa` — botão adicional "➕ Registar inseminação" em cartões de `verificar_ovulacao`. Reutiliza `insem_egua_prefill` (mecanismo do "Repetir inseminação") — égua e estadia pré-seleccionadas, sem texto livre.
  - `_carregar_tarefas_semana` — passa a devolver também `estadia_id` (necessário para o botão).
- ✅ **Tarefa de parto (4c)**:
  - `DIAS_PARTO_PREVISTO = 330` (era 340). `DIAS_PRE_PARTO = 14`.
  - **Migration 028** — adiciona `pre_parto` ao CHECK `trabalho_diario_tipo_check`.
  - `registar_resultado` — nova ramificação para (positivo, `segunda_confirmacao`): cria pre_parto (D+316, urgência 'amanha', label "Parto previsto em ~2 semanas — preparar acompanhamento") e parto_previsto (D+330, urgência 'hoje'). Idempotente. Usa a `data_parto_previsto` do acompanhamento como âncora se estiver preenchida, caso contrário calcula a partir da `data_inseminacao`.
  - Negativo tardio também apaga `pre_parto` e `parto_previsto` futuras não concluídas.
- ✅ **Constraint estadias (item 3)**:
  - **Migration 029** — `CREATE UNIQUE INDEX estadias_uma_aberta_por_animal ON estadias (animal_id) WHERE data_saida IS NULL`. Zero duplicados em produção no momento da aplicação.
  - `estadias_page._criar_estadia_apenas` — valida antes do INSERT: `SELECT ... WHERE animal_id=%s AND data_saida IS NULL` → se existir faz `raise ValueError("Este animal já tem uma estadia em aberto (id=X). Feche a existente antes de criar uma nova.")`. Antecipa a constraint da BD com mensagem amigável.
  - `modal_animal._criar_animal_e_estadia` não precisa da mesma validação porque cria animal + estadia em conjunto (por construção não há estadia prévia).
- ✅ **6 novos testes** (total 31):
  - `test_positivo_d45_cria_pre_parto_e_parto_previsto` (datas + urgências correctas)
  - `test_pre_parto_idempotente_em_d45`
  - `test_negativo_apaga_tambem_pre_parto`
  - `test_criar_estadia_apenas_valida_estadia_aberta` (ValueError amigável)
  - `test_constraint_bd_rejeita_segunda_estadia_aberta` (UniqueViolation)
  - `test_migration_029_rejeita_segunda_estadia_aberta` (regressão da bug fix Matilde adaptado à nova constraint)
- **Total: 31 testes, todos passam em 0.80s**. Migrations 028/029 aplicadas na BD de teste local e produção Render.
- **Recusado (por decisão do utilizador):** migração pandas → SQLAlchemy engine. Pandas UserWarnings persistem em 3 chamadas de `pd.read_sql_query` (cosmético, não bloqueante) — fica em backlog para uma iteração de qualidade.

## Changelog Anterior (Fev 2026 — Pedido 4 base)
- ✅ **`insemination_repo.registar_resultado`** (transaccional):
  - `WHERE operation_id = %s::uuid` — actualiza multi-lote como um único evento.
  - Modo `task_id`: fecha uma tarefa específica; fallback (sem task_id): fecha todas as pendentes matching `(estadia_id, tipo_tarefa)`.
  - Positivo D+14: INSERT idempotente D+28 + D+45 em `trabalho_diario`. Positivo D+28/D+45: mantém 'gestacao_confirmada'.
  - Negativo: DELETE tarefas futuras não concluídas (`confirmacao_gestacao`, `segunda_confirmacao`, `parto_previsto`, `data_tarefa >= data`) + NULL nas datas futuras do acompanhamento.
- ✅ **`insemination_repo.find_operation_por_tarefa(task_id)`** — devolve dict agregado (operation_id, egua, garanhao, num_lotes, total_palhetas, resultado_actual).
- ✅ **`trabalho_diario_page`**:
  - `_render_painel_resultado()` — painel inline com Positivo/Negativo + textarea observações. Aparece antes do render normal quando `resultado_task_id` está em session_state.
  - `_render_painel_pos_negativo()` — mostra opções "🔁 Repetir inseminação" / "🗑 Encerrar ciclo" após negativo em D+14.
  - `_render_cartao_tarefa` — clique em tarefa de tipo diagnóstico abre painel em vez de drill-down ao animal.
- ✅ **`insemination_page`** — pré-selecciona a égua via `st.session_state['insem_egua_prefill']` (do botão "Repetir").
- ✅ **`animal_page._render_botoes_resultado_inline`** — botões +/− na ficha da égua (historial reprodutivo) para operações pendentes com operation_id real (ignora legado `solo_<id>`). Chama a mesma função repo.
- ✅ **8 novos testes em `test_resultado_ciclo.py`**:
  1. `test_positivo_d14_cria_d28_e_d45_e_marca_gestacao`
  2. `test_positivo_d14_idempotente_nao_duplica_tarefas`
  3. `test_negativo_d14_marca_falhou_e_nao_cria_futuras`
  4. `test_negativo_d28_perde_gestacao_e_cancela_d45`
  5. `test_menu_e_ficha_registam_resultado_identico` (snapshot compare)
  6. `test_multi_lote_partilha_resultado_e_data`
  7. `test_find_operation_por_tarefa`
  8. `test_resultado_invalido_erra` (3 assertions)
- **Total: 25 testes, todos passam em 0.71s** contra a BD de teste local. Validado independentemente pelo testing_agent.

## Changelog Anterior (Fev 2026 — Bug fix "Matilde")
- ✅ **`registar_inseminacao_completa`** — nova etapa 0 de canonicalização: `SELECT id FROM estadias WHERE animal_id = %s AND data_saida IS NULL ORDER BY id ASC LIMIT 1`. Se não há estadia aberta → `raise InseminacaoError`. Se há, usa sempre a mais antiga (ignora estadia_id passado). Nunca cria estadias.
- ✅ **`listar_eguas_com_estadia_ativa`** — `SELECT DISTINCT ON (a.id) ... ORDER BY a.id, e.data_entrada ASC, e.id ASC` + re-sort por nome em Python. Uma égua com múltiplas estadias abertas devolve apenas UMA linha (a mais antiga).
- ✅ **`_carregar_inseminacoes_animal` / `_carregar_inseminacoes_garanhao`** — LEFT JOIN a `acompanhamento_inseminacao` agora via `ai.estadia_id = ins.estadia_id` (FK do Pedido 3), eliminando a multiplicação de linhas quando há 2 estadias abertas.
- ✅ **2 novos testes** em `test_insemination_repo.py`:
  - `test_registo_reusa_estadia_ativa_e_nao_duplica_palhetas` — reproduz o bug: cria mare + estadia_original, insere 2ª estadia aberta na mão, chama a função passando o estadia_id errado. Assere que resultado usa a original, tarefas+inseminacoes ficam na original, ficha mostra 10 palhetas/2 lotes (não 20/4), selectbox devolve 1 linha, nenhuma estadia nova criada.
  - `test_registo_falha_se_egua_nao_tem_estadia_ativa` — sem estadia aberta → `InseminacaoError` sem criar estadia às escondidas.
- ✅ **Total: 17 testes pytest, todos passam em 0.60s** contra a BD de teste local. Testing agent independente confirmou.
- Nota: BD de teste local teve de ser re-provisionada durante o ciclo (o container perdeu o Postgres 15 e o cliente 18). Ficou documentado em `/app/tests/README.md`.

## Changelog Anterior (Fev 2026 — Pedidos 3a + 3b)
- ✅ **Pedido 3a — UX pós-inseminação**:
  - `insemination_page.py` — campo de observações com label destacado + placeholder ("O que aconteceu? Reflexo, edema uterino, hora exacta, protocolo hormonal usado, etc.") + altura 110px.
  - Novo checkbox `insem_criar_d1` ligado por defeito com help text.
  - `insemination_repo.registar_inseminacao_completa(..., criar_tarefa_d1: bool = True)` — quando `True`, insere entrada `tipo='verificar_ovulacao'` idempotente em `trabalho_diario` na data D+1. A tarefa D+14 (`diagnostico_gestacao`) é sempre criada.
  - Migration 027 — adiciona `verificar_ovulacao` ao CHECK constraint `trabalho_diario_tipo_check`.
  - Return da função inclui `verificar_ovulacao_id` e `data_ver_ovulacao`.
- ✅ **Pedido 3b — Agrupamento por `operation_id`**:
  - `animal_page._carregar_inseminacoes_animal` — query reescrita com CTE + `GROUP BY COALESCE(operation_id::text, 'solo_' || id::text)`. Colunas: `data_inseminacao` (MIN), `garanhao` (MAX), `proprietario`, `palhetas_gastas` (SUM), `num_lotes` (COUNT), `resultado`, `observacoes`, `op_key`.
  - `animal_page._carregar_inseminacoes_garanhao` — mesma técnica, sobre FK `animal_id_garanhao`. Bug secundário corrigido: `_render_tab_fertilidade_garanhao` estava a passar `nome` em vez de `animal_id` para a função (regressão do Pedido 2 que só se manifestava em runtime).
  - Renderização: quando `num_lotes > 1` a coluna palhetas mostra "6 (2 lotes)" em vez de duplicar linhas.
  - O dashboard já agregava por `operation_id` — nenhuma alteração necessária lá.
- ✅ **Testes** — 4 novos em `test_insemination_repo.py` (`test_tarefa_d1_criada_por_defeito`, `test_tarefa_d1_pode_ser_desativada`, `test_tarefa_d1_idempotente`, `test_listagens_agrupam_por_operation_id`). Total **15 testes, 0.62s** contra a BD local.
- ✅ Migrations aplicadas em produção Render e na BD de teste.

## Changelog Anterior (Fev 2026 — Pedido 3)
- ✅ **Migration 026 — normalização acentos + espaços**:
  - `CREATE EXTENSION IF NOT EXISTS unaccent`
  - `f_unaccent(text)` IMMUTABLE (wrapper obrigatório porque `unaccent` não é IMMUTABLE)
  - `animais_nome_tipo_uniq` reconstruído com `LOWER(f_unaccent(TRIM(REGEXP_REPLACE(nome, '\\s+', ' ', 'g'))))`
  - Aplicada em produção Render e na BD local de teste.
- ✅ **`modules/repositories/insemination_repo.py` (novo)**:
  - `registar_inseminacao_completa(*, animal_id_egua, estadia_id, dono_id, garanhao_nome, data_inseminacao, registros[], observacoes, utilizador, operation_id)` — cria inseminacoes (multi-lote), acompanhamento (D+14/D+28/D+45/parto), trabalho_diario (D+14), e desconta stock, tudo numa só transacção com rollback em qualquer erro.
  - `upsert_acompanhamento_datas(...)` — primitiva partilhada de UPSERT em `acompanhamento_inseminacao`. Usada por `registar_inseminacao_completa` E pelo `_upsert_acompanhamento` da ficha da égua → uma só implementação.
  - `listar_eguas_com_estadia_ativa()` — JOIN `animais × estadias` com filtro `data_saida IS NULL`, devolve `animal_id, nome, estadia_id, alojamento_nome/tipo, dono_id, dono_nome`.
- ✅ **`modules/repositories/animal_repo.get_or_create_garanhao`** — normalização acento/espaços via `f_unaccent` + regex, alinhada com o índice único.
- ✅ **`modules/pages/insemination_page.py`**:
  - `st.text_input("Égua")` substituído por `st.selectbox` com formato "Nome — Box/Paddock — Proprietário".
  - Sem éguas com estadia activa: warning + link para "Estadias e Visitas" (não permite texto livre).
  - Criação → `registar_inseminacao_completa`. Edição continua a usar `registrar_inseminacao_multiplas` (backward compat, fora do scope deste pedido).
- ✅ **`modules/pages/animal_page.py::_upsert_acompanhamento`** — reduzida a delegação para `insemination_repo.upsert_acompanhamento_datas` (elimina segunda implementação).
- ✅ **BD de teste isolada** (`TEST_DATABASE_URL`):
  - `tests/conftest.py` sobrescreve `DATABASE_URL` antes dos imports; se `TEST_DATABASE_URL` não estiver configurada, chama `pytest.skip` a nível de módulo (safety contra correr contra produção).
  - PostgreSQL 15 local + schema replicado via `pg_dump 18` da produção + migrations 001-026 aplicadas.
  - Ver `/app/tests/README.md` para instruções de setup.
- ✅ **`tests/test_insemination_repo.py` (novo, 6 testes)**:
  1. `test_get_or_create_garanhao_normaliza_acentos_e_espacos` — variantes acento/case/espaços apontam ao mesmo id.
  2. `test_listar_eguas_so_devolve_com_estadia_ativa` — critério (d): estadia fechada → não aparece.
  3. `test_registar_inseminacao_completa_fks_datas_stock` — critérios (a)+(b)+(e): FKs, texto = nome canónico, datas D+14/D+28/D+45, entrada em `trabalho_diario`, desconto multi-lote correcto.
  4. `test_menu_e_ficha_produzem_mesmo_resultado` — critério (c): snapshot comparativo dos dois caminhos com os mesmos inputs.
  5. `test_stock_insuficiente_falha_e_faz_rollback` — falha atómica: nada escrito, stock intacto.
  6. `test_upsert_acompanhamento_datas_partilhado` — a primitiva partilhada é UPSERT (idempotente, 1 linha por estadia).
- Total: **11 testes a passar em 0.54s** contra a BD local.

## Changelog Anterior (Fev 2026 — Pedido 2)
- ✅ **Migration 025 — dedupe + índice único anti-duplicados**:
  - Fusão de duplicados por `(LOWER(TRIM(nome)), tipo)` — mantém o `id` mais antigo, reaponta TODAS as FKs (`estoque_dono.animal_id`, `inseminacoes.animal_id_egua/garanhao`, `estadias.animal_id/animal_doador_id`, `diario_clinico.animal_id`, `trabalho_diario.animal_id`, `acompanhamento_inseminacao.animal_id`) e apaga os `id` mais recentes.
  - Cria `UNIQUE INDEX animais_nome_tipo_uniq ON animais (LOWER(TRIM(nome)), tipo)` sobre todos os registos (não apenas `ativo=TRUE`).
  - No Render havia 1 duplicado ("paris" égua ids [2,5]) — fundido; nada mais restante.
- ✅ **Ficha do garanhão passa a usar FK** em `/app/modules/pages/animal_page.py`:
  - `_carregar_stock_garanhao(animal_id)` → `WHERE ed.animal_id = %s` (era `LOWER(ed.garanhao)`)
  - `_carregar_inseminacoes_garanhao(animal_id)` → `WHERE i.animal_id_garanhao = %s` + JOIN à estadia por `e.animal_id = i.animal_id_egua`
  - `_ultima_producao_garanhao(animal_id)` → `WHERE animal_id = %s`
  - Callers (`_render_tab_producao_semen/fertilidade/alertas`) passam agora `int(animal.get("id"))`.
- ✅ **Botão "➕ Novo Proprietário" removido do form "Adicionar Stock"** — proprietário criado via modal_animal fica disponível no selectbox "Proprietário do sémen" após `st.rerun()` (usa `novo_proprietario_id` como bridge, e `proprietarios` é recarregado no topo do script).
- ✅ **Testes `/app/tests/test_modal_animal.py`** (5 testes, todos passam):
  - `test_criar_garanhao_gera_fk_correcto_em_estadias` — cria animal + estadia via `_criar_animal_e_estadia`, valida `animais.tipo='garanhao'`, `estadias.animal_id == animal_id`, e JOIN `animais ↔ estadias`.
  - `test_fk_estadias_animal_id_impede_orfao` — confirma que a FK `estadias_animal_id_fkey` rejeita `animal_id` inexistente.
  - `test_indice_unico_impede_duplicados_nome_tipo` — insert de duplicados (case/espaços diferentes) bloqueado por `UniqueViolation`.
  - `test_indice_unico_permite_mesmo_nome_tipos_diferentes` — mesmo nome com tipos diferentes (égua vs garanhão) continua permitido.
  - `test_carregar_stock_garanhao_usa_fk_animal_id` — confirma que a query filtra por `animal_id` (não por nome), incluindo o caso em que dois animais partilham nome mas com tipos/FKs distintos.
- Infra: `/app/tests/conftest.py` (carrega `.env` + adiciona `/app` ao `sys.path`).

## Changelog Anterior (Maio 2026)
- ✅ **P0: Heatmap click corrigido** — A causa-raiz era uma regra CSS interna do Streamlit (`.stElementContainer:has([data-testid="stMarkdownContainer"] > style) { position: absolute }`) que aplicava `position: absolute` a qualquer markdown que começasse com `<style>`. O heatmap HTML começava com bloco `<style>` o que fazia o container saltar para o topo do DOM, sobrepondo-se a outros elementos. **Solução:** mover o CSS do heatmap para o bloco global de estilos da página (uma só vez) e fazer `build_heatmap_html()` retornar apenas o `<div>` da tabela.
- ✅ **P3 refactoring inicial:** Criados `/app/modules/db.py` (pool + `get_connection`) e `/app/modules/services/auth_service.py` (auth/sessões/permissões). `app.py` agora importa em vez de definir.

## Problema Original
Software modular de gestão veterinária de sémen (congelado/fresco) para equinos. Precisa de: mapa visual de contentores, gestão de stock, transferências, inseminações, relatórios, design premium SaaS, suporte multi-idioma, white-labeling, migrações de base de dados automáticas, e importação inteligente com criação automática de entidades.

## Arquitetura
- **Framework:** Streamlit (Python) + PostgreSQL (psycopg2)
- **Entrada:** `/app/app.py` — Router central, lógica de sessão, menus
- **Módulos core:**
  - `modules/db.py` — Pool de conexões PostgreSQL, `get_connection()`, helpers de tipo (NOVO Mai 2026)
  - `modules/services/auth_service.py` — Autenticação, gestão de utilizadores, sessões persistentes, permissões (NOVO Mai 2026)
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

### P1 — CONCLUÍDO (heatmap adicionado)
- [x] **Heatmap Canisters × Andares** dentro de cada card de contentor
- [x] Cor proporcional à quantidade (primária com opacidade 18%→96%)
- [x] Legenda visual (Vazio/Baixo/Médio/Alto)
- [x] Tooltip com C{n}/A{n}: X palhetas no hover
- [x] Andares ordenados (mais alto no topo, como contentor físico)
- [x] Redesign visual dos contentores: cards modernos, badge de palhetas, agrupamento por canister
- [x] Edição de andar/canister individual: botão ✏️ Mover → form inline
- [x] **Mover todos os lotes por andar** (batch): expander por canister com De Andar / Para Andar
- [x] DB: `mover_lotes_por_andar(contentor_id, andar_origem, andar_destino, canister)` 
- [x] Altura do mapa responsiva: calculada por nº de contentores + viewport
- [x] Vega-Lite warnings eliminados: pré-ordenação Python + sort=None + scale(zero=True)

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
