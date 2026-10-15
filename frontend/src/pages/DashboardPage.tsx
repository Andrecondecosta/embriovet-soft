import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Card, Col, Flex, Row, Spin, Statistic, Table, Tag, Typography } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { Button as MButton, DotLoading, ErrorBlock, Grid, List, Tag as MTag } from "antd-mobile";

import { api } from "../api/client";
import { useT } from "../i18n/I18n";
import { useBrand } from "../components/Brand";
import { useIsMobile } from "../components/responsive";
import { useErrorMessage } from "../components/errors";
import { dataCurta, dataHora } from "../components/csv";
import { Cabecalho } from "../components/mobile";

interface Dashboard {
  stock: { total_palhetas: number; lotes_ativos: number; stock_critico: number };
  clinica: { estadias_ativas: number; tarefas_hoje: number; tarefas_urgentes: number };
  hoje: { id: number; animal: string | null; dono: string | null; tipo: string; urgencia: string }[];
  atividade: { ts: string | null; usuario: string | null; acao: string | null; detalhe: string | null; num_lotes: number }[];
  partos: { dias: number; itens: { egua: string | null; data: string | null; dias: number }[] };
  atencao: {
    limite: number;
    itens: {
      id: number;
      garanhao: string | null;
      proprietario: string | null;
      contentor: string | null;
      canister: number | null;
      andar: number | null;
      palhetas: number;
    }[];
  };
  por_contentor: { nome: string; palhetas: number }[];
  por_proprietario: { nome: string; palhetas: number }[];
}

// No telemóvel cada lista mostra só as primeiras linhas (o resto está na página própria).
const MAX_TELEMOVEL = 5;

const COR_URGENCIA: Record<string, string> = { urgente: "red", hoje: "orange", amanha: "blue", observacao: "default" };

/** Textos e ligações comuns às duas versões. */
function useDashboard() {
  const t = useT();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard"), refetchInterval: 60_000 });
  return {
    q,
    tipo: (x: string) => t(`web.task.${x}`),
    urgencia: (u: string) => t(`web.dashboard.urg.${u}`),
    dias: (n: number) =>
      n === 0 ? t("web.dashboard.today_lc") : n === 1 ? t("web.dashboard.tomorrow_lc") : t("web.dashboard.in_days", { n }),
    local: (a: Dashboard["atencao"]["itens"][number]) => `${a.contentor ?? "—"} · C${a.canister ?? "?"} / A${a.andar ?? "?"}`,
    abrirLote: (a: Dashboard["atencao"]["itens"][number]) =>
      a.garanhao && navigate(`/stock-semen/lotes?garanhao=${encodeURIComponent(a.garanhao)}&lote=${a.id}`),
    acoes: [
      { label: t("dashboard.action.new_insem"), path: "/trabalho-diario" },
      { label: t("dashboard.action.new_transfer"), path: "/stock-semen/transferencias" },
      { label: t("dashboard.action.import"), path: "/stock-semen/importar" },
      { label: t("dashboard.action.map"), path: "/stock-semen/mapa" },
    ],
    navigate,
  };
}

