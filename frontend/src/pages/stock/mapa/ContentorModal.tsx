import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Tooltip,
  Typography,
} from "antd";
import { SwapOutlined, VerticalAlignMiddleOutlined } from "@ant-design/icons";

import { useT } from "../../../i18n/I18n";
import { useBrand } from "../../../components/Brand";
import { useIsMobile } from "../../../components/responsive";
import { confirmar, notifySuccess, useNotifyError } from "../../../components/errors";
import { CANISTERS } from "../LoteForm";
import {
  refCurta,
  useApagarContentor,
  useEditarContentor,
  useInverterAndares,
  useMoverPalhetas,
  useStockContentor,
  type Contentor,
  type LoteContentor,
} from "./api";
import { ContentorMobile } from "./MapaMobile";

export const valido = (l: LoteContentor) => !!l.canister && !!l.andar;

/** Interior de um contentor — equivalente ao diálogo "Ver interior" da app atual. */
export function ContentorModal({ contentor, todos, onClose }: { contentor: Contentor | null; todos: Contentor[]; onClose: () => void }) {
  const isMobile = useIsMobile();
  const { data } = useStockContentor(contentor?.id ?? null);
  if (isMobile) return <ContentorMobile contentor={contentor} todos={todos} onClose={onClose} />;
  // Título com o código atual (depois de editar, muda logo).
  const titulo = data?.contentor.codigo ?? contentor?.codigo;
  return (
    <Modal open={contentor !== null} onCancel={onClose} title={titulo} footer={null} width={760} destroyOnHidden>
      {contentor && <Interior contentor={contentor} todos={todos} onClose={onClose} />}
    </Modal>
  );
}

function Interior({ contentor, todos, onClose }: { contentor: Contentor; todos: Contentor[]; onClose: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const { data, isPending } = useStockContentor(contentor.id);
  const [andar, setAndar] = useState<1 | 2>(1);
  const [canister, setCanister] = useState<number | null>(null);
  const [aMover, setAMover] = useState<LoteContentor | null>(null);
  const [confirmarInverter, setConfirmarInverter] = useState(false);
  const inverter = useInverterAndares();

  const lotes = data?.lotes ?? [];
  const semLugar = lotes.filter((l) => !valido(l));

  // Mudar de andar fecha o formulário de mover (o lote pode já não estar lá).
  useEffect(() => setAMover(null), [andar]);

  const fazerInverter = async () => {
    try {
      const r = await inverter.mutateAsync(contentor.id);
      notifySuccess(t("web.map.inverted", { count: r.count }));
    } catch (err) {
      notifyError(err);
    }
    setConfirmarInverter(false);
  };

  if (isPending || !data) return <Spin style={{ display: "block", margin: 32 }} />;

  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      {contentor.descricao && <Typography.Text type="secondary">{contentor.descricao}</Typography.Text>}

      {!lotes.length ? (
        <Typography.Text type="secondary">{t("web.map.no_lots")}</Typography.Text>
      ) : (
        <>
          <Flex justify="space-between" gap={8} wrap>
            <Segmented
              value={andar}
              onChange={(v) => setAndar(v as 1 | 2)}
              options={[
                { value: 1, label: t("web.map.floor", { n: 1 }) },
                { value: 2, label: t("web.map.floor", { n: 2 }) },
              ]}
            />
            <Tooltip title={t("web.map.invert_help")}>
              <Button icon={<VerticalAlignMiddleOutlined />} onClick={() => setConfirmarInverter(true)}>
                {t("web.map.invert")}
              </Button>
            </Tooltip>
          </Flex>

          {confirmarInverter && (
            <Alert
              type="warning"
              showIcon
              title={t("web.map.invert_confirm", { code: data.contentor.codigo })}
              action={
                <Space orientation="vertical">
                  <Button size="small" type="primary" onClick={fazerInverter} loading={inverter.isPending}>
                    {t("btn.confirm")}
                  </Button>
                  <Button size="small" onClick={() => setConfirmarInverter(false)}>
                    {t("web.common.cancel")}
                  </Button>
                </Space>
              }
            />
          )}

          <Tanque lotes={lotes} andar={andar} selecionado={canister} onSelecionar={setCanister} />

          {canister !== null && (
            <BlocoCanister
              titulo={t("web.map.canister", { n: canister })}
              lotes={lotes.filter((l) => l.canister === canister && l.andar === andar)}
              onMover={setAMover}
            />
          )}

          {/* Lotes sem canister/andar: a app atual escondia-os do tanque; aqui
              aparecem à parte, para se poderem arrumar com "Mover". */}
          {semLugar.length > 0 && <BlocoCanister titulo={t("web.map.no_place")} lotes={semLugar} onMover={setAMover} />}

          {aMover && (
            <MoverForm key={aMover.id} lote={aMover} contentorAtual={data.contentor} todos={todos} onDone={() => setAMover(null)} />
          )}
        </>
      )}

      <EditarContentor contentor={data.contentor} palhetas={data.palhetas} onDeleted={onClose} />
    </Space>
  );
}

