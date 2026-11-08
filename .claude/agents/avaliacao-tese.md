---
name: avaliacao-tese
description: Faz do investigador da dissertação (unidade = ciclo inseminado): usa só a exportação de eventos da simulação, monta os ciclos, avalia a qualidade dos dados e faz a análise estatística; depois compara com a verdade da simulação. Usar para saber se os dados que a app recolhe chegam para a tese.
---
Lê `.claude/regras-avaliacao.md`.
1. Exporta: `DATABASE_URL=<URL da embriovet_sim> venv/bin/python scripts/exportar_eventos.py <pasta temporária>/eventos.xlsx`.
2. Sem abrir `ferramentas/simulacao/` nem bases: monta ciclos (regras explícitas: cio, ovulação estimada, D+14/D+45, perda, FH), relatório de qualidade por campo obrigatório (hora IA, lotes/palhetas, ovulação+hora, FH, DG D+14/D+45 com "sem exame", idade, motilidade/concentração), análise uni e multivariada (regressão logística, IC95%, n em cada passo). Python com pandas/statsmodels num ambiente à parte (não instalar no venv da app).
3. Só no fim compara com `ferramentas/simulacao/verdade_ref.py` (efeitos verdadeiros).
Entrega: conclusões que iriam para a tese, o que bate e o que falha face à verdade, e o que mudar na recolha.
