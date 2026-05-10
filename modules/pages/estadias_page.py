"""Página de Estadias e Visitas — gestão de internamentos e visitas dos animais."""

import calendar as _calendar
from datetime import date

import pandas as pd
import streamlit as st

from modules.components.modal_animal import render_modal_animal
from modules.components.modal_proprietario import render_modal_proprietario
from modules.components.search_animal import render_search_animal
from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────────────────────
TIPOS_REGISTO = ["estadia", "visita", "externo"]
MOTIVOS = ["inseminacao", "colheita", "diagnostico", "tratamento", "embriao"]

CORES_MOTIVO = {
    "inseminacao": "#9FE1CB",
    "colheita":    "#FAC775",
    "diagnostico": "#F4C0D1",
    "tratamento":  "#B5D4F4",
    "embriao":     "#DDD6FE",
}
MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# Estados finais permitidos ao registar a saída de uma estadia.
ESTADOS_SAIDA = ["gestante", "alta", "sem_resultado", "transferido"]


def _ensure_saida_constraints() -> None:
    """Garante que `estadias.estado` aceita os estados de saída (incl. 'transferido').

    Idempotente. Mantemos os estados existentes (`internado`, `visitante`,
    `gestante`, `alta`, `sem_resultado`, `externo`) e acrescentamos
    `transferido`.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_estado_check"
            )
            cur.execute("""
                ALTER TABLE estadias
                ADD CONSTRAINT estadias_estado_check
                CHECK (estado IN (
                    'internado', 'visitante', 'gestante',
                    'alta', 'sem_resultado', 'externo', 'transferido'
                ))
            """)
            cur.execute("""
                ALTER TABLE estadias
                ADD COLUMN IF NOT EXISTS observacoes_saida TEXT
            """)
            conn.commit()
            cur.close()
    except Exception:
        pass


def _registar_saida_estadia(
    estadia_id: int, data_saida, estado_final: str, observacoes: str | None,
) -> None:
    sql = """
        UPDATE estadias
           SET data_saida = %s,
               estado = %s,
               observacoes_saida = %s
         WHERE id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            sql,
            (data_saida, estado_final, (observacoes or None), int(estadia_id)),
        )
        conn.commit()
        cur.close()


# ────────────────────────────────────────────────────────────────────────────
# Helpers de acesso à BD
# ────────────────────────────────────────────────────────────────────────────
def _carregar_estadias(apenas_activas: bool) -> pd.DataFrame:
    """Carrega estadias activas (data_saida IS NULL) ou encerradas."""
    where = "e.data_saida IS NULL" if apenas_activas else "e.data_saida IS NOT NULL"
    sql = f"""
        SELECT
            e.id,
            e.animal_id,
            a.nome                                       AS animal,
            e.tipo_registo                               AS tipo,
            d.nome                                       AS proprietario,
            e.motivo,
            e.estado,
            e.data_entrada,
            e.data_saida,
            EXTRACT(DAY FROM (NOW() - e.data_entrada))::int AS dias_internado
        FROM estadias e
        JOIN animais a ON a.id = e.animal_id
        JOIN dono    d ON d.id = e.dono_id
        WHERE {where}
        ORDER BY e.data_entrada DESC, e.id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _carregar_animal_detalhe(animal_id: int) -> dict:
    sql = """
        SELECT a.id, a.nome, a.tipo, a.dono_id, d.nome AS proprietario
        FROM animais a
        LEFT JOIN dono d ON d.id = a.dono_id
        WHERE a.id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id,))
        row = cur.fetchone()
        cur.close()
    if not row:
        return {}
    return {
        "id": int(row[0]),
        "nome": row[1],
        "tipo": row[2],
        "dono_id": row[3],
        "proprietario": row[4],
    }