/** Vista redonda do contentor: os canisters com sémen (em qualquer andar)
 *  em círculo; cheios no andar escolhido aparecem na cor da marca. */
export function Tanque({
  lotes,
  andar,
  selecionado,
  onSelecionar,
}: {
  lotes: LoteContentor[];
  andar: 1 | 2;
  selecionado: number | null;
  onSelecionar: (c: number) => void;
}) {
  const t = useT();
  const isMobile = useIsMobile();
  const { primary_color } = useBrand();

  const { canisters, qtd, nomes } = useMemo(() => {
    const qtd = new Map<string, number>();
    const nomes = new Map<string, string[]>();
    const set = new Set<number>();
    for (const l of lotes.filter(valido)) {
      const k = `${l.canister}-${l.andar}`;
      qtd.set(k, (qtd.get(k) ?? 0) + l.existencia_atual);
      nomes.set(k, [...(nomes.get(k) ?? []), l.garanhao]);
      set.add(l.canister!);
    }
    return { canisters: [...set].sort((a, b) => a - b), qtd, nomes };
  }, [lotes]);

  if (!canisters.length) return null;

  const D = isMobile ? 240 : 272;
  const R = D * (100 / 272);
  const slot = isMobile ? 56 : 64;
  const nLotesAndar = lotes.filter((l) => l.andar === andar).length;

  return (
    <Flex vertical align="center" gap={6}>
      <div
        style={{
          position: "relative",
          width: D,
          height: D,
          borderRadius: "50%",
          border: "2px solid #d9d9d9",
          background: "#fafafa",
        }}
      >
        <Flex vertical align="center" justify="center" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
          <Typography.Text strong style={{ fontSize: 26, lineHeight: 1 }}>
            {nLotesAndar}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {nLotesAndar === 1 ? t("web.map.lot_one") : t("web.map.lot_many")}
          </Typography.Text>
        </Flex>
        {canisters.map((c, i) => {
          const ang = ((i * 360) / canisters.length - 90) * (Math.PI / 180);
          const k = `${c}-${andar}`;
          const q = qtd.get(k) ?? 0;
          const ns = nomes.get(k) ?? [];
          const cheio = q > 0;
          const sel = selecionado === c;
          return (
            <button
              key={c}
              type="button"
              onClick={() => onSelecionar(c)}
              title={`C${c} / A${andar}: ${q} ${t("label.straws")}`}
              style={{
                position: "absolute",
                left: D / 2 + R * Math.cos(ang),
                top: D / 2 + R * Math.sin(ang),
                width: slot,
                height: slot,
                transform: `translate(-50%, -50%) scale(${sel ? 1.08 : 1})`,
                borderRadius: "50%",
                background: cheio ? `${primary_color}29` : "#f5f5f5",
                border: `${sel ? 2.5 : 1.5}px solid ${cheio ? `${primary_color}8c` : "#d9d9d9"}`,
                outline: sel ? `2px solid ${primary_color}` : undefined,
                outlineOffset: 2,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                padding: 0,
                transition: "transform .12s",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: -8,
                  background: "#141414",
                  color: "#fff",
                  fontSize: 10,
                  fontWeight: 700,
                  borderRadius: 999,
                  padding: "1px 6px",
                }}
              >
                C{c}
              </span>
              {cheio ? (
                <>
                  <span style={{ fontWeight: 800, color: primary_color, lineHeight: 1, fontSize: isMobile ? 15 : 17 }}>{q}</span>
                  <span
                    style={{
                      fontSize: 9,
                      color: "rgba(0,0,0,.45)",
                      maxWidth: slot - 10,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {ns.length === 1 ? ns[0] : t("web.map.lots_count", { count: ns.length })}
                  </span>
                </>
              ) : (
                <span style={{ width: 6, height: 6, borderRadius: 3, background: "#bfbfbf" }} />
              )}
            </button>
          );
        })}
      </div>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {t("web.map.tank_hint")}
      </Typography.Text>
      <Space size="middle">
        <Space size={6}>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              borderRadius: 6,
              background: `${primary_color}29`,
              border: `1.5px solid ${primary_color}8c`,
            }}
          />
          <Typography.Text style={{ fontSize: 12 }}>{t("web.map.legend_full")}</Typography.Text>
        </Space>
        <Space size={6}>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              borderRadius: 6,
              background: "#f5f5f5",
              border: "1.5px solid #d9d9d9",
            }}
          />
          <Typography.Text style={{ fontSize: 12 }}>{t("web.map.legend_empty")}</Typography.Text>
        </Space>
      </Space>
    </Flex>
  );
}

