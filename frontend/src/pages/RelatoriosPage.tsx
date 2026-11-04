import { lazy, Suspense, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import dayjs, { type Dayjs } from "dayjs";
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Flex,
  Input,
  Popover,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Typography,
} from "antd";
import { DownloadOutlined, FilterOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  CapsuleTabs,
  DatePicker as MDatePicker,
  DotLoading,
  ErrorBlock,
  Grid,
  List,
  Popup,
  SearchBar,
  Selector,
} from "antd-mobile";

import { api, ApiError } from "../api/client";
import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { useErrorMessage, useNotifyError } from "../components/errors";
import { dataCurta, dataHora } from "../components/csv";
import { descarregar } from "../components/download";
import { Cabecalho, PickerCampo, SeletorPesquisa } from "../components/mobile";
import type { Grafico } from "../components/GraficoRelatorio";

const GraficoRelatorio = lazy(() => import("../components/GraficoRelatorio"));

type Modo = "garanhao" | "proprietario" | "contentor" | "historico";
type Hist = "insem" | "transf_int" | "transf_ext" | "stock";
type Formato = "csv" | "pdf" | "xlsx";
type FiltroChave = "prop" | "gar" | "can" | "and";

interface Opcoes {
  garanhoes: string[];
  proprietarios: { id: number; nome: string }[];
  contentores: { id: number; codigo: string; descricao: string | null }[];
}
interface Tabela {
  titulo: string;
  colunas: string[];
  linhas: Record<string, string | number | null>[];
}
interface Relatorio {
  kpis: [string, number][];
  tabelas: Tabela[];
  filtros: Partial<Record<FiltroChave, (string | number)[]>>;
  graficos?: Grafico[];
  exportar?: Formato[];
}

const MODOS: { value: Modo; label: string }[] = [
  { value: "garanhao", label: "reports.mode.stallion" },
  { value: "proprietario", label: "reports.mode.owner" },
  { value: "contentor", label: "reports.mode.container" },
  { value: "historico", label: "reports.mode.history" },
];
const HISTS: { value: Hist; label: string }[] = [
  { value: "insem", label: "reports.history.inseminations" },
  { value: "transf_int", label: "reports.history.transfer_internal" },
  { value: "transf_ext", label: "reports.history.transfer_external" },
  { value: "stock", label: "reports.history.full_stock" },
];
const FILTROS: { chave: FiltroChave; param: string; label: string }[] = [
  { chave: "gar", param: "f_gar", label: "reports.stallions" },
  { chave: "prop", param: "f_prop", label: "reports.owners" },
  { chave: "can", param: "f_can", label: "reports.canister" },
  { chave: "and", param: "f_and", label: "reports.floor" },
];
const FMT = "YYYY-MM-DD";
const FORMATOS: Record<Formato, string> = { pdf: "PDF", xlsx: "Excel", csv: "CSV" };

/** Períodos rápidos (o fim fica em aberto quando é "até hoje"). */
function periodos(): { chave: string; valor: [Dayjs, Dayjs] | null }[] {
  const hoje = dayjs();
  const mesPassado = hoje.subtract(1, "month");
  return [
    { chave: "web.reports.preset.this_month", valor: [hoje.startOf("month"), hoje] },
    { chave: "web.reports.preset.last_month", valor: [mesPassado.startOf("month"), mesPassado.endOf("month")] },
    { chave: "web.reports.preset.last_3_months", valor: [hoje.subtract(2, "month").startOf("month"), hoje] },
    { chave: "web.reports.preset.this_year", valor: [hoje.startOf("year"), hoje] },
    { chave: "web.reports.preset.last_year", valor: [hoje.subtract(1, "year").startOf("year"), hoje.subtract(1, "year").endOf("year")] },
    { chave: "web.reports.preset.all", valor: null },
  ];
}

