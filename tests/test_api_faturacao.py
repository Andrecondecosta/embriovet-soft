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


def _login(nivel: str, faturacao: bool) -> TestClient:
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
        "fat": _login("Visualizador", True), "sem": _login("Administrador", False),
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


def _por_faturar(c, ctx, **p):
    params = {"inicio": d(30).isoformat(), "fim": HOJE.isoformat(), "dono_id": ctx["dono"], **p}
    return c.get("/api/faturacao/por-faturar", params=params)


def test_so_quem_tem_acesso(ctx):
    # Nem um Administrador sem a autorização vê a faturação.
    assert _por_faturar(ctx["sem"], ctx).status_code == 403
    assert _por_faturar(ctx["fat"], ctx).status_code == 200
    me = ctx["fat"].get("/api/auth/me").json()["user"]
    assert me["acesso_faturacao"] is True


def test_dias_de_estadia_e_palhetas_x_dias(ctx):
    linhas = _por_faturar(ctx["fat"], ctx).json()
    por_ref = {(l["tipo"], l["ref_id"]): l for l in linhas}
    # Entrada e saída contam: de há 10 a há 3 dias = 8 dias; aberta desde há 2 = 3 dias (até hoje).
    assert por_ref[("estadia", ctx["fechada"])]["quantidade"] == 8
    assert por_ref[("estadia", ctx["aberta"])]["quantidade"] == 3
    # 6 dias com 7 + 3 dias com 5 + 2 dias com 4 = 65 (o dia em que saem ainda conta).
    lote = por_ref[("armazenamento", ctx["lote"])]
    assert (lote["quantidade"], lote["dias"], lote["palhetas_inicio"], lote["palhetas_fim"]) == (65, 11, 7, 4)
    # "Externo" não está no centro: não conta. Nem aparece no filtro de outro dono.
    todos = ctx["fat"].get("/api/faturacao/por-faturar", params={"inicio": d(30).isoformat(), "fim": HOJE.isoformat()}).json()
    assert all(l["ref_id"] != ctx["externa"] for l in todos if l["tipo"] == "estadia")
    # Só sémen.
    so_semen = _por_faturar(ctx["fat"], ctx, tipo="armazenamento").json()
    assert {l["tipo"] for l in so_semen} == {"armazenamento"}


def test_faturar_parte_nao_repete_e_anular_devolve(ctx):
    c = ctx["fat"]
    corpo = {
        "fatura_numero": " FT 2026/15 ", "fatura_data": HOJE.isoformat(),
        "linhas": [{"tipo": "armazenamento", "ref_id": ctx["lote"], "inicio": d(10).isoformat(), "fim": d(6).isoformat()}],
    }
    # Um Visualizador com acesso à faturação pode marcar.
    assert c.post("/api/faturacao/faturar", json=corpo).json() == {"linhas": 1}
    # Fica o resto do período: de há 5 dias até hoje (6 × ... = 65 − 5 × 7).
    resto = [l for l in _por_faturar(c, ctx).json() if l["tipo"] == "armazenamento"]
    assert [(l["inicio"], l["quantidade"]) for l in resto] == [(d(5).isoformat(), 30)]
    # Os mesmos dias outra vez: recusado, nada gravado.
    r = c.post("/api/faturacao/faturar", json=corpo)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "web.billing.error.changed"
    # Fora das datas do lote (antes de existir) também.
    fora = {**corpo, "linhas": [{**corpo["linhas"][0], "inicio": d(20).isoformat()}]}
    assert c.post("/api/faturacao/faturar", json=fora).status_code == 409

    feitas = c.get("/api/faturacao/faturado", params={"inicio": d(30).isoformat(), "fim": HOJE.isoformat(), "fatura": "2026/15"}).json()
    assert [(f["fatura_numero"], f["quantidade"], f["dono_id"]) for f in feitas] == [("FT 2026/15", 35, ctx["dono"])]
    assert c.post(f"/api/faturacao/linhas/{feitas[0]['id']}/anular", json={"motivo": "engano"}).status_code == 200
    lote = [l for l in _por_faturar(c, ctx).json() if l["tipo"] == "armazenamento"]
    assert [l["quantidade"] for l in lote] == [65]
    # A anulada fica guardada.
    com = c.get("/api/faturacao/faturado", params={"inicio": d(30).isoformat(), "fim": HOJE.isoformat(), "anuladas": True}).json()
    assert any(f["id"] == feitas[0]["id"] and f["anulada"] for f in com)


def test_admin_da_e_tira_acesso(ctx):
    admin = _login("Administrador", False)
    uid = _exec("SELECT id FROM usuarios WHERE username LIKE %s AND acesso_faturacao ORDER BY id DESC LIMIT 1", (f"{P}%",))[0]
    r = admin.put(f"/api/definicoes/utilizadores/{uid}/faturacao", json={"ativo": False})
    assert r.status_code == 200 and r.json()["acesso_faturacao"] is False
    assert _por_faturar(ctx["fat"], ctx).status_code == 403
    # Quem não é Administrador não muda acessos.
    assert ctx["fat"].put(f"/api/definicoes/utilizadores/{uid}/faturacao", json={"ativo": True}).status_code == 403
