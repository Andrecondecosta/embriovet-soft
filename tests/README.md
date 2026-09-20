# Testes de integração — EquiCore

Suite de testes que valida o comportamento contra uma base **PostgreSQL
real**. Corre sempre contra uma base de teste separada — **nunca**
contra produção.

## Pré-requisitos

1. **PostgreSQL 15+** local com uma base de dados de teste vazia.
2. Todas as `migrations/*.sql` aplicadas à base de teste (para que o
   schema esteja em paridade com produção).

## Setup (uma vez)

### Opção A — Postgres do sistema (Debian/Ubuntu)

```bash
sudo apt-get install -y postgresql postgresql-contrib
sudo -u postgres pg_ctlcluster 15 main start   # se ainda não estiver a correr
sudo -u postgres psql -c "CREATE USER embriovet_test WITH PASSWORD 'embriovet_test' SUPERUSER;"
sudo -u postgres createdb -O embriovet_test embriovet_test
```

### Opção B — Docker

```bash
docker run -d --name embriovet_pg_test \
    -e POSTGRES_USER=embriovet_test \
    -e POSTGRES_PASSWORD=embriovet_test \
    -e POSTGRES_DB=embriovet_test \
    -p 5432:5432 \
    postgres:18
```

### Aplicar o schema à base de teste

```bash
# Se tiveres acesso a `pg_dump` da versão certa (>= server), replica prod:
pg_dump --schema-only --no-owner --no-privileges --no-comments \
    "$(grep '^DATABASE_URL=' /app/.env | cut -d= -f2-)" \
    | PGPASSWORD=embriovet_test psql -h localhost -U embriovet_test embriovet_test

# Alternativa: aplicar as migrations do repo (idempotentes):
python3 -c "
from dotenv import load_dotenv; load_dotenv('/app/.env')
import os, psycopg2
from migration_runner import run_migrations
conn = psycopg2.connect(os.environ['TEST_DATABASE_URL'])
run_migrations(conn, migrations_dir='/app/migrations')
conn.close()
"
```

### Configurar `TEST_DATABASE_URL`

Adiciona ao `/app/.env` (o valor abaixo assume opção A ou B):

```
TEST_DATABASE_URL=postgresql://embriovet_test:embriovet_test@localhost:5432/embriovet_test
```

Sem esta variável definida, **todos os testes de integração são
saltados** — o `conftest.py` chama `pytest.skip` a nível de módulo para
garantir que ninguém corre acidentalmente contra produção.

## Correr

```bash
cd /app
python3 -m pytest tests/ -v
```

## Notas

- Os testes usam nomes prefixados por `_TEST_` e limpam-se sozinhos no
  final via fixtures pytest.
- O `conftest.py` sobrescreve `DATABASE_URL` para o valor de
  `TEST_DATABASE_URL` **antes** de qualquer import da app, para
  garantir que o pool de conexões (`modules.db`) aponta para a base
  correcta.

## Testes de fluxo completo com `AppTest` (streamlit.testing.v1)

Para páginas/formulários que escrevem na base de dados, prefere um
teste de **fluxo completo** (abrir a vista → preencher como um
utilizador → submeter → confirmar o INSERT/UPDATE na BD) a um teste
que só chama a função de repositório isolada. Foi exactamente a
ausência deste tipo de teste que deixou o bug do "Adicionar lote"
(sub-vista que perdia o estado a meio do preenchimento) escondido
durante meses — ver `test_stock_semen_subview_persistente.py` para o
padrão de referência.

### Limitação conhecida: `@st.dialog` não persiste entre `.run()`

O `AppTest` **não simula fielmente diálogos que ficam abertos entre
várias interacções**. Num browser real, um `@st.dialog` herda de
`st.fragment`: depois de aberto, qualquer widget lá dentro dispara um
rerun `scope="fragment"` (só a função do diálogo volta a correr, a
página por trás não é tocada) — e é por isso que um "gate" de
utilização única em `session_state` (ex.: `st.session_state.pop(
"abrir_modal_x_id")`) é seguro para ABRIR um diálogo: só precisa de
ser verdadeiro uma vez.

O `AppTest`, ao contrário, **reexecuta o script todo do zero em cada
`.run()`** — não há memória de "este diálogo já estava aberto" entre
chamadas. Isto tem duas consequências práticas:

1. **Um diálogo com várias interacções internas "fecha-se" sozinho**
   no teste, assim que o gate que o abriu já não está em
   `session_state` (foi consumido na 1ª passagem). Sintoma: depois de
   clicar num botão dentro do diálogo e chamar `.run()`, os widgets do
   diálogo desaparecem de `at.button`/`at.selectbox`/etc. — não
   porque a app tenha um bug, mas porque o `AppTest` "esqueceu-se" de
   que o diálogo estava aberto.

   **Contorno**: antes de cada `.run()` que precise de manter o
   diálogo aberto, redefine manualmente o gate:
   ```python
   def reabrir_e_correr():
       at.session_state["abrir_modal_x_id"] = id_alvo
       at.run(timeout=30)
   ```
   `session_state` que já vive DENTRO do diálogo (ex.: qual lote está
   a ser movido) continua a persistir normalmente entre `.run()` —
   só o gate de abertura precisa deste reforço manual.

2. **`st.rerun(scope="fragment")` dentro do diálogo lança
   `StreamlitAPIException`** quando chamado a partir de um `.run()`
   reconstruído à mão como acima (o `AppTest` não estabelece o
   contexto de "estou numa fragment rerun" que esse `scope` exige).
   Isto acontece **depois** de qualquer escrita na BD já ter corrido
   — não invalida o resultado gravado, só a bookkeeping de UI a
   seguir. Se a asserção que importa é "gravou na BD", confirma isso
   directamente na BD e não te preocupes com esta excepção específica
   quando a mensagem for exactamente sobre `scope="fragment"`.

   Se precisares de testar o que acontece depois desse rerun (ex.: o
   diálogo fecha, o formulário limpa), não é possível com o `AppTest`
   tal como está — fica como limitação a documentar, não a contornar.

Um diálogo chamado **sem** um gate de utilização única (ex.: chamar
`render_modal_animal(...)` directamente no teu próprio script de
teste, em vez de passar pelo botão real que activa uma flag
`session_state`) reabre-se sozinho em cada `.run()` e não sofre deste
problema — é a forma mais simples de testar o conteúdo de um diálogo
quando não precisas de exercitar o mecanismo de abertura em si.

### Limitação conhecida: `selectbox`/`format_func` sobre valores não-string

Um `st.selectbox(options=[...ids inteiros...], format_func=...)`
usado com `.select_index(n)`/`.select(valor)` no `AppTest` pode
rebentar com `ValueError: '#<algo>' is not in list` — bug conhecido
do `AppTest` ao tentar recalcular o índice a partir do valor já
formatado. **Contorno**: escreve directamente no `session_state` do
widget em vez de usar os métodos `.select*()`:
```python
at.session_state["<key_do_selectbox>"] = valor_bruto  # ex.: o id
at.run(timeout=30)
```
