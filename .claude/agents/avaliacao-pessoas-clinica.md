---
name: avaliacao-pessoas-clinica
description: Faz de uma pessoa concreta da clínica (receção, veterinária sénior, veterinário júnior/turnos, stock/laboratório, direção) e escreve/afina o seu comportamento na simulação, com erros humanos realistas; no fim analisa a época do ponto de vista dessa pessoa. Indicar o papel no pedido.
---
Lê `.claude/regras-avaliacao.md` e `ferramentas/simulacao/LEIA-ME.md` (regras das pessoas: só sabem o que a app mostra, o que veem e a memória própria; nada de SQL nas pessoas).
Trabalha em `ferramentas/simulacao/personas/<papel>.py` (se já existir, afina-a) e testa na tua base `embriovet_simN` com `--persona`.
Entrega: quem é a pessoa e os hábitos/erros que lhe deste; o que reparou na app (passos difíceis, informação em falta, passagem de turno); e, se houver corrida completa, a análise do seu ponto de vista com números.
