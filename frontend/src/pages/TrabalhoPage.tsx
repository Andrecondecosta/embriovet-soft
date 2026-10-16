import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import dayjs, { type Dayjs } from "dayjs";
import { Alert, Button, Card, Col, DatePicker, Flex, Popover, Row, Select, Space, Statistic, Switch, Table, Tag, Typography } from "antd";
import { FilterOutlined, LeftOutlined, RightOutlined, WarningOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  DatePicker as MDatePicker,
  DotLoading,
  ErrorBlock,
  Grid,
  List,
  Popup,
  Selector,
  Switch as MSwitch,
} from "antd-mobile";

import { api } from "../api/client";
import { useT } from "../i18n/I18n";
import { useUser } from "../components/User";
import { useBrand } from "../components/Brand";
import { useIsMobile } from "../components/responsive";
import { notifySuccess, useErrorMessage } from "../components/errors";
import { Cabecalho } from "../components/mobile";

interface Tarefa {
  tarefa_id: number;
  animal_id: number;
  animal: string | null;
  dono: string | null;
  tipo: string;
  urgencia: string;
  utilizador: string | null;
  dias_atraso?: number;
  concluida_por?: string | null;
}
interface Trabalho {
  dia: string;
  resumo: { total: number; feitas: number; por_fazer: number; atrasadas: number };
  por_fazer: Tarefa[];
  atrasadas: Tarefa[];
  feitas: Tarefa[];
}

const COR_URGENCIA: Record<string, string> = { urgente: "#dc2626", hoje: "#b45309", amanha: "#94a3b8", observacao: "#cbd5e1" };
const FMT = "YYYY-MM-DD";

/** Estado no endereço (dia, filtros) e pedidos — comum às duas versões. */
function useTrabalho() {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useUser();
  const [params, setParams] = useSearchParams();
  const pedido = params.get("dia");
  const dia: Dayjs = pedido && /^\d{4}-\d{2}-\d{2}$/.test(pedido) ? dayjs(pedido) : dayjs().startOf("day");
  const ehHoje = dia.isSame(dayjs(), "day");
  const minhas = params.get("minhas") === "1";
  const dono = params.get("dono");

  // Tarefas automáticas de 1.ª observação, ao abrir (como a app atual).
  const gerar = useMutation({
    mutationFn: () => api<{ criadas: number }>("/trabalho/gerar", "POST"),
    onSuccess: (r) => {
      if (r.criadas > 0) {
        notifySuccess(t("web.daily.created_auto", { n: r.criadas }));
        queryClient.invalidateQueries({ queryKey: ["trabalho"] });
      }
    },
  });
  useEffect(() => gerar.mutate(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const q = useQuery({
    queryKey: ["trabalho", dia.format(FMT)],
    queryFn: () => api<Trabalho>(`/trabalho?dia=${dia.format(FMT)}`),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });

  const filtrar = (lista: Tarefa[]) => lista.filter((x) => (!minhas || x.utilizador === user.username) && (!dono || x.dono === dono));
  const donos = useMemo(
    () => [...new Set([...(q.data?.por_fazer ?? []), ...(q.data?.atrasadas ?? [])].map((x) => x.dono).filter(Boolean) as string[])].sort(),
    [q.data],
  );
  const atualizar = (k: string, v: string | null) =>
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        if (v) r.set(k, v);
        else r.delete(k);
        return r;
      },
      { replace: true },
    );

  return {
    t,
    q,
    dia,
    ehHoje,
    minhas,
    dono,
    donos,
    porFazer: filtrar(q.data?.por_fazer ?? []),
    atrasadas: filtrar(q.data?.atrasadas ?? []),
    feitas: q.data?.feitas ?? [],
    nFiltros: (minhas ? 1 : 0) + (dono ? 1 : 0),
    irPara: (d: Dayjs) => atualizar("dia", d.isSame(dayjs(), "day") ? null : d.format(FMT)),
    mudarMinhas: (v: boolean) => atualizar("minhas", v ? "1" : null),
    mudarDono: (v: string | null) => atualizar("dono", v),
    // Tocar numa tarefa abre a ficha do animal logo no Diário clínico (onde
    // se faz o registo do dia). Nos garanhões, que não têm diário, abre o resumo.
    abrir: (x: Tarefa) => navigate(`/animais/${x.animal_id}${x.tipo === "colheita" ? "" : "?tab=diario"}`),
    inseminar: () => navigate("/trabalho-diario/inseminacao"),
    nome: (x: Tarefa) => (x.tipo === "colheita" ? t("web.daily.collection_of", { name: x.animal ?? "—" }) : (x.animal ?? "—")),
    tipo: (x: Tarefa) => t(`web.task.${x.tipo}`),
    urgencia: (x: Tarefa) => t(`web.dashboard.urg.${x.urgencia}`),
    atraso: (n: number) => (n === 1 ? t("web.daily.ago_one") : t("web.daily.ago", { n })),
    titulo: () => (ehHoje ? t("web.daily.today_title") : t("web.daily.day_title", { dia: dia.format("DD/MM") })),
  };
}
type T = ReturnType<typeof useTrabalho>;

