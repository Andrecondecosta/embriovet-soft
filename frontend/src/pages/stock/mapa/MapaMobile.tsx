import { useState } from "react";
import { Button, Dialog, DotLoading, Form, Input, List, NavBar, Popup, Selector, Stepper } from "antd-mobile";

import { useT } from "../../../i18n/I18n";
import { notifySuccess, useNotifyError } from "../../../components/errors";
import { Cabecalho, PickerCampo, SeletorPesquisa } from "../../../components/mobile";
import { CANISTERS } from "../LoteForm";
import { Tanque, valido } from "./ContentorModal";
import { baixarInventario } from "./MapaTab";
import {
  refCurta,
  useApagarContentor,
  useCriarContentor,
  useEditarContentor,
  useInverterAndares,
  useMoverPalhetas,
  useOrganizar,
  useStockContentor,
  type Contentor,
  type LoteContentor,
} from "./api";

/* Mapa dos contentores no telemóvel (Ant Design Mobile): as mesmas ações e
 * regras da versão de computador (`MapaTab`/`ContentorModal`). */

const folha = {
  borderTopLeftRadius: 12,
  borderTopRightRadius: 12,
  padding: "14px 16px",
  paddingBottom: "calc(16px + env(safe-area-inset-bottom))",
};

/** Barra de ações: Adicionar, Organizar e Exportar. */
export function BarraMapaMobile({ contentores, onOrganizado }: { contentores: Contentor[]; onOrganizado: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const organizar = useOrganizar();
  const [novo, setNovo] = useState(false);
  const [exportar, setExportar] = useState(false);
  const total = contentores.reduce((s, c) => s + c.palhetas, 0);

  const confirmarOrganizar = () =>
    Dialog.confirm({
      title: t("map.organize"),
      content: t("map.organize_help"),
      confirmText: t("map.organize_confirm"),
      cancelText: t("web.common.cancel"),
      onConfirm: async () => {
        try {
          const r = await organizar.mutateAsync(undefined);
          notifySuccess(t("map.organized", { count: r.count }));
          onOrganizado();
        } catch (err) {
          notifyError(err);
        }
      },
    });

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Button size="small" color="primary" onClick={() => setNovo(true)}>
          + {t("map.add")}
        </Button>
        <Button size="small" onClick={() => void confirmarOrganizar()}>
          {t("map.organize")}
        </Button>
        <Button size="small" onClick={() => setExportar(true)}>
          {t("map.export")}
        </Button>
        <span style={{ marginLeft: "auto", color: "#999", fontSize: 12 }}>
          <b>{contentores.length}</b> {t("web.map.containers")} · <b>{total}</b> {t("label.straws")}
        </span>
      </div>
      <NovoContentorMobile visible={novo} onClose={() => setNovo(false)} />
      <ExportarMobile visible={exportar} onClose={() => setExportar(false)} contentores={contentores} />
    </>
  );
}