def _carregar_donos() -> pd.DataFrame:
    sql = "SELECT id, nome FROM dono WHERE ativo = TRUE ORDER BY LOWER(nome)"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _carregar_alojamentos() -> pd.DataFrame:
    sql = (
        "SELECT id, nome, tipo, capacidade FROM alojamentos "
        "WHERE ativo = TRUE ORDER BY tipo, LOWER(nome)"
    )
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _has_animais_resultados(termo: str) -> bool:
    """Devolve True se houver pelo menos um animal cujo nome contém `termo`.

    Mantido como utilitário interno; pode ser usado por validações futuras.
    """
    sql = (
        "SELECT 1 FROM animais "
        "WHERE ativo = TRUE AND LOWER(nome) LIKE LOWER(%s) LIMIT 1"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (f"%{termo.strip()}%",))
        existe = cur.fetchone() is not None
        cur.close()
    return existe


def _ensure_externo_constraints() -> None:
    """Garante que `estadias.estado` e `estadias.tipo_registo` aceitam 'externo'."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_estado_check"
            )
            cur.execute("""
                ALTER TABLE estadias
                ADD CONSTRAINT estadias_estado_check
                CHECK (estado IN (
                    'internado', 'visitante', 'gestante',
                    'alta', 'sem_resultado', 'externo'
                ))
            """)
            cur.execute(
                "ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_tipo_registo_check"
            )
            cur.execute("""
                ALTER TABLE estadias
                ADD CONSTRAINT estadias_tipo_registo_check
                CHECK (tipo_registo IN ('estadia', 'visita', 'externo'))
            """)
            conn.commit()
            cur.close()
    except Exception:
        pass


def _criar_estadia_apenas(payload: dict) -> int:
    """Insere uma nova linha em `estadias` (sem criar animal). Devolve o id."""
    sql = """
        INSERT INTO estadias (
            tipo_registo, animal_id, alojamento_id, dono_id,
            data_entrada, data_saida, motivo, estado,
            observacoes_entrada
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING id
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            sql,
            (
                payload["tipo_registo"],
                int(payload["animal_id"]),
                payload.get("alojamento_id"),
                int(payload["dono_id"]),
                payload["data_entrada"],
                payload.get("data_saida"),
                payload["motivo"],
                payload["estado"],
                payload.get("observacoes_entrada"),
            ),
        )
        new_id = int(cur.fetchone()[0])
        conn.commit()
        cur.close()
    return new_id


# ────────────────────────────────────────────────────────────────────────────
# Helpers do diálogo
# ────────────────────────────────────────────────────────────────────────────
def _on_animal_for_estadia(animal_id: int, animal_nome: str, estadia_id: int) -> None:
    """Callback usado por `render_modal_animal` quando aberto a partir do
    fluxo "+ Nova estadia / visita" → "+ Criar novo animal"."""
    st.session_state.update({
        "animal_criado_para_estadia": {
            "id": int(animal_id),
            "nome": animal_nome,
            "estadia_id": int(estadia_id),
        },
        "reabrir_modal_nova_estadia": True,
    })
    st.rerun()


def _limpar_estado_modal_nova_estadia() -> None:
    """Limpa todo o session_state usado pelo diálogo, para começar limpo na
    próxima abertura."""
    for k in (
        "estadia_animal_search_termo",
        "estadia_animal_search_selected",
        "estadia_animal_search_select",
        "estadia_animal_search_last_pick",
        "estadia_animal_search_last_auto",
        "estadia_animal_search_open_modal",
        "ne_tipo_reg",
        "ne_motivo",
        "ne_dono",
        "ne_dt_ent",
        "ne_aloj",
        "ne_aloj_v",
        "ne_dt_saida",
        "ne_obs",
        "animal_criado_para_estadia",
    ):
        st.session_state.pop(k, None)


