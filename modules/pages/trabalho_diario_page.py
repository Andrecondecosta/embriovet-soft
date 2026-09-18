"""Página de Trabalho diário — lista densa de tarefas de hoje (Parte 1/2).

Redesenho para volume real (~100 éguas/dia, vários veterinários em
simultâneo): o antigo calendário semanal de cartões grandes foi
substituído por uma lista densa "por fazer hoje", ordenada por
urgência, com uma barra de cobertura sempre visível no topo — a dor
principal é garantir que nenhuma égua que precisa de ser vista hoje
passa ao lado.

A Parte 2 (botão "Visto" que agenda a próxima tarefa automaticamente)
ainda não está construída — o marcar-feita continua a acontecer por
via indireta (drill-down para a ficha do animal / registo de
resultado / colheita), tal como antes.

Motor de dados inalterado: `trabalho_diario` + `dashboard_repo.py`
(`carregar_tarefas_hoje`, `carregar_resumo_tarefas_hoje`).
"""

from datetime import date

import pandas as pd
import streamlit as st

from modules.repositories.dashboard_repo import (
    carregar_resumo_tarefas_hoje,
    carregar_tarefas_hoje,
)
from modules.repositories.settings_repo import get_app_settings
from modules.ui_kit import (
    DEFAULT_PRIMARY_COLOR,
    inject_design_tokens,
    render_kpi_row,
    render_zone_title,
)


# ────────────────────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────────────────────
# Semáforo de urgência — única excepção à direção neutra+marca: risco
# fino à esquerda da linha, não uma caixa colorida. "hoje" usa um âmbar
# sóbrio (não o amarelo vivo antigo); "amanhã"/"observação" ficam
# neutros (escala de cinza), sem verde/azul.
URGENCIA_COR = {
    "urgente": "#dc2626",
    "hoje": "#b45309",
    "amanha": "#94a3b8",
    "observacao": "#cbd5e1",
}
URGENCIA_LABEL = {
    "urgente": "Urgente",
    "hoje": "Hoje",
    "amanha": "Amanhã",
    "observacao": "Observação",
}
URGENCIA_ORDEM = {"urgente": 0, "hoje": 1, "amanha": 2, "observacao": 3}

_LABEL_TIPO_TAREFA = {
    "primeira_observacao": "1ª observação",
    "verificar_ovulacao": "Verificar ovulação",
    "diagnostico_gestacao": "Diagnóstico de gestação",
    "confirmacao_gestacao": "Confirmação de gestação",
    "segunda_confirmacao": "2ª confirmação",
    "pre_parto": "Pré-parto",
    "parto_previsto": "Parto previsto",
    "colheita": "Colheita",
}

def _label_tipo(tipo: str) -> str:
    return _LABEL_TIPO_TAREFA.get(tipo, tipo or "—")


