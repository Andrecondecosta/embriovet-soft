"""API nova (FastAPI): Importar sémen — contra a base de TESTE.

Usa nomes com prefixo `__api_test__` (garanhões, proprietários,
contentores) e apaga tudo o que cria.
"""

from __future__ import annotations

import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

P = "__api_test__"


def _exec(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
    return row


@pytest.fixture
def c():
    username = f"{P}{uuid.uuid4().hex[:8]}"
    _exec(
        """INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
           VALUES (%s, 'Teste API', %s, 'Gestor', TRUE, FALSE)""",
        (username, criar_hash_password("segredo123")),
    )
    cl = TestClient(app)
    assert cl.post("/api/auth/login", json={"username": username, "password": "segredo123"}).status_code == 200
    yield cl
    _exec("DELETE FROM estoque_dono WHERE garanhao LIKE %s", (f"{P}%",))
    _exec("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM dono WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM contentores WHERE codigo LIKE %s", (f"{P}%",))
    _exec("DELETE FROM user_sessions WHERE username = %s", (username,))
    _exec("DELETE FROM usuarios WHERE username = %s", (username,))


def _csv(texto: str) -> dict:
    return {"nome": "lotes.csv", "conteudo": base64.b64encode(texto.encode()).decode()}


def test_modelos(c):
    assert c.get("/api/importar/modelo", params={"formato": "csv"}).text.startswith("garanhao,")
    r = c.get("/api/importar/modelo")
    assert "spreadsheetml" in r.headers["content-type"] and r.content[:2] == b"PK"


def test_ler_valida_e_importa(c):
    s = uuid.uuid4().hex[:5]
    gar, dono, cont = f"{P}G{s}", f"{P}D{s}", f"{P}C{s}"
    # Cabeçalhos com nomes alternativos ("Palhetas", "Dono", "Contentor") e acentos.
    csv = (
        "Garanhão,Data,Palhetas,Dono,Contentor,Canister,Andar,Motilidade\n"
        f"{gar},15/03/2024,10,{dono},{cont},2,1,60\n"
        f"{gar},REF-X,5,{dono},{cont},,,\n"
    )
    linhas = c.post("/api/importar/ler", json=_csv(csv)).json()["linhas"]
    assert [l["__row"] for l in linhas] == [2, 3]
    assert linhas[0]["data_embriovet/ref"] == "15/03/2024" and linhas[0]["existencia_atual"] == "10"

    ent = c.post("/api/importar/entidades", json={"linhas": linhas}).json()
    assert ent["proprietarios"] == [dono] and ent["contentores"] == [cont]

    # Enquanto o contentor não existe, a validação acusa-o.
    v = c.post("/api/importar/validar", json={"linhas": linhas}).json()
    assert {e["erro"] for e in v["erros"]} == {"import.error.container_missing"}

    assert c.post("/api/importar/proprietario", json={"nome": dono}).status_code == 201
    assert c.post("/api/importar/contentor", json={"codigo": cont}).status_code == 201
    v = c.post("/api/importar/validar", json={"linhas": linhas}).json()
    assert v["erros"] == [] and v["validas"] == 2

    r = c.post("/api/importar/executar", json={"linhas": linhas}).json()
    assert r["importados"] == 2
    rows = _exec_all("SELECT data_embriovet, origem_externa, existencia_atual, canister, andar, data_criacao FROM estoque_dono WHERE garanhao = %s ORDER BY id", (gar,))
    # Data lida dia-primeiro; texto que não é data vai para origem_externa;
    # canister/andar vazios ficam 1/1; data_criacao = 1 jan do ano do documento.
    assert str(rows[0][0]) == "2024-03-15" and str(rows[0][5]).startswith("2024-01-01") and rows[0][3:5] == (2, 1)
    assert rows[1][1] == "REF-X" and rows[1][3:5] == (1, 1)


def _exec_all(sql, params):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def test_erros_de_validacao(c):
    s = uuid.uuid4().hex[:5]
    cont = f"{P}C{s}"
    c.post("/api/importar/contentor", json={"codigo": cont})
    linhas = [
        {"garanhao": "", "data_embriovet/ref": "2024-01-01", "existencia_atual": "3", "contentor_codigo": cont, "__row": 2},
        {"garanhao": f"{P}G", "data_embriovet/ref": "", "existencia_atual": "-1", "motilidade": "150", "contentor_codigo": cont, "andar": "3", "__row": 3},
    ]
    v = c.post("/api/importar/validar", json={"linhas": linhas}).json()
    erros = {(e["linha"], e["erro"]) for e in v["erros"]}
    assert erros == {
        (2, "import.error.garanhao_required"),
        (3, "import.error.date_required"),
        (3, "import.error.stock_positive"),
        (3, "import.error.motility_range"),
        (3, "import.error.floor_range"),
    }
    assert v["validas"] == 0
    assert c.post("/api/importar/executar", json={"linhas": linhas}).status_code == 422


def test_ficheiros_invalidos(c):
    assert c.post("/api/importar/ler", json={"nome": "x.csv", "conteudo": "%%%"}).json()["detail"]["code"] == "web.import.error.bad_file"
    assert c.post("/api/importar/ler", json={"nome": "x.pdf", "conteudo": "YWJj"}).json()["detail"]["code"] == "web.import.error.bad_type"
    r = c.post("/api/importar/ler", json=_csv("garanhao,data\nA,2024\n")).json()
    assert r["detail"]["code"] == "import.missing_columns"
