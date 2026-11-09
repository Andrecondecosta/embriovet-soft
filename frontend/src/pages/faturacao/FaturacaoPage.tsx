import { useMemo, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import dayjs, { type Dayjs } from "dayjs";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  DatePicker,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { CheckOutlined, DownloadOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  CapsuleTabs,
  Checkbox as MCheckbox,
  DotLoading,
  ErrorBlock,
  Form as MForm,
  Input as MInput,
  List,
  SearchBar,
  Selector,
  Space as MSpace,
  Switch as MSwitch,
  Tag as MTag,
  TextArea,
} from "antd-mobile";

import { ApiError } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { PageHeader } from "../../components/ds";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../components/errors";
import { DataCampo, FolhaEcraInteiro, abrirAoTocar, irParaErro } from "../../components/mobile";
import { baixarCsv, dataCurta } from "../../components/csv";
import { useOpcoes } from "../stock/api";
import {
  useAnos,
  useAnularFaturada,
  useFaturado,
  useFaturar,
  usePorFaturar,
  type CelulaAno,
  type Faturada,
  type LinhaAno,
  type PorFaturar,
  type TipoFat,
} from "./api";

const TABS = ["anos", "por-faturar", "faturado"] as const;
const ISO = "YYYY-MM-DD";
// "Tudo até": desde o início (antes de qualquer registo) até à data escolhida.
const INICIO = "1990-01-01";
const desdeInicio = (p: [Dayjs, Dayjs]) => p[0].format(ISO) === INICIO;

/** Atalhos de "Tudo até": hoje, fim do mês passado e fim dos últimos anos
 *  (ex.: faturar agora tudo até ao fim de 2024; 2025 e 2026 ficam para depois). */
const ATE = () => {
  const ano = dayjs().year();
  return [
    { id: "hoje", data: dayjs() },
    { id: "mes", data: dayjs().subtract(1, "month").endOf("month") },
    ...[1, 2, 3].map((n) => ({ id: String(ano - n), data: dayjs(`${ano - n}-12-31`) })),
  ];
};

// Períodos rápidos (pode faturar-se ao mês, ao ano ou à medida).
const PERIODOS = [
  { id: "this_month", de: () => dayjs().startOf("month"), ate: () => dayjs() },
  { id: "last_month", de: () => dayjs().subtract(1, "month").startOf("month"), ate: () => dayjs().subtract(1, "month").endOf("month") },
  { id: "this_year", de: () => dayjs().startOf("year"), ate: () => dayjs() },
  { id: "last_year", de: () => dayjs().subtract(1, "year").startOf("year"), ate: () => dayjs().subtract(1, "year").endOf("year") },
] as const;

/** Evita que um nome começado por "=" vire fórmula no Excel. */
const seguro = (v: string | number | null | undefined) => (typeof v === "string" && /^[=+\-@]/.test(v) ? `'${v}` : v);

function useTextos() {
  const t = useT();
  return {
    dono: (l: { dono_nome: string | null }) => l.dono_nome ?? t("web.billing.no_owner"),
    tipo: (x: TipoFat) => t(`web.billing.type.${x}`),
    dias: (l: Linha) => t("web.billing.days", { count: nDias(l) }),
    palhetas: (l: Linha) => (l.tipo === "armazenamento" && l.palhetas != null ? t("web.billing.straws", { count: l.palhetas }) : ""),
    /** "4 dias" na estadia; "10 palhetas · 4 dias" no sémen. */
    qtd: (l: Linha) =>
      l.tipo === "armazenamento" && l.palhetas == null
        ? t("web.billing.straw_days", { count: l.quantidade })
        : [l.tipo === "armazenamento" && t("web.billing.straws", { count: l.palhetas! }), t("web.billing.days", { count: nDias(l) })]
            .filter(Boolean)
            .join(" · "),
    periodo: (l: { inicio: string; fim: string; tipo: TipoFat; saida?: string | null }) =>
      `${dataCurta(l.inicio)} – ${dataCurta(l.fim)}` +
      (l.tipo === "estadia" && l.saida === null && l.fim === dayjs().format(ISO) ? ` (${t("web.billing.ongoing")})` : ""),
  };
}

const chave = (l: PorFaturar) => `${l.tipo}-${l.ref_id}-${l.inicio}`;

type Linha = { tipo: TipoFat; inicio: string; fim: string; quantidade: number; palhetas?: number | null };
const nDias = (l: { inicio: string; fim: string }) => dayjs(l.fim).diff(dayjs(l.inicio), "day") + 1;

function totais(linhas: Linha[]) {
  const soma = (tipo: TipoFat) => linhas.filter((l) => l.tipo === tipo).reduce((s, l) => s + nDias(l), 0);
  return { dias: soma("estadia"), ds: soma("armazenamento") };
}

export function FaturacaoPage() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { tab } = useParams();
  if (!tab || !TABS.includes(tab as (typeof TABS)[number])) return <Navigate to="/faturacao/anos" replace />;
  const conteudo = tab === "anos" ? <AnosTab /> : tab === "por-faturar" ? <PorFaturarTab /> : <FaturadoTab />;

  if (isMobile)
    return (
      <>
        <CapsuleTabs activeKey={tab} onChange={(v) => navigate(`/faturacao/${v}`)} style={{ background: "#fff" }}>
          <CapsuleTabs.Tab key="anos" title={t("web.billing.tab.years")} />
          <CapsuleTabs.Tab key="por-faturar" title={t("web.billing.tab.pending")} />
          <CapsuleTabs.Tab key="faturado" title={t("web.billing.tab.done")} />
        </CapsuleTabs>
        {conteudo}
      </>
    );

  return (
    <Card size="small">
      <PageHeader titulo={t("web.nav.faturacao")} />
      <Typography.Paragraph type="secondary">{t("web.billing.help")}</Typography.Paragraph>
      <Tabs
        activeKey={tab}
        onChange={(v) => navigate(`/faturacao/${v}`)}
        destroyOnHidden
        items={[
          { key: "anos", label: t("web.billing.tab.years"), children: tab === "anos" && conteudo },
          { key: "por-faturar", label: t("web.billing.tab.pending"), children: tab === "por-faturar" && conteudo },
          { key: "faturado", label: t("web.billing.tab.done"), children: tab === "faturado" && conteudo },
        ]}
      />
    </Card>
  );
}

