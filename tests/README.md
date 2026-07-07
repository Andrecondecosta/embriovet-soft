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
