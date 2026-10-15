import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Collapse,
  Empty,
  Flex,
  FloatButton,
  InputNumber,
  Popover,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import { DownloadOutlined, FilterOutlined, PlusOutlined, RightOutlined } from "@ant-design/icons";

import { useT } from "../../i18n/I18n";
import { useErrorMessage } from "../../components/errors";
import { useIsMobile } from "../../components/responsive";
import { KpiRow } from "../../components/ds";
import { Lista } from "../../components/Lista";
import { baixarCsv, dataCurta } from "../../components/csv";
import {
  localizacao,
  referencia,
  useGaranhoesStock,
  useLotes,
  useTransferencias,
  type Lote,
  type TransfExterna,
  type TransfInterna,
} from "./api";
import { LoteDrawer } from "./LoteDrawer";
import { LotesMobile } from "./LotesMobile";

const SEM_DONO = "sem-dono";

export function LotesTab({ onNovoLote }: { onNovoLote: () => void }) {
  // Telemóvel: ecrã próprio, com aspeto de app (Ant Design Mobile).
  return useIsMobile() ? <LotesMobile onNovoLote={onNovoLote} /> : <LotesDesktop onNovoLote={onNovoLote} />;
}

function LotesDesktop({ onNovoLote }: { onNovoLote: () => void }) {
  const t = useT();
  const errorMessage = useErrorMessage();
  const isMobile = useIsMobile();
  const [params, setParams] = useSearchParams();

  const garanhoes = useGaranhoesStock();
  const opcoesGaranhao = useMemo(
    () => (garanhoes.data ?? []).filter((g) => g.no_seletor).map((g) => g.garanhao),
    [garanhoes.data],
  );

  // Estado no endereço: "Atualizar", "Voltar" e links diretos (ex.: do
  // separador Garanhões, ou depois de adicionar um lote) caem no sítio certo.
  const pedido = params.get("garanhao");
  const garanhao = pedido && opcoesGaranhao.includes(pedido) ? pedido : opcoesGaranhao[0] ?? null;
  const donosSel = params.getAll("dono");
  const minPalhetas = Number(params.get("min")) || 0;
  const incluirVazios = params.get("vazios") === "1";
  const loteAberto = Number(params.get("lote")) || null;

  const atualizar = (fn: (p: URLSearchParams) => void) =>
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        fn(r);
        return r;
      },
      { replace: true },
    );

  const filtro = garanhao
    ? {
        garanhao,
        donos: donosSel.filter((d) => d !== SEM_DONO).map(Number),
        semDono: donosSel.includes(SEM_DONO),
        minPalhetas,
        incluirVazios,
      }
    : null;
  const lotes = useLotes(filtro);
  const transf = useTransferencias(garanhao);

  const [selecionado, setSelecionado] = useState<Lote | null>(null);
  // Abre o lote indicado no endereço (ex.: o que acabou de ser adicionado).
  useEffect(() => {
    if (loteAberto && lotes.data) {
      const l = lotes.data.items.find((x) => x.id === loteAberto);
      if (l) setSelecionado(l);
    }
  }, [loteAberto, lotes.data]);
  // Mantém o lote aberto atualizado depois de uma edição.
  useEffect(() => {
    if (selecionado && lotes.data) {
      const novo = lotes.data.items.find((x) => x.id === selecionado.id);
      if (novo && novo !== selecionado) setSelecionado(novo);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotes.data]);

  const fecharLote = () => {
    setSelecionado(null);
    if (loteAberto) atualizar((p) => p.delete("lote"));
  };

  if (garanhoes.isError) return <Alert type="error" title={errorMessage(garanhoes.error)} showIcon />;
  if (garanhoes.isPending) return <Spin style={{ display: "block", margin: 32 }} />;
  if (!garanhao)
    return (
      <Empty description={t("stock.none_registered")}>
        <Button type="primary" icon={<PlusOutlined />} onClick={onNovoLote}>
          {t("web.stock.add")}
        </Button>
      </Empty>
    );

  const nFiltros = (donosSel.length ? 1 : 0) + (minPalhetas ? 1 : 0) + (incluirVazios ? 1 : 0);
  const opcoesDonos = (lotes.data?.donos_disponiveis ?? []).map((d) =>
    d.id === null ? { value: SEM_DONO, label: t("common.no_owner") } : { value: String(d.id), label: d.nome ?? "" },
  );

  // Histórico do garanhão, com o mesmo filtro de proprietários da lista
  // (`filter_transfer_history`).
  const donosNum = new Set(filtro!.donos);
  const filtrarDono = donosSel.length > 0;
  const internas = (transf.data?.internas ?? []).filter(
    (x) => !filtrarDono || donosNum.has(x.origem_id ?? -1) || donosNum.has(x.destino_id ?? -1),
  );
  const externas = (transf.data?.externas ?? []).filter((x) => !filtrarDono || donosNum.has(x.origem_id ?? -1));
  const k = lotes.data?.kpis;

  const filtros = (
    <Space orientation="vertical" style={{ width: 260 }}>
      <Typography.Text type="secondary">{t("label.owner_plural")}</Typography.Text>
      <Select
        mode="multiple"
        allowClear
        style={{ width: "100%" }}
        value={donosSel}
        options={opcoesDonos}
        onChange={(v: string[]) =>
          atualizar((p) => {
            p.delete("dono");
            v.forEach((d) => p.append("dono", d));
          })
        }
      />
      <Typography.Text type="secondary">{t("stock.min_straws")}</Typography.Text>
      <InputNumber
        min={0}
        style={{ width: "100%" }}
        value={minPalhetas}
        onChange={(v) => atualizar((p) => (Number(v) ? p.set("min", String(v)) : p.delete("min")))}
      />
      <Space>
        <Switch
          size="small"
          checked={incluirVazios}
          onChange={(on) => atualizar((p) => (on ? p.set("vazios", "1") : p.delete("vazios")))}
        />
        <Typography.Text>{t("stock.include_empty")}</Typography.Text>
      </Space>
      {nFiltros > 0 && (
        <Button
          size="small"
          type="link"
          style={{ padding: 0 }}
          onClick={() =>
            atualizar((p) => {
              p.delete("dono");
              p.delete("min");
              p.delete("vazios");
            })
          }
        >
          {t("web.stock.clear_filters")}
        </Button>
      )}
    </Space>
  );

  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      <Flex gap={8} align="center">
        <Select
          showSearch
          value={garanhao}
          onChange={(g) =>
            atualizar((p) => {
              p.set("garanhao", g);
              p.delete("dono");
              p.delete("lote");
            })
          }
          options={opcoesGaranhao.map((g) => ({ value: g, label: g }))}
          notFoundContent={t("web.common.no_results")}
          style={{ width: isMobile ? undefined : 320, flex: isMobile ? 1 : undefined }}
          aria-label={t("label.garanhao")}
        />
        <Popover content={filtros} trigger="click" placement="bottomLeft" title={t("common.filters")}>
          <Badge count={nFiltros} size="small">
            <Button icon={<FilterOutlined />}>{!isMobile && t("common.filters")}</Button>
          </Badge>
        </Popover>
      </Flex>

      {lotes.isError ? (
        <Alert type="error" title={errorMessage(lotes.error)} showIcon />
      ) : (
        <>
          {/* Indicadores (render_kpi_strip) */}
          <KpiRow
            loading={!k}
            items={[
              [t("web.stock.kpi.lotes"), k?.lotes ?? 0],
              [t("web.stock.kpi.palhetas"), k?.palhetas ?? 0],
              [t("web.stock.kpi.proprietarios"), k?.proprietarios ?? 0],
              [t("web.stock.kpi.qualidade"), k?.qualidade_media != null ? `${k.qualidade_media}%` : "—"],
            ]}
          />

          {/* Fechados por omissão, para a lista de lotes ficar logo à vista. */}
          <Collapse
            size="small"
            items={[
              ...(lotes.data?.por_proprietario.length
                ? [
                    {
                      key: "donos",
                      label: t("web.stock.by_owner"),
                      children: (
                        <Table
                          size="small"
                          pagination={false}
                          rowKey={(r) => String(r.dono_id)}
                          dataSource={lotes.data.por_proprietario}
                          columns={[
                            { title: t("label.owner"), dataIndex: "proprietario_nome", render: (v: string | null) => v ?? t("common.no_owner") },
                            { title: t("web.stock.kpi.palhetas"), dataIndex: "palhetas", align: "right" as const },
                          ]}
                        />
                      ),
                    },
                  ]
                : []),
              {
                key: "historico",
                label: t("stock.transfer_history"),
                children: <HistoricoTransferencias garanhao={garanhao} internas={internas} externas={externas} comExportar />,
              },
            ]}
          />

          {isMobile ? (
            <Lista
              itens={lotes.data?.items ?? []}
              chave={(l) => l.id}
              carregando={lotes.isFetching}
              cabecalho={<Typography.Text strong>{t("stock.lots_detailed")}</Typography.Text>}
              vazio={t("stock.no_lots_filter")}
              onClick={setSelecionado}
              render={(l) => ({
                titulo: (
                  <Flex justify="space-between" gap={8}>
                    <Typography.Text strong ellipsis>
                      {referencia(l) ?? t("common.no_reference")}
                    </Typography.Text>
                    <Tag color={(l.existencia_atual ?? 0) > 0 ? "red" : "default"} style={{ marginInlineEnd: 0 }}>
                      {t("web.stock.straws_count", { count: l.existencia_atual ?? 0 })}
                    </Tag>
                  </Flex>
                ),
                descricao: `${l.proprietario_nome ?? t("common.no_owner")} · ${localizacao(l) ?? "—"} · M ${l.motilidade ?? 0}%`,
                extra: <RightOutlined style={{ color: "#bfbfbf" }} />,
              })}
            />
          ) : (
            <Table<Lote>
              size="small"
              bordered
              rowKey="id"
              loading={lotes.isFetching}
              dataSource={lotes.data?.items ?? []}
              locale={{ emptyText: t("stock.no_lots_filter") }}
              pagination={{ pageSize: 20, size: "small", showSizeChanger: false, hideOnSinglePage: true }}
              title={() => <Typography.Text strong>{t("stock.lots_detailed")}</Typography.Text>}
              onRow={(l) => ({ onClick: () => setSelecionado(l), style: { cursor: "pointer" } })}
              columns={[
                {
                  title: "Ref.",
                  key: "ref",
                  render: (_, l) => <Typography.Text strong>{referencia(l) ?? t("common.no_reference")}</Typography.Text>,
                  sorter: (a, b) => (referencia(a) ?? "").localeCompare(referencia(b) ?? ""),
                },
                {
                  title: t("label.owner"),
                  dataIndex: "proprietario_nome",
                  ellipsis: true,
                  render: (v: string | null) => v ?? <Typography.Text type="secondary">{t("common.no_owner")}</Typography.Text>,
                  sorter: (a, b) => (a.proprietario_nome ?? "").localeCompare(b.proprietario_nome ?? ""),
                },
                {
                  title: t("web.stock.kpi.palhetas"),
                  dataIndex: "existencia_atual",
                  align: "right",
                  width: 90,
                  sorter: (a, b) => (a.existencia_atual ?? 0) - (b.existencia_atual ?? 0),
                  render: (v: number | null) => <Tag color={v ? "red" : "default"} style={{ marginInlineEnd: 0 }}>{v ?? 0}</Tag>,
                },
                { title: t("label.location"), key: "loc", render: (_, l) => localizacao(l) ?? "—" },
                { title: t("stock.color"), dataIndex: "cor", render: (v: string | null) => v || "—", responsive: ["lg"] },
                { title: "Mot.", dataIndex: "motilidade", align: "right", render: (v: number | null) => `${v ?? 0}%` },
                { title: "Conc.", dataIndex: "concentracao", align: "right", render: (v: number | null) => `${v ?? 0} M/ml`, responsive: ["lg"] },
                { title: t("stock.quality_label"), dataIndex: "qualidade", render: (v: string | null) => v || "—", responsive: ["xl"] },
                { title: t("stock.created_at_label"), dataIndex: "data_criacao", render: (v: string | null) => dataCurta(v), responsive: ["xl"] },
              ]}
            />
          )}
        </>
      )}

      {isMobile && <FloatButton type="primary" icon={<PlusOutlined />} onClick={onNovoLote} tooltip={t("web.stock.add")} />}

      <LoteDrawer
        lote={selecionado}
        ligacoes={selecionado ? lotes.data?.ligacoes[String(selecionado.id)] : undefined}
        internas={transf.data?.internas ?? []}
        externas={transf.data?.externas ?? []}
        onClose={fecharLote}
      />
    </Space>
  );
}

