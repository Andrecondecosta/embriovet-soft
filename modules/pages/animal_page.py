"""Página de detalhe de um animal — Resumo, Diário clínico, Historial reprodutivo, Estadias."""

from datetime import date, datetime

import pandas as pd
import streamlit as st

from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Helpers de acesso à BD
# ────────────────────────────────────────────────────────────────────────────
def _carregar_animal(animal_id: int) -> dict | None:
    sql = """
        SELECT id, nome, tipo, raca, data_nascimento, numero_registo, dono_id,
               pelagem, altura, peso, pai, mae, avo_paterno, avo_materno,
               chip, observacoes, is_receptora, ativo
        FROM animais
        WHERE id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            return None
        cols = [d[0] for d in cur.description]
        cur.close()
        return dict(zip(cols, row))


def _atualizar_animal(animal_id: int, dados: dict) -> bool:
    sql = """
        UPDATE animais SET
            nome = %(nome)s,
            tipo = %(tipo)s,
            raca = %(raca)s,
            data_nascimento = %(data_nascimento)s,
            numero_registo = %(numero_registo)s,
            pelagem = %(pelagem)s,
            altura = %(altura)s,
            peso = %(peso)s,
            chip = %(chip)s,
            pai = %(pai)s,
            mae = %(mae)s,
            avo_paterno = %(avo_paterno)s,
            avo_materno = %(avo_materno)s,
            observacoes = %(observacoes)s,
            is_receptora = %(is_receptora)s,
            updated_at = NOW()
        WHERE id = %(id)s
    """
    dados = {**dados, "id": animal_id}
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, dados)
        conn.commit()
        cur.close()
    return True


def _carregar_estadias_do_animal(animal_id: int) -> pd.DataFrame:
    sql = """
        SELECT
            e.tipo_registo,
            e.motivo,
            e.estado,
            e.data_entrada,
            e.data_saida,
            EXTRACT(
                DAY FROM (COALESCE(e.data_saida::timestamp, NOW()) - e.data_entrada)
            )::int AS dias
        FROM estadias e
        WHERE e.animal_id = %s
        ORDER BY e.data_entrada DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(animal_id,))


# ── Diário clínico ─────────────────────────────────────────────────────────
def _obter_estadia_activa(animal_id: int) -> int | None:
    sql = """
        SELECT id FROM estadias
        WHERE animal_id = %s AND data_saida IS NULL
        ORDER BY data_entrada DESC
        LIMIT 1
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id,))
        row = cur.fetchone()
        cur.close()
        return int(row[0]) if row else None


def _carregar_diario_clinico(animal_id: int) -> pd.DataFrame:
    sql = """
        SELECT id, data_registo, foliculo_mm, edema_grau, fluido_uterino,
               comportamento, temperatura, tratamentos, proxima_observacao,
               observacoes
        FROM diario_clinico
        WHERE animal_id = %s
        ORDER BY data_registo DESC, id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(animal_id,))


def _atualizar_diario_clinico(registo_id: int, dados: dict) -> bool:
    sql = """
        UPDATE diario_clinico SET
            data_registo = %(data_registo)s,
            foliculo_mm = %(foliculo_mm)s,
            edema_grau = %(edema_grau)s,
            fluido_uterino = %(fluido_uterino)s,
            comportamento = %(comportamento)s,
            temperatura = %(temperatura)s,
            tratamentos = %(tratamentos)s,
            proxima_observacao = %(proxima_observacao)s,
            observacoes = %(observacoes)s
        WHERE id = %(id)s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, {**dados, "id": registo_id})
        conn.commit()
        cur.close()
    return True


def _apagar_diario_clinico(registo_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM diario_clinico WHERE id = %s", (registo_id,))
        conn.commit()
        cur.close()
    return True


def _inserir_diario_clinico(dados: dict) -> int | None:
    sql = """
        INSERT INTO diario_clinico (
            animal_id, estadia_id, data_registo, foliculo_mm, edema_grau,
            fluido_uterino, comportamento, temperatura, tratamentos,
            proxima_observacao, observacoes, utilizador
        ) VALUES (
            %(animal_id)s, %(estadia_id)s, %(data_registo)s, %(foliculo_mm)s,
            %(edema_grau)s, %(fluido_uterino)s, %(comportamento)s,
            %(temperatura)s, %(tratamentos)s, %(proxima_observacao)s,
            %(observacoes)s, %(utilizador)s
        ) RETURNING id
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, dados)
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return new_id


def _criar_tarefa_proxima_observacao(
    animal_id: int, estadia_id: int, data_proxima: date, utilizador: str | None
) -> None:
    """Cria automaticamente uma tarefa em trabalho_diario para a próxima
    observação. Urgência: 'hoje' se for amanhã, 'observacao' se for mais
    tarde. Se a data for hoje ou no passado, não cria."""
    hoje = date.today()
    if data_proxima <= hoje:
        return
    urgencia = "hoje" if (data_proxima - hoje).days == 1 else "observacao"
    sql = """
        INSERT INTO trabalho_diario (
            animal_id, estadia_id, data_tarefa, tipo, motivo,
            urgencia, criado_automaticamente, utilizador
        ) VALUES (
            %s, %s, %s, 'observacao_clinica',
            'Observação clínica agendada', %s, TRUE, %s
        )
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id, estadia_id, data_proxima, urgencia, (utilizador or "")[:50]))
        conn.commit()
        cur.close()


def _concluir_tarefas_animal_hoje(animal_id: int) -> int:
    """Marca como concluídas todas as tarefas pendentes do animal para hoje.
    Devolve o número de tarefas concluídas."""
    sql = """
        UPDATE trabalho_diario
        SET concluida = TRUE,
            data_conclusao = CURRENT_DATE,
            observacoes_conclusao = 'Concluído via registo clínico'
        WHERE animal_id = %s
          AND data_tarefa = CURRENT_DATE
          AND concluida = FALSE
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id,))
        n = cur.rowcount
        conn.commit()
        cur.close()
        return n or 0