export function NovoContentorMobile({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const criar = useCriarContentor();
  const [form] = Form.useForm<{ codigo: string; descricao: string }>();

  const guardar = async (v: { codigo: string; descricao?: string }) => {
    try {
      const c = await criar.mutateAsync({ codigo: v.codigo, descricao: v.descricao ?? "" });
      notifySuccess(t("web.map.created", { code: c.codigo }));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Popup visible={visible} onMaskClick={onClose} onClose={onClose} destroyOnClose bodyStyle={folha}>
      <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>{t("map.add_container_title")}</div>
      <Form
        form={form}
        layout="vertical"
        onFinish={guardar}
        style={{ "--border-top": "none", "--border-bottom": "none" } as React.CSSProperties}
      >
        <Form.Item
          name="codigo"
          label={t("map.container_code_required").replace(" *", "")}
          description={t("map.container_code_help")}
          rules={[{ required: true, whitespace: true, message: t("map.container_code_required_error") }]}
        >
          <Input placeholder={t("map.container_code_placeholder")} autoFocus clearable />
        </Form.Item>
        <Form.Item name="descricao" label={t("map.container_description_optional")}>
          <Input placeholder={t("map.container_description_placeholder")} clearable />
        </Form.Item>
      </Form>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <Button block onClick={onClose}>
          {t("web.common.cancel")}
        </Button>
        <Button block color="primary" loading={criar.isPending} onClick={() => form.submit()}>
          {t("btn.create_container")}
        </Button>
      </div>
    </Popup>
  );
}

function ExportarMobile({ visible, onClose, contentores }: { visible: boolean; onClose: () => void; contentores: Contentor[] }) {
  const t = useT();
  const notifyError = useNotifyError();
  const [ids, setIds] = useState<number[]>([]);
  const [aGerar, setAGerar] = useState<string | null>(null);
  const baixar = async (formato: "pdf" | "xlsx") => {
    setAGerar(formato);
    try {
      await baixarInventario(formato, ids);
    } catch (err) {
      notifyError(err);
    } finally {
      setAGerar(null);
    }
  };

  return (
    <Popup visible={visible} onMaskClick={onClose} onClose={onClose} bodyStyle={{ ...folha, maxHeight: "80dvh", overflowY: "auto" }}>
      <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>{t("map.export")}</div>
      <div style={{ color: "#666", marginBottom: 10 }}>{t("map.export_help")}</div>
      <div style={{ color: "#999", marginBottom: 6 }}>
        {t("map.export_containers")} {!ids.length && `(${t("map.export_all")})`}
      </div>
      <Selector multiple columns={3} value={ids} onChange={setIds} options={contentores.map((c) => ({ value: c.id, label: c.codigo }))} />
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <Button block onClick={() => baixar("pdf")} loading={aGerar === "pdf"}>
          PDF
        </Button>
        <Button block onClick={() => baixar("xlsx")} loading={aGerar === "xlsx"}>
          Excel
        </Button>
      </div>
    </Popup>
  );
}

/** Interior de um contentor: ecrã inteiro que entra da direita. */
export function ContentorMobile({ contentor, todos, onClose }: { contentor: Contentor | null; todos: Contentor[]; onClose: () => void }) {
  const { data } = useStockContentor(contentor?.id ?? null);
  return (
    <Popup
      visible={contentor !== null}
      onClose={onClose}
      position="right"
      destroyOnClose
      bodyStyle={{ width: "100vw", height: "100dvh", display: "flex", flexDirection: "column", background: "#f5f5f5" }}
    >
      <NavBar
        onBack={onClose}
        style={{ background: "#fff", borderBottom: "1px solid #eee", flexShrink: 0, "--height": "46px" } as React.CSSProperties}
      >
        {data?.contentor.codigo ?? contentor?.codigo}
      </NavBar>
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", paddingBottom: "env(safe-area-inset-bottom)" }}>
        {contentor && <InteriorMobile contentor={contentor} todos={todos} onClose={onClose} />}
      </div>
    </Popup>
  );
}

function InteriorMobile({ contentor, todos, onClose }: { contentor: Contentor; todos: Contentor[]; onClose: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const { data, isPending } = useStockContentor(contentor.id);
  const inverter = useInverterAndares();
  const [andar, setAndar] = useState<1 | 2>(1);
  const [canister, setCanister] = useState<number | null>(null);
  const [aMover, setAMover] = useState<LoteContentor | null>(null);

  if (isPending || !data)
    return (
      <div style={{ textAlign: "center", padding: 32 }}>
        <DotLoading color="primary" />
      </div>
    );

  const lotes = data.lotes;
  const semLugar = lotes.filter((l) => !valido(l));

  const confirmarInverter = () =>
    Dialog.confirm({
      title: t("web.map.invert"),
      content: t("web.map.invert_confirm", { code: data.contentor.codigo }),
      confirmText: t("btn.confirm"),
      cancelText: t("web.common.cancel"),
      onConfirm: async () => {
        try {
          const r = await inverter.mutateAsync(contentor.id);
          notifySuccess(t("web.map.inverted", { count: r.count }));
        } catch (err) {
          notifyError(err);
        }
      },
    });

  return (
    <>
      {contentor.descricao && <div style={{ padding: "10px 12px 0", color: "#999" }}>{contentor.descricao}</div>}

      {!lotes.length ? (
        <div style={{ padding: 24, textAlign: "center", color: "#999" }}>{t("web.map.no_lots")}</div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center", padding: 12 }}>
            <Selector
              showCheckMark={false}
              value={[andar]}
              onChange={(v) => {
                if (!v[0]) return;
                setAndar(v[0]);
                setAMover(null);
              }}
              options={[
                { value: 1 as const, label: t("web.map.floor", { n: 1 }) },
                { value: 2 as const, label: t("web.map.floor", { n: 2 }) },
              ]}
            />
            <Button size="small" style={{ marginLeft: "auto" }} onClick={() => void confirmarInverter()}>
              {t("web.map.invert")}
            </Button>
          </div>
          <div style={{ background: "#fff", padding: "14px 0" }}>
            <Tanque lotes={lotes} andar={andar} selecionado={canister} onSelecionar={setCanister} />
          </div>
          {canister !== null && (
            <ListaLotes
              titulo={t("web.map.canister", { n: canister })}
              lotes={lotes.filter((l) => l.canister === canister && l.andar === andar)}
              onMover={setAMover}
            />
          )}
          {/* Lotes sem canister/andar aparecem à parte, para se poderem arrumar. */}
          {semLugar.length > 0 && <ListaLotes titulo={t("web.map.no_place")} lotes={semLugar} onMover={setAMover} />}
        </>
      )}

      <EditarContentorMobile contentor={data.contentor} palhetas={data.palhetas} onDeleted={onClose} />

      <Popup visible={aMover !== null} onMaskClick={() => setAMover(null)} onClose={() => setAMover(null)} destroyOnClose bodyStyle={folha}>
        {aMover && <MoverMobile lote={aMover} contentorAtual={data.contentor} todos={todos} onDone={() => setAMover(null)} />}
      </Popup>
    </>
  );
}

function ListaLotes({ titulo, lotes, onMover }: { titulo: string; lotes: LoteContentor[]; onMover: (l: LoteContentor) => void }) {
  const t = useT();
  return (
    <>
      <Cabecalho>{titulo}</Cabecalho>
      <List>
        {!lotes.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.map.empty_floor")}</span>
          </List.Item>
        ) : (
          lotes.map((l) => (
            <List.Item
              key={l.id}
              description={
                <>
                  {l.proprietario_nome ?? t("common.no_owner")} · {refCurta(l)} · {l.existencia_atual} {t("label.straws")}
                  <div>
                    {t("web.map.harvest")}: {l.data_embriovet || "—"} · {t("stock.quality_label")}: {l.qualidade || "—"} · M{" "}
                    {l.motilidade ?? 0}% · {l.concentracao ?? 0}M/ml
                  </div>
                </>
              }
              extra={
                <Button size="mini" color="primary" fill="outline" onClick={() => onMover(l)}>
                  {t("web.map.move")}
                </Button>
              }
            >
              {l.garanhao}
            </List.Item>
          ))
        )}
      </List>
    </>
  );
}

/** Mover palhetas para outro canister/andar/contentor — arrumação física:
 *  o dono não muda e não fica registo em transferências. */
function MoverMobile({
  lote,
  contentorAtual,
  todos,
  onDone,
}: {
  lote: LoteContentor;
  contentorAtual: { id: number; codigo: string };
  todos: Contentor[];
  onDone: () => void;
}) {
  const t = useT();
  const notifyError = useNotifyError();
  const mover = useMoverPalhetas();
  const [destino, setDestino] = useState(contentorAtual.id);
  const [qtd, setQtd] = useState(lote.existencia_atual);
  const [canister, setCanister] = useState(Math.min(10, Math.max(1, lote.canister || 1)));
  // Por omissão, o outro andar (como a app atual).
  const [andar, setAndar] = useState<1 | 2>(lote.andar === 2 ? 1 : 2);
  const [erro, setErro] = useState<string | null>(null);
  const mesmoSitio = destino === contentorAtual.id && canister === lote.canister && andar === lote.andar;

  const submeter = async () => {
    if (mesmoSitio) return setErro(t("web.map.error.same_place"));
    try {
      await mover.mutateAsync({ lote_id: lote.id, quantidade: qtd, contentor_id: destino, canister, andar });
      const cod = todos.find((c) => c.id === destino)?.codigo ?? contentorAtual.codigo;
      notifySuccess(t("web.map.moved", { q: qtd, code: cod, c: canister, a: andar }));
      onDone();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <>
      <div style={{ fontWeight: 600, fontSize: 15 }}>{t("web.map.move_title", { garanhao: lote.garanhao })}</div>
      <div style={{ color: "#999", fontSize: 12, marginBottom: 6 }}>
        {t("web.map.move_current", { code: contentorAtual.codigo, c: lote.canister ?? "—", a: lote.andar ?? "—" })}
      </div>
      <List style={{ "--border-top": "none", "--prefix-width": "7.5em" } as React.CSSProperties}>
        <List.Item prefix={t("web.map.dest_container")} arrow>
          <SeletorPesquisa<number>
            titulo={t("web.map.dest_container")}
            value={destino}
            onChange={(v) => {
              setDestino(v);
              setErro(null);
            }}
            opcoes={todos.map((c) => ({ value: c.id, label: c.codigo }))}
          />
        </List.Item>
        <List.Item
          prefix={t("label.quantity")}
          extra={<Stepper min={1} max={lote.existencia_atual} digits={0} value={qtd} onChange={setQtd} />}
          description={t("web.transfer.of_max", { max: lote.existencia_atual })}
        />
        <List.Item prefix={t("web.map.dest_canister")} arrow>
          <PickerCampo<number>
            titulo={t("web.map.dest_canister")}
            value={canister}
            onChange={(v) => {
              setCanister(v);
              setErro(null);
            }}
            opcoes={CANISTERS.map((c) => ({ value: Number(c), label: c }))}
          />
        </List.Item>
        <List.Item prefix={t("web.map.dest_floor")}>
          <Selector
            showCheckMark={false}
            value={[andar]}
            onChange={(v) => {
              if (!v[0]) return;
              setAndar(v[0]);
              setErro(null);
            }}
            options={[
              { value: 1 as const, label: "1º" },
              { value: 2 as const, label: "2º" },
            ]}
          />
        </List.Item>
      </List>
      {erro && <div style={{ color: "var(--adm-color-warning)", marginTop: 8 }}>{erro}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <Button block onClick={onDone}>
          {t("web.common.cancel")}
        </Button>
        <Button block color="primary" loading={mover.isPending} onClick={submeter}>
          {t("web.map.move_btn")}
        </Button>
      </div>
    </>
  );
}

function EditarContentorMobile({
  contentor,
  palhetas,
  onDeleted,
}: {
  contentor: { id: number; codigo: string; descricao: string | null };
  palhetas: number;
  onDeleted: () => void;
}) {
  const t = useT();
  const notifyError = useNotifyError();
  const editar = useEditarContentor();
  const apagar = useApagarContentor();
  const [form] = Form.useForm<{ codigo: string; descricao: string }>();

  const guardar = async (v: { codigo: string; descricao?: string }) => {
    try {
      await editar.mutateAsync({ id: contentor.id, codigo: v.codigo, descricao: v.descricao ?? "" });
      notifySuccess(t("map.container_updated"));
    } catch (err) {
      notifyError(err);
    }
  };

  const confirmarApagar = () =>
    Dialog.confirm({
      title: t("web.map.delete"),
      content: t("web.map.delete_confirm", { code: contentor.codigo }),
      confirmText: <span style={{ color: "var(--adm-color-danger)" }}>{t("web.map.delete")}</span>,
      cancelText: t("web.common.cancel"),
      onConfirm: async () => {
        try {
          await apagar.mutateAsync(contentor.id);
          notifySuccess(t("web.map.deleted"));
          onDeleted();
        } catch (err) {
          notifyError(err);
        }
      },
    });

  return (
    <>
      <Cabecalho>{t("map.edit_container_title")}</Cabecalho>
      <Form
        form={form}
        layout="horizontal"
        onFinish={guardar}
        initialValues={{ codigo: contentor.codigo, descricao: contentor.descricao ?? "" }}
        style={{ "--prefix-width": "7.5em" } as React.CSSProperties}
      >
        <Form.Item
          name="codigo"
          label={t("label.code")}
          rules={[{ required: true, whitespace: true, message: t("map.container_code_required_error") }]}
        >
          <Input clearable />
        </Form.Item>
        <Form.Item name="descricao" label={t("label.description")}>
          <Input clearable />
        </Form.Item>
      </Form>
      <div style={{ display: "flex", gap: 8, padding: 12 }}>
        {/* Só dá para apagar um contentor sem sémen. */}
        <Button block color="danger" fill="outline" disabled={palhetas > 0} onClick={() => void confirmarApagar()}>
          {t("web.map.delete")}
        </Button>
        <Button block color="primary" loading={editar.isPending} onClick={() => form.submit()}>
          {t("btn.save")}
        </Button>
      </div>
      {palhetas > 0 && <div style={{ padding: "0 12px 16px", color: "#999", fontSize: 12 }}>{t("map.delete_blocked")}</div>}
    </>
  );
}
