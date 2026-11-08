---
name: avaliacao-primeiro-uso
description: Faz de uma clínica nova a instalar e usar a app pela primeira vez, sem ajuda (primeiro login, mudar credenciais, marca/idioma/fuso, alojamentos, proprietários, contentores, importar stock, primeira égua), e avalia onde se perde.
---
Lê `.claude/regras-avaliacao.md`.
Cria uma base local vazia (`createdb embriovet_novo` e `DATABASE_URL=… venv/bin/python setup_database.py` + `scripts/aplicar_migracoes.py` com essa base), arranca a app local nela e percorre a instalação no browser (ver `avaliacao-ux-browser`). Apaga a base no fim.
Entrega: o percurso real com passos, bloqueios, textos de ajuda em falta e a lista do que uma clínica precisa de saber antes de começar.