def _inserir_tarefa_acompanhamento(
    animal_id: int, estadia_id: int, data_proxima: date, utilizador: str | None
) -> None:
    """Insere uma tarefa de acompanhamento clínico em trabalho_diario para
    a data indicada, com `criado_automaticamente=FALSE` (decisão manual do
    veterinário). Urgência: 'hoje' se for amanhã, 'observacao' se for mais
    tarde. Se a data for hoje ou no passado, não cria."""
    hoje = date.today()
    if not data_proxima or data_proxima <= hoje:
        return
    urgencia = "hoje" if (data_proxima - hoje).days == 1 else "observacao"
    sql = """
        INSERT INTO trabalho_diario (
            animal_id, estadia_id, data_tarefa, tipo, motivo,
            urgencia, criado_automaticamente, utilizador
        ) VALUES (
            %s, %s, %s, 'observacao_clinica',
            'Acompanhamento clínico agendado', %s, FALSE, %s
        )
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id, estadia_id, data_proxima, urgencia, (utilizador or "")[:50]))
        conn.commit()
        cur.close()


# ────────────────────────────────────────────────────────────────────────────
# Tab Diário clínico
# ────────────────────────────────────────────────────────────────────────────
EDEMA_OPTS = [
    (0, "0 — sem edema"),
    (1, "1 — ligeiro"),
    (2, "2 — moderado"),
    (3, "3 — severo"),
]
COMPORTAMENTOS = ["cio_ativo", "sem_cio", "anestro", "pos_ovulacao"]


# ── Historial reprodutivo ──────────────────────────────────────────────────
def _carregar_inseminacoes_animal(animal_id: int, animal_nome: str) -> pd.DataFrame:
    """Histórico completo de inseminações da égua, com proprietário e resultado
    (do acompanhamento da estadia que abrange a data, se existir)."""
    sql = """
        SELECT
            i.data_inseminacao,
            i.garanhao,
            d.nome           AS proprietario,
            i.palhetas_gastas,
            COALESCE(ai.resultado, 'pendente') AS resultado,
            i.observacoes
        FROM inseminacoes i
        LEFT JOIN dono d ON d.id = i.dono_id
        LEFT JOIN estadias e
               ON e.animal_id = %s
              AND e.motivo = 'inseminacao'
              AND i.data_inseminacao BETWEEN e.data_entrada
                                         AND COALESCE(e.data_saida, CURRENT_DATE)
        LEFT JOIN acompanhamento_inseminacao ai ON ai.estadia_id = e.id
        WHERE LOWER(i.egua) = LOWER(%s)
        ORDER BY i.data_inseminacao DESC, i.id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(animal_id, animal_nome))


def _kpis_inseminacoes(df: pd.DataFrame) -> tuple[int, int, str]:
    total = len(df)
    if total == 0:
        return 0, 0, "—"
    gestacoes = int((df["resultado"] == "gestacao_confirmada").sum())
    taxa = (gestacoes / total) * 100
    return total, gestacoes, f"{taxa:.0f} %"


RESULTADO_BADGE = {
    "pendente":             ("Pendente",    "#475569", "#e2e8f0"),
    "gestacao_confirmada":  ("Gestação ✓",  "#15803d", "#dcfce7"),
    "falhou":               ("Falhou",      "#b91c1c", "#fee2e2"),
}


def _badge_resultado(resultado: str) -> str:
    label, fg, bg = RESULTADO_BADGE.get(
        resultado, (str(resultado or "—"), "#475569", "#e2e8f0"),
    )
    return (
        f"<span style='display:inline-block;padding:2px 9px;border-radius:999px;"
        f"background:{bg};color:{fg};font-size:.7rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.4px;'>{label}</span>"
    )


def _render_tab_historial_reprodutivo(animal: dict) -> None:
    df_ins = _carregar_inseminacoes_animal(animal["id"], animal.get("nome") or "")

    total, gestacoes, taxa = _kpis_inseminacoes(df_ins)
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Total inseminações", total)
    with k2:
        st.metric("Gestações confirmadas", gestacoes)
    with k3:
        st.metric("Taxa de sucesso", taxa)

    st.markdown("---")

    if df_ins.empty:
        st.info("Sem inseminações registadas para este animal.")
    else:
        # Cabeçalho da tabela
        cols_w = [1.0, 1.4, 1.6, 0.8, 1.2, 2.0]
        headers = ["Data", "Garanhão", "Proprietário", "Palhetas",
                   "Resultado", "Observações"]
        head_cols = st.columns(cols_w)
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

        for _, row in df_ins.iterrows():
            cols = st.columns(cols_w)
            dt = row["data_inseminacao"]
            cols[0].write(dt.strftime("%d/%m/%Y") if pd.notna(dt) else "—")
            cols[1].write(row["garanhao"] or "—")
            cols[2].write(row["proprietario"] or "—")
            cols[3].write(int(row["palhetas_gastas"]) if pd.notna(row["palhetas_gastas"]) else "—")
            cols[4].markdown(_badge_resultado(row["resultado"]), unsafe_allow_html=True)
            obs = row["observacoes"] or "—"
            obs_short = obs if len(obs) <= 60 else obs[:59] + "…"
            cols[5].write(obs_short)

    # ── Estadias anteriores ────────────────────────────────────────────────
    st.markdown("##### Estadias anteriores")
    df_est = _carregar_estadias_do_animal(animal["id"])
    if df_est.empty:
        st.info("Sem estadias registadas.")
        return

    view = df_est.rename(columns={
        "tipo_registo": "Tipo registo",
        "motivo": "Motivo",
        "estado": "Estado",
        "data_entrada": "Data entrada",
        "data_saida": "Data saída",
        "dias": "Dias estadia",
    })
    st.dataframe(view, width="stretch", hide_index=True)


