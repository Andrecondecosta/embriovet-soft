---
name: avaliacao-backup-recuperacao
description: Faz um ensaio de recuperação: tira uma cópia de segurança pela app, simula um desastre numa base local e repõe; confirma que nada se perde (contagens, ligações, ficheiros) e cronometra.
---
Lê `.claude/regras-avaliacao.md`.
Numa base local própria (`createdb -T embriovet_sim embriovet_dr`): descarrega a cópia pelo endpoint de backup (Administrador), apaga/corrompe dados, repõe com a ferramenta do projeto, e compara contagens e somas por tabela (animais, estadias, inseminações, diagnósticos, lotes/existências, tarefas, histórico). Apaga a base no fim.
Entrega: o procedimento passo a passo para a clínica, tempo total, o que não ficou na cópia, e riscos (ex.: reposição parcial, cópias antigas).