// ── Filtros comuns ───────────────────────────────────────────────────────────

function usePeriodo() {
  // Vindo do quadro "Por ano": período e proprietário já escolhidos no endereço.
  const [params] = useSearchParams();
  const [periodo, setPeriodo] = useState<[Dayjs, Dayjs]>(() =>
    params.get("inicio") && params.get("fim")
      ? [dayjs(params.get("inicio")), dayjs(params.get("fim"))]
      : [PERIODOS[0].de(), PERIODOS[0].ate()],
  );
  const [dono, setDono] = useState<number | null>(() => (params.get("dono") ? Number(params.get("dono")) : null));
  return { periodo, setPeriodo, dono, setDono, filtro: { inicio: periodo[0].format(ISO), fim: periodo[1].format(ISO), dono_id: dono } };
}

function useRotuloAte() {
  const t = useT();
  return (id: string) =>
    id === "hoje" ? t("web.billing.until_today") : id === "mes" ? t("web.billing.until_last_month") : t("web.billing.until_end_of", { ano: id });
}

function FiltrosDesktop({ p, children }: { p: ReturnType<typeof usePeriodo>; children?: React.ReactNode }) {
  const t = useT();
  const rotuloAte = useRotuloAte();
  const donos = useOpcoes("proprietarios");
  const ate = desdeInicio(p.periodo);
  return (
    <Flex gap={8} wrap align="center" style={{ marginBottom: 12 }}>
      <Segmented<"periodo" | "ate">
        value={ate ? "ate" : "periodo"}
        onChange={(v) =>
          p.setPeriodo(v === "ate" ? [dayjs(INICIO), dayjs()] : [PERIODOS[0].de(), PERIODOS[0].ate()])
        }
        options={[
          { value: "periodo", label: t("web.billing.mode.period") },
          { value: "ate", label: t("web.billing.mode.until") },
        ]}
      />
      {ate ? (
        <DatePicker
          format="DD/MM/YYYY"
          allowClear={false}
          value={p.periodo[1]}
          onChange={(v) => v && p.setPeriodo([dayjs(INICIO), v])}
          presets={ATE().map((x) => ({ label: rotuloAte(x.id), value: x.data }))}
        />
      ) : (
        <DatePicker.RangePicker
          format="DD/MM/YYYY"
          allowClear={false}
          value={p.periodo}
          onChange={(v) => v?.[0] && v[1] && p.setPeriodo([v[0], v[1]])}
          presets={PERIODOS.map((x) => ({ label: t(`web.billing.${x.id}`), value: [x.de(), x.ate()] as [Dayjs, Dayjs] }))}
        />
      )}
      <Select
        showSearch
        allowClear
        optionFilterProp="label"
        placeholder={t("web.billing.all_owners")}
        value={p.dono ?? undefined}
        onChange={(v) => p.setDono(v ?? null)}
        options={(donos.data ?? []).map((d) => ({ value: d.id, label: d.nome }))}
        style={{ width: 260 }}
      />
      {children}
    </Flex>
  );
}