def _render_form_novo_registo(animal_id: int) -> None:
    estadia_id = _obter_estadia_activa(animal_id)
    if estadia_id is None:
        st.warning(
            "Não existe nenhuma estadia activa para este animal. "
            "Crie uma estadia antes de registar observações clínicas."
        )
        return

    with st.form(f"form_diario_{animal_id}", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            data_registo = st.date_input("Data do registo", value=date.today())
            foliculo_mm = st.number_input(
                "Folículo (mm)", min_value=0, max_value=99, value=0, step=1,
            )
        with c2:
            edema_grau_label = st.selectbox(
                "Edema",
                options=[lbl for _, lbl in EDEMA_OPTS],
            )
            edema_grau = next(v for v, lbl in EDEMA_OPTS if lbl == edema_grau_label)
            comportamento = st.selectbox("Comportamento", options=COMPORTAMENTOS)
        with c3:
            temperatura = st.number_input(
                "Temperatura (°C)", min_value=0.0, max_value=45.0, value=0.0, step=0.1,
                format="%.1f",
            )
            fluido_uterino = st.checkbox("Fluido uterino")

        proxima_observacao = st.date_input(
            "Próxima observação (opcional)",
            value=None,
            help="Se preenchida, cria automaticamente uma tarefa no Trabalho diário.",
        )
        tratamentos = st.text_area(
            "Tratamentos (opcional)",
            placeholder="Lista livre de tratamentos aplicados…",
        )
        observacoes = st.text_area("Observações (opcional)")

        b1, b2 = st.columns(2)
        with b1:
            guardar = st.form_submit_button("Guardar", type="primary", width="stretch")
        with b2:
            cancelar = st.form_submit_button("Cancelar", width="stretch")

        if cancelar:
            st.session_state[f"diario_novo_{animal_id}"] = False
            st.rerun()

        if guardar:
            utilizador = (st.session_state.get("user") or {}).get("username") or ""
            try:
                _inserir_diario_clinico({
                    "animal_id": animal_id,
                    "estadia_id": estadia_id,
                    "data_registo": data_registo,
                    "foliculo_mm": int(foliculo_mm) if foliculo_mm else None,
                    "edema_grau": int(edema_grau),
                    "fluido_uterino": bool(fluido_uterino),
                    "comportamento": comportamento,
                    "temperatura": float(temperatura) if temperatura else None,
                    "tratamentos": tratamentos.strip() or None,
                    "proxima_observacao": proxima_observacao or None,
                    "observacoes": observacoes.strip() or None,
                    "utilizador": utilizador[:50],
                })

                # 1) Concluir tarefas pendentes do animal para hoje
                tarefas_concluidas = 0
                try:
                    tarefas_concluidas = _concluir_tarefas_animal_hoje(animal_id)
                except Exception as e:
                    st.warning(f"Registo guardado, mas falha ao concluir tarefas: {e}")

                # 2) Criar tarefa de acompanhamento se foi indicada próxima observação
                if proxima_observacao:
                    try:
                        _inserir_tarefa_acompanhamento(
                            animal_id, estadia_id, proxima_observacao, utilizador,
                        )
                    except Exception as e:
                        st.warning(f"Registo guardado, mas falha ao criar tarefa: {e}")

                # 3) Toast de confirmação
                if tarefas_concluidas > 0:
                    st.toast(
                        "✓ Registo guardado — tarefa concluída na agenda",
                        icon="✅",
                    )
                else:
                    st.toast("✓ Registo guardado", icon="✅")

                st.session_state[f"diario_novo_{animal_id}"] = False
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao guardar: {e}")


def _render_form_editar_diario(registo: dict) -> None:
    """Form inline para editar um registo do diário clínico."""
    rid = int(registo["id"])
    with st.form(f"form_edit_diario_{rid}"):
        st.markdown("##### Editar registo")
        c1, c2, c3 = st.columns(3)
        with c1:
            data_registo = st.date_input(
                "Data do registo",
                value=registo.get("data_registo") or date.today(),
                key=f"ed_data_{rid}",
            )
            foliculo_mm = st.number_input(
                "Folículo (mm)", min_value=0, max_value=99, step=1,
                value=int(registo.get("foliculo_mm") or 0),
                key=f"ed_folic_{rid}",
            )
        with c2:
            cur_edema = registo.get("edema_grau")
            edema_idx = next(
                (i for i, (v, _) in enumerate(EDEMA_OPTS) if v == (cur_edema if cur_edema is not None else 0)),
                0,
            )
            edema_grau_label = st.selectbox(
                "Edema",
                options=[lbl for _, lbl in EDEMA_OPTS],
                index=edema_idx,
                key=f"ed_edema_{rid}",
            )
            edema_grau = next(v for v, lbl in EDEMA_OPTS if lbl == edema_grau_label)
            cur_comp = registo.get("comportamento") or COMPORTAMENTOS[0]
            comp_idx = COMPORTAMENTOS.index(cur_comp) if cur_comp in COMPORTAMENTOS else 0
            comportamento = st.selectbox(
                "Comportamento", options=COMPORTAMENTOS, index=comp_idx,
                key=f"ed_comp_{rid}",
            )
        with c3:
            temperatura = st.number_input(
                "Temperatura (°C)", min_value=0.0, max_value=45.0, step=0.1,
                format="%.1f",
                value=float(registo.get("temperatura") or 0),
                key=f"ed_temp_{rid}",
            )
            fluido_uterino = st.checkbox(
                "Fluido uterino",
                value=bool(registo.get("fluido_uterino")),
                key=f"ed_fluido_{rid}",
            )

        proxima_observacao = st.date_input(
            "Próxima observação (opcional)",
            value=registo.get("proxima_observacao") or None,
            key=f"ed_prox_{rid}",
        )
        tratamentos = st.text_area(
            "Tratamentos (opcional)",
            value=registo.get("tratamentos") or "",
            key=f"ed_trat_{rid}",
        )
        observacoes = st.text_area(
            "Observações (opcional)",
            value=registo.get("observacoes") or "",
            key=f"ed_obs_{rid}",
        )

        b1, b2 = st.columns(2)
        with b1:
            guardar = st.form_submit_button(
                "Guardar alterações", type="primary", width="stretch",
            )
        with b2:
            cancelar = st.form_submit_button("Cancelar", width="stretch")

        if cancelar:
            st.session_state[f"diario_edit_{rid}"] = False
            st.rerun()

        if guardar:
            try:
                _atualizar_diario_clinico(rid, {
                    "data_registo": data_registo,
                    "foliculo_mm": int(foliculo_mm) if foliculo_mm else None,
                    "edema_grau": int(edema_grau),
                    "fluido_uterino": bool(fluido_uterino),
                    "comportamento": comportamento,
                    "temperatura": float(temperatura) if temperatura else None,
                    "tratamentos": tratamentos.strip() or None,
                    "proxima_observacao": proxima_observacao or None,
                    "observacoes": observacoes.strip() or None,
                })
                st.session_state[f"diario_edit_{rid}"] = False
                st.success("Registo atualizado.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")


def _render_tab_diario_clinico(animal_id: int) -> None:
    novo_key = f"diario_novo_{animal_id}"
    aberto = st.session_state.get(novo_key, False)

    label = "Fechar registo" if aberto else "+ Registo de hoje"
    if st.button(label, key=f"btn_{novo_key}", type="primary"):
        st.session_state[novo_key] = not aberto
        st.rerun()

    if aberto:
        with st.container(border=True):
            _render_form_novo_registo(animal_id)
        st.markdown("---")

    df = _carregar_diario_clinico(animal_id)
    if df.empty:
        st.info("Sem registos clínicos para este animal.")
        return

    # Cabeçalho da lista
    cols_w = [1.0, 0.8, 0.8, 0.7, 1.2, 1.4, 1.0, 1.4, 0.85, 0.85]
    headers = [
        "Data", "Folículo", "Edema", "Fluido", "Comportamento",
        "Tratamentos", "Próxima obs.", "Observações", "", "",
    ]
    head_cols = st.columns(cols_w)
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
        rid = int(row["id"])
        edit_key = f"diario_edit_{rid}"
        del_confirm_key = f"diario_del_confirm_{rid}"

        cols = st.columns(cols_w)
        cols[0].write(row["data_registo"].strftime("%d/%m/%Y") if pd.notna(row["data_registo"]) else "—")
        cols[1].write("—" if pd.isna(row["foliculo_mm"]) else int(row["foliculo_mm"]))
        cols[2].write("—" if pd.isna(row["edema_grau"]) else int(row["edema_grau"]))
        cols[3].write("Sim" if bool(row["fluido_uterino"]) else "Não")
        cols[4].write(row["comportamento"] or "—")
        trat_txt = (row["tratamentos"] or "—")
        cols[5].write(trat_txt[:40] + ("…" if len(trat_txt) > 40 else ""))
        prox = row["proxima_observacao"]
        cols[6].write(prox.strftime("%d/%m/%Y") if pd.notna(prox) else "—")
        obs_txt = (row["observacoes"] or "—")
        cols[7].write(obs_txt[:40] + ("…" if len(obs_txt) > 40 else ""))

        with cols[8]:
            if st.button("Editar", key=f"btn_dc_edit_{rid}", width="stretch"):
                st.session_state[edit_key] = True
                # Fecha qualquer confirmação de apagar pendente
                st.session_state[del_confirm_key] = False
                st.rerun()

        with cols[9]:
            if st.button("Apagar", key=f"btn_dc_del_{rid}", width="stretch"):
                st.session_state[del_confirm_key] = True
                st.session_state[edit_key] = False
                st.rerun()

        # Confirmação de apagar (linha-a-linha)
        if st.session_state.get(del_confirm_key, False):
            st.warning(
                f"Tem a certeza que pretende apagar o registo de "
                f"{row['data_registo'].strftime('%d/%m/%Y') if pd.notna(row['data_registo']) else '?'}? "
                "Esta operação não pode ser desfeita."
            )
            cb1, cb2, _ = st.columns([1, 1, 6])
            with cb1:
                if st.button("Confirmar apagar", key=f"btn_dc_confirm_del_{rid}", type="primary", width="stretch"):
                    try:
                        _apagar_diario_clinico(rid)
                        st.session_state[del_confirm_key] = False
                        st.success("Registo apagado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao apagar: {e}")
            with cb2:
                if st.button("Cancelar", key=f"btn_dc_cancel_del_{rid}", width="stretch"):
                    st.session_state[del_confirm_key] = False
                    st.rerun()

        # Form de edição inline
        if st.session_state.get(edit_key, False):
            with st.container(border=True):
                _render_form_editar_diario(row.to_dict())

        st.markdown(
            "<hr style='border:none;border-top:1px dashed #e2e8f0;margin:6px 0 10px;'>",
            unsafe_allow_html=True,
        )


# ────────────────────────────────────────────────────────────────────────────
# Helpers de apresentação
# ────────────────────────────────────────────────────────────────────────────
TIPOS_ANIMAL = ["egua", "garanhao", "receptora"]


def _calcular_idade(data_nasc) -> str:
    if not data_nasc:
        return "—"
    if isinstance(data_nasc, datetime):
        data_nasc = data_nasc.date()
    hoje = date.today()
    anos = hoje.year - data_nasc.year - ((hoje.month, hoje.day) < (data_nasc.month, data_nasc.day))
    if anos < 1:
        meses = (hoje.year - data_nasc.year) * 12 + hoje.month - data_nasc.month
        if hoje.day < data_nasc.day:
            meses -= 1
        return f"{max(meses, 0)} meses"
    return f"{anos} ano" + ("s" if anos != 1 else "")


def _campo(label: str, valor) -> None:
    """Renderiza um par label/valor em formato compacto."""
    txt = "—" if valor is None or (isinstance(valor, str) and not valor.strip()) else str(valor)
    st.markdown(
        f"<div style='margin-bottom:8px;'>"
        f"<div style='font-size:.7rem;color:#94a3b8;text-transform:uppercase;"
        f"letter-spacing:.5px;font-weight:600;'>{label}</div>"
        f"<div style='font-size:.95rem;color:#0f172a;font-weight:500;'>{txt}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────────────
# Tab Resumo + form de edição
# ────────────────────────────────────────────────────────────────────────────
def _render_form_editar(animal: dict) -> None:
    with st.form(f"form_editar_animal_{animal['id']}"):
        st.markdown("#### Editar ficha")

        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome", value=animal.get("nome") or "")
            tipo_idx = TIPOS_ANIMAL.index(animal.get("tipo")) if animal.get("tipo") in TIPOS_ANIMAL else 0
            tipo = st.selectbox("Tipo", options=TIPOS_ANIMAL, index=tipo_idx)
            raca = st.text_input("Raça", value=animal.get("raca") or "")
            pelagem = st.text_input("Pelagem", value=animal.get("pelagem") or "")
            altura = st.number_input(
                "Altura (cm)", min_value=0.0, max_value=999.9, step=0.1,
                value=float(animal.get("altura") or 0),
            )
            peso = st.number_input(
                "Peso (kg)", min_value=0.0, max_value=99999.9, step=0.1,
                value=float(animal.get("peso") or 0),
            )
        with c2:
            chip = st.text_input("Chip", value=animal.get("chip") or "")
            numero_registo = st.text_input("Número de registo", value=animal.get("numero_registo") or "")
            data_nascimento = st.date_input(
                "Data de nascimento",
                value=animal.get("data_nascimento") or None,
            )
            is_receptora = st.checkbox("É receptora", value=bool(animal.get("is_receptora")))

        st.markdown("##### Pedigree")
        c3, c4 = st.columns(2)
        with c3:
            pai = st.text_input("Pai", value=animal.get("pai") or "")
            avo_paterno = st.text_input("Avô paterno", value=animal.get("avo_paterno") or "")
        with c4:
            mae = st.text_input("Mãe", value=animal.get("mae") or "")
            avo_materno = st.text_input("Avô materno", value=animal.get("avo_materno") or "")

        observacoes = st.text_area("Observações", value=animal.get("observacoes") or "")

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            guardar = st.form_submit_button("Guardar alterações", type="primary", width="stretch")
        with bcol2:
            cancelar = st.form_submit_button("Cancelar", width="stretch")

        if cancelar:
            st.session_state[f"animal_edit_{animal['id']}"] = False
            st.rerun()

        if guardar:
            if not nome.strip():
                st.error("O nome é obrigatório.")
                return
            try:
                _atualizar_animal(animal["id"], {
                    "nome": nome.strip(),
                    "tipo": tipo,
                    "raca": raca.strip() or None,
                    "data_nascimento": data_nascimento,
                    "numero_registo": numero_registo.strip() or None,
                    "pelagem": pelagem.strip() or None,
                    "altura": float(altura) if altura else None,
                    "peso": float(peso) if peso else None,
                    "chip": chip.strip() or None,
                    "pai": pai.strip() or None,
                    "mae": mae.strip() or None,
                    "avo_paterno": avo_paterno.strip() or None,
                    "avo_materno": avo_materno.strip() or None,
                    "observacoes": observacoes.strip() or None,
                    "is_receptora": bool(is_receptora),
                })
                st.success("Ficha atualizada.")
                st.session_state[f"animal_edit_{animal['id']}"] = False
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")


def _render_tab_resumo(animal: dict) -> None:
    edit_key = f"animal_edit_{animal['id']}"

    if st.session_state.get(edit_key, False):
        _render_form_editar(animal)
        return

    # Cabeçalho com botão de edição
    col_head, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("Editar ficha", key=f"btn_edit_{animal['id']}", type="primary", width="stretch"):
            st.session_state[edit_key] = True
            st.rerun()

    # Grupo Identificação
    st.markdown("#### Identificação")
    g1, g2, g3 = st.columns(3)
    with g1:
        _campo("Nome", animal.get("nome"))
        _campo("Tipo", animal.get("tipo"))
        _campo("Raça", animal.get("raca"))
    with g2:
        _campo("Pelagem", animal.get("pelagem"))
        altura = animal.get("altura")
        peso = animal.get("peso")
        _campo("Altura (cm)", f"{altura}" if altura is not None else None)
        _campo("Peso (kg)", f"{peso}" if peso is not None else None)
    with g3:
        _campo("Chip", animal.get("chip"))
        _campo("Número de registo", animal.get("numero_registo"))
        dn = animal.get("data_nascimento")
        dn_txt = dn.strftime("%d/%m/%Y") if dn else "—"
        _campo("Data nascimento", f"{dn_txt} ({_calcular_idade(dn)})" if dn else "—")

    st.markdown("---")

    # Grupo Pedigree
    st.markdown("#### Pedigree")
    p1, p2 = st.columns(2)
    with p1:
        _campo("Pai", animal.get("pai"))
        _campo("Avô paterno", animal.get("avo_paterno"))
    with p2:
        _campo("Mãe", animal.get("mae"))
        _campo("Avô materno", animal.get("avo_materno"))


# ────────────────────────────────────────────────────────────────────────────
# Tab Estadias
# ────────────────────────────────────────────────────────────────────────────
def _render_tab_estadias(animal_id: int) -> None:
    df = _carregar_estadias_do_animal(animal_id)
    if df.empty:
        st.info("Sem estadias registadas para este animal.")
    else:
        view = df.rename(columns={
            "tipo_registo": "Tipo registo",
            "motivo": "Motivo",
            "estado": "Estado",
            "data_entrada": "Data entrada",
            "data_saida": "Data saída",
            "dias": "Dias",
        })
        st.dataframe(view, width="stretch", hide_index=True)

    # Secção de acompanhamento pós-inseminação (apenas se houver estadia
    # activa com motivo='inseminacao')
    estadia = _obter_estadia_activa_inseminacao(animal_id)
    if estadia is not None:
        st.markdown("---")
        _render_seccao_acompanhamento(animal_id, estadia)


# ────────────────────────────────────────────────────────────────────────────
# Acompanhamento pós-inseminação
# ────────────────────────────────────────────────────────────────────────────
def _obter_estadia_activa_inseminacao(animal_id: int) -> dict | None:
    sql = """
        SELECT id, garanhao, data_entrada
        FROM estadias
        WHERE animal_id = %s
          AND data_saida IS NULL
          AND motivo = 'inseminacao'
        ORDER BY data_entrada DESC
        LIMIT 1
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return {"id": int(row[0]), "garanhao": row[1], "data_entrada": row[2]}


def _obter_acompanhamento(estadia_id: int) -> dict | None:
    sql = """
        SELECT id, data_inseminacao, data_1o_diagnostico, data_confirmacao,
               data_2a_confirmacao, data_parto_previsto, resultado
        FROM acompanhamento_inseminacao
        WHERE estadia_id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (estadia_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            return None
        cols = [d[0] for d in cur.description]
        cur.close()
        return dict(zip(cols, row))


def _upsert_acompanhamento(animal_id: int, estadia_id: int, dados: dict) -> None:
    """Delega para a implementação partilhada em `insemination_repo` —
    garante que a lógica de UPSERT em `acompanhamento_inseminacao` é única
    e usada por menu + ficha da égua."""
    from modules.repositories.insemination_repo import (
        upsert_acompanhamento_datas,
    )
    upsert_acompanhamento_datas(
        estadia_id=estadia_id,
        animal_id=animal_id,
        data_inseminacao=dados.get("data_inseminacao"),
        data_1o_diagnostico=dados.get("data_1o_diagnostico"),
        data_confirmacao=dados.get("data_confirmacao"),
        data_2a_confirmacao=dados.get("data_2a_confirmacao"),
        data_parto_previsto=dados.get("data_parto_previsto"),
    )


def _atualizar_garanhao_estadia(estadia_id: int, garanhao: str | None) -> None:
    sql = "UPDATE estadias SET garanhao = %s, updated_at = NOW() WHERE id = %s"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (garanhao, estadia_id))
        conn.commit()
        cur.close()


def _render_timeline_acompanhamento(acomp: dict) -> None:
    """Renderiza as datas guardadas como timeline visual."""
    etapas = [
        ("Inseminação",         acomp.get("data_inseminacao"),    "#2563eb"),
        ("1º diagnóstico",      acomp.get("data_1o_diagnostico"), "#7c3aed"),
        ("Confirmação",         acomp.get("data_confirmacao"),    "#16a34a"),
        ("2ª confirmação",      acomp.get("data_2a_confirmacao"), "#0891b2"),
        ("Parto previsto",      acomp.get("data_parto_previsto"), "#dc2626"),
    ]

    html_items = []
    for label, dt, cor in etapas:
        ativo = dt is not None
        bg = cor if ativo else "#e2e8f0"
        text_color = "#ffffff" if ativo else "#94a3b8"
        dt_txt = dt.strftime("%d/%m/%Y") if dt else "—"
        html_items.append(
            f"<div style='flex:1;text-align:center;'>"
            f"<div style='width:32px;height:32px;border-radius:50%;background:{bg};"
            f"color:{text_color};display:inline-flex;align-items:center;"
            f"justify-content:center;font-size:.85rem;font-weight:700;"
            f"margin-bottom:6px;'>{'✓' if ativo else '·'}</div>"
            f"<div style='font-size:.7rem;color:#64748b;text-transform:uppercase;"
            f"letter-spacing:.4px;font-weight:600;'>{label}</div>"
            f"<div style='font-size:.85rem;color:#0f172a;font-weight:600;margin-top:2px;'>"
            f"{dt_txt}</div>"
            f"</div>"
        )
    linha = (
        "<div style='display:flex;align-items:flex-start;gap:8px;"
        "padding:12px 4px;'>"
        + "".join(html_items)
        + "</div>"
    )
    st.markdown(linha, unsafe_allow_html=True)


def _render_seccao_acompanhamento(animal_id: int, estadia: dict) -> None:
    estadia_id = estadia["id"]
    acomp = _obter_acompanhamento(estadia_id) or {}

    st.subheader("Acompanhamento pós-inseminação")
    st.caption(f"Estadia activa de inseminação · entrada {estadia['data_entrada'].strftime('%d/%m/%Y') if estadia.get('data_entrada') else '—'}")

    with st.form(f"form_acomp_{estadia_id}"):
        garanhao = st.text_input(
            "Garanhão",
            value=estadia.get("garanhao") or "",
            key=f"acomp_garanhao_{estadia_id}",
        )

        c1, c2 = st.columns(2)
        with c1:
            data_inseminacao = st.date_input(
                "Quando foi inseminada",
                value=acomp.get("data_inseminacao") or None,
                key=f"acomp_data_insem_{estadia_id}",
            )
            data_1o_diagnostico = st.date_input(
                "1º diagnóstico gestação",
                value=acomp.get("data_1o_diagnostico") or None,
                key=f"acomp_1o_{estadia_id}",
            )
            data_confirmacao = st.date_input(
                "Confirmação gestação",
                value=acomp.get("data_confirmacao") or None,
                key=f"acomp_conf_{estadia_id}",
            )
        with c2:
            data_2a_confirmacao = st.date_input(
                "2ª confirmação",
                value=acomp.get("data_2a_confirmacao") or None,
                key=f"acomp_2a_{estadia_id}",
            )
            data_parto_previsto = st.date_input(
                "Parto previsto",
                value=acomp.get("data_parto_previsto") or None,
                key=f"acomp_parto_{estadia_id}",
            )

        guardar = st.form_submit_button(
            "Guardar acompanhamento", type="primary", width="stretch",
        )

        if guardar:
            try:
                _atualizar_garanhao_estadia(estadia_id, (garanhao or "").strip() or None)
                _upsert_acompanhamento(animal_id, estadia_id, {
                    "data_inseminacao":    data_inseminacao or None,
                    "data_1o_diagnostico": data_1o_diagnostico or None,
                    "data_confirmacao":    data_confirmacao or None,
                    "data_2a_confirmacao": data_2a_confirmacao or None,
                    "data_parto_previsto": data_parto_previsto or None,
                })
                st.success("Acompanhamento guardado.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao guardar: {e}")

    # Timeline com os valores guardados (após reload)
    acomp_atual = _obter_acompanhamento(estadia_id)
    if acomp_atual:
        st.markdown("##### Timeline")
        _render_timeline_acompanhamento(acomp_atual)


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────
# Tabs específicas para tipo='garanhao'
# ────────────────────────────────────────────────────────────────────────────
def _carregar_stock_garanhao(animal_id: int) -> pd.DataFrame:
    """Lotes de sémen deste garanhão — matching por FK (`ed.animal_id`).

    Requer que a migration 023/024 tenha sincronizado `estoque_dono.animal_id`
    e que a 025 tenha eliminado duplicados em `animais`.
    """
    sql = """
        SELECT
            ed.data_embriovet         AS data_producao,
            d.nome                    AS proprietario,
            ed.palhetas_produzidas    AS palhetas_iniciais,
            ed.existencia_atual       AS palhetas_restantes,
            ed.motilidade,
            ed.concentracao,
            ed.qualidade,
            c.codigo                  AS contentor,
            ed.canister,
            ed.andar,
            ed.origem_externa
        FROM estoque_dono ed
        LEFT JOIN dono d        ON d.id = ed.dono_id
        LEFT JOIN contentores c ON c.id = ed.contentor_id
        WHERE ed.animal_id = %s
        ORDER BY ed.data_embriovet DESC, ed.id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(int(animal_id),))


def _kpis_stock_garanhao(df: pd.DataFrame) -> tuple[int, int, str, int, int]:
    if df.empty:
        return 0, 0, "—", 0, 0
    palh = df["palhetas_restantes"].fillna(0)
    total_palh = int(palh.sum())
    lotes_act = int((palh > 0).sum())
    motil_validas = df.loc[palh > 0, "motilidade"].dropna()
    motil_avg = f"{motil_validas.mean():.0f} %" if len(motil_validas) else "—"
    origem = df.get("origem_externa", pd.Series([None] * len(df))).fillna("").astype(str).str.strip()
    mask_externo = origem != ""
    palh_internas = int(palh.where(~mask_externo, 0).sum())
    palh_externas = int(palh.where(mask_externo, 0).sum())
    return total_palh, lotes_act, motil_avg, palh_internas, palh_externas


def _carregar_inseminacoes_garanhao(animal_id: int) -> pd.DataFrame:
    """Inseminações deste garanhão — matching por FK (`i.animal_id_garanhao`).

    O JOIN à égua também usa FK (`i.animal_id_egua`) para localizar a
    estadia de inseminação correspondente.
    """
    sql = """
        SELECT
            i.data_inseminacao,
            i.egua,
            d.nome           AS proprietario,
            i.palhetas_gastas,
            COALESCE(ai.resultado, 'pendente') AS resultado
        FROM inseminacoes i
        LEFT JOIN dono d ON d.id = i.dono_id
        LEFT JOIN estadias e
               ON e.animal_id = i.animal_id_egua
              AND e.motivo = 'inseminacao'
              AND i.data_inseminacao BETWEEN e.data_entrada
                                         AND COALESCE(e.data_saida, CURRENT_DATE)
        LEFT JOIN acompanhamento_inseminacao ai ON ai.estadia_id = e.id
        WHERE i.animal_id_garanhao = %s
        ORDER BY i.data_inseminacao DESC, i.id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(int(animal_id),))


def _kpis_fertilidade_garanhao(df: pd.DataFrame) -> tuple[int, int, str, float | None]:
    total = len(df)
    if total == 0:
        return 0, 0, "—", None
    ges = int((df["resultado"] == "gestacao_confirmada").sum())
    taxa = (ges / total) * 100
    return total, ges, f"{taxa:.0f} %", taxa


def _ultima_producao_garanhao(animal_id: int):
    """Data da última produção — matching por FK (`animal_id`).

    `data_embriovet` é VARCHAR no schema legado — convertemos para DATE
    com `NULLIF` para tolerar valores vazios/strings inválidas.
    """
    sql = """
        SELECT MAX(NULLIF(data_embriovet, '')::date) FROM estoque_dono
        WHERE animal_id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, (int(animal_id),))
            row = cur.fetchone()
        except Exception:
            # Fallback: faz o parsing em Python se houver formatos inválidos
            conn.rollback()
            cur.execute(
                "SELECT data_embriovet FROM estoque_dono "
                "WHERE animal_id = %s",
                (int(animal_id),),
            )
            datas: list[date] = []
            for (val,) in cur.fetchall():
                if not val:
                    continue
                try:
                    datas.append(datetime.strptime(str(val)[:10], "%Y-%m-%d").date())
                except Exception:
                    continue
            cur.close()
            return max(datas) if datas else None
        cur.close()
        return row[0] if row else None


def _render_tab_producao_semen(animal: dict) -> None:
    animal_id = int(animal.get("id"))
    df = _carregar_stock_garanhao(animal_id)
    total_palh, lotes_act, motil_avg, palh_internas, palh_externas = _kpis_stock_garanhao(df)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Total palhetas em stock", total_palh)
    with k2:
        st.metric("Total lotes activos", lotes_act)
    with k3:
        st.metric("Motilidade média", motil_avg)
    with k4:
        st.metric("Palhetas produzidas aqui", palh_internas)
    with k5:
        st.metric("Palhetas recebidas de fora", palh_externas)

    st.markdown("---")

    if df.empty:
        st.info("Sem lotes registados para este garanhão.")
        return

    view = df.copy()
    view["data_producao"] = pd.to_datetime(view["data_producao"]).dt.strftime("%d/%m/%Y")
    origem_col = view.get("origem_externa", pd.Series([None] * len(view))).fillna("").astype(str).str.strip()
    view["Origem"] = origem_col.apply(
        lambda v: "🏠 Colheita interna" if not v else f"🌍 Externo — {v}"
    )
    if "origem_externa" in view.columns:
        view = view.drop(columns=["origem_externa"])
    view = view.rename(columns={
        "data_producao": "Data produção",
        "proprietario": "Proprietário",
        "palhetas_iniciais": "Palhetas iniciais",
        "palhetas_restantes": "Palhetas restantes",
        "motilidade": "Motilidade (%)",
        "concentracao": "Concentração",
        "qualidade": "Qualidade",
        "contentor": "Contentor",
        "canister": "Canister",
        "andar": "Andar",
    })
    # Coloca "Origem" logo após a "Data produção" para leitura natural
    cols = list(view.columns)
    if "Origem" in cols and "Data produção" in cols:
        cols.remove("Origem")
        idx = cols.index("Data produção") + 1
        cols.insert(idx, "Origem")
        view = view[cols]
    st.dataframe(view, width="stretch", hide_index=True)


def _render_tab_fertilidade_garanhao(animal: dict) -> None:
    nome = animal.get("nome") or ""
    df = _carregar_inseminacoes_garanhao(nome)
    total, ges, taxa_txt, _ = _kpis_fertilidade_garanhao(df)

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Total inseminações realizadas", total)
    with k2:
        st.metric("Gestações confirmadas", ges)
    with k3:
        st.metric("Taxa de fertilidade", taxa_txt)

    st.markdown("---")

    if df.empty:
        st.info("Sem inseminações registadas para este garanhão.")
        return

    cols_w = [1.0, 1.6, 1.6, 0.9, 1.4]
    headers = ["Data", "Égua", "Proprietário", "Palhetas", "Resultado"]
    head_cols = st.columns(cols_w)
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
        cols = st.columns(cols_w)
        dt = row["data_inseminacao"]
        cols[0].write(dt.strftime("%d/%m/%Y") if pd.notna(dt) else "—")
        cols[1].write(row["egua"] or "—")
        cols[2].write(row["proprietario"] or "—")
        cols[3].write(int(row["palhetas_gastas"]) if pd.notna(row["palhetas_gastas"]) else "—")
        cols[4].markdown(_badge_resultado(row["resultado"]), unsafe_allow_html=True)


def _render_tab_alertas_garanhao(animal: dict) -> None:
    animal_id = int(animal.get("id"))
    nome = animal.get("nome") or ""
    df_stock = _carregar_stock_garanhao(animal_id)
    df_ins = _carregar_inseminacoes_garanhao(animal_id)
    total_palh, _, _, _, _ = _kpis_stock_garanhao(df_stock)
    _, _, _, taxa_pct = _kpis_fertilidade_garanhao(df_ins)
    ultima = _ultima_producao_garanhao(animal_id)

    alertas_emitidos = 0

    # 🔴 Stock crítico
    if total_palh < 10:
        st.error(
            f"🔴 **Stock crítico** — apenas **{total_palh} palhetas** em stock "
            f"({nome}). Considere repor.",
        )
        alertas_emitidos += 1
    # 🟡 Stock baixo (não duplica se já foi crítico)
    elif total_palh < 25:
        st.warning(
            f"🟡 **Stock baixo** — apenas **{total_palh} palhetas** em stock "
            f"({nome}). Vigie a evolução.",
        )
        alertas_emitidos += 1

    # ⚪ Última produção há mais de 30 dias
    if ultima:
        if isinstance(ultima, datetime):
            ultima = ultima.date()
        elif isinstance(ultima, str):
            try:
                ultima = datetime.strptime(ultima[:10], "%Y-%m-%d").date()
            except Exception:
                ultima = None
    if ultima:
        dias = (date.today() - ultima).days
        if dias > 30:
            st.info(
                f"⚪ **Sem produção recente** — última produção em "
                f"**{ultima.strftime('%d/%m/%Y')}** ({dias} dias).",
            )
            alertas_emitidos += 1
    else:
        st.info(f"⚪ **Sem produção registada** para {nome}.")
        alertas_emitidos += 1

    # 🟢 Taxa de fertilidade > 70%
    if taxa_pct is not None and taxa_pct > 70:
        st.success(
            f"🟢 **Excelente fertilidade** — taxa de **{taxa_pct:.0f} %** "
            f"({nome}).",
        )
        alertas_emitidos += 1

    if alertas_emitidos == 0:
        st.markdown(
            "<div style='color:#94a3b8;font-style:italic;padding:12px 0;'>"
            "Sem alertas activos para este garanhão.</div>",
            unsafe_allow_html=True,
        )


def run_animal_page(animal_id: int, context: dict, tab_inicial: int = 0):
    """Página de detalhe de um animal com 4 tabs (variam consoante o tipo)."""

    animal = _carregar_animal(animal_id)
    if not animal:
        st.error(f"Animal #{animal_id} não encontrado.")
        return

    st.markdown(f"## {animal.get('nome') or 'Animal sem nome'}")
    st.session_state[f"animal_{animal_id}_tab_inicial"] = tab_inicial

    if (animal.get("tipo") or "").lower() == "garanhao":
        # ── Layout específico para garanhão ─────────────────────────────────
        nomes_tabs = ["Resumo", "Produção de sémen", "Fertilidade", "Alertas"]
        tab_resumo, tab_producao, tab_fert, tab_alertas = st.tabs(nomes_tabs)

        with tab_resumo:
            _render_tab_resumo(animal)
        with tab_producao:
            _render_tab_producao_semen(animal)
        with tab_fert:
            _render_tab_fertilidade_garanhao(animal)
        with tab_alertas:
            _render_tab_alertas_garanhao(animal)
        return

    # ── Layout padrão para égua/receptora (mantido) ─────────────────────────
    nomes_tabs = ["Resumo", "Diário clínico", "Historial reprodutivo", "Estadias"]
    tab_resumo, tab_clinico, tab_repro, tab_estadias = st.tabs(nomes_tabs)

    with tab_resumo:
        _render_tab_resumo(animal)

    with tab_clinico:
        _render_tab_diario_clinico(animal_id)

    with tab_repro:
        _render_tab_historial_reprodutivo(animal)

    with tab_estadias:
        _render_tab_estadias(animal_id)