# ────────────────────────────────────────────────────────────────────────────
# Diálogo "Nova estadia / visita"
# ────────────────────────────────────────────────────────────────────────────
def _render_modal_nova_estadia() -> None:
    @st.dialog("Nova estadia / visita", width="large")
    def _modal() -> None:
        # Pré-preencher animal se acabámos de regressar do fluxo "+ Criar novo animal"
        recem = st.session_state.pop("animal_criado_para_estadia", None)
        if recem:
            det = _carregar_animal_detalhe(int(recem["id"]))
            st.session_state["estadia_animal_search_selected"] = {
                "id": int(recem["id"]),
                "nome": recem["nome"],
                "proprietario": det.get("proprietario"),
            }
            st.session_state["estadia_animal_search_termo"] = recem["nome"]

        # Antes de renderizar a pesquisa, descarta qualquer selecção stale
        # (ex.: utilizador escreveu novo termo que não devolve o animal já
        # seleccionado) — assim o "+ Criar novo animal" só aparece quando faz
        # mesmo sentido.
        termo_atual = (st.session_state.get("estadia_animal_search_termo") or "").strip()
        sel_atual = st.session_state.get("estadia_animal_search_selected") or {}
        nome_sel = (sel_atual.get("nome") or "").lower()
        if (
            len(termo_atual) >= 2
            and termo_atual.lower() not in nome_sel
        ):
            st.session_state.pop("estadia_animal_search_selected", None)
            st.session_state.pop("estadia_animal_search_last_pick", None)
            st.session_state.pop("estadia_animal_search_last_auto", None)

        # Pesquisa de animal + botão "+" condicional
        col_search, col_plus = st.columns([6, 1])
        with col_search:
            animal = render_search_animal(
                key="estadia_animal_search",
                label="Animal *",
            )

        with col_plus:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button(
                "➕ Criar",
                key="ne_btn_criar_animal",
                help="Criar novo animal",
                width="stretch",
            ):
                st.session_state["abrir_modal_animal_para_estadia"] = True
                st.rerun()

        if not animal:
            st.caption("Pesquise um animal pelo nome ou crie um novo.")
            return

        det = _carregar_animal_detalhe(int(animal["id"]))

        st.markdown("---")

        # Inicializar defaults dos widgets antes de renderizar (evita avisos)
        if "ne_dt_ent" not in st.session_state:
            st.session_state["ne_dt_ent"] = date.today()
        if "ne_dt_saida" not in st.session_state:
            st.session_state["ne_dt_saida"] = None

        c1, c2 = st.columns(2)
        with c1:
            tipo_registo = st.selectbox(
                "Tipo de registo",
                TIPOS_REGISTO,
                key="ne_tipo_reg",
                format_func=lambda x: {
                    "estadia": "Estadia — fica internada no centro",
                    "visita": "Visita — vem no dia e vai embora",
                    "externo": "Externo — não vem ao centro / sémen enviado",
                }.get(x, x.capitalize()),
            )
            motivo_label = (
                "Motivo (opcional)"
                if tipo_registo == "externo"
                else "Motivo"
            )
            motivo = st.selectbox(
                motivo_label,
                MOTIVOS,
                key="ne_motivo",
                format_func=lambda x: {
                    "inseminacao": "Inseminação",
                    "colheita": "Colheita",
                    "diagnostico": "Diagnóstico",
                    "tratamento": "Tratamento",
                    "embriao": "Embrião",
                }.get(x, x.capitalize()),
            )

        with c2:
            donos_df = _carregar_donos()
            default_dono_id = det.get("dono_id")
            dono_options = [None] + donos_df["id"].tolist()
            if (
                "ne_dono" not in st.session_state
                and default_dono_id in dono_options
            ):
                st.session_state["ne_dono"] = default_dono_id

            def _fmt_dono(did):
                if did is None:
                    return "— Selecionar proprietário —"
                row = donos_df.loc[donos_df["id"] == did]
                return str(row.iloc[0]["nome"]) if not row.empty else f"#{did}"

            dono_id = st.selectbox(
                "Proprietário *",
                dono_options,
                format_func=_fmt_dono,
                key="ne_dono",
            )

            dt_label = (
                "Data do serviço / envio"
                if tipo_registo == "externo"
                else "Data de entrada"
            )
            data_entrada = st.date_input(
                dt_label, key="ne_dt_ent", format="DD/MM/YYYY",
            )

        # Alojamento — só aparece para estadia (obrigatório) e visita (opcional)
        alojamento_id = None
        if tipo_registo in ("estadia", "visita"):
            alojamentos_df = _carregar_alojamentos()
            if alojamentos_df.empty:
                if tipo_registo == "estadia":
                    st.warning(
                        "Não existem alojamentos activos. Crie um em "
                        "Definições → Alojamentos.",
                    )
            else:
                aloj_options = [None] + alojamentos_df["id"].tolist()

                def _fmt_aloj(aid):
                    if aid is None:
                        return "— Selecionar alojamento —"
                    row = alojamentos_df.loc[alojamentos_df["id"] == aid]
                    if row.empty:
                        return f"#{aid}"
                    r = row.iloc[0]
                    return f"{r['nome']} ({r['tipo']})"

                alojamento_id = st.selectbox(
                    (
                        "Alojamento *"
                        if tipo_registo == "estadia"
                        else "Alojamento (opcional)"
                    ),
                    aloj_options,
                    format_func=_fmt_aloj,
                    key="ne_aloj",
                )

        # Data prevista de saída — não aparece para externo
        data_saida = None
        if tipo_registo != "externo":
            data_saida = st.date_input(
                "Data prevista de saída",
                key="ne_dt_saida",
                format="DD/MM/YYYY",
            )

        observacoes = st.text_area(
            "Observações", key="ne_obs", height=80,
        )

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1:
            cancelar = st.button(
                "Cancelar", key="ne_btn_cancelar", width="stretch",
            )
        with b2:
            guardar = st.button(
                "Guardar", type="primary", key="ne_btn_guardar", width="stretch",
            )

        if cancelar:
            _limpar_estado_modal_nova_estadia()
            st.rerun()

        if not guardar:
            return

        # Validações
        if not dono_id:
            st.error("Selecione o proprietário.")
            return
        if tipo_registo == "estadia" and not alojamento_id:
            st.error("O alojamento é obrigatório quando o tipo é 'estadia'.")
            return

        if tipo_registo == "externo":
            _ensure_externo_constraints()
            estado = "externo"
        elif tipo_registo == "estadia":
            estado = "internado"
        else:
            estado = "visitante"

        payload = {
            "tipo_registo": tipo_registo,
            "animal_id": int(animal["id"]),
            "alojamento_id": alojamento_id,
            "dono_id": int(dono_id),
            "data_entrada": data_entrada,
            "data_saida": data_saida,
            "motivo": motivo,
            "estado": estado,
            "observacoes_entrada": (observacoes or "").strip() or None,
        }

        try:
            estadia_id = _criar_estadia_apenas(payload)
        except Exception as exc:
            st.error(f"Erro ao guardar: {exc}")
            return

        st.session_state["ultima_estadia_criada"] = estadia_id
        st.session_state["ultimo_animal_criado"] = int(animal["id"])
        _limpar_estado_modal_nova_estadia()
        st.success("Estadia/visita registada.")
        st.rerun()

    _modal()