/** Barras horizontais simples (sem biblioteca de gráficos). */
function Barras({ itens }: { itens: { nome: string; palhetas: number }[] }) {
  const { primary_color } = useBrand();
  const max = Math.max(1, ...itens.map((i) => i.palhetas));
  return (
    <div>
      {itens.map((i) => (
        <div key={i.nome} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span
            style={{ width: 110, flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12 }}
            title={i.nome}
          >
            {i.nome}
          </span>
          <div style={{ flex: 1, background: "#f5f5f5", borderRadius: 4, height: 14 }}>
            <div
              style={{ width: `${(i.palhetas / max) * 100}%`, minWidth: 2, height: "100%", borderRadius: 4, background: primary_color }}
            />
          </div>
          <b style={{ width: 40, textAlign: "right", fontSize: 12 }}>{i.palhetas}</b>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  return useIsMobile() ? <DashboardMobile /> : <DashboardDesktop />;
}

function DashboardDesktop() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const x = useDashboard();
  const d = x.q.data;

  if (x.q.isError) return <Alert type="error" showIcon title={errorMessage(x.q.error)} />;
  if (!d) return <Spin style={{ display: "block", margin: 48 }} />;

  const vazio = (texto: string) => ({ emptyText: texto });

  return (
    <Flex vertical gap={12}>
      <Row gutter={[12, 12]}>
        <Col xs={24} md={12}>
          <Card size="small" title={t("reports.section.stock")}>
            <Flex gap={48}>
              <Statistic title={t("dashboard.kpi.total")} value={d.stock.total_palhetas} />
              <Statistic title={t("dashboard.kpi.active")} value={d.stock.lotes_ativos} />
            </Flex>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card size="small" title={t("web.dashboard.clinic")}>
            <Flex gap={48}>
              <Statistic title={t("web.dashboard.active_stays")} value={d.clinica.estadias_ativas} />
              <Statistic
                title={t("web.dashboard.tasks_today")}
                value={d.clinica.tarefas_hoje}
                suffix={
                  d.clinica.tarefas_urgentes > 0 && (
                    <Tag color="red">{t("web.dashboard.urgent", { count: d.clinica.tarefas_urgentes })}</Tag>
                  )
                }
              />
            </Flex>
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={14}>
          <Card
            size="small"
            title={t("web.dashboard.today")}
            extra={
              <Button type="link" size="small" onClick={() => x.navigate("/trabalho-diario")}>
                {t("web.dashboard.open_daily")} <ArrowRightOutlined />
              </Button>
            }
          >
            <Table
              size="small"
              rowKey="id"
              dataSource={d.hoje}
              pagination={false}
              scroll={{ y: 220 }}
              locale={vazio(t("web.dashboard.no_tasks"))}
              columns={[
                { title: t("web.dashboard.mare"), dataIndex: "animal", render: (v) => v ?? "—" },
                { title: t("web.dashboard.owner"), dataIndex: "dono", render: (v) => v ?? "—" },
                { title: t("web.dashboard.task_type"), dataIndex: "tipo", render: x.tipo },
                {
                  title: t("web.dashboard.urgency"),
                  dataIndex: "urgencia",
                  width: 110,
                  render: (u) => <Tag color={COR_URGENCIA[u]}>{x.urgencia(u)}</Tag>,
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card size="small" title={t("web.dashboard.births", { dias: d.partos.dias })}>
            <Table
              size="small"
              rowKey={(r) => `${r.egua}-${r.data}`}
              dataSource={d.partos.itens}
              pagination={false}
              scroll={{ y: 220 }}
              locale={vazio(t("web.dashboard.no_births"))}
              columns={[
                { title: t("web.dashboard.mare"), dataIndex: "egua", render: (v) => v ?? "—" },
                { title: t("web.dashboard.expected_date"), dataIndex: "data", render: (v) => (v ? dataCurta(v) : "—") },
                { title: t("web.dashboard.days_left"), dataIndex: "dias", render: x.dias },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card
        size="small"
        title={t("dashboard.activity")}
        extra={
          <Button type="link" size="small" onClick={() => x.navigate("/atividade")}>
            {t("web.dashboard.all_activity")} <ArrowRightOutlined />
          </Button>
        }
      >
        <Table
          size="small"
          rowKey={(r, i) => `${r.ts}-${i}`}
          dataSource={d.atividade}
          pagination={false}
          locale={vazio(t("web.dashboard.no_activity"))}
          columns={[
            { title: t("web.dashboard.col.time"), dataIndex: "ts", width: 140, render: (v) => (v ? dataHora(v) : "—") },
            { title: t("web.dashboard.col.user"), dataIndex: "usuario", width: 120, render: (v) => v ?? "—" },
            { title: t("web.dashboard.col.action"), dataIndex: "acao", width: 170, render: (v) => v ?? "—" },
            { title: t("web.dashboard.col.detail"), dataIndex: "detalhe", ellipsis: true },
            { title: t("web.dashboard.col.lots"), dataIndex: "num_lotes", width: 70, align: "right" },
          ]}
        />
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={14}>
          <Card size="small" title={t("web.dashboard.attention", { limite: d.atencao.limite })}>
            <Table
              size="small"
              rowKey="id"
              dataSource={d.atencao.itens}
              pagination={false}
              locale={vazio(t("web.dashboard.no_attention"))}
              onRow={(a) => ({ onClick: () => x.abrirLote(a), style: { cursor: "pointer" } })}
              columns={[
                { title: t("label.garanhao"), dataIndex: "garanhao", render: (v) => <Typography.Text strong>{v ?? "—"}</Typography.Text> },
                { title: t("label.owner"), dataIndex: "proprietario", render: (v) => v ?? "—" },
                { title: t("label.location"), key: "local", render: (_, a) => x.local(a) },
                {
                  title: t("web.stock.kpi.palhetas"),
                  dataIndex: "palhetas",
                  width: 90,
                  align: "right",
                  render: (v) => <Tag color="red">{v}</Tag>,
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card size="small" title={t("web.dashboard.distribution")}>
            {d.por_contentor.length > 0 && (
              <>
                <Typography.Text type="secondary" style={{ display: "block", marginBottom: 6 }}>
                  {t("web.dashboard.by_container")}
                </Typography.Text>
                <Barras itens={d.por_contentor} />
              </>
            )}
            {d.por_proprietario.length > 0 && (
              <>
                <Typography.Text type="secondary" style={{ display: "block", margin: "12px 0 6px" }}>
                  {t("web.dashboard.by_owner")}
                </Typography.Text>
                <Barras itens={d.por_proprietario} />
              </>
            )}
          </Card>
        </Col>
      </Row>

      <Card size="small" title={t("dashboard.actions")}>
        <Row gutter={[8, 8]}>
          {x.acoes.map((a) => (
            <Col key={a.path} xs={12} md={6}>
              <Button block onClick={() => x.navigate(a.path)}>
                {a.label}
              </Button>
            </Col>
          ))}
        </Row>
      </Card>
    </Flex>
  );
}

function DashboardMobile() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const x = useDashboard();
  const d = x.q.data;

  if (x.q.isError) return <ErrorBlock status="default" title={errorMessage(x.q.error)} description="" />;
  if (!d)
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <DotLoading color="primary" />
      </div>
    );

  const kpis: [string, number, React.ReactNode?][] = [
    [t("dashboard.kpi.total"), d.stock.total_palhetas],
    [t("dashboard.kpi.active"), d.stock.lotes_ativos],
    [t("web.dashboard.active_stays"), d.clinica.estadias_ativas],
    [
      t("web.dashboard.tasks_today"),
      d.clinica.tarefas_hoje,
      d.clinica.tarefas_urgentes > 0 && (
        <MTag color="danger" fill="outline" style={{ marginLeft: 4 }}>
          {t("web.dashboard.urgent", { count: d.clinica.tarefas_urgentes })}
        </MTag>
      ),
    ],
  ];

  return (
    <>
      <Grid columns={2} gap={8} style={{ padding: 8 }}>
        {kpis.map(([label, n, extra]) => (
          <Grid.Item key={label} style={{ background: "#fff", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: "#999" }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>
              {n}
              {extra}
            </div>
          </Grid.Item>
        ))}
      </Grid>

      <List header={t("web.dashboard.today")}>
        {!d.hoje.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.dashboard.no_tasks")}</span>
          </List.Item>
        ) : (
          d.hoje.slice(0, MAX_TELEMOVEL).map((h) => (
            <List.Item
              key={h.id}
              description={`${h.dono ?? "—"} · ${x.tipo(h.tipo)}`}
              extra={
                <MTag color={h.urgencia === "urgente" ? "danger" : h.urgencia === "hoje" ? "warning" : "default"} fill="outline">
                  {x.urgencia(h.urgencia)}
                </MTag>
              }
            >
              {h.animal ?? "—"}
            </List.Item>
          ))
        )}
        <List.Item arrow onClick={() => x.navigate("/trabalho-diario")} style={{ color: "var(--adm-color-primary)" }}>
          {t("web.dashboard.open_daily")}
        </List.Item>
      </List>

      <List header={t("web.dashboard.births", { dias: d.partos.dias })}>
        {!d.partos.itens.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.dashboard.no_births")}</span>
          </List.Item>
        ) : (
          d.partos.itens.map((p) => (
            <List.Item key={`${p.egua}-${p.data}`} description={p.data ? dataCurta(p.data) : "—"} extra={x.dias(p.dias)}>
              {p.egua ?? "—"}
            </List.Item>
          ))
        )}
      </List>

      <List header={t("dashboard.activity")}>
        {!d.atividade.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.dashboard.no_activity")}</span>
          </List.Item>
        ) : (
          d.atividade.slice(0, MAX_TELEMOVEL).map((a, i) => (
            <List.Item
              key={`${a.ts}-${i}`}
              description={`${a.usuario ?? "—"} · ${a.detalhe ?? ""}`}
              extra={<span style={{ fontSize: 11 }}>{a.ts ? dataHora(a.ts) : "—"}</span>}
            >
              {a.acao ?? "—"}
            </List.Item>
          ))
        )}
        <List.Item arrow onClick={() => x.navigate("/atividade")} style={{ color: "var(--adm-color-primary)" }}>
          {t("web.dashboard.all_activity")}
        </List.Item>
      </List>

      <List header={t("web.dashboard.attention", { limite: d.atencao.limite })}>
        {!d.atencao.itens.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.dashboard.no_attention")}</span>
          </List.Item>
        ) : (
          d.atencao.itens.slice(0, MAX_TELEMOVEL).map((a) => (
            <List.Item
              key={a.id}
              arrow
              onClick={() => x.abrirLote(a)}
              description={`${a.proprietario ?? "—"} · ${x.local(a)}`}
              extra={
                <MTag color="danger" fill="outline">
                  {t("web.stock.straws_count", { count: a.palhetas })}
                </MTag>
              }
            >
              {a.garanhao ?? "—"}
            </List.Item>
          ))
        )}
      </List>

      {(d.por_contentor.length > 0 || d.por_proprietario.length > 0) && (
        <>
          <Cabecalho>{t("web.dashboard.distribution")}</Cabecalho>
          <div style={{ background: "#fff", padding: 12 }}>
            {d.por_contentor.length > 0 && (
              <>
                <div style={{ color: "#999", fontSize: 12, marginBottom: 6 }}>{t("web.dashboard.by_container")}</div>
                <Barras itens={d.por_contentor} />
              </>
            )}
            {d.por_proprietario.length > 0 && (
              <>
                <div style={{ color: "#999", fontSize: 12, margin: "12px 0 6px" }}>{t("web.dashboard.by_owner")}</div>
                <Barras itens={d.por_proprietario} />
              </>
            )}
          </div>
        </>
      )}

      <Cabecalho>{t("dashboard.actions")}</Cabecalho>
      <Grid columns={2} gap={8} style={{ padding: "0 8px 16px" }}>
        {x.acoes.map((a) => (
          <Grid.Item key={a.path}>
            <MButton block onClick={() => x.navigate(a.path)}>
              {a.label}
            </MButton>
          </Grid.Item>
        ))}
      </Grid>
    </>
  );
}
