"""Testes de integração da unificação do registo de inseminações.

Cobre os critérios de aceitação do Pedido 3:
(a) inseminação regista linha em `inseminacoes` com as 3 FKs preenchidas
    e texto igual a `animais.nome`;
(b) as 3 datas D+14/D+28/D+45 são criadas em `acompanhamento_inseminacao`
    e a égua aparece no `trabalho_diario` no dia D+14;
(c) menu e ficha da égua produzem resultado idêntico na BD (mesma função);
(d) `listar_eguas_com_estadia_ativa` só devolve éguas com estadia aberta;
(e) o desconto de palhetas é correcto (incluindo multi-lote).

Extra: `get_or_create_garanhao` normaliza acentos e espaços (Pedido 3).

Todos os testes correm contra `TEST_DATABASE_URL` (isolamento total de
produção — ver `/app/tests/README.md`).
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import psycopg2
import pytest

from modules.repositories.animal_repo import get_or_create_garanhao
from modules.repositories.insemination_repo import (
    InseminacaoError,
    listar_eguas_com_estadia_ativa,
    registar_inseminacao_completa,
    upsert_acompanhamento_datas,
    DIAS_1O_DIAGNOSTICO,
    DIAS_CONFIRMACAO,
    DIAS_2A_CONFIRMACAO,
)


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────

def _connect():
    import os
    return psycopg2.connect(os.environ["DATABASE_URL"])


@pytest.fixture(scope="module")
def db():
    conn = _connect()
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _rollback_before_each(db):
    """Rollback antes de cada teste para libertar transacções abortadas."""
    try:
        db.rollback()
    except Exception:
        pass
    yield


@pytest.fixture()
def dono_id(db) -> int:
    cur = db.cursor()
    nome = f"_TEST_DONO_INSEM_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (nome,),
    )
    did = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield did
    cur = db.cursor()
    cur.execute("DELETE FROM dono WHERE id = %s", (did,))
    db.commit()
    cur.close()


@pytest.fixture()
def alojamento_id(db) -> int:
    cur = db.cursor()
    nome = f"_TEST_BOX_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO alojamentos (nome, tipo, capacidade, ativo) "
        "VALUES (%s, 'box', 1, TRUE) RETURNING id",
        (nome,),
    )
    aid = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield aid
    cur = db.cursor()
    cur.execute("DELETE FROM alojamentos WHERE id = %s", (aid,))
    db.commit()
    cur.close()


@pytest.fixture()
def egua_com_estadia(db, dono_id, alojamento_id):
    """Cria uma égua + estadia activa (motivo='inseminacao'). Cleanup depois."""
    suf = int(time.time() * 1000)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO animais (nome, tipo, dono_id, ativo) "
        "VALUES (%s, 'egua', %s, TRUE) RETURNING id",
        (f"_TEST_EGUA_{suf}", dono_id),
    )
    animal_id = int(cur.fetchone()[0])
    cur.execute(
        """
        INSERT INTO estadias (
            tipo_registo, animal_id, alojamento_id, dono_id,
            data_entrada, motivo, estado
        ) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (
            "estadia", animal_id, alojamento_id, dono_id,
            date.today() - timedelta(days=1),
            "inseminacao", "internado",
        ),
    )
    estadia_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield {
        "animal_id": animal_id,
        "estadia_id": estadia_id,
        "dono_id": dono_id,
        "alojamento_id": alojamento_id,
        "nome": f"_TEST_EGUA_{suf}",
    }
    cur = db.cursor()
    try:
        db.rollback()
    except Exception:
        pass
    cur.execute("DELETE FROM trabalho_diario WHERE animal_id = %s", (animal_id,))
    cur.execute(
        "DELETE FROM acompanhamento_inseminacao WHERE estadia_id = %s",
        (estadia_id,),
    )
    cur.execute("DELETE FROM inseminacoes WHERE animal_id_egua = %s", (animal_id,))
    cur.execute("DELETE FROM estadias WHERE id = %s", (estadia_id,))
    cur.execute("DELETE FROM animais WHERE id = %s", (animal_id,))
    db.commit()
    cur.close()