/** Telemóvel: só os períodos rápidos e os "Tudo até" (o período à medida
 *  faz-se no computador). */
function PeriodoMobile({ p }: { p: ReturnType<typeof usePeriodo> }) {
  const t = useT();
  const rotuloAte = useRotuloAte();
  const opcoes = [
    ...PERIODOS.map((x) => ({ value: x.id, label: t(`web.billing.${x.id}`), de: x.de(), ate: x.ate() })),
    ...ATE().map((x) => ({ value: `ate-${x.id}`, label: rotuloAte(x.id), de: dayjs(INICIO), ate: x.data })),
  ];
  const atual = opcoes.find((x) => x.de.isSame(p.periodo[0], "day") && x.ate.isSame(p.periodo[1], "day"))?.value;
  return (
    <Selector
      columns={2}
      showCheckMark={false}
      value={atual ? [atual] : []}
      onChange={(v) => {
        const x = opcoes.find((y) => y.value === v[0]);
        if (x) p.setPeriodo([x.de, x.ate]);
      }}
      options={opcoes.map(({ value, label }) => ({ value, label }))}
    />
  );
}

// ── Por faturar ──────────────────────────────────────────────────────────────

function PorFaturarTab() {
  const t = useT();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const tx = useTextos();
  const p = usePeriodo();
  const [tipo, setTipo] = useState<TipoFat | null>(null);
  const [pesquisa, setPesquisa] = useState("");
  const q = usePorFaturar({ ...p.filtro, tipo });
  const [sel, setSel] = useState<string[]>([]);
  const [marcar, setMarcar] = useState(false);

  const linhas = useMemo(() => {
    const s = pesquisa.trim().toLowerCase();
    return (q.data ?? []).filter((l) => !s || `${l.dono_nome ?? ""} ${l.descricao}`.toLowerCase().includes(s));
  }, [q.data, pesquisa]);
  // Só contam as escolhidas que ainda estão na lista (o período/filtro pode ter mudado).
  const escolhidas = linhas.filter((l) => sel.includes(chave(l)));
  const tot = totais(escolhidas.length ? escolhidas : linhas);
  const resumo = escolhidas.length
    ? t("web.billing.summary", { linhas: escolhidas.length, dias: tot.dias, ds: tot.ds })
    : t("web.billing.total", { dias: tot.dias, ds: tot.ds });

  const exportar = () =>
    baixarCsv(
      `por-faturar_${p.filtro.inicio}_${p.filtro.fim}.csv`,
      [t("label.owner"), t("web.billing.col.what"), t("web.billing.type.all"), t("web.billing.col.period"), "", t("web.billing.col.straws"), t("web.billing.col.days"), t("web.billing.col.qty")],
      linhas.map((l) => [
        seguro(tx.dono(l)),
        seguro(l.descricao),
        tx.tipo(l.tipo),
        l.inicio,
        l.fim,
        l.tipo === "armazenamento" ? l.palhetas : "",
        nDias(l),
        l.tipo === "armazenamento" ? t("web.billing.straw_days", { count: l.quantidade }) : "",
      ]),
    );

  const janela = (
    <MarcarFaturado
      aberto={marcar}
      linhas={escolhidas}
      onClose={(feito) => {
        setMarcar(false);
        if (feito) setSel([]);
      }}
    />
  );

  if (isMobile)
    return (
      <>
        <div style={{ padding: 8, background: "#fff" }}>
          <PeriodoMobile p={p} />
          <SearchBar style={{ marginTop: 8 }} placeholder={t("web.common.search")} value={pesquisa} onChange={setPesquisa} />
          <div style={{ color: "#999", fontSize: 13, margin: "8px 0" }}>{resumo}</div>
          <MButton block color="primary" disabled={!escolhidas.length} onClick={() => setMarcar(true)}>
            {t("web.billing.mark")}
          </MButton>
        </div>
        {q.isPending ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <DotLoading color="primary" />
          </div>
        ) : !linhas.length ? (
          <ErrorBlock status="empty" title={t("web.billing.empty_pending")} description="" />
        ) : (
          <MCheckbox.Group value={sel} onChange={(v) => setSel(v as string[])}>
            <List>
              {linhas.map((l) => (
                <List.Item
                  key={chave(l)}
                  prefix={<MCheckbox value={chave(l)} />}
                  description={`${tx.dono(l)} · ${tx.periodo(l)}`}
                  extra={tx.qtd(l)}
                >
                  {l.descricao}
                </List.Item>
              ))}
            </List>
          </MCheckbox.Group>
        )}
        {janela}
      </>
    );

  return (
    <>
      <FiltrosDesktop p={p}>
        <Segmented<TipoFat | "todos">
          value={tipo ?? "todos"}
          onChange={(v) => setTipo(v === "todos" ? null : v)}
          options={[
            { value: "todos", label: t("web.billing.type.all") },
            { value: "estadia", label: t("web.billing.type.estadia") },
            { value: "armazenamento", label: t("web.billing.type.armazenamento") },
          ]}
        />
      </FiltrosDesktop>
      {q.isError && <Alert type="error" showIcon title={errorMessage(q.error)} style={{ marginBottom: 12 }} />}
      <Flex justify="space-between" align="center" gap={8} wrap style={{ marginBottom: 8 }}>
        <Typography.Text type="secondary">{resumo}</Typography.Text>
        <Space>
          <Button icon={<DownloadOutlined />} disabled={!linhas.length} onClick={exportar}>
            {t("web.billing.export")}
          </Button>
          <Button type="primary" icon={<CheckOutlined />} disabled={!escolhidas.length} onClick={() => setMarcar(true)}>
            {t("web.billing.mark")}
          </Button>
        </Space>
      </Flex>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
        {t("web.billing.mark_help")}
      </Typography.Paragraph>
      <Table<PorFaturar>
        size="small"
        bordered
        loading={q.isFetching}
        rowKey={chave}
        dataSource={linhas}
        locale={{ emptyText: t("web.billing.empty_pending") }}
        pagination={{ pageSize: 100, hideOnSinglePage: true, size: "small" }}
        rowSelection={{ selectedRowKeys: sel, onChange: (k) => setSel(k as string[]) }}
        columns={[
          { title: t("label.owner"), render: (_, l) => tx.dono(l), sorter: (a, b) => tx.dono(a).localeCompare(tx.dono(b)), defaultSortOrder: "ascend" },
          {
            title: t("web.billing.col.what"),
            render: (_, l) => (
              <>
                <Tag color={l.tipo === "estadia" ? "blue" : "purple"}>{tx.tipo(l.tipo)}</Tag>
                {l.descricao}
                {l.local && <Typography.Text type="secondary"> · {l.local}</Typography.Text>}
              </>
            ),
          },
          { title: t("web.billing.col.period"), render: (_, l) => tx.periodo(l) },
          { title: t("web.billing.col.straws"), align: "right", render: (_, l) => tx.palhetas(l) },
          { title: t("web.billing.col.days"), align: "right", render: (_, l) => <Typography.Text strong>{tx.dias(l)}</Typography.Text> },
        ]}
      />
      {janela}
    </>
  );
}

