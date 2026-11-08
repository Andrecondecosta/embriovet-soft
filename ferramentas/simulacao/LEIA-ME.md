# Clínica simulada — instruções para cada agente

Uma clínica de reprodução equina com 150 éguas, de 1 fev. a 1 nov. 2027 (273 dias),
a usar a app EquiCore (este repositório).
Cinco pessoas trabalham lá; cada agente é UMA delas e escreve o seu comportamento.

## Ficheiros (pasta `ferramentas/simulacao/`)
- `simcore.py` — base própria, relógio, classe `Pessoa` (API, notas, memória). Ler.
- `mundo.py` — a "natureza": ciclos, ovulação, gestação, sémen, chegadas, donos. Ler a API pública
  (`chegadas`, `saidas_imprevistas`, `perfil_dono`, `wid_por_nome`, `exame`, `inseminar`, `induzir`,
  `semen_chega`, `pedir_semen`). NÃO ler/alterar o estado interno das éguas (é batota: a pessoa não sabe).
- `personas_base.py` — versão base, simples e correta, das 5 pessoas. Ponto de partida.
- `runner.py` — corre a clínica. `personas/` — onde fica a tua pessoa.

## O que fazer
1. Lê `LEIA-ME.md`, `simcore.py`, `mundo.py`, `personas_base.py`, e os routers da app que a tua
   pessoa usa (`backend/routers/*.py`) para saberes o que a app aceita e mostra.
2. Escreve `personas/<papel>.py` com uma classe que herda de `simcore.Pessoa` (ou da classe base do
   teu papel) e tem `papel = "<papel>"`, `nome = "<nome curto>"`, `ordem` igual à base, e `dia(self, rel)`.
3. Testa só a tua pessoa (o resto na versão base), na TUA base:
   `cd ferramentas/simulacao && ../../venv/bin/python runner.py --db embriovet_simN --persona personas/<papel>.py --dias 120`
   Saída em `ferramentas/simulacao/saida/embriovet_simN/` (acoes, erros, notas, verdade .jsonl). Corrige até não haver
   exceções da tua pessoa (`excecao` em erros.jsonl). Erros 4xx da APP são dados úteis, não bugs teus —
   mas confirma que o teu pedido estava certo antes de os culpar à app.
4. No fim, responde com: quem é a pessoa, os hábitos/erros humanos que lhe deste, e o que já reparaste
   na app ao escrevê-la. Curto. Depois vais receber os resultados da corrida completa (as 5 pessoas
   juntas) para analisares do ponto de vista da tua pessoa.

## Regras (importante)
- A pessoa só sabe o que: (a) a app lhe mostra via `self.api(...)`; (b) vê/ouve no mundo
  (exame que ela própria faz, chegadas à porta, telefonemas dos donos, sémen que chega);
  (c) está na sua memória privada `self.memoria`. Não há memória partilhada entre pessoas: a
  coordenação tem de passar pela app (é isso que estamos a testar). Nada de SQL nas pessoas.
- Datas: o mundo usa datas simuladas (`rel.hoje`); a app usa datas reais — converte com
  `rel.real(dia_simulado)` (e `rel.simulado(dia_real)` no sentido inverso). Horas mantêm-se.
- Ações físicas passam pelo mundo: quem insemina chama `mundo.inseminar(wid, quando_simulado, codigo_lote)`
  (o código "LT-xxx" está nas observações do lote, se o stock o escreveu: a lista `/inseminacoes/lotes` NÃO traz as observações; lê-as na ficha `GET /stock/lotes/{id}` — é a etiqueta da palheta); quem induz chama
  `mundo.induzir`. Registar na app é outra coisa (a pessoa pode esquecer-se, atrasar-se, enganar-se).
- Torna a pessoa REAL: horário, folgas, pressa, esquecimentos, gralhas, atrasos, preferências,
  confiança (ou não) na app. Usa um `random.Random(semente)` próprio para os erros (reprodutível).
  Mas é uma profissional competente: os erros são os de quem trabalha numa clínica a sério,
  não sabotagem. Regista com `self.nota("...")` o que a pessoa acharia difícil, confuso ou em falta na app.
- Não alteres o repo da app, `simcore.py`, `mundo.py`, `runner.py` nem `personas_base.py`.
  Só a tua base `embriovet_simN` (localhost). Nunca outra base.
- Cada dia simulado deve correr depressa (a corrida completa tem de caber em ~10 min).
