import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import dayjs, { type Dayjs } from "dayjs";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Flex,
  Input,
  Modal,
  Segmented,
  Row,
  Select,
  Space,
  Statistic,
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
  List,
  SearchBar,
  Selector,
  Space as MSpace,
  Switch as MSwitch,
  Tag as MTag,
  TextArea,
} from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { PageHeader } from "../../components/ds";
import { useIsMobile } from "../../components/responsive";
import { useUser } from "../../components/User";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../components/errors";
import { FolhaEcraInteiro } from "../../components/mobile";
import { baixarCsv, dataCurta } from "../../components/csv";
import { useOpcoes } from "../stock/api";
import { ResumoFaturar } from "./ResumoFaturar";
import {
  escalao,
  useAtraso,
  useAnos,
  useAnularFaturada,
  useFaturado,
  usePorFaturar,
  type Atraso,
  type AtrasoTipo,
  type CelulaAno,
  type Faturada,
  type LinhaAno,
  type PorFaturar,
  type TipoFat,
} from "./api";

const TABS = ["atraso", "anos", "por-faturar", "faturado"] as const;
const ISO = "YYYY-MM-DD";
// Primeiro ano do quadro "Por ano" (início da faturação na app); cada ano
// novo acrescenta uma coluna.
const ANO_INICIAL = 2025;
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
  if (!tab || !TABS.includes(tab as (typeof TABS)[number])) return <Navigate to="/faturacao/atraso" replace />;
  const conteudo = tab === "atraso" ? <AtrasoTab /> : tab === "anos" ? <AnosTab /> : tab === "por-faturar" ? <PorFaturarTab /> : <FaturadoTab />;

  if (isMobile)
    return (
      <>
        <CapsuleTabs activeKey={tab} onChange={(v) => navigate(`/faturacao/${v}`)} style={{ background: "#fff" }}>
          <CapsuleTabs.Tab key="atraso" title={t("web.billing.tab.overdue")} />
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
          { key: "atraso", label: t("web.billing.tab.overdue"), children: tab === "atraso" && conteudo },
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
    <ResumoFaturar
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
            {t("web.billing.review")}
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
            {t("web.billing.review")}
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
  // "Só ver" não anula.
  const podeEditar = useUser().acesso_faturacao === "editar";
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
                onClick={l.anulada || !podeEditar ? undefined : () => setAnular(l)}
                arrow={!l.anulada && podeEditar}
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
              !l.anulada &&
              podeEditar && (
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
  const [soPendentes, setSoPendentes] = useState(true);
  const [pesquisa, setPesquisa] = useState("");
  const q = useAnos(ANO_INICIAL);
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

  // Muitos anos não cabem no ecrã: a tabela abre no ano mais recente e
  // anda-se para trás para ver os anteriores.
  const caixa = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = caixa.current?.querySelector<HTMLElement>(".ant-table-content, .ant-table-body");
    if (el) el.scrollLeft = el.scrollWidth;
  }, [anos.length, linhas.length]);

  const abrir = (l: LinhaAno, k: string) => {
    const fim = k === String(dayjs().year()) ? dayjs().format(ISO) : `${k}-12-31`;
    const dono = l.dono_id != null ? `&dono=${l.dono_id}` : "";
    navigate(`/faturacao/por-faturar?inicio=${k}-01-01&fim=${fim}${dono}`);
  };
  const falta = (c: CelulaAno) =>
    [
      c.dias > 0 && t("web.billing.stay_days", { count: c.dias }),
      c.dias_semen > 0 && `${t("web.billing.semen_days", { count: c.dias_semen })} (${t("web.stock.n_lots", { count: c.lotes })})`,
    ]
      .filter(Boolean)
      .join(" · ");
  const nome = (l: LinhaAno) => l.dono_nome ?? t("web.billing.no_owner");
  /** Ano da última fatura deste proprietário: é aí que se mostra a data. */
  const anoUltima = (l: LinhaAno) => anos.filter((k) => l.celulas[k]?.faturado_ate).at(-1);
  /** ✓ (ano todo faturado), ✓ + data (ano da última fatura), "até dd/mm/aaaa"
   *  + o que falta (faturado em parte) ou "Por faturar". */
  const estado = (l: LinhaAno, k: string) => {
    const c = l.celulas[k];
    if (!c?.atividade) return null;
    if (!pendente(c))
      return { cor: "success", texto: k === anoUltima(l) && c.faturado_ate ? `✓ ${dataCurta(c.faturado_ate)}` : "✓", falta: "" };
    if (c.faturado_ate) return { cor: "warning", texto: t("web.billing.until_date", { data: dataCurta(c.faturado_ate) }), falta: falta(c) };
    return { cor: "error", texto: t("web.billing.pending"), falta: falta(c) };
  };

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
                  // O ano mais recente primeiro.
                  <MSpace wrap style={{ marginTop: 4 }}>
                    {[...anos].reverse().map((k) => {
                      const e = estado(l, k);
                      return (
                        e && (
                          <MTag
                            key={k}
                            color={e.cor === "error" ? "danger" : e.cor}
                            fill="outline"
                            onClick={() => abrir(l, k)}
                          >
                            {k} · {e.texto}
                            {e.falta && ` · ${e.falta}`}
                          </MTag>
                        )
                      );
                    })}
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
        <Checkbox checked={soPendentes} onChange={(e) => setSoPendentes(e.target.checked)}>
          {t("web.billing.only_pending")}
        </Checkbox>
      </Flex>
      {q.isError && <Alert type="error" showIcon title={errorMessage(q.error)} style={{ marginBottom: 12 }} />}
      <div ref={caixa}>
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
            {
              title: t("label.owner"),
              fixed: "left",
              width: 240,
              render: (_, l) => <Typography.Text strong>{nome(l)}</Typography.Text>,
            },
            ...anos.map((k) => ({
              title: k,
              key: k,
              width: 190,
              align: "center" as const,
              onCell: (l: LinhaAno) => ({
                onClick: l.celulas[k]?.atividade ? () => abrir(l, k) : undefined,
                style: { cursor: l.celulas[k]?.atividade ? "pointer" : undefined },
              }),
              render: (_: unknown, l: LinhaAno) => {
                const e = estado(l, k);
                if (!e) return <Typography.Text type="secondary">—</Typography.Text>;
                return (
                  <>
                    <Tag color={e.cor}>{e.texto}</Tag>
                    {e.falta && <div style={{ fontSize: 12 }}>{e.falta}</div>}
                  </>
                );
              },
            })),
          ]}
        />
      </div>
    </>
  );
}