# ────────────────────────────────────────────────────────────────────────────
# Calendário visual de ocupação mensal
# ────────────────────────────────────────────────────────────────────────────
def _target_year_month(offset: int) -> tuple[int, int]:
    today = date.today()
    y, m = today.year, today.month + offset
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


def _carregar_estadias_mes(primeiro: date, ultimo: date) -> pd.DataFrame:
    sql = """
        SELECT
            e.id, e.animal_id, e.alojamento_id,
            a.nome AS animal_nome,
            d.nome AS proprietario_nome,
            e.data_entrada, e.data_saida, e.motivo, e.tipo_registo
        FROM estadias e
        JOIN animais   a  ON a.id  = e.animal_id
        JOIN dono      d  ON d.id  = e.dono_id
        JOIN alojamentos al ON al.id = e.alojamento_id
        WHERE e.tipo_registo = 'estadia'
          AND e.alojamento_id IS NOT NULL
          AND e.data_entrada <= %s
          AND (e.data_saida IS NULL OR e.data_saida >= %s)
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(ultimo, primeiro))


def _contar_ocupados_em(d: date) -> int:
    sql = """
        SELECT COUNT(DISTINCT alojamento_id)
        FROM estadias
        WHERE tipo_registo = 'estadia'
          AND alojamento_id IS NOT NULL
          AND data_entrada <= %s
          AND (data_saida IS NULL OR data_saida >= %s)
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (d, d))
        n = int(cur.fetchone()[0] or 0)
        cur.close()
        return n


