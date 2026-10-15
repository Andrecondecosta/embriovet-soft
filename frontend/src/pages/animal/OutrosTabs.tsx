import dayjs from "dayjs";
import { Alert, Button, Card, Col, DatePicker, Flex, Form, Input, Row, Space, Statistic, Steps, Table, Tag, Typography } from "antd";
import { Button as MButton, Dialog, Form as MForm, Grid, Input as MInput, List, Steps as MSteps, Tag as MTag } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { dataCurta } from "../../components/csv";
import { confirmar, notifySuccess, useNotifyError } from "../../components/errors";
import { Cabecalho, DataCampo, abrirAoTocar } from "../../components/mobile";
import {
  useAlertas,
  useEstadiasAnimal,
  useFertilidade,
  useGuardarAcompanhamento,
  useProducao,
  useReprodutivo,
  useResultado,
  type Acompanhamento,
  type Animal,
  type Inseminacao,
} from "./api";

const COR_RESULTADO: Record<string, string> = { pendente: "default", gestacao_confirmada: "success", falhou: "error" };
const COR_RESULTADO_M: Record<string, "default" | "success" | "danger"> = {
  pendente: "default",
  gestacao_confirmada: "success",
  falhou: "danger",
};

/** Números grandes no topo (KPIs) — Statistic no computador, grelha no telemóvel. */
function Kpis({ itens }: { itens: [string, string | number][] }) {
  const isMobile = useIsMobile();
  if (isMobile)
    return (
      <Grid columns={Math.min(itens.length, 3)} style={{ background: "#fff", padding: "10px 4px", rowGap: 10 }}>
        {itens.map(([label, n]) => (
          <Grid.Item key={label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{n}</div>
            <div style={{ fontSize: 10, color: "#999" }}>{label}</div>
          </Grid.Item>
        ))}
      </Grid>
    );
  return (
    <Flex gap={40} wrap style={{ marginBottom: 12 }}>
      {itens.map(([label, n]) => (
        <Statistic key={label} title={label} value={n} />
      ))}
    </Flex>
  );
}

function usePalhetas() {
  const t = useT();
  return (i: Inseminacao) => `${i.palhetas_gastas ?? 0}${i.num_lotes > 1 ? ` (${t("web.animal.lots_n", { n: i.num_lotes })})` : ""}`;
}

// ── Historial reprodutivo (égua) ────────────────────────────────────────────

export function ReprodutivoTab({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const q = useReprodutivo(animal.id);
  const registar = useResultado(animal.id);
  const palhetas = usePalhetas();
  const d = q.data;
  const res = (r: string) => t(`web.animal.result.${r}`);

  /** Resultado +/− de uma inseminação pendente (etapa D+14/28/45 pelos dias). */
  const resultado = (i: Inseminacao, r: "positivo" | "negativo") => {
    const rotulo = t(r === "positivo" ? "web.animal.result.positive" : "web.animal.result.negative", { etapa: i.etapa ?? "" });
    const fazer = async () => {
      try {
        await registar.mutateAsync({ op_key: i.op_key!, resultado: r });
        notifySuccess(t(r === "positivo" ? "web.animal.result.saved_pos" : "web.animal.result.saved_neg"));
      } catch (err) {
        notifyError(err);
      }
    };
    const texto = t("web.animal.result.confirm", { res: rotulo, data: dataCurta(i.data_inseminacao) });
    if (isMobile) void Dialog.confirm({ content: texto, confirmText: "OK", cancelText: t("web.common.cancel"), onConfirm: fazer });
    else confirmar({ titulo: rotulo, texto, ok: "OK", cancelar: t("web.common.cancel"), perigo: r === "negativo", onOk: fazer });
  };

  const kpis: [string, string | number][] = [
    [t("web.animal.kpi.inseminations"), d?.total ?? "—"],
    [t("web.animal.kpi.pregnancies"), d?.gestacoes ?? "—"],
    [t("web.animal.kpi.success"), d?.taxa != null ? `${d.taxa} %` : "—"],
  ];

  if (isMobile)
    return (
      <>
        <Kpis itens={kpis} />
        <List style={{ marginTop: 8 }}>
          {!d?.inseminacoes.length ? (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.animal.no_inseminations")}</span>
            </List.Item>
          ) : (
            d.inseminacoes.map((i) => (
              <List.Item
                key={i.op_key}
                description={
                  <>
                    {i.garanhao ?? "—"} · {i.proprietario ?? "—"} · {palhetas(i)}
                    {i.pode_resultado && (
                      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                        <MButton size="mini" color="success" fill="outline" onClick={() => resultado(i, "positivo")}>
                          ✓ {t("web.animal.result.positive", { etapa: i.etapa ?? "" })}
                        </MButton>
                        <MButton size="mini" color="danger" fill="outline" onClick={() => resultado(i, "negativo")}>
                          ✗ {t("web.animal.result.negative", { etapa: i.etapa ?? "" })}
                        </MButton>
                      </div>
                    )}
                  </>
                }
                extra={<MTag color={COR_RESULTADO_M[i.resultado] ?? "default"}>{res(i.resultado)}</MTag>}
              >
                {dataCurta(i.data_inseminacao)}
              </List.Item>
            ))
          )}
        </List>
      </>
    );

  return (
    <>
      <Kpis itens={kpis} />
      <Table<Inseminacao>
        size="small"
        bordered
        rowKey={(i) => String(i.op_key)}
        loading={q.isPending}
        dataSource={d?.inseminacoes ?? []}
        pagination={false}
        locale={{ emptyText: t("web.animal.no_inseminations") }}
        columns={[
          { title: t("web.animal.col.date"), dataIndex: "data_inseminacao", width: 100, render: dataCurta },
          { title: t("web.animal.col.stallion"), dataIndex: "garanhao", render: (v) => v ?? "—" },
          { title: t("web.animal.col.owner"), dataIndex: "proprietario", render: (v) => v ?? "—" },
          { title: t("web.animal.col.straws"), key: "p", width: 110, render: (_, i) => palhetas(i) },
          {
            title: t("web.animal.col.result"),
            dataIndex: "resultado",
            width: 120,
            render: (r) => <Tag color={COR_RESULTADO[r]}>{res(r)}</Tag>,
          },
          { title: t("web.animal.col.notes"), dataIndex: "observacoes", ellipsis: true, render: (v) => v ?? "—" },
          {
            key: "acoes",
            width: 230,
            render: (_, i) =>
              i.pode_resultado && (
                <Space size={4}>
                  <Button size="small" onClick={() => resultado(i, "positivo")}>
                    ✓ {t("web.animal.result.positive", { etapa: i.etapa ?? "" })}
                  </Button>
                  <Button size="small" danger onClick={() => resultado(i, "negativo")}>
                    ✗ {t("web.animal.result.negative", { etapa: i.etapa ?? "" })}
                  </Button>
                </Space>
              ),
          },
        ]}
      />
    </>
  );
}

// ── Estadias (égua) + acompanhamento pós-inseminação ────────────────────────

const ETAPAS: [keyof Acompanhamento, string][] = [
  ["data_inseminacao", "web.animal.followup.insemination"],
  ["data_1o_diagnostico", "web.animal.followup.first"],
  ["data_confirmacao", "web.animal.followup.confirm"],
  ["data_2a_confirmacao", "web.animal.followup.second"],
  ["data_parto_previsto", "web.animal.followup.birth"],
];

export function EstadiasAnimalTab({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const q = useEstadiasAnimal(animal.id);
  const guardar = useGuardarAcompanhamento(animal.id);
  const [form] = Form.useForm();
  const [mform] = MForm.useForm();
  const a = q.data?.acompanhamento;
  const iso = (v: unknown) => (v ? dayjs(v as string).format("YYYY-MM-DD") : null);

  const submeter = async (v: Record<string, unknown>) => {
    try {
      await guardar.mutateAsync({
        garanhao: (v.garanhao as string) ?? null,
        ...(Object.fromEntries(ETAPAS.map(([k]) => [k, iso(v[k])])) as Record<string, string | null>),
      } as never);
      notifySuccess(t("web.animal.followup.saved"));
    } catch (err) {
      notifyError(err);
    }
  };
  const motivo = (m: string | null) => (m ? t(`web.stays.reason.${m}`) : "—");
  const estado = (s: string | null) => (s ? t(`web.stays.state.${s}`) : "—");
  const passo = ETAPAS.reduce((n, [k], i) => (a?.[k] ? i : n), -1);

  if (isMobile)
    return (
      <>
        <List>
          {!q.data?.estadias.length ? (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.animal.no_stays")}</span>
            </List.Item>
          ) : (
            q.data.estadias.map((e, i) => (
              <List.Item
                key={i}
                description={`${motivo(e.motivo)} · ${dataCurta(e.data_entrada)} → ${e.data_saida ? dataCurta(e.data_saida) : t("web.stays.in_progress")}`}
                extra={<MTag fill="outline">{estado(e.estado)}</MTag>}
              >
                {t(`web.stays.kind.${e.tipo_registo}`)} · {e.dias ?? 0} d
              </List.Item>
            ))
          )}
        </List>
        {a && (
          <>
            <Cabecalho>{t("web.animal.followup")}</Cabecalho>
            <div style={{ background: "#fff", padding: "8px 4px" }}>
              <MSteps direction="vertical" current={passo}>
                {ETAPAS.map(([k, l]) => (
                  <MSteps.Step key={k} title={t(l)} description={a[k] ? dataCurta(a[k] as string) : "—"} />
                ))}
              </MSteps>
            </div>
            <MForm
              form={mform}
              layout="horizontal"
              style={{ "--prefix-width": "9em" } as React.CSSProperties}
              initialValues={a}
              onFinish={submeter}
            >
              <MForm.Item name="garanhao" label={t("web.animal.col.stallion")}>
                <MInput clearable />
              </MForm.Item>
              {ETAPAS.map(([k, l]) => (
                <MForm.Item key={k} name={k} label={t(l)} arrow onClick={abrirAoTocar}>
                  <DataCampo limpar />
                </MForm.Item>
              ))}
            </MForm>
            <div style={{ padding: 12 }}>
              <MButton block color="primary" loading={guardar.isPending} onClick={() => mform.submit()}>
                {t("web.animal.followup.save")}
              </MButton>
            </div>
          </>
        )}
      </>
    );

  return (
    <Space orientation="vertical" size={16} style={{ width: "100%" }}>
      <Table
        size="small"
        bordered
        rowKey={(_, i) => String(i)}
        loading={q.isPending}
        dataSource={q.data?.estadias ?? []}
        pagination={false}
        locale={{ emptyText: t("web.animal.no_stays") }}
        columns={[
          { title: t("web.stays.col.type"), dataIndex: "tipo_registo", render: (v) => t(`web.stays.kind.${v}`) },
          { title: t("web.stays.col.reason"), dataIndex: "motivo", render: motivo },
          { title: t("web.stays.col.state"), dataIndex: "estado", render: (v) => <Tag>{estado(v)}</Tag> },
          { title: t("web.stays.col.entry"), dataIndex: "data_entrada", render: dataCurta },
          { title: t("web.stays.col.exit"), dataIndex: "data_saida", render: (v) => (v ? dataCurta(v) : t("web.stays.in_progress")) },
          { title: t("web.animal.col.days"), dataIndex: "dias", align: "right" },
        ]}
      />
      {a && (
        <Card
          size="small"
          title={t("web.animal.followup")}
          extra={<Typography.Text type="secondary">{t("web.animal.followup_help", { data: dataCurta(a.data_entrada) })}</Typography.Text>}
        >
          <Steps
            size="small"
            current={passo}
            style={{ marginBottom: 16 }}
            items={ETAPAS.map(([k, l]) => ({ title: t(l), content: a[k] ? dataCurta(a[k] as string) : "—" }))}
          />
          <Form
            form={form}
            layout="vertical"
            initialValues={{ garanhao: a.garanhao, ...Object.fromEntries(ETAPAS.map(([k]) => [k, a[k] ? dayjs(a[k] as string) : null])) }}
            onFinish={submeter}
          >
            <Row gutter={12}>
              <Col xs={24} sm={8}>
                <Form.Item name="garanhao" label={t("web.animal.col.stallion")}>
                  <Input />
                </Form.Item>
              </Col>
              {ETAPAS.map(([k, l]) => (
                <Col key={k} xs={12} sm={8}>
                  <Form.Item name={k} label={t(l)}>
                    <DatePicker format="DD/MM/YYYY" style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              ))}
            </Row>
            <Button type="primary" htmlType="submit" loading={guardar.isPending}>
              {t("web.animal.followup.save")}
            </Button>
          </Form>
        </Card>
      )}
    </Space>
  );
}

// ── Garanhão ────────────────────────────────────────────────────────────────

export function ProducaoTab({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const q = useProducao(animal.id);
  const k = q.data?.kpis;
  const origem = (o: unknown) => (o ? t("web.animal.prod.external", { origem: String(o) }) : t("web.animal.prod.internal"));
  const local = (l: Record<string, unknown>) => (l.contentor ? `${l.contentor} · C${l.canister ?? "?"} / A${l.andar ?? "?"}` : "—");
  const kpis: [string, string | number][] = [
    [t("web.animal.prod.kpi.straws"), k?.palhetas ?? "—"],
    [t("web.animal.prod.kpi.lots"), k?.lotes ?? "—"],
    [t("web.animal.prod.kpi.motility"), k?.motilidade ?? "—"],
    [t("web.animal.prod.kpi.internal"), k?.internas ?? "—"],
    [t("web.animal.prod.kpi.external"), k?.externas ?? "—"],
  ];
  const lotes = q.data?.lotes ?? [];

  if (isMobile)
    return (
      <>
        <Kpis itens={kpis} />
        <List style={{ marginTop: 8 }}>
          {!lotes.length ? (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.animal.prod.no_lots")}</span>
            </List.Item>
          ) : (
            lotes.map((l, i) => (
              <List.Item
                key={i}
                description={`${origem(l.origem_externa)} · ${l.proprietario ?? "—"} · ${local(l)} · M ${l.motilidade ?? 0}%`}
                extra={`${l.palhetas_restantes ?? 0}/${l.palhetas_iniciais ?? 0}`}
              >
                {l.data_producao ? String(l.data_producao) : "—"}
              </List.Item>
            ))
          )}
        </List>
      </>
    );

  return (
    <>
      <Kpis itens={kpis} />
      <Table
        size="small"
        bordered
        rowKey={(_, i) => String(i)}
        loading={q.isPending}
        dataSource={lotes}
        pagination={false}
        scroll={{ x: true }}
        locale={{ emptyText: t("web.animal.prod.no_lots") }}
        columns={[
          { title: t("web.animal.prod.col.date"), dataIndex: "data_producao", render: (v) => v ?? "—" },
          { title: t("web.animal.prod.col.origin"), dataIndex: "origem_externa", render: origem },
          { title: t("web.animal.col.owner"), dataIndex: "proprietario", render: (v) => v ?? "—" },
          { title: t("web.animal.prod.col.initial"), dataIndex: "palhetas_iniciais", align: "right" },
          { title: t("web.animal.prod.col.left"), dataIndex: "palhetas_restantes", align: "right" },
          { title: t("stock.motility_label"), dataIndex: "motilidade", align: "right", render: (v) => (v == null ? "—" : `${v}%`) },
          { title: t("stock.concentration_label"), dataIndex: "concentracao", align: "right", render: (v) => v ?? "—" },
          { title: t("stock.quality_label"), dataIndex: "qualidade", render: (v) => v || "—" },
          { title: t("web.animal.prod.col.location"), key: "local", render: (_, l) => local(l) },
        ]}
      />
    </>
  );
}

export function FertilidadeTab({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const q = useFertilidade(animal.id);
  const palhetas = usePalhetas();
  const d = q.data;
  const res = (r: string) => t(`web.animal.result.${r}`);
  const kpis: [string, string | number][] = [
    [t("web.animal.kpi.inseminations"), d?.total ?? "—"],
    [t("web.animal.kpi.pregnancies"), d?.gestacoes ?? "—"],
    [t("web.animal.kpi.fertility"), d?.taxa != null ? `${d.taxa} %` : "—"],
  ];

  if (isMobile)
    return (
      <>
        <Kpis itens={kpis} />
        <List style={{ marginTop: 8 }}>
          {!d?.inseminacoes.length ? (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.animal.no_inseminations")}</span>
            </List.Item>
          ) : (
            d.inseminacoes.map((i, n) => (
              <List.Item
                key={n}
                description={`${i.proprietario ?? "—"} · ${palhetas(i)}`}
                extra={<MTag color={COR_RESULTADO_M[i.resultado] ?? "default"}>{res(i.resultado)}</MTag>}
              >
                {dataCurta(i.data_inseminacao)} · {i.egua ?? "—"}
              </List.Item>
            ))
          )}
        </List>
      </>
    );

  return (
    <>
      <Kpis itens={kpis} />
      <Table<Inseminacao>
        size="small"
        bordered
        rowKey={(_, i) => String(i)}
        loading={q.isPending}
        dataSource={d?.inseminacoes ?? []}
        pagination={false}
        locale={{ emptyText: t("web.animal.no_inseminations") }}
        columns={[
          { title: t("web.animal.col.date"), dataIndex: "data_inseminacao", width: 100, render: dataCurta },
          { title: t("web.animal.col.mare"), dataIndex: "egua", render: (v) => v ?? "—" },
          { title: t("web.animal.col.owner"), dataIndex: "proprietario", render: (v) => v ?? "—" },
          { title: t("web.animal.col.straws"), key: "p", width: 110, render: (_, i) => palhetas(i) },
          {
            title: t("web.animal.col.result"),
            dataIndex: "resultado",
            width: 120,
            render: (r) => <Tag color={COR_RESULTADO[r]}>{res(r)}</Tag>,
          },
        ]}
      />
    </>
  );
}

export function AlertasTab({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const q = useAlertas(animal.id);
  const tipo = { erro: "error", aviso: "warning", info: "info", ok: "success" } as const;
  const lista = (q.data ?? []).map((a) => ({
    ...a,
    texto: t(a.chave, { ...a.params, ...(a.params.data ? { data: dataCurta(String(a.params.data)) } : {}) }),
  }));

  if (!q.data) return null;
  if (!lista.length)
    return isMobile ? (
      <div style={{ padding: 16, color: "#999" }}>{t("web.animal.alert.none")}</div>
    ) : (
      <Typography.Text type="secondary">{t("web.animal.alert.none")}</Typography.Text>
    );
  return (
    <Space orientation="vertical" style={{ width: "100%", padding: isMobile ? 12 : 0 }}>
      {lista.map((a) => (
        <Alert key={a.chave} type={tipo[a.nivel]} showIcon title={a.texto} />
      ))}
    </Space>
  );
}