# ────────────────────────────────────────────────────────────────────────────
# Helpers DB
# ────────────────────────────────────────────────────────────────────────────
def _gerar_tarefas_primeira_observacao() -> int:
    """Cria automaticamente tarefas 'primeira_observacao' para animais em
    estadias activas que ainda não têm registo no diário clínico —
    apenas se ainda não existir uma tarefa do mesmo tipo para hoje.
    """
    from modules.db import get_connection

    sql = """
        INSERT INTO trabalho_diario (
            animal_id, estadia_id, data_tarefa, tipo,
            motivo, urgencia, criado_automaticamente
        )
        SELECT
            e.animal_id, e.id, CURRENT_DATE, 'primeira_observacao',
            '1ª observação — sem registo clínico ainda', 'hoje', TRUE
        FROM estadias e
        WHERE e.data_saida IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM diario_clinico dc
              WHERE dc.animal_id = e.animal_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM trabalho_diario td
              WHERE td.animal_id = e.animal_id
                AND td.estadia_id = e.id
                AND td.data_tarefa = CURRENT_DATE
                AND td.tipo = 'primeira_observacao'
          )
        RETURNING id
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        n = cur.rowcount
        conn.commit()
        cur.close()
        return n or 0


# ────────────────────────────────────────────────────────────────────────────
# Painéis de resultado (diagnóstico D+14/D+28/D+45) — inalterados
# ────────────────────────────────────────────────────────────────────────────
def _render_painel_resultado() -> bool:
    """Painel inline para registar o resultado de uma tarefa de
    diagnóstico (D+14/D+28/D+45). Devolve True se foi renderizado."""
    task_id = st.session_state.get("resultado_task_id")
    if not task_id:
        return False

    from modules.repositories.insemination_repo import (
        InseminacaoError,
        find_operation_por_tarefa,
        registar_resultado,
    )

    info = find_operation_por_tarefa(int(task_id))
    if info is None:
        st.warning(
            "Esta tarefa não está ligada a uma inseminação registada. "
            "Marque como concluída manualmente na ficha do animal."
        )
        if st.button("← Voltar", key="btn_res_voltar_erro"):
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()
        return True

    tipo = str(info["tipo"])
    label_etapa = {
        "diagnostico_gestacao": "1º diagnóstico (D+14)",
        "confirmacao_gestacao": "Confirmação (D+28)",
        "segunda_confirmacao": "2ª confirmação (D+45)",
    }.get(tipo, tipo)

    st.markdown(
        f"<div style='background:#fef3c7;border:1px solid #fde68a;"
        f"border-radius:12px;padding:20px;margin-bottom:16px;'>"
        f"<div style='font-size:.75rem;color:#78716c;text-transform:uppercase;"
        f"letter-spacing:.5px;font-weight:700;margin-bottom:4px;'>"
        f"Registar resultado — {label_etapa}</div>"
        f"<div style='font-size:1.35rem;font-weight:700;color:#0f172a;'>"
        f"{info['egua']} × {info['garanhao']}</div>"
        f"<div style='font-size:.85rem;color:#64748b;margin-top:2px;'>"
        f"Inseminação de {info['data_inseminacao'].strftime('%d/%m/%Y')} "
        f"· {int(info['total_palhetas'] or 0)} palhetas em "
        f"{int(info['num_lotes'] or 1)} lote(s)"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    obs = st.text_area(
        "Observações do exame",
        key=f"res_obs_{task_id}",
        placeholder="Ex.: reflexo positivo, útero vazio, presença de embrião...",
        height=90,
    )

    c1, c2, c3 = st.columns([1, 1, 0.6])
    with c1:
        clicked_pos = st.button(
            "✓ Positivo", key=f"res_pos_{task_id}",
            type="primary", width="stretch",
        )
    with c2:
        clicked_neg = st.button(
            "✗ Negativo", key=f"res_neg_{task_id}",
            width="stretch",
        )
    with c3:
        if st.button("Cancelar", key=f"res_cancel_{task_id}", width="stretch"):
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()

    if clicked_pos or clicked_neg:
        resultado = "positivo" if clicked_pos else "negativo"
        try:
            _ret = registar_resultado(
                operation_id=str(info["operation_id"]),
                resultado=resultado,
                tipo_tarefa=tipo,
                data=date.today(),
                observacoes=obs or None,
                utilizador=st.session_state.get("user", {}).get("username", "—"),
                task_id=int(task_id),
            )
        except InseminacaoError as e:
            st.error(f"❌ {e}")
            return True

        if resultado == "negativo" and tipo == "diagnostico_gestacao":
            # Guardar dados para as opções pós-negativo (repetir / encerrar)
            st.session_state["resultado_pos_neg"] = {
                "animal_id": int(info["animal_id"]),
                "estadia_id": int(info["estadia_id"]),
                "dono_id": int(info["dono_id"]),
                "egua": info["egua"],
                "garanhao": info["garanhao"],
            }
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()
        else:
            msg = "✓ Gestação confirmada — D+28 e D+45 adicionados à agenda." if resultado == "positivo" else "✗ Resultado negativo — ciclo encerrado."
            st.success(msg)
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()

    return True


def _render_painel_pos_negativo() -> bool:
    """Painel de escolha após negativo em D+14: Repetir ou Encerrar."""
    dados = st.session_state.get("resultado_pos_neg")
    if not dados:
        return False

    st.markdown(
        f"<div style='background:#fee2e2;border:1px solid #fecaca;"
        f"border-radius:12px;padding:20px;margin-bottom:16px;'>"
        f"<div style='font-size:.75rem;color:#991b1b;text-transform:uppercase;"
        f"letter-spacing:.5px;font-weight:700;margin-bottom:4px;'>"
        f"Diagnóstico negativo</div>"
        f"<div style='font-size:1.2rem;font-weight:700;color:#0f172a;'>"
        f"{dados['egua']} × {dados['garanhao']} · não gestante</div>"
        f"<div style='font-size:.85rem;color:#7f1d1d;margin-top:4px;'>"
        f"O que quer fazer a seguir?</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Repetir inseminação", key="btn_repetir_insem",
                     type="primary", width="stretch"):
            # Pré-preencher o formulário do menu de registo
            st.session_state["insem_egua_prefill"] = {
                "animal_id": dados["animal_id"],
                "estadia_id": dados["estadia_id"],
                "dono_id": dados["dono_id"],
                "nome": dados["egua"],
            }
            st.session_state["insem_show_success"] = False
            st.session_state.pop("resultado_pos_neg", None)
            # Pedido 7: Registar inseminação vive dentro do Trabalho
            # Diário — activamos o flow flag e ficamos no mesmo sítio.
            st.session_state["insem_flow_active"] = True
            st.rerun()
    with c2:
        if st.button("Encerrar ciclo", key="btn_encerrar_ciclo",
                     width="stretch"):
            st.session_state.pop("resultado_pos_neg", None)
            st.success("Ciclo encerrado — operação marcada como falhada.")
            st.rerun()

    return True


# ────────────────────────────────────────────────────────────────────────────
# Lista densa — CSS
# ────────────────────────────────────────────────────────────────────────────
_LISTA_MAX_HEIGHT_CSS = "calc(100vh - 410px)"


def _inject_lista_css() -> None:
    """CSS da lista densa — linhas de folha de cálculo (~36px), zebra
    cinza/branco, risco de urgência fino à esquerda, sem bordas
    pesadas. A lista inteira vive num `st.container(key="td-list")`
    com scroll interno (max-height + overflow-y:auto) — a barra de
    cobertura e os filtros, fora deste container, ficam sempre fixos.
    Cada linha é um `st.container(key=f"tdrow-{urgencia}-{id}")`."""
    regras_urgencia = "\n".join(
        f'div[class*="st-key-tdrow-{urgencia}-"] {{ border-left-color: {cor}; }}'
        for urgencia, cor in URGENCIA_COR.items()
    )
    st.markdown(
        f"""
        <style>
            /* Lista com scroll interno — só isto rola, cabeçalho/KPIs/
               filtros (fora deste container) ficam sempre visíveis. */
            div.st-key-td-list {{
                max-height: {_LISTA_MAX_HEIGHT_CSS};
                overflow-y: auto;
                gap: 0 !important;
                padding-right: 4px;
            }}

            /* Zebra — alternância de fundo entre linhas, sem bordas.
               :nth-child conta os wrappers directos (stLayoutWrapper)
               de cada `st.container(key=...)` dentro da lista. */
            div.st-key-td-list > div[data-testid="stLayoutWrapper"]:nth-child(even)
                > div[class*="st-key-tdrow-"] {{
                background: var(--ds-gray-50);
            }}

            div[class*="st-key-tdrow-"] {{
                border-left: 3px solid transparent;
                padding: 3px 10px 3px 12px;
            }}
            {regras_urgencia}
            /* A linha inteira é o botão — sem chrome de botão, só texto,
               numa única linha (sem quebra). A ação real fica na ficha
               do animal (a lista serve para triar e navegar, não para
               agir); hover subtil é o único indício de que é clicável. */
            div[class*="st-key-tdrow-"] button {{
                width: 100% !important;
                background: transparent !important;
                border: none !important;
                border-radius: 3px !important;
                box-shadow: none !important;
                padding: 0 8px !important;
                min-height: 30px !important;
                height: 30px !important;
                font-weight: 400 !important;
                font-size: .8rem !important;
                color: var(--ds-gray-900) !important;
                justify-content: flex-start !important;
                cursor: pointer !important;
            }}
            div[class*="st-key-tdrow-"] button:hover {{
                background: var(--ds-gray-100) !important;
                border: none !important;
                color: var(--ds-gray-900) !important;
            }}
            div[class*="st-key-tdrow-"] button:focus-visible {{
                outline: 2px solid var(--ds-gray-300) !important;
                outline-offset: -2px !important;
            }}
            /* O rótulo do botão não usa <p> nesta versão do Streamlit —
               é uma cadeia de div/span internos, cada um com o seu
               próprio justify-content:center/text-align:center. Em vez
               de perseguir classes com hash (mudam de versão para
               versão), força alinhamento à esquerda em qualquer
               descendente por tipo de elemento — robusto e idempotente. */
            div[class*="st-key-tdrow-"] button div,
            div[class*="st-key-tdrow-"] button span {{
                justify-content: flex-start !important;
                width: auto !important;
            }}
            div[class*="st-key-tdrow-"] button * {{
                text-align: left !important;
            }}
            div[class*="st-key-tdrow-"] button p,
            div[class*="st-key-tdrow-"] button span {{
                margin: 0 !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
                font-variant-numeric: tabular-nums;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────────────
# Lista densa — linha de tarefa
# ────────────────────────────────────────────────────────────────────────────
def _render_linha_tarefa(row: dict, numero: int) -> None:
    tid = int(row["tarefa_id"])
    urgencia = row.get("urgencia") or "observacao"
    urgencia_label = URGENCIA_LABEL.get(urgencia, urgencia)
    tipo_tarefa = row.get("tipo") or ""

    is_colheita = tipo_tarefa == "colheita"

    # Colheitas não têm "égua" — o animal referenciado é o garanhão.
    nome_exibido = f"Colheita — {row['animal']}" if is_colheita else (row.get("animal") or "—")
    dono_exibido = row.get("dono") or "—"
    tipo_label = _label_tipo(tipo_tarefa)

    label = (
        f":gray[{numero:>4}]  **{nome_exibido}**  ·  {dono_exibido}  ·  "
        f"{tipo_label}  ·  :gray[{urgencia_label}]"
    )

    with st.container(key=f"tdrow-{urgencia}-{tid}"):
        # Linha inteira clicável → ficha do animal (mesmo destino que o
        # antigo botão "Ver"). A lista serve só para triar e navegar;
        # registar resultados, colheitas e inseminações já têm os seus
        # próprios atalhos na ficha do animal (animal_page.py).
        if st.button(label, key=f"tdbtn-{tid}", width="stretch"):
            st.session_state["ver_animal_id"] = int(row["animal_id"])
            st.session_state["ver_animal_tab"] = 0
            st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def run_trabalho_diario_page(context: dict):
    """Trabalho diário — lista densa das tarefas de hoje (Parte 1/2)."""

    # Fluxo "Registar inseminação" (Pedido 7): quando um botão externo
    # (estadia, ficha da égua, Repetir, tarefa) activa este flag, o
    # Trabalho Diário delega para o form de inseminação. O flag é
    # limpo automaticamente pelo `insemination_page` no fim do fluxo,
    # ou por qualquer clique na sidebar (`_clear_page_state` limpa
    # tudo com prefixo `insem_`).
    if st.session_state.get("insem_flow_active"):
        from modules.pages.insemination_page import run_insemination_page
        if st.button("← Voltar ao Trabalho Diário",
                     key="btn_voltar_insem_flow"):
            st.session_state.pop("insem_flow_active", None)
            st.session_state.pop("insem_egua_prefill", None)
            st.rerun()
        run_insemination_page(context)
        return

    # Drill-down para ficha do animal
    if st.session_state.get("ver_animal_id") is not None:
        if st.button("← Voltar ao trabalho diário", key="btn_voltar_trab_diario"):
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

    # Painel de registo de resultado (D+14/D+28/D+45) — inline no topo
    if _render_painel_resultado():
        return
    if _render_painel_pos_negativo():
        return

    # Geração automática de tarefas (idempotente)
    try:
        criadas = _gerar_tarefas_primeira_observacao()
        if criadas > 0:
            st.toast(f"Criadas {criadas} tarefas automáticas de 1ª observação.", icon="🆕")
    except Exception as e:
        st.warning(f"Não foi possível gerar tarefas automáticas: {e}")

    app_settings = get_app_settings() or {}
    primary_color = app_settings.get("primary_color") or DEFAULT_PRIMARY_COLOR

    inject_design_tokens()
    _inject_lista_css()

    # Barra de cobertura — totais de HOJE, independentes dos filtros.
    try:
        resumo = carregar_resumo_tarefas_hoje()
    except Exception as e:
        st.error(f"Erro ao carregar resumo de tarefas: {e}")
        resumo = {"total": 0, "feitas": 0, "por_fazer": 0}

    por_fazer_valor = (
        f"<span style='color:{primary_color};'>{resumo['por_fazer']}</span>"
    )
    render_kpi_row([
        ("Por fazer", por_fazer_valor),
        ("Tarefas", resumo["total"]),
        ("Feitas", resumo["feitas"]),
    ])

    # Tarefas de hoje por fazer (motor existente — dashboard_repo)
    try:
        df = carregar_tarefas_hoje()
    except Exception as e:
        st.error(f"Erro ao carregar tarefas de hoje: {e}")
        df = pd.DataFrame()

    render_zone_title("Tarefas por fazer", "ds-zone-title")

    # Filtros — não alteram os totais da barra de cobertura, só a lista.
    utilizador_atual = (st.session_state.get("user") or {}).get("username")
    f1, f2 = st.columns([0.3, 0.7])
    with f1:
        minhas = st.toggle("As minhas tarefas", key="td_filtro_minhas")
    with f2:
        donos_disponiveis = (
            sorted(df["dono"].dropna().unique().tolist()) if not df.empty else []
        )
        dono_sel = st.selectbox(
            "Dono",
            ["Todos"] + donos_disponiveis,
            key="td_filtro_dono",
            label_visibility="collapsed",
        )

    df_filtrado = df
    if minhas and utilizador_atual:
        df_filtrado = df_filtrado[df_filtrado["utilizador"] == utilizador_atual]
    if dono_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["dono"] == dono_sel]

    if df_filtrado.empty:
        if df.empty:
            st.caption("Sem tarefas por fazer hoje.")
        else:
            st.caption("Sem tarefas por fazer com estes filtros.")
    else:
        df_ordenado = df_filtrado.assign(
            _ordem=df_filtrado["urgencia"].map(URGENCIA_ORDEM).fillna(9),
        ).sort_values(["_ordem", "animal"])
        with st.container(key="td-list"):
            for numero, (_, row) in enumerate(df_ordenado.iterrows(), start=1):
                _render_linha_tarefa(row.to_dict(), numero)