function BlocoCanister({ titulo, lotes, onMover }: { titulo: string; lotes: LoteContentor[]; onMover: (l: LoteContentor) => void }) {
  const t = useT();
  return (
    <Card size="small" title={titulo}>
      {!lotes.length ? (
        <Typography.Text type="secondary">{t("web.map.empty_floor")}</Typography.Text>
      ) : (
        <Collapse
          size="small"
          ghost
          items={lotes.map((l) => ({
            key: l.id,
            label: (
              <div>
                <Typography.Text strong>{l.garanhao}</Typography.Text>
                <div>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {l.proprietario_nome ?? t("common.no_owner")} · {refCurta(l)} · {l.existencia_atual} {t("label.straws")}
                  </Typography.Text>
                </div>
              </div>
            ),
            children: (
              <Flex justify="space-between" align="flex-start" gap={8}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t("web.map.harvest")}: {l.data_embriovet || "—"} · {t("stock.quality_label")}: {l.qualidade || "—"} ·{" "}
                  {t("stock.motility_label")}: {l.motilidade ?? 0}% · {t("stock.concentration_label")}: {l.concentracao ?? 0}M/ml
                </Typography.Text>
                <Button size="small" icon={<SwapOutlined />} onClick={() => onMover(l)} style={{ flexShrink: 0 }}>
                  {t("web.map.move")}
                </Button>
              </Flex>
            ),
          }))}
        />
      )}
    </Card>
  );
}

/** Mover palhetas para outro canister/andar/contentor — arrumação física:
 *  o dono não muda e não fica registo em transferências. */