def _render_tab_calendario() -> None:
    """Calendário visual mensal — linhas = alojamentos, colunas = dias."""
    # ── Drill-down via query-param (clique nos blocos) ───────────────────
    try:
        qp = st.query_params
        if "ver_animal_cal" in qp:
            raw = qp.get("ver_animal_cal")
            try:
                aid = int(raw if isinstance(raw, str) else raw[0])
                st.session_state["ver_animal_id"] = aid
                st.session_state["ver_animal_tab"] = 0
            except (TypeError, ValueError):
                pass
            del qp["ver_animal_cal"]
            st.rerun()
    except Exception:
        pass

    if "calendario_offset" not in st.session_state:
        st.session_state["calendario_offset"] = 0

    offset = int(st.session_state["calendario_offset"])
    target_y, target_m = _target_year_month(offset)
    primeiro = date(target_y, target_m, 1)
    _, last_d = _calendar.monthrange(target_y, target_m)
    ultimo = date(target_y, target_m, last_d)
    today = date.today()

    # ── Navegação ────────────────────────────────────────────────────────
    c_prev, c_title, c_next = st.columns([1, 2, 1])
    with c_prev:
        if st.button("◀ Mês anterior", key="cal_btn_prev", width="stretch"):
            st.session_state["calendario_offset"] = offset - 1
            st.rerun()
    with c_title:
        st.markdown(
            f"<h3 style='text-align:center;margin:6px 0;color:#0f172a;"
            f"font-weight:700;'>{MESES_PT[target_m - 1]} {target_y}</h3>",
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button("Mês seguinte ▶", key="cal_btn_next", width="stretch"):
            st.session_state["calendario_offset"] = offset + 1
            st.rerun()

    # ── Carregar dados ───────────────────────────────────────────────────
    alojamentos = _carregar_alojamentos()
    if alojamentos.empty:
        st.info("Sem alojamentos activos. Crie um em Definições → Alojamentos.")
        return

    df_est = _carregar_estadias_mes(primeiro, ultimo)

    # ── Pré-computar ocupação (aloj_id, dia) → estadia ───────────────────
    # Construímos PRIMEIRO o mapa de ocupação para que a taxa de ocupação
    # seja calculada com pares únicos (aloj_id, dia) — evita ultrapassar
    # 100% se houver sobreposição de estadias no mesmo alojamento.
    occ: dict[tuple[int, int], dict] = {}
    aloj_ids_validos = {int(a) for a in alojamentos["id"].tolist()}
    for _, r in df_est.iterrows():
        aloj_id = int(r["alojamento_id"])
        if aloj_id not in aloj_ids_validos:
            continue
        de_d = pd.to_datetime(r["data_entrada"]).date()
        ds = (
            pd.to_datetime(r["data_saida"]).date()
            if pd.notna(r["data_saida"]) else ultimo
        )
        for d_num in range(1, last_d + 1):
            cur_day = date(target_y, target_m, d_num)
            if de_d <= cur_day <= ds:
                # Mantém a estadia mais recente para esse par (aloj_id, dia)
                # — em caso de sobreposição, prevalece a última do iter
                occ[(aloj_id, d_num)] = {
                    "animal_id": int(r["animal_id"]),
                    "animal_nome": r["animal_nome"] or "",
                    "proprietario": r["proprietario_nome"] or "",
                    "motivo": r["motivo"] or "",
                }

    # ── KPIs ─────────────────────────────────────────────────────────────
    total_aloj = len(alojamentos)
    ocupados_hoje = _contar_ocupados_em(today)
    livres_hoje = max(total_aloj - ocupados_hoje, 0)

    total_dias_aloj = total_aloj * last_d
    dias_ocupados = len(occ)  # pares únicos (aloj_id, dia)
    taxa = (dias_ocupados / total_dias_aloj * 100) if total_dias_aloj > 0 else 0.0
    taxa = min(taxa, 100.0)  # safety: nunca passa de 100%

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total alojamentos", total_aloj)
    k2.metric("Ocupados hoje", ocupados_hoje)
    k3.metric("Livres hoje", livres_hoje)
    k4.metric("Taxa de ocupação (mês)", f"{taxa:.0f}%")

    st.markdown(
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:8px 0 12px;'>",
        unsafe_allow_html=True,
    )

    # ── Construir HTML da grelha ─────────────────────────────────────────
    header_cells = []
    for d_num in range(1, last_d + 1):
        is_today = (target_y, target_m, d_num) == (today.year, today.month, today.day)
        bg = "#DBEAFE" if is_today else "#F8FAFC"
        color = "#1E40AF" if is_today else "#64748B"
        header_cells.append(
            f"<th style='padding:4px 6px;font-size:10px;text-align:center;"
            f"background:{bg};color:{color};border:1px solid #E2E8F0;"
            f"font-weight:700;min-width:30px;'>{d_num}</th>"
        )

    rows_html = []
    for _, aloj in alojamentos.iterrows():
        aloj_id = int(aloj["id"])
        aloj_label = f"{aloj['nome']}"
        cells = []
        for d_num in range(1, last_d + 1):
            entry = occ.get((aloj_id, d_num))
            if entry:
                cor = CORES_MOTIVO.get(entry["motivo"], "#E2E8F0")
                nome_trunc = entry["animal_nome"][:8] if entry["animal_nome"] else ""
                title = (
                    f"{entry['animal_nome']} ({entry['proprietario']})"
                    f" — {entry['motivo']}"
                ).replace('"', "'")
                cells.append(
                    f"<td style='padding:0;border:1px solid #E2E8F0;'>"
                    f"<a href='?ver_animal_cal={entry['animal_id']}' "
                    f"target='_self' "
                    f"style='display:block;background:{cor};padding:6px 4px;"
                    f"font-size:10px;color:#1E293B;text-decoration:none;"
                    f"text-align:center;font-weight:600;white-space:nowrap;"
                    f"overflow:hidden;text-overflow:ellipsis;cursor:pointer;' "
                    f"title=\"{title}\">{nome_trunc}</a></td>"
                )
            else:
                cells.append(
                    "<td style='background:white;border:1px solid #E2E8F0;"
                    "padding:6px 4px;min-width:30px;'>&nbsp;</td>"
                )
        rows_html.append(
            f"<tr><th style='text-align:left;padding:4px 10px;"
            f"border:1px solid #E2E8F0;background:#F8FAFC;font-size:11px;"
            f"font-weight:600;color:#1E293B;white-space:nowrap;"
            f"position:sticky;left:0;z-index:1;'>{aloj_label}</th>"
            f"{''.join(cells)}</tr>"
        )

    grid_html = f"""
    <div style='overflow-x:auto;border:1px solid #E2E8F0;border-radius:6px;
                background:white;'>
      <table style='border-collapse:collapse;font-family:inherit;width:100%;'>
        <thead>
          <tr>
            <th style='text-align:left;padding:6px 10px;background:#F8FAFC;
                       border:1px solid #E2E8F0;font-size:10px;color:#64748B;
                       font-weight:700;text-transform:uppercase;
                       letter-spacing:.5px;position:sticky;left:0;z-index:2;'>
              Alojamento
            </th>
            {''.join(header_cells)}
          </tr>
        </thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    """
    st.markdown(grid_html, unsafe_allow_html=True)

    # ── Legenda ──────────────────────────────────────────────────────────
    legenda_items = " · ".join(
        f"<span style='display:inline-block;width:11px;height:11px;"
        f"background:{cor};border:1px solid #E2E8F0;border-radius:2px;"
        f"vertical-align:middle;margin-right:5px;'></span>{m.capitalize()}"
        for m, cor in CORES_MOTIVO.items()
    )
    st.markdown(
        f"<div style='margin-top:12px;font-size:11px;color:#64748B;'>"
        f"<b style='color:#1E293B;'>Legenda:</b> {legenda_items}</div>",
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────────────
# Lista de estadias
# ────────────────────────────────────────────────────────────────────────────
def _render_lista_estadias(df: pd.DataFrame, apenas_activas: bool, key_prefix: str) -> None:
    """Renderiza a lista de estadias com botão 'Ver ficha' em cada linha."""
    if df.empty:
        st.info(
            "Sem estadias ou visitas activas." if apenas_activas
            else "Sem estadias encerradas."
        )
        return

    if apenas_activas:
        col_w = [1.8, 0.9, 1.7, 1.3, 1.2, 0.9, 1.2, 1.4]
        headers = [
            "Animal", "Tipo", "Proprietário", "Motivo", "Estado",
            "Dias", "", "",
        ]
    else:
        col_w = [1.8, 1, 1.8, 1.4, 1.3, 1, 1.2, 1.2]
        headers = [
            "Animal", "Tipo", "Proprietário", "Motivo", "Estado",
            "Dias", "Data saída", "",
        ]

    head_cols = st.columns(col_w)
    for i, h in enumerate(headers):
        head_cols[i].markdown(
            f"<div style='font-size:.7rem;color:#94a3b8;text-transform:uppercase;"
            f"letter-spacing:.5px;font-weight:700;'>{h}</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:4px 0 8px;'>",
        unsafe_allow_html=True,
    )

    for _, row in df.iterrows():
        cols = st.columns(col_w)
        cols[0].write(row["animal"])
        cols[1].write(row["tipo"])
        cols[2].write(row["proprietario"])
        cols[3].write(row["motivo"])
        cols[4].write(row["estado"])
        cols[5].write(
            str(int(row["dias_internado"])) if pd.notna(row["dias_internado"]) else "—"
        )

        estadia_id = int(row["id"])
        if apenas_activas:
            with cols[6]:
                if st.button(
                    "Ver ficha",
                    key=f"{key_prefix}_ver_{estadia_id}",
                    width="stretch",
                ):
                    st.session_state["ver_animal_id"] = int(row["animal_id"])
                    st.session_state["ver_animal_tab"] = 0
                    st.rerun()
            with cols[7]:
                if st.button(
                    "Registar saída",
                    key=f"{key_prefix}_saida_{estadia_id}",
                    type="primary",
                    width="stretch",
                ):
                    st.session_state["abrir_modal_saida_id"] = estadia_id
                    st.session_state["abrir_modal_saida_animal"] = row["animal"]
                    st.rerun()
        else:
            data_saida = row.get("data_saida")
            cols[6].write(
                data_saida.strftime("%d/%m/%Y") if pd.notna(data_saida) else "—"
            )
            with cols[7]:
                if st.button(
                    "Ver ficha",
                    key=f"{key_prefix}_ver_{estadia_id}",
                    width="stretch",
                ):
                    st.session_state["ver_animal_id"] = int(row["animal_id"])
                    st.session_state["ver_animal_tab"] = 0
                    st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# Diálogo "Registar saída"
# ────────────────────────────────────────────────────────────────────────────
def _render_modal_saida(estadia_id: int, animal_label: str | None) -> None:
    @st.dialog("Registar saída")
    def _modal() -> None:
        st.markdown(
            f"<div style='color:#475569;font-size:.85rem;margin-bottom:8px;'>"
            f"Encerra a estadia activa de "
            f"<b>{animal_label or '—'}</b> (ID #{estadia_id}).</div>",
            unsafe_allow_html=True,
        )

        if "ms_data_saida" not in st.session_state:
            st.session_state["ms_data_saida"] = date.today()

        c1, c2 = st.columns(2)
        with c1:
            data_saida = st.date_input(
                "Data de saída",
                key="ms_data_saida",
                format="DD/MM/YYYY",
            )
        with c2:
            estado_final = st.selectbox(
                "Estado final",
                ESTADOS_SAIDA,
                key="ms_estado",
                format_func=lambda x: {
                    "gestante": "Gestante",
                    "alta": "Alta",
                    "sem_resultado": "Outro",
                    "transferido": "Transferido",
                }.get(x, x.capitalize()),
            )

        observacoes = st.text_area(
            "Observações de saída"
            + (" *" if estado_final == "sem_resultado" else ""),
            key="ms_obs",
            height=80,
            help=(
                "Obrigatório quando o estado final é 'Outro'."
                if estado_final == "sem_resultado" else None
            ),
        )

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1:
            cancelar = st.button(
                "Cancelar", key="ms_btn_cancel", width="stretch",
            )
        with b2:
            guardar = st.button(
                "Guardar saída", type="primary",
                key="ms_btn_save", width="stretch",
            )

        if cancelar:
            for k in ("ms_data_saida", "ms_estado", "ms_obs"):
                st.session_state.pop(k, None)
            st.rerun()

        if not guardar:
            return

        # Quando o estado final é 'Outro' (sem_resultado), as observações
        # passam a ser obrigatórias.
        if (
            estado_final == "sem_resultado"
            and not (observacoes or "").strip()
        ):
            st.warning("Por favor descreva o motivo nas observações")
            return

        _ensure_saida_constraints()
        try:
            _registar_saida_estadia(
                estadia_id, data_saida, estado_final,
                (observacoes or "").strip(),
            )
        except Exception as exc:
            st.error(f"Erro ao registar saída: {exc}")
            return

        for k in ("ms_data_saida", "ms_estado", "ms_obs"):
            st.session_state.pop(k, None)
        st.success("Saída registada com sucesso.")
        st.rerun()

    _modal()


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def run_estadias_page(context: dict):
    """Página de Estadias e Visitas."""

    # ── Orquestração de modais (Streamlit não permite diálogos aninhados) ───
    if st.session_state.get("abrir_modal_prop_standalone"):
        del st.session_state["abrir_modal_prop_standalone"]
        render_modal_proprietario(
            key="modal_prop_standalone",
            on_success=lambda dono_id, dono_nome: (
                st.session_state.update({
                    "novo_prop_id": dono_id,
                    "novo_prop_nome": dono_nome,
                    "reabrir_modal_animal": True,
                }),
                st.rerun(),
            ),
        )

    if st.session_state.get("abrir_modal_animal_para_estadia"):
        del st.session_state["abrir_modal_animal_para_estadia"]
        render_modal_animal(
            key="modal_animal_from_estadia",
            tipo_default="egua",
            on_success=_on_animal_for_estadia,
        )

    if st.session_state.get("reabrir_modal_animal"):
        del st.session_state["reabrir_modal_animal"]
        render_modal_animal(
            key="modal_animal_from_estadia",
            tipo_default="egua",
            on_success=_on_animal_for_estadia,
        )

    if (
        st.session_state.get("abrir_modal_nova_estadia")
        or st.session_state.get("reabrir_modal_nova_estadia")
    ):
        st.session_state.pop("abrir_modal_nova_estadia", None)
        st.session_state.pop("reabrir_modal_nova_estadia", None)
        _render_modal_nova_estadia()

    if st.session_state.get("abrir_modal_saida_id"):
        eid = int(st.session_state.pop("abrir_modal_saida_id"))
        animal_label = st.session_state.pop("abrir_modal_saida_animal", None)
        _render_modal_saida(eid, animal_label)

    # ── Drill-down para ficha do animal ─────────────────────────────────────
    if st.session_state.get("ver_animal_id") is not None:
        if st.button("← Voltar às estadias", key="btn_voltar_estadias"):
            st.session_state.pop("ver_animal_id", None)
            st.session_state.pop("ver_animal_tab", None)
            st.rerun()
        from modules.pages.animal_page import run_animal_page
        run_animal_page(
            st.session_state["ver_animal_id"],
            context,
            st.session_state.get("ver_animal_tab", 0),
        )
        return

    # Cabeçalho com botão à direita
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown("## Estadias e Visitas")
    with col_btn:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        if st.button(
            "+ Nova estadia / visita", type="primary", width="stretch",
        ):
            _limpar_estado_modal_nova_estadia()
            st.session_state["abrir_modal_nova_estadia"] = True
            st.rerun()

    # Tabs (ordem pedida: Calendário → Activas → Encerradas)
    tab_calendario, tab_activas, tab_encerradas = st.tabs(
        ["Calendário", "Activas", "Encerradas"]
    )

    with tab_calendario:
        _render_tab_calendario()

    with tab_activas:
        df = _carregar_estadias(apenas_activas=True)
        _render_lista_estadias(df, apenas_activas=True, key_prefix="act")

    with tab_encerradas:
        df = _carregar_estadias(apenas_activas=False)
        _render_lista_estadias(df, apenas_activas=False, key_prefix="enc")
