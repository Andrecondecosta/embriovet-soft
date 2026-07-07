"""Modal de criação rápida de um animal + estadia/visita associada.

Uso típico:
    if st.button("+ Novo animal"):
        render_modal_animal(
            "modal_animal_egua",
            tipo_default="egua",
            on_success=lambda aid, nome, eid: st.session_state.update(...),
        )
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Catálogos
# ────────────────────────────────────────────────────────────────────────────

TIPOS_ANIMAL = ["egua", "garanhao", "receptora"]
TIPOS_REGISTO = ["estadia", "visita", "externo"]
MOTIVOS = ["inseminacao", "colheita", "diagnostico", "tratamento", "embriao"]


def _ensure_externo_constraints() -> None:
    """Garante que as CHECK constraints de `estadias` aceitam 'externo'.

    O spec menciona explicitamente o `estado`, mas a coluna `tipo_registo`
    também tem uma CHECK constraint que bloquearia o INSERT, pelo que ambas
    são actualizadas. Idempotente — pode ser chamada múltiplas vezes.
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
        # Falha silenciosa para não bloquear a UI; será tentada novamente
        # no próximo INSERT.
        pass


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


# ────────────────────────────────────────────────────────────────────────────
# Validações & inserts
# ────────────────────────────────────────────────────────────────────────────

def _existe_animal_com_nome_e_dono(nome: str, dono_id: int) -> bool:
    """True se já existir um animal com o mesmo nome E o mesmo proprietário."""
    sql = (
        "SELECT 1 FROM animais "
        "WHERE LOWER(nome) = LOWER(%s) AND dono_id = %s LIMIT 1"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (nome, int(dono_id)))
        existe = cur.fetchone() is not None
        cur.close()
        return existe


def _existe_animal_com_nome_outro_dono(nome: str, dono_id: int) -> bool:
    """True se já existir um animal com o mesmo nome de OUTRO proprietário.

    Usado para mostrar um aviso informativo (não bloqueia a criação).
    """
    sql = (
        "SELECT 1 FROM animais "
        "WHERE LOWER(nome) = LOWER(%s) AND dono_id IS DISTINCT FROM %s LIMIT 1"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (nome, int(dono_id) if dono_id is not None else None))
        existe = cur.fetchone() is not None
        cur.close()
        return existe