function MoverForm({
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
  const isMobile = useIsMobile();
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
    <Card
      size="small"
      title={t("web.map.move_title", { garanhao: lote.garanhao })}
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t("web.map.move_current", { code: contentorAtual.codigo, c: lote.canister ?? "—", a: lote.andar ?? "—" })}
        </Typography.Text>
      }
      styles={{ body: { background: "#fafafa" } }}
    >
      <Row gutter={[12, 8]}>
        <Col xs={24} sm={12}>
          <Typography.Text type="secondary">{t("web.map.dest_container")}</Typography.Text>
          <Select
            showSearch
            optionFilterProp="label"
            style={{ width: "100%" }}
            value={destino}
            onChange={setDestino}
            options={todos.map((c) => ({ value: c.id, label: c.codigo }))}
          />
        </Col>
        <Col xs={24} sm={12}>
          <Typography.Text type="secondary">
            {t("label.quantity")} ({t("web.transfer.of_max", { max: lote.existencia_atual })})
          </Typography.Text>
          <InputNumber
            min={1}
            max={lote.existencia_atual}
            style={{ width: "100%" }}
            value={qtd}
            onChange={(v) => setQtd(Number(v) || 1)}
            inputMode="numeric"
          />
        </Col>
        <Col xs={12} sm={12}>
          <Typography.Text type="secondary">{t("web.map.dest_canister")}</Typography.Text>
          <Select
            style={{ width: "100%" }}
            value={canister}
            onChange={setCanister}
            options={CANISTERS.map((c) => ({ value: Number(c), label: c }))}
          />
        </Col>
        <Col xs={12} sm={12}>
          <Typography.Text type="secondary">{t("web.map.dest_floor")}</Typography.Text>
          <Segmented
            block
            value={andar}
            onChange={(v) => setAndar(v as 1 | 2)}
            options={[
              { value: 1, label: "1º" },
              { value: 2, label: "2º" },
            ]}
          />
        </Col>
      </Row>
      {erro && <Alert type="warning" showIcon title={erro} style={{ marginTop: 8 }} />}
      <Flex gap={8} justify="flex-end" style={{ marginTop: 12 }}>
        <Button onClick={onDone} block={isMobile}>
          {t("web.common.cancel")}
        </Button>
        <Button type="primary" onClick={submeter} loading={mover.isPending} block={isMobile}>
          {t("web.map.move_btn")}
        </Button>
      </Flex>
    </Card>
  );
}

function EditarContentor({
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

  const guardar = async (v: { codigo: string; descricao?: string }) => {
    try {
      await editar.mutateAsync({ id: contentor.id, codigo: v.codigo, descricao: v.descricao ?? "" });
      notifySuccess(t("map.container_updated"));
    } catch (err) {
      notifyError(err);
    }
  };

  const confirmarApagar = () =>
    confirmar({
      titulo: t("web.map.delete"),
      texto: t("web.map.delete_confirm", { code: contentor.codigo }),
      ok: t("web.map.delete"),
      cancelar: t("web.common.cancel"),
      perigo: true,
      onOk: async () => {
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
    <Collapse
      size="small"
      items={[
        {
          key: "editar",
          label: t("map.edit_container_title"),
          children: (
            <Form layout="vertical" onFinish={guardar} initialValues={{ codigo: contentor.codigo, descricao: contentor.descricao ?? "" }}>
              <Row gutter={12}>
                <Col xs={24} sm={12}>
                  <Form.Item
                    name="codigo"
                    label={t("label.code")}
                    rules={[{ required: true, whitespace: true, message: t("map.container_code_required_error") }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="descricao" label={t("label.description")}>
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
              <Flex justify="space-between">
                {/* Só dá para apagar um contentor sem sémen (a contagem é a atual,
                    já depois de mover palhetas para fora). */}
                <Tooltip title={palhetas > 0 ? t("map.delete_blocked") : undefined}>
                  <Button danger type="text" onClick={confirmarApagar} disabled={palhetas > 0}>
                    {t("web.map.delete")}
                  </Button>
                </Tooltip>
                <Button type="primary" htmlType="submit" loading={editar.isPending}>
                  {t("btn.save")}
                </Button>
              </Flex>
            </Form>
          ),
        },
      ]}
    />
  );
}
