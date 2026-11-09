"""API nova: Stock de sémen (Lotes, Garanhões, Adicionar lote) — base de TESTE.

Cria dono, contentor e garanhão próprios (prefixo `__api_stock__`) e apaga
tudo no fim.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

P = "__api_stock__"


def _exec(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
    return row


def _login(nivel: str) -> TestClient:
    username = f"{P}{nivel}{uuid.uuid4().hex[:6]}"
    _exec(
        "INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)"
        " VALUES (%s, 'Teste', %s, %s, TRUE, FALSE)",
        (username, criar_hash_password("x123"), nivel),
    )
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "x123"}).status_code == 200
    return c


@pytest.fixture
def ctx():
    sufixo = uuid.uuid4().hex[:8]
    dono = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}dono{sufixo}",))[0]
    dono_inativo = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, FALSE) RETURNING id", (f"{P}inativo{sufixo}",))[0]
    contentor = _exec(
        "INSERT INTO contentores (codigo, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}C{sufixo}",)
    )[0]
    yield {
        "admin": _login("Administrador"),
        "gestor": _login("Gestor"),
        "dono": dono,
        "dono_inativo": dono_inativo,
        "contentor": contentor,
        "garanhao": f"{P}Garanhão {sufixo}",
    }
    _exec(
        "DELETE FROM estoque_dono WHERE dono_id IN (%s, %s) OR contentor_id = %s",
        (dono, dono_inativo, contentor),
    )
    _exec("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM dono WHERE id IN (%s, %s)", (dono, dono_inativo))
    _exec("DELETE FROM contentores WHERE id = %s", (contentor,))
    _exec("DELETE FROM user_sessions WHERE username LIKE %s", (f"{P}%",))
    _exec("DELETE FROM usuarios WHERE username LIKE %s", (f"{P}%",))


def _novo(ctx, **extra):
    body = {
        "garanhao": ctx["garanhao"],
        "dono_id": ctx["dono"],
        "palhetas": 10,
        "contentor_id": ctx["contentor"],
        "canister": 3,
        "andar": 2,
        "qualidade": "80",
        "motilidade": 60,
        "concentracao": 200,
        "data_embriovet": "2026-05-10",
        **extra,
    }
    return ctx["gestor"].post("/api/stock/lotes", json=body)


def test_adicionar_lote_cria_garanhao_e_regista_utilizador(ctx):
    r = _novo(ctx)
    assert r.status_code == 201, r.text
    lote = r.json()
    assert lote["garanhao_nome"] == ctx["garanhao"]
    assert lote["animal_id"] is not None
    assert lote["existencia_atual"] == 10 and lote["quantidade_inicial"] == 10
    assert lote["criado_por"].startswith(f"{P}Gestor")
    assert (lote["contentor_id"], lote["canister"], lote["andar"]) == (ctx["contentor"], 3, 2)


def test_adicionar_lote_validacoes(ctx):
    assert _novo(ctx, palhetas=0).status_code == 422
    assert _novo(ctx, garanhao="  ").status_code == 422
    assert _novo(ctx, canister=11).status_code == 422
    assert _novo(ctx, andar=3).status_code == 422
    assert _novo(ctx, contentor_id=-1).status_code == 422


def test_lotes_kpis_e_resumo(ctx):
    _novo(ctx, palhetas=10, qualidade="80")
    _novo(ctx, palhetas=5, qualidade="60")
    r = ctx["gestor"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    assert r["kpis"] == {"lotes": 2, "palhetas": 15, "proprietarios": 1, "qualidade_media": 70.0}
    assert r["por_proprietario"] == [{"dono_id": ctx["dono"], "proprietario_nome": r["items"][0]["proprietario_nome"], "palhetas": 15}]
    # Ligações só para Administrador (como na app atual).
    assert r["ligacoes"] == {}


def test_lotes_de_dono_inativo_nao_aparecem(ctx):
    _novo(ctx)
    _novo(ctx, dono_id=ctx["dono_inativo"])
    r = ctx["gestor"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    assert [l["dono_id"] for l in r["items"]] == [ctx["dono"]]


def test_filtros(ctx):
    _novo(ctx, palhetas=10)
    _novo(ctx, palhetas=2)
    g = ctx["garanhao"]
    c = ctx["gestor"]
    assert len(c.get("/api/stock/lotes", params={"garanhao": g, "min_palhetas": 5}).json()["items"]) == 1
    assert len(c.get("/api/stock/lotes", params={"garanhao": g, "donos": [ctx["dono"]]}).json()["items"]) == 2
    assert len(c.get("/api/stock/lotes", params={"garanhao": g, "sem_dono": True}).json()["items"]) == 0


def test_filtro_periodo_producao_e_entrada(ctx):
    a = _novo(ctx, data_embriovet="2021-01-12").json()["id"]
    # Lotes antigos com a data escrita à mão (já não se consegue criar assim).
    b, c_, d = (_novo(ctx).json()["id"] for _ in range(3))
    for lote, texto in ((b, "12-03-2021"), (c_, "2019"), (d, "Várias")):
        _exec("UPDATE estoque_dono SET data_embriovet = %s WHERE id = %s", (texto, lote))
    g, c = ctx["garanhao"], ctx["gestor"]

    def ids(**p):
        return sorted(l["id"] for l in c.get("/api/stock/lotes", params={"garanhao": g, **p}).json()["items"])

    assert ids(prod_de="2021-01-01", prod_ate="2021-01-31") == [a]
    assert ids(prod_de="2021-01-01") == sorted([a, b])
    assert ids(prod_ate="2019-06-30") == [c_]
    # Entrada: todos foram criados hoje.
    hoje = date.today().isoformat()
    assert len(ids(entrada_de=hoje, entrada_ate=hoje)) == 4
    assert ids(entrada_ate="2000-01-01") == []
    r = c.get("/api/stock/lotes", params={"garanhao": g, "prod_de": "2021-01-01", "prod_ate": "2021-01-31"}).json()
    assert r["kpis"]["lotes"] == 1 and r["kpis"]["palhetas"] == 10


def test_data_producao_so_do_calendario(ctx):
    assert _novo(ctx, data_embriovet="12-01-2021").status_code == 422
    assert _novo(ctx, data_embriovet="2021-02-30").status_code == 422
    assert _novo(ctx, data_embriovet="").status_code == 201  # pode ficar vazia
    assert _novo(ctx).json()["data_embriovet"] == "2026-05-10"


def test_editar_lote_antigo_mantem_ou_normaliza_a_data(ctx):
    lote = _novo(ctx).json()
    body = {
        "garanhao": lote["garanhao"], "dono_id": ctx["dono"], "contentor_id": ctx["contentor"],
        "canister": 3, "andar": 2, "palhetas_produzidas": 10, "existencia_atual": 10,
    }
    url = f"/api/stock/lotes/{lote['id']}"
    a = ctx["admin"]
    # Texto antigo que não é um dia: fica como estava se não lhe mexerem.
    _exec("UPDATE estoque_dono SET data_embriovet = '2014' WHERE id = %s", (lote["id"],))
    assert a.put(url, json={**body, "data_embriovet": "2014"}).json()["data_embriovet"] == "2014"
    # Mas não se pode escrever texto novo à mão.
    r = a.put(url, json={**body, "data_embriovet": "Várias"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "web.stock.error.prod_date_format"
    # Dia certo escrito à antiga passa a AAAA-MM-DD ao guardar.
    _exec("UPDATE estoque_dono SET data_embriovet = '12-01-2021' WHERE id = %s", (lote["id"],))
    assert a.put(url, json={**body, "data_embriovet": "12-01-2021"}).json()["data_embriovet"] == "2021-01-12"
    assert a.put(url, json={**body, "data_embriovet": "2020-06-01"}).json()["data_embriovet"] == "2020-06-01"


def test_garanhoes(ctx):
    _novo(ctx, palhetas=4)
    lista = ctx["gestor"].get("/api/stock/garanhoes").json()
    g = next(x for x in lista if x["garanhao"] == ctx["garanhao"])
    assert (g["palhetas"], g["lotes"], g["donos"], g["no_seletor"]) == (4, 1, 1, True)


def test_novo_garanhao_sem_lote_nem_estadia(ctx):
    c = ctx["gestor"]
    r = c.post("/api/stock/garanhoes", json={"nome": f"  {ctx['garanhao']}  "})
    assert r.status_code == 201, r.text
    animal = r.json()["animal_id"]
    assert _exec("SELECT tipo FROM animais WHERE id = %s", (animal,))[0] == "garanhao"
    assert _exec("SELECT COUNT(*) FROM estadias WHERE animal_id = %s", (animal,))[0] == 0
    # Aparece no separador Garanhões (sem lotes, sem "Pouco stock"), não no seletor dos Lotes.
    g = next(x for x in c.get("/api/stock/garanhoes?incluir_vazios=true").json() if x["animal_id"] == animal)
    assert (g["lotes"], g["palhetas"], g["pouco"]) == (0, 0, False)
    assert all(x["animal_id"] != animal for x in c.get("/api/stock/garanhoes").json())
    # O mesmo nome sem acento/maiúsculas: já existe.
    r = c.post("/api/stock/garanhoes", json={"nome": ctx["garanhao"].upper().replace("Ã", "A")})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "web.stock.error.stallion_exists"
    assert c.post("/api/stock/garanhoes", json={"nome": "   "}).status_code == 422
    # O primeiro lote fica ligado ao mesmo animal e ele deixa de aparecer como "sem lotes".
    assert _novo(ctx).json()["animal_id"] == animal
    linhas = [x for x in c.get("/api/stock/garanhoes?incluir_vazios=true").json() if x["animal_id"] == animal]
    assert [x["lotes"] for x in linhas] == [1]


def test_editar_gestor_e_apagar_so_admin(ctx):
    lote = _novo(ctx).json()
    body = {
        "garanhao": lote["garanhao"], "dono_id": ctx["dono"], "contentor_id": ctx["contentor"],
        "canister": 5, "andar": 1, "palhetas_produzidas": 10, "existencia_atual": 7,
        "certificado": "Não", "motilidade": 50,
    }
    # O stock (Gestor) corrige o lote — ex.: motilidade quando chega o certificado.
    assert ctx["gestor"].put(f"/api/stock/lotes/{lote['id']}", json=body).status_code == 200
    assert ctx["gestor"].delete(f"/api/stock/lotes/{lote['id']}").status_code == 403

    r = ctx["admin"].put(f"/api/stock/lotes/{lote['id']}", json=body)
    assert r.status_code == 200
    assert (r.json()["existencia_atual"], r.json()["canister"], r.json()["certificado"]) == (7, 5, "Não")

    admin_lotes = ctx["admin"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    assert admin_lotes["items"][0]["id"] == lote["id"]

    assert ctx["admin"].delete(f"/api/stock/lotes/{lote['id']}").status_code == 200
    assert ctx["admin"].get(f"/api/stock/lotes/{lote['id']}").status_code == 404


def test_editar_muda_o_garanhao_a_serio(ctx):
    """Trocar o garanhão ao editar muda a ligação à ficha (animal_id) —
    o lote passa a aparecer no garanhão novo."""
    lote = _novo(ctx).json()
    novo_nome = ctx["garanhao"] + " B"
    body = {
        "garanhao": novo_nome, "dono_id": ctx["dono"], "contentor_id": ctx["contentor"],
        "canister": 3, "andar": 2, "palhetas_produzidas": 10, "existencia_atual": 10,
    }
    r = ctx["admin"].put(f"/api/stock/lotes/{lote['id']}", json=body)
    assert r.status_code == 200
    editado = r.json()
    assert editado["garanhao_nome"] == novo_nome
    assert editado["animal_id"] != lote["animal_id"]

    antigo = ctx["admin"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    novo = ctx["admin"].get("/api/stock/lotes", params={"garanhao": novo_nome}).json()
    assert antigo["items"] == [] and [l["id"] for l in novo["items"]] == [lote["id"]]

    # Escrever o nome de um garanhão que já existe (outras maiúsculas) não
    # cria duplicado: volta para o primeiro.
    r = ctx["admin"].put(f"/api/stock/lotes/{lote['id']}", json={**body, "garanhao": ctx["garanhao"].upper()})
    assert r.json()["animal_id"] == lote["animal_id"]


def test_motilidade_nao_medida_fica_vazia(ctx):
    lote = _novo(ctx, motilidade=None, concentracao=None, origem_externa="Haras X").json()
    assert lote["motilidade"] is None and lote["concentracao"] is None
    insem = next(l for l in ctx["gestor"].get("/api/inseminacoes/lotes").json() if l["id"] == lote["id"])
    assert insem["motilidade"] is None and "observacoes" in insem


def test_editar_lote_nao_repoe_existencia_antiga(ctx):
    lote = _novo(ctx).json()  # 10 palhetas
    body = {
        "garanhao": lote["garanhao"], "dono_id": ctx["dono"], "contentor_id": ctx["contentor"],
        "canister": 3, "andar": 2, "palhetas_produzidas": 10, "existencia_atual": 10, "existencia_original": 10,
        "observacoes": "corrigido",
    }
    _exec("UPDATE estoque_dono SET existencia_atual = 8 WHERE id = %s", (lote["id"],))  # alguém gastou 2
    r = ctx["gestor"].put(f"/api/stock/lotes/{lote['id']}", json=body)
    assert r.status_code == 200 and r.json()["existencia_atual"] == 8
    # Se o utilizador também mudou a existência, não se adivinha: conflito.
    r = ctx["gestor"].put(f"/api/stock/lotes/{lote['id']}", json={**body, "existencia_atual": 5})
    assert r.json()["detail"]["code"] == "web.stock.error.changed_meanwhile"
