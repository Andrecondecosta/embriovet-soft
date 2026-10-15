import { forwardRef, useImperativeHandle, useMemo, useState, type ReactElement, type ReactNode, type Ref } from "react";
import { Button, CheckList, List, NavBar, Picker, Popup, SearchBar } from "antd-mobile";
import { AddOutline } from "antd-mobile-icons";

import { useT } from "../i18n/I18n";

/* Peças comuns aos formulários do telemóvel (Ant Design Mobile). Os campos
 * são "controlados" (`value`/`onChange`), por isso funcionam dentro de um
 * `Form.Item` do antd-mobile. */

/** Formulário em ecrã inteiro: Cancelar à esquerda, Guardar à direita. */
export function FolhaEcraInteiro({
  visible,
  titulo,
  onCancel,
  onOk,
  okText,
  loading,
  children,
}: {
  visible: boolean;
  titulo: ReactNode;
  onCancel: () => void;
  onOk: () => void;
  okText: string;
  loading?: boolean;
  children: ReactNode;
}) {
  const t = useT();
  return (
    <Popup
      visible={visible}
      onClose={onCancel}
      position="right"
      destroyOnClose
      bodyStyle={{ width: "100vw", height: "100dvh", display: "flex", flexDirection: "column", background: "#f5f5f5" }}
    >
      <NavBar
        back={t("web.common.cancel")}
        backIcon={false}
        onBack={onCancel}
        right={
          <Button size="small" color="primary" fill="none" loading={loading} onClick={onOk} style={{ fontWeight: 600 }}>
            {okText}
          </Button>
        }
        style={{ background: "#fff", borderBottom: "1px solid #eee", flexShrink: 0, "--height": "46px" } as React.CSSProperties}
      >
        {titulo}
      </NavBar>
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", paddingBottom: "env(safe-area-inset-bottom)" }}>{children}</div>
    </Popup>
  );
}

export interface Opcao<V> {
  value: V;
  label: string;
}

/** Valor mostrado num campo que abre uma folha (vazio → texto cinzento). */
function Valor({ texto, placeholder }: { texto?: string; placeholder?: string }) {
  return texto ? <span>{texto}</span> : <span style={{ color: "#ccc" }}>{placeholder ?? "—"}</span>;
}

/** Permite ao `Form.Item` abrir a folha ao tocar em qualquer ponto da linha:
 *  `<Form.Item onClick={abrirAoTocar}>`. */
export interface Abrivel {
  open: () => void;
}
export const abrirAoTocar = (_: unknown, ref: { current: unknown }) => (ref.current as Abrivel | null)?.open();

/**
 * Escolher um de muitos (proprietário, contentor, garanhão…): toca-se no
 * campo e sobe uma folha com pesquisa. `novo` permite usar o texto escrito
 * como valor novo (ex.: garanhão que ainda não existe); `acao` acrescenta
 * uma linha no fim (ex.: "+ Novo proprietário").
 */
function SeletorPesquisaBase<V extends string | number>(
  {
    value,
    onChange,
    opcoes,
    titulo,
    placeholder,
    novo,
    acao,
  }: {
    value?: V | null;
    onChange?: (v: V) => void;
    opcoes: Opcao<V>[];
    titulo: string;
    placeholder?: string;
    novo?: (texto: string) => V;
    acao?: { texto: string; onClick: () => void };
  },
  ref: Ref<Abrivel>,
) {
  const t = useT();
  const [aberto, setAberto] = useState(false);
  useImperativeHandle(ref, () => ({ open: () => setAberto(true) }));
  const [q, setQ] = useState("");
  const atual = opcoes.find((o) => o.value === value);
  const filtradas = useMemo(() => {
    const s = q.trim().toLowerCase();
    return opcoes.filter((o) => !s || o.label.toLowerCase().includes(s)).slice(0, 100);
  }, [opcoes, q]);
  const texto = q.trim();
  const podeNovo = novo && texto && !opcoes.some((o) => o.label.toLowerCase() === texto.toLowerCase());
  const escolher = (v: V) => {
    onChange?.(v);
    setAberto(false);
    setQ("");
  };

  return (
    <>
      <div onClick={() => setAberto(true)} style={{ cursor: "pointer", minHeight: 22 }}>
        <Valor texto={atual?.label ?? (value != null && value !== "" ? String(value) : undefined)} placeholder={placeholder} />
      </div>
      <Popup
        visible={aberto}
        onMaskClick={() => setAberto(false)}
        onClose={() => setAberto(false)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, height: "80dvh", display: "flex", flexDirection: "column" }}
      >
        <div style={{ padding: "14px 16px 8px", fontWeight: 600, fontSize: 15 }}>{titulo}</div>
        <div style={{ padding: "0 12px 8px" }}>
          <SearchBar value={q} onChange={setQ} placeholder={t("web.common.search")} />
        </div>
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
          {acao && (
            <List>
              <List.Item
                prefix={<AddOutline />}
                onClick={() => {
                  setAberto(false);
                  acao.onClick();
                }}
                style={{ color: "var(--adm-color-primary)" }}
              >
                {acao.texto}
              </List.Item>
            </List>
          )}
          {podeNovo && (
            <List>
              <List.Item prefix={<AddOutline />} onClick={() => escolher(novo(texto))} style={{ color: "var(--adm-color-primary)" }}>
                {t("web.mobile.use_new", { name: texto })}
              </List.Item>
            </List>
          )}
          <CheckList value={value != null ? [value] : []} onChange={(v) => v.length && escolher(v[0] as V)}>
            {filtradas.map((o) => (
              <CheckList.Item key={String(o.value)} value={o.value}>
                {o.label}
              </CheckList.Item>
            ))}
          </CheckList>
          {!filtradas.length && !podeNovo && (
            <div style={{ padding: 24, textAlign: "center", color: "#999" }}>{t("web.common.no_results")}</div>
          )}
        </div>
      </Popup>
    </>
  );
}
/* `forwardRef` para o `Form.Item` conseguir abrir a folha (ver `abrirAoTocar`). */
export const SeletorPesquisa = forwardRef(SeletorPesquisaBase) as <V extends string | number>(
  p: Parameters<typeof SeletorPesquisaBase<V>>[0] & { ref?: Ref<Abrivel> },
) => ReactElement;