export function HistoricoTransferencias({
  garanhao,
  internas,
  externas,
  comExportar = false,
}: {
  garanhao: string;
  internas: TransfInterna[];
  externas: TransfExterna[];
  comExportar?: boolean;
}) {
  const t = useT();
  if (!internas.length && !externas.length) return <Typography.Text type="secondary">{t("stock.no_transfers")}</Typography.Text>;

  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      {comExportar && (
        <Space wrap>
          {internas.length > 0 && (
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={() =>
                baixarCsv(
                  `transferencias_internas_${garanhao}.csv`,
                  ["data_transferencia", "garanhao", "proprietario_origem", "proprietario_destino", "quantidade"],
                  internas.map((x) => [x.data, garanhao, x.origem, x.destino, x.quantidade]),
                )
              }
            >
              {t("stock.csv_internal")}
            </Button>
          )}
          {externas.length > 0 && (
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={() =>
                baixarCsv(
                  `transferencias_externas_${garanhao}.csv`,
                  ["data_transferencia", "garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"],
                  externas.map((x) => [x.data, garanhao, x.origem, x.destinatario, x.tipo, x.quantidade, x.observacoes]),
                )
              }
            >
              {t("stock.csv_external")}
            </Button>
          )}
        </Space>
      )}

      {internas.length > 0 && (
        <Table<TransfInterna>
          size="small"
          bordered
          rowKey="id"
          title={() => <Typography.Text strong>{t("web.stock.history.internal")}</Typography.Text>}
          dataSource={internas}
          pagination={{ pageSize: 10, size: "small", hideOnSinglePage: true }}
          scroll={{ x: 360 }}
          columns={[
            { title: t("label.date"), dataIndex: "data", render: (v: string | null) => dataCurta(v) },
            { title: t("label.from"), dataIndex: "origem", render: (v) => v ?? "—" },
            { title: t("label.to"), dataIndex: "destino", render: (v) => v ?? "—" },
            { title: t("web.stock.kpi.palhetas"), dataIndex: "quantidade", align: "right" },
          ]}
        />
      )}

      {externas.length > 0 && (
        <Table<TransfExterna>
          size="small"
          bordered
          rowKey="id"
          title={() => <Typography.Text strong>{t("web.stock.history.external")}</Typography.Text>}
          dataSource={externas}
          pagination={{ pageSize: 10, size: "small", hideOnSinglePage: true }}
          scroll={{ x: 480 }}
          columns={[
            { title: t("label.date"), dataIndex: "data", render: (v: string | null) => dataCurta(v) },
            { title: t("label.from"), dataIndex: "origem", render: (v) => v ?? "—" },
            { title: t("label.to"), dataIndex: "destinatario" },
            { title: t("label.type"), dataIndex: "tipo", render: (v) => v ?? "—" },
            { title: t("web.stock.kpi.palhetas"), dataIndex: "quantidade", align: "right" },
            { title: t("label.notes"), dataIndex: "observacoes", render: (v) => v ?? "" },
          ]}
        />
      )}
    </Space>
  );
}
