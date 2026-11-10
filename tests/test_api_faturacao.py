"""API nova: Faturação (estadias em dias, sémen em palhetas × dias) — base
de TESTE. Dados próprios com prefixo `__api_fat__`, apagados no fim."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

P = "__api_fat__"
HOJE = date.today()


def _exec(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
    return row


def _login(nivel: str, faturacao: str) -> TestClient:
    username = f"{P}{uuid.uuid4().hex[:8]}"
    _exec(
        """INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password, acesso_faturacao)
           VALUES (%s, 'Teste', %s, %s, TRUE, FALSE, %s)""",
        (username, criar_hash_password("x123"), nivel, faturacao),
    )
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "x123"}).status_code == 200
    return c


def d(n: int) -> date:
    return HOJE - timedelta(days=n)


@pytest.fixture
def ctx():
    s = uuid.uuid4().hex[:6]
    dono = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}dono{s}",))[0]
    outro = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}outro{s}",))[0]
    egua = _exec("INSERT INTO animais (nome, tipo, dono_id, ativo) VALUES (%s, 'egua', %s, TRUE) RETURNING id", (f"{P}egua{s}", dono))[0]
    egua2 = _exec("INSERT INTO animais (nome, tipo, dono_id, ativo) VALUES (%s, 'egua', %s, TRUE) RETURNING id", (f"{P}egua2{s}", dono))[0]
    egua3 = _exec("INSERT INTO animais (nome, tipo, dono_id, ativo) VALUES (%s, 'egua', %s, TRUE) RETURNING id", (f"{P}egua3{s}", outro))[0]

    def estadia(animal, dono_id, entrada, saida, tipo="estadia"):
        return _exec(
            """INSERT INTO estadias (tipo_registo, animal_id, dono_id, data_entrada, data_saida, motivo, estado)
               VALUES (%s, %s, %s, %s, %s, 'inseminacao', %s) RETURNING id""",
            (tipo, animal, dono_id, entrada, saida, "alta" if saida else ("externo" if tipo == "externo" else "internado")),
        )[0]

    fechada = estadia(egua, dono, d(10), d(3))
    aberta = estadia(egua2, dono, d(2), None)
    externa = estadia(egua3, outro, d(5), None, tipo="externo")
    cont = _exec("INSERT INTO contentores (codigo, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}C{s}",))[0]
    # Lote com 7 palhetas há 10 dias; 2 gastas há 5 dias, 1 enviada há 2 → hoje 4.
    lote = _exec(
        """INSERT INTO estoque_dono (garanhao, dono_id, existencia_atual, quantidade_inicial, contentor_id, canister, andar, data_criacao)
           VALUES (%s, %s, 4, 7, %s, 1, 1, %s) RETURNING id""",
        (f"{P}Zeus", dono, cont, d(10)),
    )[0]
    _exec("INSERT INTO inseminacoes (garanhao, egua, data_inseminacao, palhetas_gastas, estoque_id) VALUES ('z', 'e', %s, 2, %s)", (d(5), lote))
    _exec("INSERT INTO transferencias_externas (estoque_id, quantidade, data_transferencia, destinatario_externo) VALUES (%s, 1, %s, 'Fora')", (lote, d(2)))
    yield {
        "fat": _login("Visualizador", "editar"), "sem": _login("Administrador", "nenhum"),
        "dono": dono, "outro": outro, "fechada": fechada, "aberta": aberta, "externa": externa, "lote": lote,
    }
    _exec("DELETE FROM faturacao_linhas WHERE dono_id IN (%s, %s)", (dono, outro))
    _exec("DELETE FROM inseminacoes WHERE estoque_id = %s", (lote,))
    _exec("DELETE FROM transferencias_externas WHERE estoque_id = %s", (lote,))
    _exec("DELETE FROM estoque_dono WHERE id = %s", (lote,))
    _exec("DELETE FROM contentores WHERE id = %s", (cont,))
    _exec("DELETE FROM estadias WHERE dono_id IN (%s, %s)", (dono, outro))
    _exec("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM dono WHERE id IN (%s, %s)", (dono, outro))
    _exec("DELETE FROM user_sessions WHERE username LIKE %s", (f"{P}%",))
    _exec("DELETE FROM usuarios WHERE username LIKE %s", (f"{P}%",))


def _fatura(dono, numero, data, linhas, **extra):
    return {"faturas": [{"dono_id": dono, "fatura_numero": numero, "fatura_data": data, "linhas": linhas, **extra}]}


def _por_faturar(c, ctx, **p):
    params = {"inicio": d(30).isoformat(), "fim": HOJE.isoformat(), "dono_id": ctx["dono"], **p}
    return c.get("/api/faturacao/por-faturar", params=params)


def test_so_quem_tem_acesso(ctx):
    # Nem um Administrador sem a autorização vê a faturação.
    assert _por_faturar(ctx["sem"], ctx).status_code == 403
    assert _por_faturar(ctx["fat"], ctx).status_code == 200
    me = ctx["fat"].get("/api/auth/me").json()["user"]
    assert me["acesso_faturacao"] == "editar"


def test_dias_de_estadia_e_palhetas_x_dias(ctx):
    linhas = _por_faturar(ctx["fat"], ctx).json()
    por_ref = {(l["tipo"], l["ref_id"]): l for l in linhas}
    # Entrada e saída contam: de há 10 a há 3 dias = 8 dias; aberta desde há 2 = 3 dias (até hoje).
    assert por_ref[("estadia", ctx["fechada"])]["quantidade"] == 8
    assert por_ref[("estadia", ctx["aberta"])]["quantidade"] == 3
    # Uma linha por troço com as mesmas palhetas: 6 dias com 7, 3 com 5, 2 com 4
    # (o dia em que saem ainda conta) = 65 palhetas × dia.
    lote = [(l["inicio"], l["dias"], l["palhetas"]) for l in linhas if l["tipo"] == "armazenamento"]
    assert lote == [(d(10).isoformat(), 6, 7), (d(4).isoformat(), 3, 5), (d(1).isoformat(), 2, 4)]
    assert sum(l["quantidade"] for l in linhas if l["tipo"] == "armazenamento") == 65
    # "Externo" não está no centro: não conta. Nem aparece no filtro de outro dono.
    todos = ctx["fat"].get("/api/faturacao/por-faturar", params={"inicio": d(30).isoformat(), "fim": HOJE.isoformat()}).json()
    assert all(l["ref_id"] != ctx["externa"] for l in todos if l["tipo"] == "estadia")
    # Só sémen.
    so_semen = _por_faturar(ctx["fat"], ctx, tipo="armazenamento").json()
    assert {l["tipo"] for l in so_semen} == {"armazenamento"}


def test_faturar_parte_nao_repete_e_anular_devolve(ctx):
    c = ctx["fat"]
    linha = {"tipo": "armazenamento", "ref_id": ctx["lote"], "inicio": d(10).isoformat(), "fim": d(6).isoformat()}
    corpo = _fatura(ctx["dono"], " FT 2026/15 ", HOJE.isoformat(), [linha])
    # Um Visualizador com acesso à faturação pode marcar.
    assert c.post("/api/faturacao/faturar", json=corpo).json() == {"linhas": 1}
    # Fica o resto do período: de há 5 dias até hoje (6 × ... = 65 − 5 × 7).
    resto = [l for l in _por_faturar(c, ctx).json() if l["tipo"] == "armazenamento"]
    assert [(l["inicio"], l["dias"], l["palhetas"]) for l in resto] == [
        (d(5).isoformat(), 1, 7), (d(4).isoformat(), 3, 5), (d(1).isoformat(), 2, 4)]
    # Os mesmos dias outra vez: recusado, nada gravado.
    r = c.post("/api/faturacao/faturar", json=corpo)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "web.billing.error.changed"
    # Fora das datas do lote (antes de existir) também.
    fora = _fatura(ctx["dono"], "FT 2026/16", HOJE.isoformat(), [{**linha, "inicio": d(20).isoformat()}])
    assert c.post("/api/faturacao/faturar", json=fora).status_code == 409

    feitas = c.get("/api/faturacao/faturado", params={"inicio": d(30).isoformat(), "fim": HOJE.isoformat(), "fatura": "2026/15"}).json()
    assert [(f["fatura_numero"], f["quantidade"], f["palhetas"], f["dono_id"]) for f in feitas] == [("FT 2026/15", 35, 7, ctx["dono"])]
    assert c.post(f"/api/faturacao/linhas/{feitas[0]['id']}/anular", json={"motivo": "engano"}).status_code == 200
    lote = [l for l in _por_faturar(c, ctx).json() if l["tipo"] == "armazenamento"]
    assert sum(l["quantidade"] for l in lote) == 65 and lote[0]["inicio"] == d(10).isoformat()
    # A anulada fica guardada.
    com = c.get("/api/faturacao/faturado", params={"inicio": d(30).isoformat(), "fim": HOJE.isoformat(), "anuladas": True}).json()
    assert any(f["id"] == feitas[0]["id"] and f["anulada"] for f in com)


def test_acesso_por_pessoa_sem_ver_editar(ctx):
    admin = _login("Administrador", "nenhum")
    uid = _exec("SELECT id FROM usuarios WHERE username LIKE %s AND acesso_faturacao = 'editar' ORDER BY id DESC LIMIT 1", (f"{P}%",))[0]
    linha = {"tipo": "estadia", "ref_id": ctx["fechada"], "inicio": d(10).isoformat(), "fim": d(3).isoformat()}
    # Só ver: consulta tudo (e o resumo), mas não marca nem anula.
    r = admin.put(f"/api/definicoes/utilizadores/{uid}/faturacao", json={"acesso": "ver"})
    assert r.status_code == 200 and r.json()["acesso_faturacao"] == "ver"
    assert _por_faturar(ctx["fat"], ctx).status_code == 200
    assert ctx["fat"].post("/api/faturacao/resumo", json={"linhas": [linha]}).status_code == 200
    assert ctx["fat"].post("/api/faturacao/faturar", json=_fatura(ctx["dono"], "FT 1", HOJE.isoformat(), [linha])).status_code == 403
    assert ctx["fat"].post("/api/faturacao/linhas/1/anular", json={"motivo": "x"}).status_code == 403
    # Sem acesso: nada.
    assert admin.put(f"/api/definicoes/utilizadores/{uid}/faturacao", json={"acesso": "nenhum"}).status_code == 200
    assert _por_faturar(ctx["fat"], ctx).status_code == 403
    assert admin.put(f"/api/definicoes/utilizadores/{uid}/faturacao", json={"acesso": "outro"}).status_code == 422
    # Quem não é Administrador não muda acessos.
    assert ctx["fat"].put(f"/api/definicoes/utilizadores/{uid}/faturacao", json={"acesso": "editar"}).status_code == 403


def test_quadro_por_ano(ctx):
    c = ctx["fat"]
    ano = HOJE.year
    # Estadia de 30/12/2024 a 02/01/2025: só conta a parte de 2025 (não há coluna "antes").
    egua = _exec("SELECT animal_id FROM estadias WHERE id = %s", (ctx["fechada"],))[0]
    velha = _exec(
        """INSERT INTO estadias (tipo_registo, animal_id, dono_id, data_entrada, data_saida, motivo, estado)
           VALUES ('estadia', %s, %s, '2024-12-30', '2025-01-02', 'inseminacao', 'alta') RETURNING id""",
        (egua, ctx["dono"]),
    )[0]
    r = c.get("/api/faturacao/anos", params={"desde": 2025}).json()
    # Uma coluna por ano, de 2025 até ao ano atual.
    assert r["anos"] == [str(y) for y in range(2025, ano + 1)]
    linha = next(l for l in r["linhas"] if l["dono_id"] == ctx["dono"])
    assert linha["celulas"]["2025"]["dias"] == 2 and linha["celulas"]["2025"]["faturado_ate"] is None
    # Faturada a parte de 2025: fica tudo faturado nesse ano, e até que dia.
    corpo = _fatura(ctx["dono"], "FT 2025/9", "2025-01-10",
                    [{"tipo": "estadia", "ref_id": velha, "inicio": "2025-01-01", "fim": "2025-01-02"}])
    assert c.post("/api/faturacao/faturar", json=corpo).status_code == 200
    linha = next(l for l in c.get("/api/faturacao/anos", params={"desde": 2025}).json()["linhas"] if l["dono_id"] == ctx["dono"])
    assert (linha["celulas"]["2025"]["atividade"], linha["celulas"]["2025"]["dias"]) == (True, 0)
    assert linha["celulas"]["2025"]["faturado_ate"] == "2025-01-02"
    # Sémen deste ano: os 11 dias do lote por faturar (contados uma vez), 1 lote.
    if d(10).year == ano:
        este = linha["celulas"][str(ano)]
        assert (este["dias_semen"], este["lotes"]) == (11, 1)

    assert ctx["sem"].get("/api/faturacao/anos").status_code == 403


def test_tudo_ate_fim_de_2024_deixa_2025_em_diante(ctx):
    c = ctx["fat"]
    # Sémen guardado desde junho de 2024 (5 palhetas, nunca saiu): aluguer de espaço, conta sempre.
    lote = _exec(
        """INSERT INTO estoque_dono (garanhao, dono_id, existencia_atual, quantidade_inicial, data_criacao)
           VALUES (%s, %s, 5, 5, '2024-06-01') RETURNING id""",
        (f"{P}Velho", ctx["dono"]),
    )[0]
    try:
        ate_2024 = {"inicio": "1990-01-01", "fim": "2024-12-31", "dono_id": ctx["dono"], "tipo": "armazenamento"}
        linhas = c.get("/api/faturacao/por-faturar", params=ate_2024).json()
        l = next(x for x in linhas if x["ref_id"] == lote)
        assert (l["inicio"], l["fim"], l["quantidade"]) == ("2024-06-01", "2024-12-31", 214 * 5)
        corpo = _fatura(ctx["dono"], "Anterior à app", HOJE.isoformat(),
                        [{"tipo": "armazenamento", "ref_id": lote, "inicio": l["inicio"], "fim": l["fim"]}])
        assert c.post("/api/faturacao/faturar", json=corpo).status_code == 200
        # Falta de 1/1/2025 até hoje, e continua a contar.
        tudo = c.get("/api/faturacao/por-faturar", params={**ate_2024, "fim": HOJE.isoformat()}).json()
        resto = [x for x in tudo if x["ref_id"] == lote]
        assert [(x["inicio"], x["fim"]) for x in resto] == [("2025-01-01", HOJE.isoformat())]
    finally:
        _exec("DELETE FROM faturacao_linhas WHERE ref_id = %s AND tipo = 'armazenamento'", (lote,))
        _exec("DELETE FROM estoque_dono WHERE id = %s", (lote,))


def test_uma_fatura_por_proprietario_numero_obrigatorio_e_resumo(ctx):
    c = ctx["fat"]
    linha = {"tipo": "estadia", "ref_id": ctx["fechada"], "inicio": d(10).isoformat(), "fim": d(3).isoformat()}
    # Sem número: recusado.
    r = c.post("/api/faturacao/faturar", json=_fatura(ctx["dono"], "", HOJE.isoformat(), [linha]))
    assert r.json()["detail"]["code"] == "web.billing.error.invoice_required"
    # Linha de um proprietário numa fatura de outro: recusado, nada gravado.
    r = c.post("/api/faturacao/faturar", json=_fatura(ctx["outro"], "FT 1", HOJE.isoformat(), [linha]))
    assert r.json()["detail"]["code"] == "web.billing.error.one_owner"
    # O resumo explica cada mudança de palhetas e traz os dados do proprietário.
    lote = {"tipo": "armazenamento", "ref_id": ctx["lote"], "inicio": d(10).isoformat(), "fim": HOJE.isoformat()}
    r = c.post("/api/faturacao/resumo", json={"linhas": [linha, lote], "dono_ids": [ctx["dono"]]}).json()
    assert [(m["data"], m["quantidade"], m["tipo"]) for m in r["movimentos"]] == [
        (d(5).isoformat(), 2, "inseminacao"), (d(2).isoformat(), 1, "externa")]
    assert r["movimentos"][1]["detalhe"] == "Fora"
    assert r["donos"][0]["id"] == ctx["dono"]
    # Com número: grava; "Faturado até" no quadro.
    assert c.post("/api/faturacao/faturar", json=_fatura(ctx["dono"], "FT 5", HOJE.isoformat(), [linha])).status_code == 200
    anos = c.get("/api/faturacao/anos").json()["linhas"]
    assert next(l for l in anos if l["dono_id"] == ctx["dono"])["celulas"][str(d(3).year)]["faturado_ate"] == d(3).isoformat()


def test_em_atraso_e_numeros_usados(ctx):
    c = ctx["fat"]
    linha = next(l for l in c.get("/api/faturacao/atraso").json() if l["dono_id"] == ctx["dono"])
    # Estadias: a mais antiga por faturar entrou há 10 dias; 8 + 3 dias, 2 estadias.
    assert linha["estadia"] == {"desde": d(10).isoformat(), "dias": 11, "itens": 2}
    # Sémen: 11 dias do calendário, 1 lote.
    assert linha["armazenamento"] == {"desde": d(10).isoformat(), "dias": 11, "itens": 1}
    est = {"tipo": "estadia", "ref_id": ctx["fechada"], "inicio": d(10).isoformat(), "fim": d(3).isoformat()}
    assert c.post("/api/faturacao/faturar", json=_fatura(ctx["dono"], "FT 99/2026", HOJE.isoformat(), [est])).status_code == 200
    # O mesmo número (escrito de outra maneira) já foi usado — e para quem.
    usados = c.get("/api/faturacao/numeros", params={"n": [" ft 99/2026 ", "FT 100"]}).json()
    assert usados == [{"fatura_numero": "FT 99/2026", "dono_id": ctx["dono"], "dono_nome": usados[0]["dono_nome"]}]
    linha = next(l for l in c.get("/api/faturacao/atraso").json() if l["dono_id"] == ctx["dono"])
    assert linha["estadia"] == {"desde": d(2).isoformat(), "dias": 3, "itens": 1}


def test_primeira_fatura_pode_comecar_antes_da_entrada_sem_mudar_o_lote(ctx):
    c = ctx["fat"]
    params = {"inicio": "1990-01-01", "fim": HOJE.isoformat(), "dono_id": ctx["dono"], "tipo": "armazenamento"}
    l = c.get("/api/faturacao/por-faturar", params=params).json()[0]
    assert (l["inicio"], l["entrada_app"], l["pode_mudar_inicio"]) == (d(10).isoformat(), d(10).isoformat(), True)
    # O sémen já estava guardado 20 dias antes de entrar na app: 26 dias com as 7 palhetas iniciais.
    linha = {"tipo": "armazenamento", "ref_id": ctx["lote"], "inicio": d(30).isoformat(), "fim": l["fim"]}
    assert c.post("/api/faturacao/faturar", json=_fatura(ctx["dono"], "FT 1/2026", HOJE.isoformat(), [linha])).status_code == 200
    f = c.get("/api/faturacao/faturado", params={"inicio": "1990-01-01", "fim": HOJE.isoformat(), "dono_id": ctx["dono"]}).json()
    assert [(x["inicio"], x["quantidade"], x["palhetas"]) for x in f] == [(d(30).isoformat(), 26 * 7, 7)]
    # O lote não mudou.
    assert str(_exec("SELECT data_criacao::date FROM estoque_dono WHERE id = %s", (ctx["lote"],))[0]) == d(10).isoformat()
    # Só na primeira vez: depois já não pode começar antes da entrada.
    resto = c.get("/api/faturacao/por-faturar", params=params).json()
    assert all(not x["pode_mudar_inicio"] for x in resto)
    outra = {"tipo": "armazenamento", "ref_id": ctx["lote"], "inicio": d(40).isoformat(), "fim": d(31).isoformat()}
    assert c.post("/api/faturacao/faturar", json=_fatura(ctx["dono"], "FT 2/2026", HOJE.isoformat(), [outra])).status_code == 409
