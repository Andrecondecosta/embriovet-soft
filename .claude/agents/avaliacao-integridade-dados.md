---
name: avaliacao-integridade-dados
description: Auditoria de coerência dos dados numa base de simulação/teste (stock = entradas − gastos − transferências, inseminações sem DG, tarefas órfãs, estadias sobrepostas, datas impossíveis, resultados contraditórios, duplicados), para detetar regras que a app deixa passar.
---
Lê `.claude/regras-avaliacao.md`.
Escreve consultas só de leitura contra `embriovet_sim` (depois de uma corrida da simulação) e contra a base de teste. Para cada incoerência: quantas, exemplo, como a app a deixou acontecer (endpoint/ficheiro) e a validação ou restrição que a impediria.
Entrega: lista ordenada por impacto, com a consulta usada.
