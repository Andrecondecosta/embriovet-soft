---
name: avaliacao-desempenho
description: Mede o desempenho com volume realista (vários anos de clínica, milhares de animais/registos/lotes): tempos de resposta por endpoint, consultas lentas (EXPLAIN ANALYZE), índices em falta, N+1, tamanho do JavaScript e carga no telemóvel.
---
Lê `.claude/regras-avaliacao.md`.
Usa uma base local própria (`createdb -T embriovet_sim embriovet_perf`), multiplica dados (ex.: correr a simulação com outras sementes ou replicar linhas) e mede com o TestClient ou um uvicorn local. Usa `EXPLAIN ANALYZE` nas consultas mais pesadas (estadias, trabalho diário, reprodutivo, relatórios, dashboard, stock). Vê o tamanho dos bundles em `frontend/dist`. Apaga a base no fim.
Entrega: top 10 lentidões com tempo medido, causa e correção (índice, consulta, paginação), e o limite de dados a partir do qual a app degrada.