function comparar(a: unknown, b: unknown): number {
  if (a == null || a === "") return b == null || b === "" ? 0 : 1;
  if (b == null || b === "") return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/** Sem acentos e em minúsculas, para a pesquisa. */
function normalizar(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/** Datas ISO formatadas; texto livre (ex.: data de produção) fica como está. */
function celula(v: string | number | null): string {
  if (v === null || v === "") return "—";
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) && !/T00:00(:00)?$/.test(v)) return dataHora(v);
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}(T00:00(:00)?)?$/.test(v)) return dataCurta(v.slice(0, 10));
  return String(v);
}

/** Estado no endereço + pedidos — comum ao computador e ao telemóvel. */
function useRelatorio() {
  const t = useT();
  const notifyError = useNotifyError();
  const [params, setParams] = useSearchParams();
  const modo = (MODOS.find((m) => m.value === params.get("modo"))?.value ?? "garanhao") as Modo;
  const hist = (HISTS.find((h) => h.value === params.get("hist"))?.value ?? "insem") as Hist;
  const inicio = params.get("inicio");
  const fim = params.get("fim");

  const opcoes = useQuery({ queryKey: ["relatorios", "opcoes"], queryFn: () => api<Opcoes>("/relatorios/opcoes") });
  // Sem escolha por omissão: o relatório só abre depois de escolher.
  const garanhao = params.get("g");
  const proprietario = params.get("p");
  const contentor = params.get("c");
  const semEscolha =
    (modo === "garanhao" && !garanhao) || (modo === "proprietario" && !proprietario) || (modo === "contentor" && !contentor);

  const consulta = new URLSearchParams({ modo });
  if (modo === "garanhao" && garanhao) consulta.set("garanhao", garanhao);
  if (modo === "proprietario" && proprietario) consulta.set("proprietario", proprietario);
  if (modo === "contentor" && contentor) consulta.set("contentor", contentor);
  if (modo === "historico") consulta.set("hist", hist);
  if (inicio) consulta.set("inicio", inicio);
  if (fim) consulta.set("fim", fim);
  for (const f of FILTROS) params.getAll(f.param).forEach((v) => consulta.append(f.param, v));

  const relatorio = useQuery({
    queryKey: ["relatorios", consulta.toString()],
    queryFn: () => api<Relatorio>(`/relatorios?${consulta}`),
    enabled: opcoes.isSuccess && !semEscolha,
    placeholderData: keepPreviousData,
  });

  const atualizar = (fn: (p: URLSearchParams) => void) =>
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        fn(r);
        return r;
      },
      { replace: true },
    );
  /** Mudar o modo ou a escolha limpa os filtros, que dependem dela. */
  const limparFiltros = (p: URLSearchParams) => FILTROS.forEach((f) => p.delete(f.param));
  const [aExportar, setAExportar] = useState<Formato | null>(null);
  const [pesquisa, setPesquisa] = useState("");
  const termo = normalizar(pesquisa.trim());

  return {
    t,
    modo,
    hist,
    inicio,
    fim,
    garanhao,
    proprietario,
    contentor,
    semEscolha,
    opcoes,
    relatorio,
    pesquisa,
    setPesquisa,
    /** Linhas da tabela que têm o texto pesquisado em alguma coluna. */
    filtrar: (tab: Tabela) =>
      termo ? tab.linhas.filter((l) => tab.colunas.some((c) => normalizar(celula(l[c])).includes(termo))) : tab.linhas,
    valoresFiltro: (param: string) => params.getAll(param),
    // Outro relatório, outra pesquisa: o texto escrito não passa de um para o outro.
    mudarModo: (m: Modo) => (setPesquisa(""), atualizar((p) => (p.set("modo", m), limparFiltros(p)))),
    mudarHist: (h: Hist) => (setPesquisa(""), atualizar((p) => p.set("hist", h))),
    escolher: (k: "g" | "p" | "c", v: string) => (setPesquisa(""), atualizar((p) => (p.set(k, v), limparFiltros(p)))),
    mudarFiltro: (param: string, valores: (string | number)[]) =>
      atualizar((p) => (p.delete(param), valores.forEach((v) => p.append(param, String(v))))),
    mudarPeriodo: (i: string | null, f: string | null) =>
      atualizar((p) => {
        if (i) p.set("inicio", i);
        else p.delete("inicio");
        if (f) p.set("fim", f);
        else p.delete("fim");
      }),
    nFiltros: (inicio || fim ? 1 : 0) + FILTROS.filter((f) => params.getAll(f.param).length).length,
    nFiltrosLista: FILTROS.filter((f) => params.getAll(f.param).length).length,
    aExportar,
    exportar: async (formato: Formato) => {
      setAExportar(formato);
      try {
        await descarregar(`/relatorios/exportar?${consulta}&formato=${formato}`);
      } catch (err) {
        notifyError(err);
      } finally {
        setAExportar(null);
      }
    },
  };
}