function MarcarFaturado({ aberto, linhas, onClose }: { aberto: boolean; linhas: PorFaturar[]; onClose: (feito: boolean) => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const faturar = useFaturar();
  const notifyError = useNotifyError();
  const [form] = Form.useForm<{ fatura_numero: string; fatura_data: Dayjs; observacoes?: string }>();
  const [mform] = MForm.useForm<{ fatura_numero: string; fatura_data: string; observacoes?: string }>();
  const tot = totais(linhas);

  const guardar = async (v: { fatura_numero: string; fatura_data: string; observacoes?: string }) => {
    try {
      const r = await faturar.mutateAsync({
        ...v,
        linhas: linhas.map((l) => ({ tipo: l.tipo, ref_id: l.ref_id, inicio: l.inicio, fim: l.fim })),
      });
      notifySuccess(t("web.billing.marked", { n: r.linhas }));
      onClose(true);
    } catch (err) {
      notifyError(err);
      // Já faturado entretanto: a lista atualiza (onSettled) e escolhe-se de novo.
      if (err instanceof ApiError && err.code === "web.billing.error.changed") onClose(true);
    }
  };
  const resumo = t("web.billing.summary", { linhas: linhas.length, dias: tot.dias, ds: tot.ds });
  const regraNumero = [{ required: true, whitespace: true, message: t("web.billing.error.invoice_required") }];

  if (isMobile)
    return (
      <FolhaEcraInteiro
        visible={aberto}
        titulo={t("web.billing.mark")}
        onCancel={() => onClose(false)}
        onOk={() => mform.submit()}
        okText={t("web.billing.mark")}
        loading={faturar.isPending}
      >
        <MForm
          form={mform}
          onFinish={guardar}
          onFinishFailed={irParaErro}
          footer={null}
          initialValues={{ fatura_data: dayjs().format(ISO) }}
        >
          <MForm.Header>{resumo}</MForm.Header>
          <MForm.Item name="fatura_numero" label={t("web.billing.invoice_number")} rules={regraNumero}>
            <MInput clearable />
          </MForm.Item>
          <MForm.Item name="fatura_data" label={t("web.billing.invoice_date")} rules={[{ required: true }]} arrow onClick={abrirAoTocar}>
            <DataCampo />
          </MForm.Item>
          <MForm.Item name="observacoes" label={t("web.billing.notes")}>
            <TextArea autoSize={{ minRows: 2 }} />
          </MForm.Item>
        </MForm>
      </FolhaEcraInteiro>
    );

  return (
    <Modal
      open={aberto}
      title={t("web.billing.mark")}
      okText={t("web.billing.mark")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      onCancel={() => onClose(false)}
      confirmLoading={faturar.isPending}
      destroyOnHidden
    >
      <Typography.Paragraph type="secondary">{resumo}</Typography.Paragraph>
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={{ fatura_data: dayjs() }}
        onFinish={(v) => guardar({ ...v, fatura_data: v.fatura_data.format(ISO) })}
      >
        <Flex gap={12}>
          <Form.Item name="fatura_numero" label={t("web.billing.invoice_number")} rules={regraNumero} style={{ flex: 1 }}>
            <Input autoFocus maxLength={60} />
          </Form.Item>
          <Form.Item name="fatura_data" label={t("web.billing.invoice_date")} rules={[{ required: true }]}>
            <DatePicker format="DD/MM/YYYY" allowClear={false} />
          </Form.Item>
        </Flex>
        <Form.Item name="observacoes" label={t("web.billing.notes")}>
          <Input.TextArea autoSize={{ minRows: 2 }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ── Faturado ─────────────────────────────────────────────────────────────────

function FaturadoTab() {
  const t = useT();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const tx = useTextos();
  const p = usePeriodo();
  const [fatura, setFatura] = useState("");
  const [anuladas, setAnuladas] = useState(false);
  const q = useFaturado({ ...p.filtro, fatura, anuladas });
  const [anular, setAnular] = useState<Faturada | null>(null);
  const linhas = q.data ?? [];
  const tot = totais(linhas.filter((l) => !l.anulada));

  const exportar = () =>
    baixarCsv(
      `faturado_${p.filtro.inicio}_${p.filtro.fim}.csv`,
      [t("web.billing.col.invoice"), t("web.billing.col.invoice_date"), t("label.owner"), t("web.billing.col.what"), t("web.billing.col.period"), "", t("web.billing.col.straws"), t("web.billing.col.days"), t("web.billing.col.by"), t("web.billing.cancelled")],
      linhas.map((l) => [
        seguro(l.fatura_numero),
        l.fatura_data,
        seguro(tx.dono(l)),
        seguro(l.descricao),
        l.inicio,
        l.fim,
        l.tipo === "armazenamento" ? (l.palhetas ?? t("web.billing.straw_days", { count: l.quantidade })) : "",
        nDias(l),
        l.criado_por,
        l.anulada ? l.motivo_anulacao : "",
      ]),
    );
  const janela = <AnularLinha linha={anular} onClose={() => setAnular(null)} />;

  if (isMobile)
    return (
      <>
        <div style={{ padding: 8, background: "#fff" }}>
          <PeriodoMobile p={p} />
          <SearchBar style={{ marginTop: 8 }} placeholder={t("web.billing.search_invoice")} value={fatura} onChange={setFatura} />
          <div style={{ color: "#999", fontSize: 13, marginTop: 8 }}>{t("web.billing.total", tot)}</div>
        </div>
        {q.isPending ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <DotLoading color="primary" />
          </div>
        ) : !linhas.length ? (
          <ErrorBlock status="empty" title={t("web.billing.empty_done")} description="" />
        ) : (
          <List>
            {linhas.map((l) => (
              <List.Item
                key={l.id}
                description={`${l.fatura_numero} · ${dataCurta(l.fatura_data)} · ${tx.dono(l)} · ${tx.periodo(l)}`}
                extra={tx.qtd(l)}
                onClick={l.anulada ? undefined : () => setAnular(l)}
                arrow={!l.anulada}
              >
                {l.descricao}
                {l.anulada && (
                  <MTag color="danger" fill="outline" style={{ marginLeft: 6 }}>
                    {t("web.billing.cancelled")}
                  </MTag>
                )}
              </List.Item>
            ))}
          </List>
        )}
        {janela}
      </>
    );

  return (
    <>
      <FiltrosDesktop p={p}>
        <Input.Search allowClear placeholder={t("web.billing.search_invoice")} onSearch={setFatura} style={{ width: 220 }} />
        <Checkbox checked={anuladas} onChange={(e) => setAnuladas(e.target.checked)}>
          {t("web.billing.show_cancelled")}
        </Checkbox>
      </FiltrosDesktop>
      {q.isError && <Alert type="error" showIcon title={errorMessage(q.error)} style={{ marginBottom: 12 }} />}
      <Flex justify="space-between" align="center" gap={8} wrap style={{ marginBottom: 8 }}>
        <Typography.Text type="secondary">{t("web.billing.total", tot)}</Typography.Text>
        <Button icon={<DownloadOutlined />} disabled={!linhas.length} onClick={exportar}>
          {t("web.billing.export")}
        </Button>
      </Flex>
      <Table<Faturada>
        size="small"
        bordered
        loading={q.isFetching}
        rowKey="id"
        dataSource={linhas}
        locale={{ emptyText: t("web.billing.empty_done") }}
        pagination={{ pageSize: 100, hideOnSinglePage: true, size: "small" }}
        columns={[
          {
            title: t("web.billing.col.invoice"),
            render: (_, l) => (
              <>
                <Typography.Text strong delete={l.anulada}>
                  {l.fatura_numero}
                </Typography.Text>
                {l.anulada && (
                  <Tag color="red" style={{ marginLeft: 8 }} title={l.motivo_anulacao ?? undefined}>
                    {t("web.billing.cancelled")}
                  </Tag>
                )}
              </>
            ),
          },
          { title: t("web.billing.col.invoice_date"), render: (_, l) => dataCurta(l.fatura_data) },
          { title: t("label.owner"), render: (_, l) => tx.dono(l) },
          {
            title: t("web.billing.col.what"),
            render: (_, l) => (
              <>
                <Tag color={l.tipo === "estadia" ? "blue" : "purple"}>{tx.tipo(l.tipo)}</Tag>
                {l.descricao}
              </>
            ),
          },
          { title: t("web.billing.col.period"), render: (_, l) => tx.periodo(l) },
          { title: t("web.billing.col.straws"), align: "right", render: (_, l) => (l.palhetas == null && l.tipo === "armazenamento" ? t("web.billing.straw_days", { count: l.quantidade }) : tx.palhetas(l)) },
          { title: t("web.billing.col.days"), align: "right", render: (_, l) => tx.dias(l) },
          { title: t("web.billing.col.by"), dataIndex: "criado_por" },
          {
            title: "",
            width: 90,
            render: (_, l) =>
              !l.anulada && (
                <Button size="small" danger type="link" onClick={() => setAnular(l)}>
                  {t("web.billing.cancel")}
                </Button>
              ),
          },
        ]}
      />
      {janela}
    </>
  );
}

function AnularLinha({ linha, onClose }: { linha: Faturada | null; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const anular = useAnularFaturada();
  const notifyError = useNotifyError();
  const [motivo, setMotivo] = useState("");
  const fazer = async () => {
    if (!linha || !motivo.trim()) return;
    try {
      await anular.mutateAsync({ id: linha.id, motivo: motivo.trim() });
      notifySuccess(t("web.billing.cancel_done"));
      setMotivo("");
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };
  const corpo = linha && (
    <>
      <p>
        {linha.fatura_numero} · {linha.descricao} · {dataCurta(linha.inicio)} – {dataCurta(linha.fim)}
      </p>
      <p style={{ color: "#999" }}>{t("web.billing.cancel_help")}</p>
    </>
  );

  if (isMobile)
    return (
      <FolhaEcraInteiro
        visible={linha !== null}
        titulo={t("web.billing.cancel_title")}
        onCancel={onClose}
        onOk={fazer}
        okText={t("web.billing.cancel")}
        loading={anular.isPending}
      >
        <div style={{ padding: 12 }}>
          {corpo}
          <TextArea placeholder={t("web.billing.reason")} value={motivo} onChange={setMotivo} autoSize={{ minRows: 2 }} />
        </div>
      </FolhaEcraInteiro>
    );

  return (
    <Modal
      open={linha !== null}
      title={t("web.billing.cancel_title")}
      okText={t("web.billing.cancel")}
      okButtonProps={{ danger: true, disabled: !motivo.trim() }}
      cancelText={t("web.common.cancel")}
      onOk={fazer}
      onCancel={onClose}
      confirmLoading={anular.isPending}
      destroyOnHidden
    >
      {corpo}
      <Input.TextArea placeholder={t("web.billing.reason")} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoSize={{ minRows: 2 }} />
    </Modal>
  );
}

// ── Por ano ──────────────────────────────────────────────────────────────────

/** Proprietário × ano: tudo faturado (verde), algo por faturar (vermelho,
 *  com as quantidades) ou sem nada nesse ano (—). Clicar abre as linhas. */
function AnosTab() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const [desde, setDesde] = useState(2025);
  const [soPendentes, setSoPendentes] = useState(true);
  const [pesquisa, setPesquisa] = useState("");
  const q = useAnos(desde);
  const anos = q.data?.anos ?? [];
  const pendente = (c?: CelulaAno) => !!c && (c.dias > 0 || c.dias_semen > 0);
  const linhas = useMemo(() => {
    const s = pesquisa.trim().toLowerCase();
    return (q.data?.linhas ?? []).filter(
      (l) =>
        (!s || (l.dono_nome ?? "").toLowerCase().includes(s)) &&
        (!soPendentes || Object.values(l.celulas).some(pendente)),
    );
  }, [q.data, pesquisa, soPendentes]);

  const rotulo = (k: string) => (k === "antes" ? t("web.billing.before", { ano: desde }) : k);
  const abrir = (l: LinhaAno, k: string) => {
    const inicio = k === "antes" ? INICIO : `${k}-01-01`;
    const fim = k === "antes" ? `${desde - 1}-12-31` : k === String(dayjs().year()) ? dayjs().format(ISO) : `${k}-12-31`;
    const dono = l.dono_id != null ? `&dono=${l.dono_id}` : "";
    navigate(`/faturacao/por-faturar?inicio=${inicio}&fim=${fim}${dono}`);
  };
  const falta = (c: CelulaAno) =>
    [
      c.dias > 0 && t("web.billing.stay_days", { count: c.dias }),
      c.dias_semen > 0 && `${t("web.billing.semen_days", { count: c.dias_semen })} (${t("web.stock.n_lots", { count: c.lotes })})`,
    ]
      .filter(Boolean)
      .join(" · ");
  const nome = (l: LinhaAno) => l.dono_nome ?? t("web.billing.no_owner");

  if (isMobile)
    return (
      <>
        <div style={{ padding: 8, background: "#fff" }}>
          <SearchBar placeholder={t("web.common.search")} value={pesquisa} onChange={setPesquisa} />
          <Flex justify="space-between" align="center" style={{ marginTop: 8, fontSize: 13 }}>
            <span>{t("web.billing.only_pending")}</span>
            <MSwitch checked={soPendentes} onChange={setSoPendentes} />
          </Flex>
        </div>
        {q.isPending ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <DotLoading color="primary" />
          </div>
        ) : !linhas.length ? (
          <ErrorBlock status="empty" title={t("web.billing.empty_years")} description="" />
        ) : (
          <List>
            {linhas.map((l) => (
              <List.Item
                key={l.dono_id ?? "sem"}
                description={
                  <MSpace wrap style={{ marginTop: 4 }}>
                    {anos
                      .filter((k) => l.celulas[k]?.atividade)
                      .map((k) => (
                        <MTag
                          key={k}
                          color={pendente(l.celulas[k]) ? "danger" : "success"}
                          fill="outline"
                          onClick={() => abrir(l, k)}
                        >
                          {rotulo(k)} {pendente(l.celulas[k]) ? `· ${falta(l.celulas[k])}` : "✓"}
                        </MTag>
                      ))}
                  </MSpace>
                }
              >
                {nome(l)}
              </List.Item>
            ))}
          </List>
        )}
      </>
    );

  return (
    <>
      <Typography.Paragraph type="secondary">{t("web.billing.years_help")}</Typography.Paragraph>
      <Flex gap={12} wrap align="center" style={{ marginBottom: 12 }}>
        <Input.Search allowClear placeholder={t("web.common.search")} onChange={(e) => setPesquisa(e.target.value)} style={{ width: 260 }} />
        <Space>
          {t("web.billing.since")}
          <InputNumber min={1990} max={dayjs().year()} value={desde} onChange={(v) => v && setDesde(v)} style={{ width: 90 }} />
        </Space>
        <Checkbox checked={soPendentes} onChange={(e) => setSoPendentes(e.target.checked)}>
          {t("web.billing.only_pending")}
        </Checkbox>
      </Flex>
      {q.isError && <Alert type="error" showIcon title={errorMessage(q.error)} style={{ marginBottom: 12 }} />}
      <Table<LinhaAno>
        size="small"
        bordered
        loading={q.isFetching}
        rowKey={(l) => l.dono_id ?? "sem"}
        dataSource={linhas}
        locale={{ emptyText: t("web.billing.empty_years") }}
        pagination={{ pageSize: 100, hideOnSinglePage: true, size: "small" }}
        scroll={{ x: "max-content" }}
        columns={[
          { title: t("label.owner"), fixed: "left", render: (_, l) => <Typography.Text strong>{nome(l)}</Typography.Text> },
          ...anos.map((k) => ({
            title: rotulo(k),
            key: k,
            align: "center" as const,
            onCell: (l: LinhaAno) => ({
              onClick: l.celulas[k]?.atividade ? () => abrir(l, k) : undefined,
              style: { cursor: l.celulas[k]?.atividade ? "pointer" : undefined },
            }),
            render: (_: unknown, l: LinhaAno) => {
              const c = l.celulas[k];
              if (!c?.atividade) return <Typography.Text type="secondary">—</Typography.Text>;
              if (!pendente(c)) return <Tag color="success">✓ {t("web.billing.billed")}</Tag>;
              return (
                <>
                  <Tag color="error">{t("web.billing.pending")}</Tag>
                  <div style={{ fontSize: 12 }}>{falta(c)}</div>
                </>
              );
            },
          })),
        ]}
      />
    </>
  );
}