/** Escolher um de poucos numa roda (canister, etc.). */
function PickerCampoBase<V extends string | number>(
  {
    value,
    onChange,
    opcoes,
    titulo,
    placeholder,
  }: {
    value?: V | null;
    onChange?: (v: V) => void;
    opcoes: Opcao<V>[];
    titulo?: string;
    placeholder?: string;
  },
  ref: Ref<Abrivel>,
) {
  const [aberto, setAberto] = useState(false);
  useImperativeHandle(ref, () => ({ open: () => setAberto(true) }));
  return (
    <>
      <div onClick={() => setAberto(true)} style={{ cursor: "pointer", minHeight: 22 }}>
        <Valor texto={opcoes.find((o) => o.value === value)?.label} placeholder={placeholder} />
      </div>
      <Picker
        title={titulo}
        visible={aberto}
        onClose={() => setAberto(false)}
        columns={[opcoes]}
        value={value != null ? [value] : []}
        onConfirm={(v) => v[0] != null && onChange?.(v[0] as V)}
      />
    </>
  );
}
/* `forwardRef` para o `Form.Item` conseguir abrir a folha (ver `abrirAoTocar`). */
export const PickerCampo = forwardRef(PickerCampoBase) as <V extends string | number>(
  p: Parameters<typeof PickerCampoBase<V>>[0] & { ref?: Ref<Abrivel> },
) => ReactElement;

/** Número escrito à mão (teclado numérico); guarda `number`. */
export function NumeroCampo({
  value,
  onChange,
  min = 0,
  max,
  placeholder,
}: {
  value?: number | null;
  onChange?: (v: number) => void;
  min?: number;
  max?: number;
  placeholder?: string;
}) {
  return (
    <input
      type="number"
      inputMode="numeric"
      className="adm-input-element"
      style={{ width: "100%" }}
      value={value ?? ""}
      placeholder={placeholder}
      min={min}
      max={max}
      onFocus={(e) => e.target.select()}
      onChange={(e) => {
        let n = e.target.value === "" ? 0 : Number(e.target.value);
        if (Number.isNaN(n)) return;
        if (n < min) n = min;
        if (max != null && n > max) n = max;
        onChange?.(n);
      }}
    />
  );
}

/** Título de secção dentro de um formulário (o `Form.Header` do antd-mobile
 *  só funciona como filho direto do `Form`). */
export function Cabecalho({ children }: { children: ReactNode }) {
  return <div style={{ padding: "14px 12px 6px", fontSize: 12, color: "#999", background: "#f5f5f5" }}>{children}</div>;
}

/** `onFinishFailed`: desliza até ao primeiro campo com erro (pode estar
 *  fora do ecrã num formulário comprido). */
export function irParaErro() {
  requestAnimationFrame(() =>
    document
      .querySelector(".adm-form-item-feedback-error")
      ?.closest(".adm-list-item")
      ?.scrollIntoView({ behavior: "smooth", block: "center" }),
  );
}
