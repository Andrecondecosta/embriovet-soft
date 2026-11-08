---
name: avaliacao-migracoes-deploy
description: Verifica, antes de publicar, que as migrações novas e o arranque no Render são seguros (só acrescentam, idempotentes, NOT VALID onde há dados antigos, sem UPDATE/DELETE inesperados, sem quebrar a versão anterior) e que o deploy não altera dados existentes.
---
Lê `.claude/regras-avaliacao.md`.
1. `git diff origin/master --stat` e lê cada migração nova em `migrations/`, `start.sh`, `setup_database.py`, `scripts/aplicar_migracoes.py`.
2. Aplica as migrações numa cópia local nova (`createdb -T embriovet_test embriovet_deploy`), duas vezes seguidas (idempotência), e corre os testes contra ela se possível; apaga a cópia no fim.
3. Procura: UPDATE/DELETE/TRUNCATE, restrições sem NOT VALID sobre dados possivelmente antigos, colunas NOT NULL sem DEFAULT, mudanças de comportamento visíveis (permissões, ecrãs), dependências novas no build.
Entrega: veredicto "pode publicar / não publicar", riscos para dados existentes, e o que verificar no log do Render.
