---
name: avaliacao-seguranca-dados
description: Revisão de segurança e de perda/corrupção de dados (autenticação, permissões por nível, injeção, XSS, cabeçalhos, segredos, apagar/editar sem rasto, concorrência, transações, migrações, cópias de segurança), confirmando com experiências numa cópia local.
---
Lê `.claude/regras-avaliacao.md`.
Para experiências destrutivas cria uma cópia local (`createdb -T embriovet_test embriovet_seg`) e apaga-a no fim.
Cobrir: login/sessões/passwords; `pode_escrever` e `require_nivel` em todos os POST/PUT/PATCH/DELETE; SQL com f-strings; uploads/importação; exportações (dados pessoais, fórmulas); DELETE e cascatas; edições que reescrevem linhas; stock em concorrência; operações em várias transações; `start.sh`/`setup_database.py`/migrações; cópia de segurança e reposição; fuso horário. Rever também `git log -15`.
Entrega: CRÍTICO/ALTO/MÉDIO/BAIXO com cenário, ficheiro:linha, confirmado/suspeito e correção mínima; o que está bem.
