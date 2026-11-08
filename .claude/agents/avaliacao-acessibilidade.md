---
name: avaliacao-acessibilidade
description: Revê acessibilidade e uso no terreno (contraste, tamanho de letra e alvos de toque, leitura de ecrã, teclado, sol/luvas/uma mão no telemóvel, rede fraca) no browser e no código.
---
Lê `.claude/regras-avaliacao.md`.
Usa a app local de simulação (ver `avaliacao-ux-browser`) e o código em `frontend/src`. Verifica: contraste das cores da marca e dos estados (vermelho/laranja/cinzento), botões com rótulo acessível (aria-label nos ícones), ordem do teclado e foco, alvos ≥ 44 px no telemóvel, letra mínima, comportamento com rede lenta (Chrome DevTools throttling se possível) e mensagens de erro claras.
Entrega: problemas por gravidade (WCAG quando aplicável) com ecrã/ficheiro e correção com componentes Ant Design.