type R = ReturnType<typeof useRelatorio>;

export function RelatoriosPage() {
  const r = useRelatorio();
  return useIsMobile() ? <RelatoriosMobile r={r} /> : <RelatoriosDesktop r={r} />;
}

function ErroPeriodo({ r }: { r: R }) {
  const errorMessage = useErrorMessage();
  return r.relatorio.error instanceof ApiError ? <Alert type="warning" showIcon title={errorMessage(r.relatorio.error)} /> : null;
}

function RelatoriosDesktop({ r }: { r: R }) {
  const { t } = r;
  const errorMessage = useErrorMessage();
  const o = r.opcoes.data;
  const d = r.relatorio.data;

  if (r.opcoes.isError) return <Alert type="error" showIcon title={errorMessage(r.opcoes.error)} />;
  if (!o) return <Spin style={{ display: "block", margin: 48 }} />;

  const seletor =
    r.modo === "garanhao" ? (
      <Select
        showSearch
        style={{ width: 280 }}
        value={r.garanhao ?? undefined}
        onChange={(v) => r.escolher("g", v)}
        options={o.garanhoes.map((g) => ({ value: g, label: g }))}
        placeholder={t("reports.select_stallion")}
      />
    ) : r.modo === "proprietario" ? (
      <Select
        showSearch
        optionFilterProp="label"
        style={{ width: 280 }}
        value={r.proprietario ?? undefined}
        onChange={(v) => r.escolher("p", v)}
        options={o.proprietarios.map((p) => ({ value: String(p.id), label: p.nome }))}
        placeholder={t("reports.select_owner")}
      />
    ) : r.modo === "contentor" ? (
      <Select
        showSearch
        optionFilterProp="label"
        style={{ width: 280 }}
        value={r.contentor ?? undefined}
        onChange={(v) => r.escolher("c", v)}
        options={o.contentores.map((c) => ({ value: String(c.id), label: c.codigo }))}
        placeholder={t("reports.select_container")}
      />
    ) : (
      <Segmented
        value={r.hist}
        onChange={(v) => r.mudarHist(v as Hist)}
        options={HISTS.map((h) => ({ value: h.value, label: t(h.label) }))}
      />
    );

  const filtrosDisponiveis = FILTROS.filter((f) => d?.filtros[f.chave]?.length);
  const painelFiltros = (
    <Space orientation="vertical" size={10} style={{ width: 320 }}>
      {filtrosDisponiveis.map((f) => (
        <div key={f.chave}>
          <Typography.Text type="secondary">{t(f.label)}</Typography.Text>
          <Select
            mode="multiple"
            allowClear
            style={{ width: "100%" }}
            placeholder={t("web.reports.all")}
            value={r.valoresFiltro(f.param)}
            onChange={(v) => r.mudarFiltro(f.param, v)}
            options={(d?.filtros[f.chave] ?? []).map((v) => ({ value: String(v), label: String(v) }))}
          />
        </div>
      ))}
    </Space>
  );

  return (
    <Card size="small">
      <Flex vertical gap={12}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t("reports.title")}
        </Typography.Title>
        <Segmented
          value={r.modo}
          onChange={(v) => r.mudarModo(v as Modo)}
          options={MODOS.map((m) => ({ value: m.value, label: t(m.label) }))}
        />
        <Flex gap={8} wrap align="center">
          {seletor}
          <DatePicker.RangePicker
            format="DD/MM/YYYY"
            allowEmpty={[true, true]}
            placeholder={[t("reports.date_start"), t("reports.date_end")]}
            value={[r.inicio ? dayjs(r.inicio) : null, r.fim ? dayjs(r.fim) : null]}
            onChange={(v) => r.mudarPeriodo(v?.[0]?.format(FMT) ?? null, v?.[1]?.format(FMT) ?? null)}
            presets={periodos()
              .filter((p) => p.valor)
              .map((p) => ({ label: t(p.chave), value: p.valor! }))}
          />
          {filtrosDisponiveis.length > 0 && (
            <Popover trigger="click" placement="bottomLeft" title={t("reports.filters_title")} content={painelFiltros}>
              <Button icon={<FilterOutlined />}>
                {t("reports.filters_title")}
                {r.nFiltrosLista > 0 && ` (${r.nFiltrosLista})`}
              </Button>
            </Popover>
          )}
          <Flex gap={8} style={{ marginLeft: "auto" }}>
            {(d?.exportar ?? []).map((f) => (
              <Button key={f} icon={<DownloadOutlined />} loading={r.aExportar === f} onClick={() => r.exportar(f)}>
                {FORMATOS[f]}
              </Button>
            ))}
          </Flex>
        </Flex>
        <ErroPeriodo r={r} />

        {r.semEscolha ? (
          <Empty description={t("web.reports.choose_first")} />
        ) : (
          <>
            {d && d.kpis.length > 0 && (
              <Flex gap={40} wrap>
                {d.kpis.map(([label, n]) => (
                  <Statistic key={label} title={t(label)} value={n} />
                ))}
              </Flex>
            )}

            {d && (d.graficos ?? []).length > 0 && (
              <Row gutter={[12, 12]}>
                {d.graficos!.map((g) => (
                  <Col key={g.titulo} xs={24} lg={12}>
                    <Card size="small" title={t(g.titulo)}>
                      <Suspense fallback={<Spin />}>
                        <GraficoRelatorio g={g} />
                      </Suspense>
                    </Card>
                  </Col>
                ))}
              </Row>
            )}

            {d && d.tabelas.length > 0 && (
              <Input.Search
                allowClear
                style={{ width: 280 }}
                placeholder={t("web.reports.search")}
                value={r.pesquisa}
                onChange={(e) => r.setPesquisa(e.target.value)}
              />
            )}

            {!d ? (
              r.relatorio.isFetching && <Spin />
            ) : !d.tabelas.length ? (
              <Empty description={t("reports.no_data_filters")} />
            ) : (
              d.tabelas.map((tab) => {
                const linhas = r.filtrar(tab);
                return (
                  <div key={tab.titulo}>
                    <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
                      {t(tab.titulo)} · {linhas.length}
                    </Typography.Text>
                    <Table
                      size="small"
                      bordered
                      loading={r.relatorio.isFetching}
                      rowKey="__k"
                      dataSource={linhas.map((l, i) => ({ ...l, __k: i }))}
                      pagination={{ pageSize: 50, hideOnSinglePage: true, size: "small", showSizeChanger: false }}
                      scroll={{ x: true }}
                      locale={{ emptyText: t(r.pesquisa ? "web.common.no_results" : "reports.no_data_filters") }}
                      columns={tab.colunas.map((c) => ({
                        title: t(`web.reports.col.${c}`),
                        dataIndex: c,
                        render: celula,
                        sorter: (a: Record<string, unknown>, b: Record<string, unknown>) => comparar(a[c], b[c]),
                        align: typeof tab.linhas[0]?.[c] === "number" ? ("right" as const) : undefined,
                      }))}
                    />
                  </div>
                );
              })
            )}
          </>
        )}
      </Flex>
    </Card>
  );
}