// ── Em atraso ────────────────────────────────────────────────────────────────

const ESCALOES = [3, 6, 12] as const;
const COR_ESCALAO: Record<number, string> = { 3: "gold", 6: "orange", 12: "red" };
const TIPOS_ATRASO = ["estadia", "armazenamento"] as const;

/** Quem tem dias por faturar há mais de 3 / 6 / 12 meses (a contar do dia
 *  mais antigo por faturar), estadias e sémen à parte. */
function AtrasoTab() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const tx = useTextos();
  const q = useAtraso();
  const [minimo, setMinimo] = useState<number>(3);
  const [tipo, setTipo] = useState<TipoFat | null>(null);

  const conta = (k: TipoFat, m: number) => (q.data ?? []).filter((l) => escalao(l[k]?.desde) >= m).length;
  const linhas = (q.data ?? []).filter((l) => (tipo ? [tipo] : TIPOS_ATRASO).some((k) => escalao(l[k]?.desde) >= minimo));
  const ver = (l: Atraso) =>
    navigate(`/faturacao/por-faturar?inicio=1990-01-01&fim=${dayjs().format(ISO)}${l.dono_id != null ? `&dono=${l.dono_id}` : ""}`);
  const rotuloEscalao = (m: number) => t(m === 12 ? "web.billing.over_12" : m === 6 ? "web.billing.over_6" : "web.billing.over_3");
  const meses = (desde: string) => dayjs().diff(dayjs(desde), "month");
  const detalhe = (k: TipoFat, c: AtrasoTipo) =>
    `${t("web.billing.days", { count: c.dias })} · ${k === "estadia" ? t("web.billing.stays_n", { count: c.itens }) : t("web.stock.n_lots", { count: c.itens })}`;
  const celula = (k: TipoFat, c: AtrasoTipo | null) => {
    const e = escalao(c?.desde);
    if (!c) return <Typography.Text type="secondary">—</Typography.Text>;
    return (
      <>
        <Tag color={e ? COR_ESCALAO[e] : undefined}>{t("web.billing.ago_months", { count: meses(c.desde) })}</Tag>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t("web.billing.since_date", { data: dataCurta(c.desde) })}
        </Typography.Text>
        <div style={{ fontSize: 12 }}>{detalhe(k, c)}</div>
      </>
    );
  };

  const cartoes = (
    <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
      {TIPOS_ATRASO.map((k) => (
        <Col xs={24} md={12} key={k}>
          <Card size="small" title={tx.tipo(k)}>
            <Row gutter={8}>
              {ESCALOES.map((m) => (
                <Col span={8} key={m}>
                  <div
                    role="button"
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      setTipo(k);
                      setMinimo(m);
                    }}
                  >
                    <Statistic
                      title={rotuloEscalao(m)}
                      value={conta(k, m)}
                      valueStyle={{ color: conta(k, m) ? (m === 12 ? "#cf1322" : m === 6 ? "#d46b08" : "#d48806") : undefined }}
                    />
                  </div>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      ))}
    </Row>
  );
  const filtros = (
    <Flex gap={8} wrap align="center" style={{ marginBottom: 12 }}>
      <Segmented<number>
        value={minimo}
        onChange={setMinimo}
        options={ESCALOES.map((m) => ({ value: m, label: rotuloEscalao(m) }))}
      />
      <Segmented<TipoFat | "todos">
        value={tipo ?? "todos"}
        onChange={(v) => setTipo(v === "todos" ? null : v)}
        options={[
          { value: "todos", label: t("web.billing.type.all") },
          { value: "estadia", label: t("web.billing.type.estadia") },
          { value: "armazenamento", label: t("web.billing.type.armazenamento") },
        ]}
      />
    </Flex>
  );

  if (isMobile)
    return (
      <>
        <div style={{ padding: 8, background: "#fff" }}>
          <div style={{ color: "#999", fontSize: 13, marginBottom: 8 }}>{t("web.billing.overdue_help")}</div>
          <Selector
            columns={3}
            showCheckMark={false}
            value={[String(minimo)]}
            onChange={(v) => v[0] && setMinimo(Number(v[0]))}
            options={ESCALOES.map((m) => ({ value: String(m), label: `${rotuloEscalao(m)}` }))}
          />
        </div>
        {q.isPending ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <DotLoading color="primary" />
          </div>
        ) : !linhas.length ? (
          <ErrorBlock status="empty" title={t("web.billing.nothing_overdue")} description="" />
        ) : (
          <List header={t("web.billing.owners_n", { count: linhas.length })}>
            {linhas.map((l) => (
              <List.Item
                key={l.dono_id ?? "sem"}
                arrow
                onClick={() => ver(l)}
                description={TIPOS_ATRASO.filter((k) => l[k]).map((k) => (
                  <div key={k}>
                    {tx.tipo(k)}: {t("web.billing.ago_months", { count: meses(l[k]!.desde) })} · {detalhe(k, l[k]!)}
                  </div>
                ))}
              >
                {tx.dono(l)}
              </List.Item>
            ))}
          </List>
        )}
      </>
    );

  return (
    <>
      <Typography.Paragraph type="secondary">{t("web.billing.overdue_help")}</Typography.Paragraph>
      {q.isError && <Alert type="error" showIcon title={errorMessage(q.error)} style={{ marginBottom: 12 }} />}
      {cartoes}
      {filtros}
      <Table<Atraso>
        size="small"
        bordered
        loading={q.isFetching}
        rowKey={(l) => l.dono_id ?? "sem"}
        dataSource={linhas}
        locale={{ emptyText: t("web.billing.nothing_overdue") }}
        pagination={{ pageSize: 100, hideOnSinglePage: true, size: "small" }}
        title={() => <Typography.Text type="secondary">{t("web.billing.owners_n", { count: linhas.length })}</Typography.Text>}
        columns={[
          { title: t("label.owner"), render: (_, l) => <Typography.Text strong>{tx.dono(l)}</Typography.Text> },
          { title: t("web.billing.type.estadia"), render: (_, l) => celula("estadia", l.estadia) },
          { title: t("web.billing.type.armazenamento"), render: (_, l) => celula("armazenamento", l.armazenamento) },
          {
            title: "",
            width: 140,
            render: (_, l) => (
              <Button size="small" type="link" onClick={() => ver(l)}>
                {t("web.billing.see")}
              </Button>
            ),
          },
        ]}
      />
    </>
  );
}