def _criar_animal_e_estadia(animal: dict, estadia: dict) -> tuple[int, int]:
    """Cria animal + estadia. Devolve `(animal_id, estadia_id)` numa transacção."""
    sql_animal = """
        INSERT INTO animais (
            nome, tipo, raca, pelagem, data_nascimento, numero_registo, chip,
            altura, peso, dono_id, pai, mae, avo_paterno, avo_materno,
            observacoes, is_receptora, ativo
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, TRUE
        ) RETURNING id
    """
    sql_estadia = """
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
        try:
            cur.execute(
                sql_animal,
                (
                    animal["nome"], animal["tipo"], animal.get("raca"),
                    animal.get("pelagem"), animal.get("data_nascimento"),
                    animal.get("numero_registo"), animal.get("chip"),
                    animal.get("altura"), animal.get("peso"),
                    animal.get("dono_id"),
                    animal.get("pai"), animal.get("mae"),
                    animal.get("avo_paterno"), animal.get("avo_materno"),
                    animal.get("observacoes"),
                    bool(animal.get("is_receptora", False)),
                ),
            )
            animal_id = int(cur.fetchone()[0])

            cur.execute(
                sql_estadia,
                (
                    estadia["tipo_registo"], animal_id,
                    estadia.get("alojamento_id"), estadia["dono_id"],
                    estadia["data_entrada"], estadia.get("data_saida"),
                    estadia["motivo"], estadia["estado"],
                    estadia.get("observacoes_entrada"),
                ),
            )
            estadia_id = int(cur.fetchone()[0])

            conn.commit()
            return animal_id, estadia_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


# ────────────────────────────────────────────────────────────────────────────
# UI
# ────────────────────────────────────────────────────────────────────────────

def _section_title(label: str) -> None:
    st.markdown(
        f"<div style='font-size:.78rem;color:#64748b;text-transform:uppercase;"
        f"letter-spacing:.6px;font-weight:700;margin:14px 0 6px;'>{label}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_modal_animal(
    key: str,
    tipo_default: str = "egua",
    on_success: Optional[Callable[[int, str, int], None]] = None,
    tipo_locked: bool = False,
) -> None:
    """Abre um modal completo para criar um animal + estadia/visita.

    Parâmetros
    ----------
    key : str
        Prefixo único para os widgets (necessário se usares mais que um
        modal na mesma página).
    tipo_default : str
        Valor pré-seleccionado em "tipo" (egua/garanhao/receptora).
    on_success : Optional[Callable[[int, str, int], None]]
        Callback `(animal_id, animal_nome, estadia_id)` invocado após
        criação bem-sucedida.
    tipo_locked : bool
        Se True, o campo "Tipo" fica fixo em `tipo_default` (não é mostrado)
        e o campo "É receptora" também fica escondido — o modal fica
        focado num único tipo de animal.
    """

    if tipo_default not in TIPOS_ANIMAL:
        tipo_default = "egua"

    dono_version_key = f"{key}_dono_version"
    applied_prop_key = f"{key}_applied_novo_prop"
    draft_applied_flag = f"{key}_draft_applied"
    if dono_version_key not in st.session_state:
        st.session_state[dono_version_key] = 0

    # ── Restauro do draft (vindo do fluxo "+ Novo proprietário") ────────────
    # Aplicamos UMA VEZ por reabertura — Streamlit exige que o set seja
    # feito ANTES dos widgets serem instanciados.
    draft = st.session_state.get("modal_animal_draft")
    if draft and not st.session_state.get(draft_applied_flag):
        st.session_state[f"{key}_an_nome"] = draft.get("nome", "")
        if draft.get("tipo") in TIPOS_ANIMAL:
            st.session_state[f"{key}_an_tipo"] = draft["tipo"]
        st.session_state[f"{key}_an_raca"] = draft.get("raca", "")
        st.session_state[f"{key}_an_pelagem"] = draft.get("pelagem", "")
        st.session_state[f"{key}_an_dt_nasc"] = draft.get("data_nascimento")
        st.session_state[f"{key}_an_reg"] = draft.get("numero_registo", "")
        st.session_state[f"{key}_an_chip"] = draft.get("chip", "")
        st.session_state[f"{key}_an_altura"] = float(draft.get("altura") or 0.0)
        st.session_state[f"{key}_an_peso"] = float(draft.get("peso") or 0.0)
        st.session_state[f"{key}_an_pai"] = draft.get("pai", "")
        st.session_state[f"{key}_an_mae"] = draft.get("mae", "")
        st.session_state[f"{key}_an_avo_p"] = draft.get("avo_paterno", "")
        st.session_state[f"{key}_an_avo_m"] = draft.get("avo_materno", "")
        if draft.get("tipo_registo") in TIPOS_REGISTO:
            st.session_state[f"{key}_es_tipo_reg"] = draft["tipo_registo"]
        if draft.get("motivo") in MOTIVOS:
            st.session_state[f"{key}_es_motivo"] = draft["motivo"]
        if draft.get("data_entrada"):
            st.session_state[f"{key}_es_dt_ent"] = draft["data_entrada"]
        st.session_state[f"{key}_es_dt_saida"] = draft.get("data_saida")
        if draft.get("alojamento_id") is not None:
            st.session_state[f"{key}_es_aloj"] = draft["alojamento_id"]
        st.session_state[f"{key}_an_obs"] = draft.get("observacoes", "")
        st.session_state[f"{key}_an_is_receptora"] = bool(draft.get("is_receptora"))
        st.session_state[draft_applied_flag] = True

    @st.dialog("Novo animal", width="large")
    def _modal() -> None:
        # Catálogos (recarregam consoante as versões em session_state)
        donos_df = _carregar_donos()
        alojamentos_df = _carregar_alojamentos()

        # Inicializa session_state para widgets sem `value=` para evitar
        # avisos do Streamlit ("created with a default value but also had
        # its value set via the Session State API").
        for k_init, v_default in (
            (f"{key}_an_dt_nasc", None),
            (f"{key}_an_altura", 0.0),
            (f"{key}_an_peso", 0.0),
            (f"{key}_es_dt_ent", date.today()),
            (f"{key}_es_dt_saida", None),
        ):
            if k_init not in st.session_state:
                st.session_state[k_init] = v_default

        # ── Identificação ────────────────────────────────────────────────
        _section_title("Identificação")
        c1, c2, c3 = st.columns(3)
        with c1:
            nome = st.text_input(
                "Nome *", key=f"{key}_an_nome",
                placeholder="Ex.: Tornado",
            )
            if tipo_locked:
                # Tipo fixo — não mostra o selectbox
                tipo = tipo_default
            else:
                tipo = st.selectbox(
                    "Tipo",
                    TIPOS_ANIMAL,
                    index=TIPOS_ANIMAL.index(tipo_default),
                    key=f"{key}_an_tipo",
                    format_func=lambda x: {
                        "egua": "Égua",
                        "garanhao": "Garanhão",
                        "receptora": "Receptora",
                    }.get(x, x),
                )
            raca = st.text_input("Raça", key=f"{key}_an_raca")
        with c2:
            pelagem = st.text_input("Pelagem / cor", key=f"{key}_an_pelagem")
            data_nascimento = st.date_input(
                "Data de nascimento",
                key=f"{key}_an_dt_nasc",
                format="DD/MM/YYYY",
            )
            numero_registo = st.text_input(
                "Nº de registo / passaporte", key=f"{key}_an_reg",
            )
        with c3:
            chip = st.text_input("Chip electrónico", key=f"{key}_an_chip")
            altura = st.number_input(
                "Altura (cm)", min_value=0.0, max_value=300.0,
                step=1.0, key=f"{key}_an_altura",
            )
            peso = st.number_input(
                "Peso (kg)", min_value=0.0, max_value=2000.0,
                step=1.0, key=f"{key}_an_peso",
            )

        # ── Proprietário ────────────────────────────────────────────────
        _section_title("Proprietário")

        # Se foi acabado de criar um proprietário no modal centralizado,
        # forçamos o re-mount do selectbox (bumpando a versão) para que
        # o novo dono fique seleccionado por defeito.
        novo_prop_id = st.session_state.get("novo_prop_id")
        if (
            novo_prop_id is not None
            and st.session_state.get(applied_prop_key) != novo_prop_id
        ):
            st.session_state[dono_version_key] += 1
            st.session_state[applied_prop_key] = novo_prop_id

        if donos_df.empty:
            st.info(
                "Ainda não existem proprietários activos. Crie um abaixo "
                "para continuar.",
            )
            dono_id: Optional[int] = None
        else:
            opcoes = [None] + donos_df["id"].tolist()
            default_idx = 0
            if novo_prop_id is not None and novo_prop_id in opcoes:
                default_idx = opcoes.index(novo_prop_id)

            def _fmt_dono(did: Optional[int]) -> str:
                if did is None:
                    return "— Selecionar proprietário —"
                row = donos_df.loc[donos_df["id"] == did]
                return str(row.iloc[0]["nome"]) if not row.empty else f"#{did}"

            dono_id = st.selectbox(
                "Proprietário *",
                opcoes,
                index=default_idx,
                format_func=_fmt_dono,
                key=f"{key}_an_dono_{st.session_state[dono_version_key]}",
            )

        col_btn, _ = st.columns([1, 2])
        with col_btn:
            if st.button(
                "+ Novo proprietário",
                key=f"{key}_btn_novo_dono",
                width="stretch",
            ):
                # Workaround: Streamlit não permite diálogos aninhados.
                # Guardamos um snapshot do formulário em session_state e
                # delegamos a abertura do modal de proprietário ao orquestrador
                # da página (que corre em cada rerun).
                st.session_state["modal_animal_draft"] = {
                    "nome": st.session_state.get(f"{key}_an_nome", ""),
                    "tipo": st.session_state.get(f"{key}_an_tipo", tipo_default),
                    "raca": st.session_state.get(f"{key}_an_raca", ""),
                    "pelagem": st.session_state.get(f"{key}_an_pelagem", ""),
                    "data_nascimento": st.session_state.get(f"{key}_an_dt_nasc"),
                    "numero_registo": st.session_state.get(f"{key}_an_reg", ""),
                    "chip": st.session_state.get(f"{key}_an_chip", ""),
                    "altura": st.session_state.get(f"{key}_an_altura", 0.0),
                    "peso": st.session_state.get(f"{key}_an_peso", 0.0),
                    "pai": st.session_state.get(f"{key}_an_pai", ""),
                    "mae": st.session_state.get(f"{key}_an_mae", ""),
                    "avo_paterno": st.session_state.get(f"{key}_an_avo_p", ""),
                    "avo_materno": st.session_state.get(f"{key}_an_avo_m", ""),
                    "tipo_registo": st.session_state.get(
                        f"{key}_es_tipo_reg", "estadia",
                    ),
                    "motivo": st.session_state.get(
                        f"{key}_es_motivo", "inseminacao",
                    ),
                    "data_entrada": st.session_state.get(
                        f"{key}_es_dt_ent", date.today(),
                    ),
                    "data_saida": st.session_state.get(f"{key}_es_dt_saida"),
                    "alojamento_id": st.session_state.get(f"{key}_es_aloj"),
                    "observacoes": st.session_state.get(f"{key}_an_obs", ""),
                    "is_receptora": bool(
                        st.session_state.get(f"{key}_an_is_receptora", False),
                    ),
                }
                st.session_state["abrir_modal_prop_standalone"] = True
                # Limpar a flag de "draft já aplicado" para que, ao reabrir,
                # os campos sejam realmente repopulados.
                st.session_state.pop(draft_applied_flag, None)
                st.rerun()

        # ── Pedigree ────────────────────────────────────────────────────
        _section_title("Pedigree")
        p1, p2 = st.columns(2)
        with p1:
            pai = st.text_input("Pai", key=f"{key}_an_pai")
            avo_paterno = st.text_input(
                "Avô paterno", key=f"{key}_an_avo_p",
            )
        with p2:
            mae = st.text_input("Mãe", key=f"{key}_an_mae")
            avo_materno = st.text_input(
                "Avô materno", key=f"{key}_an_avo_m",
            )

        # ── Estadia / Visita ────────────────────────────────────────────
        _section_title("Estadia / Visita")
        e1, e2 = st.columns(2)
        with e1:
            tipo_registo = st.selectbox(
                "Tipo de registo",
                TIPOS_REGISTO,
                key=f"{key}_es_tipo_reg",
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
                key=f"{key}_es_motivo",
                format_func=lambda x: {
                    "inseminacao": "Inseminação",
                    "colheita": "Colheita",
                    "diagnostico": "Diagnóstico",
                    "tratamento": "Tratamento",
                    "embriao": "Embrião",
                }.get(x, x.capitalize()),
            )
        with e2:
            dt_label = (
                "Data do serviço / envio"
                if tipo_registo == "externo"
                else "Data de entrada"
            )
            data_entrada = st.date_input(
                dt_label,
                key=f"{key}_es_dt_ent",
                format="DD/MM/YYYY",
            )
            if tipo_registo != "externo":
                data_saida = st.date_input(
                    "Data prevista de saída",
                    key=f"{key}_es_dt_saida",
                    format="DD/MM/YYYY",
                )
            else:
                # Limpa qualquer valor anterior — não aplicável a 'externo'
                data_saida = None
                st.session_state[f"{key}_es_dt_saida"] = None

        alojamento_id: Optional[int] = None
        if tipo_registo != "externo":
            if alojamentos_df.empty:
                if tipo_registo == "estadia":
                    st.warning(
                        "Não existem alojamentos activos. Crie um em "
                        "Definições → Alojamentos antes de registar uma estadia.",
                    )
            else:
                def _fmt_aloj(aid: Optional[int]) -> str:
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
                    [None] + alojamentos_df["id"].tolist(),
                    format_func=_fmt_aloj,
                    key=f"{key}_es_aloj",
                )

        # ── Observações + receptora ─────────────────────────────────────
        _section_title("Observações")
        observacoes = st.text_area(
            "Observações", key=f"{key}_an_obs", height=80,
        )

        is_receptora = False
        if tipo == "egua" and not tipo_locked:
            is_receptora = st.checkbox(
                "É receptora",
                key=f"{key}_an_is_receptora",
            )

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # Aviso informativo (não bloqueia) — nome já em uso por outro proprietário
        nome_preview = (nome or "").strip()
        if (
            nome_preview
            and dono_id
            and _existe_animal_com_nome_outro_dono(nome_preview, int(dono_id))
        ):
            st.warning(
                "Já existe um animal com este nome de outro proprietário — "
                "confirme que é um animal diferente.",
            )

        # ── Botões ──────────────────────────────────────────────────────
        b1, b2 = st.columns(2)
        with b1:
            cancelar = st.button(
                "Cancelar",
                key=f"{key}_btn_cancelar",
                width="stretch",
            )
        with b2:
            guardar = st.button(
                "Guardar animal",
                type="primary",
                key=f"{key}_btn_guardar",
                width="stretch",
            )

        if cancelar:
            st.session_state.pop("novo_prop_id", None)
            st.session_state.pop("novo_prop_nome", None)
            st.session_state.pop("modal_animal_draft", None)
            st.session_state.pop("reabrir_modal_animal", None)
            st.session_state.pop(draft_applied_flag, None)
            st.rerun()

        if not guardar:
            return

        # ── Validações ──────────────────────────────────────────────────
        nome_clean = (nome or "").strip()
        if not nome_clean:
            st.error("O nome do animal é obrigatório.")
            return

        if not dono_id:
            st.error("Selecione um proprietário ou crie um novo.")
            return

        # Bloquear apenas se já existir animal com o MESMO nome E o MESMO
        # proprietário (mesmo nome com outro proprietário é permitido — só
        # mostra aviso informativo acima).
        if _existe_animal_com_nome_e_dono(nome_clean, int(dono_id)):
            st.error(
                f"Já existe um animal com o nome '{nome_clean}' deste "
                "proprietário. Escolha outro nome.",
            )
            return

        if tipo_registo == "estadia" and not alojamento_id:
            st.error("O alojamento é obrigatório quando o tipo é 'estadia'.")
            return

        # Garante que as CHECK constraints aceitam 'externo' antes do INSERT.
        if tipo_registo == "externo":
            _ensure_externo_constraints()

        # ── INSERTs ─────────────────────────────────────────────────────
        animal_payload = {
            "nome": nome_clean,
            "tipo": tipo,
            "raca": (raca or "").strip() or None,
            "pelagem": (pelagem or "").strip() or None,
            "data_nascimento": data_nascimento or None,
            "numero_registo": (numero_registo or "").strip() or None,
            "chip": (chip or "").strip() or None,
            "altura": altura if altura and altura > 0 else None,
            "peso": peso if peso and peso > 0 else None,
            "dono_id": dono_id,
            "pai": (pai or "").strip() or None,
            "mae": (mae or "").strip() or None,
            "avo_paterno": (avo_paterno or "").strip() or None,
            "avo_materno": (avo_materno or "").strip() or None,
            "observacoes": (observacoes or "").strip() or None,
            "is_receptora": is_receptora,
        }
        if tipo_registo == "externo":
            estado_inicial = "externo"
        elif tipo_registo == "estadia":
            estado_inicial = "internado"
        else:
            estado_inicial = "visitante"
        estadia_payload = {
            "tipo_registo": tipo_registo,
            "alojamento_id": alojamento_id,
            "dono_id": dono_id,
            "data_entrada": data_entrada,
            "data_saida": data_saida or None,
            "motivo": motivo,
            "estado": estado_inicial,
            "observacoes_entrada": (observacoes or "").strip() or None,
        }

        try:
            animal_id, estadia_id = _criar_animal_e_estadia(
                animal_payload, estadia_payload,
            )
        except Exception as exc:
            st.error(f"Erro ao guardar: {exc}")
            return

        if on_success is not None:
            try:
                on_success(animal_id, nome_clean, estadia_id)
            except Exception as exc:  # pragma: no cover
                st.warning(f"Animal criado, mas callback falhou: {exc}")

        # Reset estado interno do modal
        st.session_state.pop("novo_prop_id", None)
        st.session_state.pop("novo_prop_nome", None)
        st.session_state.pop(applied_prop_key, None)
        st.session_state.pop("modal_animal_draft", None)
        st.session_state.pop("reabrir_modal_animal", None)
        st.session_state.pop(draft_applied_flag, None)
        st.session_state[dono_version_key] += 1
        st.success(
            f"Animal '{nome_clean}' criado e estadia/visita registada.",
        )
        st.rerun()

    _modal()
