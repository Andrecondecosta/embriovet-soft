---
name: avaliacao-rgpd
description: Revê proteção de dados pessoais (RGPD): que dados de proprietários/utilizadores existem, quem os vê por nível, exportações e cópias de segurança, retenção e apagamento, registo de acessos, pseudonimização dos dados para estudo.
---
Lê `.claude/regras-avaliacao.md`.
Mapeia campos pessoais (dono: nome, NIF, email, telemóvel, morada; utilizadores), onde aparecem (ecrãs, PDF/Excel/CSV, backup, logs) e quem lhes acede. Verifica a pseudonimização de `scripts/exportar_eventos.py`, o direito ao apagamento (o que impede apagar um dono), retenção de sessões/auditoria e transmissão (HTTPS, cookies).
Entrega: lacunas por gravidade, com o artigo do RGPD quando relevante, e medidas práticas para uma clínica pequena.
