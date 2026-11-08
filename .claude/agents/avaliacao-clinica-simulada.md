---
name: avaliacao-clinica-simulada
description: Corre a época simulada (150 éguas, 9 meses, 5 pessoas com hábitos humanos) contra a app e compara o que a app ficou a saber com o que aconteceu de verdade. Usar depois de mudanças no fluxo clínico/stock para apanhar regressões de comportamento.
---
Lê `.claude/regras-avaliacao.md` e `ferramentas/simulacao/LEIA-ME.md`.

1. `cd ferramentas/simulacao && ../../venv/bin/python runner.py --db embriovet_sim --dias 273` (aplica as migrações e limpa a base de simulação).
2. `../../venv/bin/python avaliar.py --db embriovet_sim --dias 273` → `saida/embriovet_sim/avaliacao.json`.
3. Se existir uma avaliação anterior guardada, compara antes/depois (inseminações sem registo, gestação verdade→app, pendentes no fim, saídas "gestante" vazias, tarefas, donos, lotes, erros da API, exceções das pessoas).
4. Para cada número que piorou, investiga a causa nos dados (SELECT na embriovet_sim) e no código, e diz se é da app ou da simulação.
Entrega: tabela antes/depois, regressões com causa, e o que melhorou.
