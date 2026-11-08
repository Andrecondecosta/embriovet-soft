---
name: avaliacao-traducoes
description: Verifica traduções e textos (pt-PT, en, fr, de): chaves em falta ou a mostrar o nome da chave, plurais e singulares, textos técnicos/ambíguos, consistência de termos clínicos, e nenhuma referência ao estudo no ecrã.
---
Lê `.claude/regras-avaliacao.md`.
Cruza as chaves usadas em `frontend/src` (`t("...")`) com `backend/i18n_web.py` e `modules/i18n.py` nos 4 idiomas; procura chaves em falta, iguais ao português noutro idioma, "(s)" em vez de singular/plural (`<chave>_one`), termos diferentes para a mesma coisa, e as palavras estudo/tese/dissertação. Pode correr `scripts/i18n_audit.py` se existir.
Entrega: lista por idioma (em falta, errado, inconsistente) e textos a reescrever, com a proposta.
