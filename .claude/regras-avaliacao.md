# Regras comuns a todos os agentes de avaliação (lidas por cada agente)

- Responder em português de Portugal.
- NUNCA ligar à base de dados real/produção, nem para ler. Só `TEST_DATABASE_URL` (localhost) ou as bases
  de simulação `embriovet_sim*` (localhost). Fora do Render, `backend/config.py` força a de teste.
- Não alterar o código da app, salvo pedido explícito. Ficheiros temporários fora do repositório.
- Testes: `venv/bin/python -m pytest -q` (usam a base de teste). Frontend: `cd frontend && npx tsc -b --noEmit && npm run build`.
- Interface: só componentes Ant Design (computador) / Ant Design Mobile (telemóvel), tamanho normal.
- Nada no ecrã pode referir o estudo/tese (a app é um produto para clínicas).
- Entregar sempre: achados ordenados por gravidade, com evidência (ficheiro:linha, passos, números),
  separando "problema da app" de "comportamento/artefacto do teste", e a correção mínima sugerida.