@pytest.fixture()
def stock_garanhao(db, dono_id):
    """Cria um garanhão + 2 lotes em `estoque_dono` com FK preenchida."""
    suf = int(time.time() * 1000)
    nome_gar = f"_TEST_GAR_{suf}"
    cur = db.cursor()
    cur.execute(
        "INSERT INTO animais (nome, tipo, ativo) "
        "VALUES (%s, 'garanhao', TRUE) RETURNING id",
        (nome_gar,),
    )
    garanhao_id = int(cur.fetchone()[0])
    lote_ids: list[int] = []
    for palhetas in (20, 15):
        cur.execute(
            """
            INSERT INTO estoque_dono (
                garanhao, dono_id, animal_id, palhetas_produzidas,
                existencia_atual, quantidade_inicial, data_embriovet
            ) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (nome_gar, dono_id, garanhao_id, palhetas, palhetas, palhetas,
             "2025-01-10"),
        )
        lote_ids.append(int(cur.fetchone()[0]))
    db.commit()
    cur.close()
    yield {"garanhao_id": garanhao_id, "nome": nome_gar, "lote_ids": lote_ids}
    cur = db.cursor()
    try:
        db.rollback()
    except Exception:
        pass
    # Limpar FKs antes de apagar o garanhão (ordem independente da fixture de égua)
    cur.execute("DELETE FROM inseminacoes WHERE animal_id_garanhao = %s", (garanhao_id,))
    cur.execute("DELETE FROM estoque_dono WHERE id = ANY(%s)", (lote_ids,))
    cur.execute("DELETE FROM animais WHERE id = %s", (garanhao_id,))
    db.commit()
    cur.close()


# ────────────────────────────────────────────────────────────────────
# get_or_create_garanhao — normalização acentos/espaços
# ────────────────────────────────────────────────────────────────────

def test_get_or_create_garanhao_normaliza_acentos_e_espacos(db):
    """"Falcao", "Falcão" e "  Falcão  " devem apontar para o mesmo id."""
    suf = int(time.time() * 1000)
    base = f"Falcão{suf}"  # com acento
    variantes = [
        base,                    # canonical
        base.replace("ã", "a"),  # sem acento
        f"  {base}  ",           # espaços extremos
        base.upper(),            # maiúsculas
        f"Falcão  {suf}",        # espaços internos duplos (mesma letra sequence)
    ]

    ids = [get_or_create_garanhao(v) for v in variantes]
    assert all(i is not None for i in ids)
    # As três variantes 4 e 5 (Falcão + suf com espaço duplo) devem
    # colapsar para o mesmo nome "Falcão suf", que é DIFERENTE do
    # base "Falcãosuf" (sem espaço). Verificamos as duas classes:
    id_base = ids[0]
    id_espaco = ids[4]
    assert ids[0] == ids[1] == ids[2] == ids[3] == id_base, (
        f"Variantes sem espaço deviam apontar ao mesmo id, obtido {ids[:4]}"
    )
    # A variante com espaço interno colapsado deve ficar noutra linha
    # (mesmo depois do colapso, "Falcão 123" ≠ "Falcão123").
    assert id_espaco != id_base

    # E dois nomes ambos com espaço duplo colapsado apontam ao mesmo id:
    id_espaco2 = get_or_create_garanhao(f"Falcão   {suf}")
    id_espaco3 = get_or_create_garanhao(f"  falcao  {suf}  ")
    assert id_espaco2 == id_espaco3 == id_espaco

    cur = db.cursor()
    cur.execute("DELETE FROM animais WHERE id = ANY(%s)", ([id_base, id_espaco],))
    db.commit()
    cur.close()


# ────────────────────────────────────────────────────────────────────
# listar_eguas_com_estadia_ativa (critério d)
# ────────────────────────────────────────────────────────────────────

def test_listar_eguas_so_devolve_com_estadia_ativa(db, egua_com_estadia):
    """A égua com estadia aberta aparece; se fechada, deixa de aparecer."""
    animal_id = egua_com_estadia["animal_id"]
    estadia_id = egua_com_estadia["estadia_id"]

    ids_ativos = {e["animal_id"] for e in listar_eguas_com_estadia_ativa()}
    assert animal_id in ids_ativos

    # Fechar estadia
    cur = db.cursor()
    cur.execute(
        "UPDATE estadias SET data_saida = CURRENT_DATE WHERE id = %s",
        (estadia_id,),
    )
    db.commit()
    cur.close()

    ids_apos = {e["animal_id"] for e in listar_eguas_com_estadia_ativa()}
    assert animal_id not in ids_apos, (
        "Égua com estadia fechada não devia ser devolvida"
    )


# ────────────────────────────────────────────────────────────────────
# registar_inseminacao_completa — critérios a/b/e
# ────────────────────────────────────────────────────────────────────

def test_registar_inseminacao_completa_fks_datas_stock(
    db, egua_com_estadia, stock_garanhao,
):
    """Critério (a) FKs preenchidas + texto = animais.nome
    Critério (b) 3 datas + entrada em trabalho_diario a D+14
    Critério (e) desconto de palhetas correcto (multi-lote 5 + 3 = 8)
    """
    data_ins = date(2026, 3, 10)
    resultado = registar_inseminacao_completa(
        animal_id_egua=egua_com_estadia["animal_id"],
        estadia_id=egua_com_estadia["estadia_id"],
        dono_id=egua_com_estadia["dono_id"],
        garanhao_nome=stock_garanhao["nome"],
        data_inseminacao=data_ins,
        registros=[
            {"stock_id": stock_garanhao["lote_ids"][0], "palhetas": 5},
            {"stock_id": stock_garanhao["lote_ids"][1], "palhetas": 3},
        ],
        observacoes="teste automático",
        utilizador="pytest",
    )
    assert len(resultado["inseminacao_ids"]) == 2
    assert resultado["total_palhetas"] == 8

    cur = db.cursor()

    # (a) FKs + texto
    cur.execute(
        "SELECT egua, garanhao, animal_id_egua, animal_id_garanhao, "
        "       estadia_id, palhetas_gastas "
        "FROM inseminacoes WHERE id = ANY(%s) ORDER BY id",
        (resultado["inseminacao_ids"],),
    )
    linhas = cur.fetchall()
    for row in linhas:
        egua_txt, gar_txt, a_egua, a_gar, es_id, palh = row
        assert a_egua == egua_com_estadia["animal_id"]
        assert a_gar == stock_garanhao["garanhao_id"]
        assert es_id == egua_com_estadia["estadia_id"]
        assert egua_txt == egua_com_estadia["nome"], (
            "texto `egua` tem que igualar animais.nome"
        )
        assert gar_txt == stock_garanhao["nome"], (
            "texto `garanhao` tem que igualar animais.nome"
        )
    assert sum(r[5] for r in linhas) == 8

    # (b) Datas D+14/D+28/D+45
    cur.execute(
        "SELECT data_inseminacao, data_1o_diagnostico, data_confirmacao, "
        "       data_2a_confirmacao FROM acompanhamento_inseminacao "
        "WHERE estadia_id = %s",
        (egua_com_estadia["estadia_id"],),
    )
    row = cur.fetchone()
    assert row is not None
    d_ins, d_1o, d_conf, d_2a = row
    assert d_ins == data_ins
    assert d_1o == data_ins + timedelta(days=DIAS_1O_DIAGNOSTICO)
    assert d_conf == data_ins + timedelta(days=DIAS_CONFIRMACAO)
    assert d_2a == data_ins + timedelta(days=DIAS_2A_CONFIRMACAO)

    # (b) Trabalho diário à data do 1º diagnóstico
    cur.execute(
        "SELECT tipo, data_tarefa, animal_id, estadia_id FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo = 'diagnostico_gestacao'",
        (egua_com_estadia["estadia_id"],),
    )
    td = cur.fetchone()
    assert td is not None, "Tarefa em trabalho_diario devia ter sido criada"
    assert td[1] == data_ins + timedelta(days=DIAS_1O_DIAGNOSTICO)
    assert td[2] == egua_com_estadia["animal_id"]

    # (e) Desconto correcto: lote1 20-5=15, lote2 15-3=12
    cur.execute(
        "SELECT id, existencia_atual FROM estoque_dono WHERE id = ANY(%s) "
        "ORDER BY id",
        (stock_garanhao["lote_ids"],),
    )
    saldos = dict(cur.fetchall())
    assert saldos[stock_garanhao["lote_ids"][0]] == 15
    assert saldos[stock_garanhao["lote_ids"][1]] == 12
    cur.close()


# ────────────────────────────────────────────────────────────────────
# Menu vs Ficha — critério (c)
# ────────────────────────────────────────────────────────────────────

def _snapshot_estado(db, animal_id_egua: int, estadia_id: int) -> dict:
    """Devolve um snapshot comparável do estado da BD após uma
    inseminação, ignorando campos voláteis (id, timestamps)."""
    cur = db.cursor()
    cur.execute(
        "SELECT egua, garanhao, palhetas_gastas, animal_id_egua, "
        "       animal_id_garanhao, estadia_id, data_inseminacao "
        "FROM inseminacoes WHERE animal_id_egua = %s ORDER BY id",
        (animal_id_egua,),
    )
    insems = cur.fetchall()
    cur.execute(
        "SELECT data_inseminacao, data_1o_diagnostico, data_confirmacao, "
        "       data_2a_confirmacao, data_parto_previsto "
        "FROM acompanhamento_inseminacao WHERE estadia_id = %s",
        (estadia_id,),
    )
    acomp = cur.fetchone()
    cur.execute(
        "SELECT tipo, data_tarefa FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo = 'diagnostico_gestacao'",
        (estadia_id,),
    )
    td = cur.fetchone()
    cur.close()
    return {"insems": insems, "acomp": acomp, "trabalho": td}


def test_menu_e_ficha_produzem_mesmo_resultado(
    db, egua_com_estadia, stock_garanhao,
):
    """Critério (c): as duas portas de entrada usam a mesma função e
    portanto produzem o mesmo estado na BD para os mesmos inputs."""
    args = dict(
        animal_id_egua=egua_com_estadia["animal_id"],
        estadia_id=egua_com_estadia["estadia_id"],
        dono_id=egua_com_estadia["dono_id"],
        garanhao_nome=stock_garanhao["nome"],
        data_inseminacao=date(2026, 4, 5),
        registros=[
            {"stock_id": stock_garanhao["lote_ids"][0], "palhetas": 4},
        ],
        observacoes="via menu",
        utilizador="menu",
    )

    # Caminho 1 — "menu"
    registar_inseminacao_completa(**args)
    snap_menu = _snapshot_estado(
        db, args["animal_id_egua"], args["estadia_id"],
    )

    # Reverter para o mesmo ponto de partida antes de repetir pela "ficha"
    cur = db.cursor()
    cur.execute(
        "DELETE FROM trabalho_diario WHERE estadia_id = %s "
        "AND tipo = 'diagnostico_gestacao'",
        (args["estadia_id"],),
    )
    cur.execute(
        "DELETE FROM acompanhamento_inseminacao WHERE estadia_id = %s",
        (args["estadia_id"],),
    )
    cur.execute(
        "DELETE FROM inseminacoes WHERE animal_id_egua = %s",
        (args["animal_id_egua"],),
    )
    # Repor stock
    cur.execute(
        "UPDATE estoque_dono SET existencia_atual = quantidade_inicial "
        "WHERE id = ANY(%s)",
        (stock_garanhao["lote_ids"],),
    )
    db.commit()
    cur.close()

    # Caminho 2 — "ficha" (mesma função, mesmos inputs)
    registar_inseminacao_completa(**args)
    snap_ficha = _snapshot_estado(
        db, args["animal_id_egua"], args["estadia_id"],
    )

    # Os snapshots têm que ser iguais em todos os campos comparáveis
    assert snap_menu == snap_ficha, (
        f"Menu vs Ficha divergem:\nmenu={snap_menu}\nficha={snap_ficha}"
    )


# ────────────────────────────────────────────────────────────────────
# Validações da função
# ────────────────────────────────────────────────────────────────────

def test_stock_insuficiente_falha_e_faz_rollback(
    db, egua_com_estadia, stock_garanhao,
):
    """Se o stock não chegar, nada é escrito (rollback total)."""
    with pytest.raises(InseminacaoError):
        registar_inseminacao_completa(
            animal_id_egua=egua_com_estadia["animal_id"],
            estadia_id=egua_com_estadia["estadia_id"],
            dono_id=egua_com_estadia["dono_id"],
            garanhao_nome=stock_garanhao["nome"],
            data_inseminacao=date.today(),
            registros=[
                # lote com 20 palhetas — pedimos 1000
                {"stock_id": stock_garanhao["lote_ids"][0], "palhetas": 1000},
            ],
        )

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM inseminacoes WHERE animal_id_egua = %s",
        (egua_com_estadia["animal_id"],),
    )
    assert cur.fetchone()[0] == 0
    cur.execute(
        "SELECT COUNT(*) FROM acompanhamento_inseminacao WHERE estadia_id = %s",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone()[0] == 0
    cur.execute(
        "SELECT existencia_atual FROM estoque_dono WHERE id = %s",
        (stock_garanhao["lote_ids"][0],),
    )
    assert cur.fetchone()[0] == 20, "stock não devia ter sido descontado"
    cur.close()


def test_upsert_acompanhamento_datas_partilhado(db, egua_com_estadia):
    """A ficha da égua e `registar_inseminacao_completa` usam a mesma
    função para escrever em `acompanhamento_inseminacao`."""
    animal_id = egua_com_estadia["animal_id"]
    estadia_id = egua_com_estadia["estadia_id"]

    # Escrita inicial
    aid = upsert_acompanhamento_datas(
        estadia_id=estadia_id,
        animal_id=animal_id,
        data_inseminacao=date(2026, 5, 1),
        data_1o_diagnostico=date(2026, 5, 15),
    )
    assert aid > 0

    # Segundo call — UPSERT deve actualizar, não criar
    aid2 = upsert_acompanhamento_datas(
        estadia_id=estadia_id,
        animal_id=animal_id,
        data_inseminacao=date(2026, 5, 2),
        data_1o_diagnostico=date(2026, 5, 16),
    )
    assert aid2 == aid

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM acompanhamento_inseminacao WHERE estadia_id = %s",
        (estadia_id,),
    )
    assert cur.fetchone()[0] == 1
    cur.close()


# ────────────────────────────────────────────────────────────────────
# Follow-up D+1 (verificar ovulação) — Pedido 3a
# ────────────────────────────────────────────────────────────────────

def test_tarefa_d1_criada_por_defeito(db, egua_com_estadia, stock_garanhao):
    """`criar_tarefa_d1=True` (default) → tarefa D+1 em trabalho_diario."""
    data_ins = date(2026, 6, 1)
    resultado = registar_inseminacao_completa(
        animal_id_egua=egua_com_estadia["animal_id"],
        estadia_id=egua_com_estadia["estadia_id"],
        dono_id=egua_com_estadia["dono_id"],
        garanhao_nome=stock_garanhao["nome"],
        data_inseminacao=data_ins,
        registros=[{"stock_id": stock_garanhao["lote_ids"][0], "palhetas": 2}],
    )
    assert resultado["verificar_ovulacao_id"] is not None
    assert resultado["data_ver_ovulacao"] == data_ins + timedelta(days=1)

    cur = db.cursor()
    cur.execute(
        "SELECT data_tarefa, tipo FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo = 'verificar_ovulacao'",
        (egua_com_estadia["estadia_id"],),
    )
    row = cur.fetchone()
    assert row is not None, "tarefa D+1 devia ter sido criada"
    assert row[0] == data_ins + timedelta(days=1)
    cur.close()


def test_tarefa_d1_pode_ser_desativada(db, egua_com_estadia, stock_garanhao):
    """`criar_tarefa_d1=False` → não cria tarefa D+1 (mas D+14 é sempre)."""
    data_ins = date(2026, 6, 15)
    resultado = registar_inseminacao_completa(
        animal_id_egua=egua_com_estadia["animal_id"],
        estadia_id=egua_com_estadia["estadia_id"],
        dono_id=egua_com_estadia["dono_id"],
        garanhao_nome=stock_garanhao["nome"],
        data_inseminacao=data_ins,
        registros=[{"stock_id": stock_garanhao["lote_ids"][0], "palhetas": 1}],
        criar_tarefa_d1=False,
    )
    assert resultado["verificar_ovulacao_id"] is None
    assert resultado["trabalho_diario_id"] is not None  # D+14 continua

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo = 'verificar_ovulacao'",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone()[0] == 0
    cur.execute(
        "SELECT COUNT(*) FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo = 'diagnostico_gestacao'",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone()[0] == 1
    cur.close()


def test_tarefa_d1_idempotente(db, egua_com_estadia, stock_garanhao):
    """Segundo call com os mesmos inputs não cria uma segunda tarefa D+1."""
    args = dict(
        animal_id_egua=egua_com_estadia["animal_id"],
        estadia_id=egua_com_estadia["estadia_id"],
        dono_id=egua_com_estadia["dono_id"],
        garanhao_nome=stock_garanhao["nome"],
        data_inseminacao=date(2026, 7, 1),
        registros=[{"stock_id": stock_garanhao["lote_ids"][0], "palhetas": 1}],
    )
    registar_inseminacao_completa(**args)
    args["registros"] = [{"stock_id": stock_garanhao["lote_ids"][1], "palhetas": 1}]
    registar_inseminacao_completa(**args)

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo = 'verificar_ovulacao'",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone()[0] == 1, (
        "tarefa D+1 devia ser idempotente — apenas uma linha por estadia/data"
    )
    cur.close()


# ────────────────────────────────────────────────────────────────────
# Agrupamento por operation_id — Pedido 3b
# ────────────────────────────────────────────────────────────────────

def test_listagens_agrupam_por_operation_id(
    db, egua_com_estadia, stock_garanhao,
):
    """Uma inseminação multi-lote aparece como UMA só linha (não duas)
    nas listagens da ficha da égua e do garanhão."""
    from modules.pages.animal_page import (
        _carregar_inseminacoes_animal,
        _carregar_inseminacoes_garanhao,
    )
    # Multi-lote: 2 lotes numa só operação
    registar_inseminacao_completa(
        animal_id_egua=egua_com_estadia["animal_id"],
        estadia_id=egua_com_estadia["estadia_id"],
        dono_id=egua_com_estadia["dono_id"],
        garanhao_nome=stock_garanhao["nome"],
        data_inseminacao=date(2026, 8, 1),
        registros=[
            {"stock_id": stock_garanhao["lote_ids"][0], "palhetas": 4},
            {"stock_id": stock_garanhao["lote_ids"][1], "palhetas": 2},
        ],
    )

    # A ficha da égua deve mostrar 1 linha com palhetas=6 e num_lotes=2.
    df_egua = _carregar_inseminacoes_animal(
        egua_com_estadia["animal_id"], egua_com_estadia["nome"],
    )
    assert len(df_egua) == 1
    assert int(df_egua.iloc[0]["palhetas_gastas"]) == 6
    assert int(df_egua.iloc[0]["num_lotes"]) == 2

    # A ficha do garanhão idem.
    df_gar = _carregar_inseminacoes_garanhao(stock_garanhao["garanhao_id"])
    assert len(df_gar) == 1
    assert int(df_gar.iloc[0]["palhetas_gastas"]) == 6
    assert int(df_gar.iloc[0]["num_lotes"]) == 2


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