export function TrabalhoPage() {
  const x = useTrabalho();
  return useIsMobile() ? <TrabalhoMobile x={x} /> : <TrabalhoDesktop x={x} />;
}

/** Cor do atraso: laranja, vermelho a partir de 3 dias, forte a partir de 7. */
function corAtraso(n: number) {
  return n >= 3 ? "#dc2626" : "#d97706";
}

// ── Computador ──────────────────────────────────────────────────────────────

function TrabalhoDesktop({ x }: { x: T }) {
  const { t } = x;
  const { primary_color } = useBrand();
  const errorMessage = useErrorMessage();
  const r = x.q.data?.resumo;

  if (x.q.isError) return <Alert type="error" showIcon title={errorMessage(x.q.error)} />;

  const linha = (tarefa: Tarefa) => ({
    onClick: () => x.abrir(tarefa),
    style: {
      cursor: "pointer",
      boxShadow: `inset 3px 0 0 ${tarefa.dias_atraso ? "#dc2626" : (COR_URGENCIA[tarefa.urgencia] ?? "transparent")}`,
    },
  });
  const colunas = [
    {
      title: "#",
      key: "n",
      width: 44,
      render: (_: unknown, __: Tarefa, i: number) => <Typography.Text type="secondary">{i + 1}</Typography.Text>,
    },
    {
      title: t("web.dashboard.mare"),
      key: "animal",
      render: (_: unknown, a: Tarefa) => <Typography.Text strong>{x.nome(a)}</Typography.Text>,
    },
    { title: t("web.dashboard.owner"), dataIndex: "dono", render: (v: string | null) => v ?? "—" },
    { title: t("web.dashboard.task_type"), key: "tipo", render: (_: unknown, a: Tarefa) => x.tipo(a) },
  ];

  return (
    <Flex vertical gap={12}>
      <Card size="small">
        <Flex gap={48} align="center" wrap>
          <Statistic title={t("web.daily.kpi.todo")} value={r?.por_fazer ?? "—"} styles={{ content: { color: primary_color } }} />
          <Statistic title={t("web.daily.kpi.tasks")} value={r?.total ?? "—"} />
          <Statistic title={t("web.daily.kpi.done")} value={r?.feitas ?? "—"} />
          {!!r?.atrasadas && (
            <Tag color="red" icon={<WarningOutlined />} style={{ fontSize: 13, padding: "4px 10px" }}>
              {t("web.daily.overdue_banner", { n: r.atrasadas })}
            </Tag>
          )}
          <Button type="primary" style={{ marginLeft: "auto" }} onClick={x.inseminar}>
            {t("web.insem.title")}
          </Button>
        </Flex>
      </Card>
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={14}>
          <Card
            size="small"
            title={`${x.titulo()} (${x.porFazer.length})`}
            extra={
              <Popover
                trigger="click"
                placement="bottomRight"
                content={
                  <Space orientation="vertical" style={{ width: 240 }}>
                    <Flex justify="space-between" align="center">
                      {t("web.daily.mine")}
                      <Switch checked={x.minhas} onChange={x.mudarMinhas} />
                    </Flex>
                    <Select
                      allowClear
                      style={{ width: "100%" }}
                      placeholder={`${t("web.dashboard.owner")}: ${t("web.stays.animals.all")}`}
                      value={x.dono}
                      onChange={(v) => x.mudarDono(v ?? null)}
                      options={x.donos.map((d) => ({ value: d, label: d }))}
                    />
                  </Space>
                }
              >
                <Button size="small" icon={<FilterOutlined />}>
                  {t("common.filters")}
                  {x.nFiltros > 0 && ` (${x.nFiltros})`}
                </Button>
              </Popover>
            }
          >
            <Flex gap={6} align="center" style={{ marginBottom: 10 }}>
              <Button icon={<LeftOutlined />} onClick={() => x.irPara(x.dia.subtract(1, "day"))} />
              <DatePicker value={x.dia} onChange={(d) => d && x.irPara(d)} allowClear={false} format="DD/MM/YYYY" />
              <Button icon={<RightOutlined />} onClick={() => x.irPara(x.dia.add(1, "day"))} />
              {!x.ehHoje && (
                <Button type="link" onClick={() => x.irPara(dayjs())}>
                  {t("web.transfer.today")}
                </Button>
              )}
            </Flex>
            <Table<Tarefa>
              size="small"
              rowKey="tarefa_id"
              loading={x.q.isFetching}
              dataSource={x.porFazer}
              pagination={false}
              scroll={{ y: "calc(100vh - 420px)" }}
              onRow={linha}
              locale={{
                emptyText:
                  x.nFiltros && x.q.data?.por_fazer.length
                    ? t("web.daily.none_filters")
                    : x.ehHoje
                      ? t("web.daily.none_today")
                      : t("web.daily.none_day"),
              }}
              columns={[
                ...colunas,
                {
                  title: t("web.dashboard.urgency"),
                  key: "urg",
                  width: 110,
                  render: (_, a) => <Typography.Text type="secondary">{x.urgencia(a)}</Typography.Text>,
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Flex vertical gap={12}>
            <Card size="small" title={<span style={{ color: "#dc2626" }}>{`${t("web.daily.overdue")} (${x.atrasadas.length})`}</span>}>
              <Table<Tarefa>
                size="small"
                rowKey="tarefa_id"
                dataSource={x.atrasadas}
                pagination={false}
                scroll={{ y: 190 }}
                showHeader={false}
                onRow={linha}
                locale={{ emptyText: t("web.daily.no_overdue") }}
                columns={[
                  ...colunas.slice(1, 2),
                  ...colunas.slice(3),
                  {
                    key: "atraso",
                    width: 100,
                    render: (_, a) => (
                      <span style={{ color: corAtraso(a.dias_atraso ?? 0), fontWeight: (a.dias_atraso ?? 0) >= 7 ? 700 : 400 }}>
                        {x.atraso(a.dias_atraso ?? 0)}
                      </span>
                    ),
                  },
                ]}
              />
            </Card>
            <Card size="small" title={`${t("web.daily.done_today")} (${x.feitas.length})`}>
              <Table<Tarefa>
                size="small"
                rowKey="tarefa_id"
                dataSource={x.feitas}
                pagination={false}
                scroll={{ y: 260 }}
                showHeader={false}
                locale={{ emptyText: t("web.daily.none_done") }}
                columns={[
                  { key: "ok", width: 28, render: () => <span style={{ color: primary_color }}>✓</span> },
                  { key: "nome", render: (_, a) => <Typography.Text type="secondary">{x.nome(a)}</Typography.Text> },
                  { key: "tipo", render: (_, a) => <Typography.Text type="secondary">{x.tipo(a)}</Typography.Text> },
                  { dataIndex: "concluida_por", width: 110, render: (v) => <Typography.Text type="secondary">{v ?? "—"}</Typography.Text> },
                ]}
              />
            </Card>
          </Flex>
        </Col>
      </Row>
    </Flex>
  );
}

// ── Telemóvel ───────────────────────────────────────────────────────────────

function TrabalhoMobile({ x }: { x: T }) {
  const { t } = x;
  const { primary_color } = useBrand();
  const errorMessage = useErrorMessage();
  const [filtros, setFiltros] = useState(false);
  const [calendario, setCalendario] = useState(false);
  const r = x.q.data?.resumo;

  if (x.q.isError) return <ErrorBlock status="default" title={errorMessage(x.q.error)} description="" />;
  if (!x.q.data)
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <DotLoading color="primary" />
      </div>
    );

  const item = (a: Tarefa, direita: React.ReactNode) => (
    <List.Item
      key={a.tarefa_id}
      onClick={() => x.abrir(a)}
      arrow
      description={`${a.dono ?? "—"} · ${x.tipo(a)}`}
      extra={direita}
      style={{ boxShadow: `inset 3px 0 0 ${a.dias_atraso ? "#dc2626" : (COR_URGENCIA[a.urgencia] ?? "transparent")}` }}
    >
      {x.nome(a)}
    </List.Item>
  );

  return (
    <>
      <Grid columns={3} style={{ background: "#fff", padding: "10px 4px" }}>
        {(
          [
            [t("web.daily.kpi.todo"), r?.por_fazer, primary_color],
            [t("web.daily.kpi.tasks"), r?.total],
            [t("web.daily.kpi.done"), r?.feitas],
          ] as [string, number | undefined, string?][]
        ).map(([label, n, cor]) => (
          <Grid.Item key={label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: cor }}>{n ?? "—"}</div>
            <div style={{ fontSize: 10, color: "#999" }}>{label}</div>
          </Grid.Item>
        ))}
      </Grid>
      {!!r?.atrasadas && (
        <div style={{ background: "#fef2f2", color: "#dc2626", padding: "6px 12px", fontWeight: 600, fontSize: 12 }}>
          ⚠︎ {t("web.daily.overdue_banner", { n: r.atrasadas })}
        </div>
      )}

      <div style={{ padding: "8px 12px 0", background: "#fff", marginTop: 8 }}>
        <MButton block color="primary" onClick={x.inseminar}>
          {t("web.insem.title")}
        </MButton>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", background: "#fff" }}>
        <MButton size="small" onClick={() => x.irPara(x.dia.subtract(1, "day"))}>
          ‹
        </MButton>
        <MButton size="small" style={{ flex: 1 }} onClick={() => setCalendario(true)}>
          {x.dia.format("DD/MM/YYYY")}
        </MButton>
        <MButton size="small" onClick={() => x.irPara(x.dia.add(1, "day"))}>
          ›
        </MButton>
        <MButton size="small" color={x.nFiltros ? "primary" : "default"} fill="outline" onClick={() => setFiltros(true)}>
          {t("common.filters")}
          {x.nFiltros > 0 && ` (${x.nFiltros})`}
        </MButton>
      </div>
      <MDatePicker
        visible={calendario}
        onClose={() => setCalendario(false)}
        value={x.dia.toDate()}
        min={dayjs().subtract(2, "year").toDate()}
        max={dayjs().add(1, "year").toDate()}
        onConfirm={(d) => x.irPara(dayjs(d))}
      />

      <List header={`${x.titulo()} (${x.porFazer.length})`}>
        {!x.porFazer.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>
              {x.nFiltros && x.q.data.por_fazer.length
                ? t("web.daily.none_filters")
                : x.ehHoje
                  ? t("web.daily.none_today")
                  : t("web.daily.none_day")}
            </span>
          </List.Item>
        ) : (
          x.porFazer.map((a) => item(a, <span style={{ fontSize: 11, color: "#999" }}>{x.urgencia(a)}</span>))
        )}
      </List>

      <Cabecalho>
        <span style={{ color: "#dc2626" }}>
          {t("web.daily.overdue")} ({x.atrasadas.length})
        </span>
      </Cabecalho>
      <List>
        {!x.atrasadas.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.daily.no_overdue")}</span>
          </List.Item>
        ) : (
          x.atrasadas.map((a) =>
            item(
              a,
              <span style={{ fontSize: 11, color: corAtraso(a.dias_atraso ?? 0), fontWeight: (a.dias_atraso ?? 0) >= 7 ? 700 : 400 }}>
                {x.atraso(a.dias_atraso ?? 0)}
              </span>,
            ),
          )
        )}
      </List>

      <List header={`${t("web.daily.done_today")} (${x.feitas.length})`}>
        {!x.feitas.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{t("web.daily.none_done")}</span>
          </List.Item>
        ) : (
          x.feitas.map((a) => (
            <List.Item
              key={a.tarefa_id}
              prefix={<span style={{ color: primary_color }}>✓</span>}
              description={x.tipo(a)}
              extra={a.concluida_por ?? "—"}
            >
              <span style={{ color: "#888" }}>{x.nome(a)}</span>
            </List.Item>
          ))
        )}
      </List>

      <Popup
        visible={filtros}
        onMaskClick={() => setFiltros(false)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16 }}
      >
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>{t("common.filters")}</div>
        <List style={{ "--border-top": "none" } as React.CSSProperties}>
          <List.Item extra={<MSwitch checked={x.minhas} onChange={x.mudarMinhas} />}>{t("web.daily.mine")}</List.Item>
        </List>
        <div style={{ color: "#999", margin: "10px 0 6px" }}>{t("web.dashboard.owner")}</div>
        <Selector
          columns={2}
          value={x.dono ? [x.dono] : []}
          onChange={(v) => x.mudarDono((v[0] as string) ?? null)}
          options={x.donos.map((d) => ({ value: d, label: d }))}
        />
        <MButton block color="primary" style={{ marginTop: 14 }} onClick={() => setFiltros(false)}>
          OK
        </MButton>
      </Popup>
    </>
  );
}