function RelatoriosMobile({ r }: { r: R }) {
  const { t } = r;
  const errorMessage = useErrorMessage();
  const [filtros, setFiltros] = useState(false);
  const [data, setData] = useState<"inicio" | "fim" | null>(null);
  const o = r.opcoes.data;
  const d = r.relatorio.data;

  if (r.opcoes.isError) return <ErrorBlock status="default" title={errorMessage(r.opcoes.error)} description="" />;
  if (!o)
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <DotLoading color="primary" />
      </div>
    );

  return (
    <>
      <CapsuleTabs activeKey={r.modo} onChange={(v) => r.mudarModo(v as Modo)} style={{ background: "#fff" }}>
        {MODOS.map((m) => (
          <CapsuleTabs.Tab key={m.value} title={t(m.label)} />
        ))}
      </CapsuleTabs>

      <List style={{ "--prefix-width": "7.5em" } as React.CSSProperties}>
        {r.modo === "garanhao" && (
          <List.Item prefix={t("label.garanhao")} arrow>
            <SeletorPesquisa<string>
              titulo={t("reports.select_stallion")}
              placeholder={t("reports.select_stallion")}
              value={r.garanhao}
              onChange={(v) => r.escolher("g", v)}
              opcoes={o.garanhoes.map((g) => ({ value: g, label: g }))}
            />
          </List.Item>
        )}
        {r.modo === "proprietario" && (
          <List.Item prefix={t("label.owner")} arrow>
            <SeletorPesquisa<string>
              titulo={t("reports.select_owner")}
              placeholder={t("reports.select_owner")}
              value={r.proprietario}
              onChange={(v) => r.escolher("p", v)}
              opcoes={o.proprietarios.map((p) => ({ value: String(p.id), label: p.nome }))}
            />
          </List.Item>
        )}
        {r.modo === "contentor" && (
          <List.Item prefix={t("label.container")} arrow>
            <SeletorPesquisa<string>
              titulo={t("reports.select_container")}
              placeholder={t("reports.select_container")}
              value={r.contentor}
              onChange={(v) => r.escolher("c", v)}
              opcoes={o.contentores.map((c) => ({ value: String(c.id), label: c.codigo }))}
            />
          </List.Item>
        )}
        {r.modo === "historico" && (
          <List.Item prefix={t("reports.history_type")} arrow>
            <PickerCampo<Hist>
              titulo={t("reports.history_type")}
              value={r.hist}
              onChange={r.mudarHist}
              opcoes={HISTS.map((h) => ({ value: h.value, label: t(h.label) }))}
            />
          </List.Item>
        )}
        <List.Item arrow onClick={() => setFiltros(true)} extra={r.nFiltros ? `(${r.nFiltros})` : ""}>
          {t("reports.filters_title")}
        </List.Item>
      </List>
      <ErroPeriodo r={r} />

      {r.semEscolha ? (
        <List>
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.reports.choose_first")}</span>
          </List.Item>
        </List>
      ) : (
        <>
          {d && d.kpis.length > 0 && (
            <Grid columns={d.kpis.length > 3 ? 4 : 3} style={{ background: "#fff", margin: "8px 0", padding: "10px 4px" }}>
              {d.kpis.map(([label, n]) => (
                <Grid.Item key={label} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{n}</div>
                  <div style={{ fontSize: 10, color: "#999" }}>{t(label)}</div>
                </Grid.Item>
              ))}
            </Grid>
          )}

          {(d?.exportar ?? []).length > 0 && (
            <div style={{ display: "flex", gap: 8, padding: "4px 12px 8px" }}>
              {d!.exportar!.map((f) => (
                <MButton key={f} size="small" loading={r.aExportar === f} onClick={() => r.exportar(f)}>
                  {FORMATOS[f]}
                </MButton>
              ))}
            </div>
          )}

          {(d?.graficos ?? []).map((g) => (
            <div key={g.titulo}>
              <Cabecalho>{t(g.titulo)}</Cabecalho>
              <div style={{ background: "#fff", padding: "8px 4px" }}>
                <Suspense fallback={<DotLoading />}>
                  <GraficoRelatorio g={g} compacto />
                </Suspense>
              </div>
            </div>
          ))}

          {d && d.tabelas.length > 0 && (
            <div style={{ padding: "8px 12px 0" }}>
              <SearchBar placeholder={t("web.reports.search")} value={r.pesquisa} onChange={r.setPesquisa} />
            </div>
          )}

          {!d ? (
            <div style={{ textAlign: "center", padding: 24 }}>
              <DotLoading />
            </div>
          ) : (
            d.tabelas.map((tab) => {
              const linhas = r.filtrar(tab);
              return (
                <div key={tab.titulo}>
                  <Cabecalho>
                    {t(tab.titulo)} · {linhas.length}
                  </Cabecalho>
                  <List>
                    {!linhas.length ? (
                      <List.Item>
                        <span style={{ color: "#999" }}>{t(r.pesquisa ? "web.common.no_results" : "reports.no_data_filters")}</span>
                      </List.Item>
                    ) : (
                      // Primeira coluna como título; as outras por baixo.
                      linhas.slice(0, 200).map((l, i) => (
                        <List.Item
                          key={i}
                          description={tab.colunas
                            .slice(1)
                            .map((c) => `${t(`web.reports.col.${c}`)}: ${celula(l[c])}`)
                            .join(" · ")}
                        >
                          {celula(l[tab.colunas[0]])}
                        </List.Item>
                      ))
                    )}
                  </List>
                </div>
              );
            })
          )}
        </>
      )}

      <Popup
        visible={filtros}
        onMaskClick={() => setFiltros(false)}
        onClose={() => setFiltros(false)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16, maxHeight: "80dvh", overflowY: "auto" }}
      >
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>{t("reports.filters_title")}</div>
        <Selector
          columns={3}
          style={{ "--padding": "6px 8px", marginBottom: 8 } as React.CSSProperties}
          value={[
            periodos().find((p) =>
              p.valor ? p.valor[0].format(FMT) === r.inicio && p.valor[1].format(FMT) === r.fim : !r.inicio && !r.fim,
            )?.chave ?? "",
          ]}
          onChange={(v) => {
            const p = periodos().find((x) => x.chave === v[0]);
            if (p) r.mudarPeriodo(p.valor?.[0].format(FMT) ?? null, p.valor?.[1].format(FMT) ?? null);
          }}
          options={periodos().map((p) => ({ value: p.chave, label: t(p.chave) }))}
        />
        <List style={{ "--border-top": "none" } as React.CSSProperties}>
          <List.Item prefix={t("reports.date_start")} extra={r.inicio ? dataCurta(r.inicio) : "—"} onClick={() => setData("inicio")} />
          <List.Item prefix={t("reports.date_end")} extra={r.fim ? dataCurta(r.fim) : "—"} onClick={() => setData("fim")} />
        </List>
        {FILTROS.filter((f) => d?.filtros[f.chave]?.length).map((f) => (
          <div key={f.chave} style={{ marginTop: 12 }}>
            <div style={{ color: "#999", marginBottom: 6 }}>{t(f.label)}</div>
            <Selector
              multiple
              columns={2}
              value={r.valoresFiltro(f.param)}
              onChange={(v) => r.mudarFiltro(f.param, v)}
              options={(d?.filtros[f.chave] ?? []).map((v) => ({ value: String(v), label: String(v) }))}
            />
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          {r.nFiltros > 0 && (
            <MButton
              block
              onClick={() => {
                r.mudarPeriodo(null, null);
                FILTROS.forEach((f) => r.mudarFiltro(f.param, []));
              }}
            >
              {t("web.stock.clear_filters")}
            </MButton>
          )}
          <MButton block color="primary" onClick={() => setFiltros(false)}>
            OK
          </MButton>
        </div>
      </Popup>
      <MDatePicker
        visible={data !== null}
        onClose={() => setData(null)}
        value={data && (data === "inicio" ? r.inicio : r.fim) ? dayjs(data === "inicio" ? r.inicio : r.fim).toDate() : new Date()}
        min={dayjs().subtract(15, "year").toDate()}
        max={dayjs().add(2, "year").toDate()}
        onConfirm={(v) => {
          const s = dayjs(v).format(FMT);
          if (data === "inicio") r.mudarPeriodo(s, r.fim);
          else r.mudarPeriodo(r.inicio, s);
        }}
      />
    </>
  );
}
