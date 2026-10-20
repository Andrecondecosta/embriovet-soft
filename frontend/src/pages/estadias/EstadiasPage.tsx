import { useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import dayjs, { type Dayjs } from "dayjs";
import { Alert, Button, Card, Col, DatePicker, Flex, Form, Input, Modal, Row, Select, Statistic, Table, Tabs, Tag, Typography } from "antd";
import { LeftOutlined, PlusOutlined, RightOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  CapsuleTabs,
  DatePicker as MDatePicker,
  DotLoading,
  ErrorBlock,
  FloatingBubble,
  List,
  Popup,
  Selector,
  SwipeAction,
  Tag as MTag,
  SearchBar,
  TextArea,
} from "antd-mobile";
import { AddOutline } from "antd-mobile-icons";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { dataCurta } from "../../components/csv";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../components/errors";
import { Cabecalho } from "../../components/mobile";
import { NovaEstadia } from "./NovaEstadia";
import {
  ESTADOS_SAIDA,
  TIPOS_ANIMAL,
  useHistoricoEstadias,
  useInternadas,
  useMovimentos,
  useRegistarSaida,
  type Estadia,
  type EstadoSaida,
  type TipoAnimal,
} from "./api";

const TABS = [
  { id: "internadas", label: "web.stays.tab.internal" },
  { id: "movimentos", label: "web.stays.tab.movements" },
  { id: "historico", label: "web.stays.tab.history" },
];
type Ordem = "dias" | "nome" | "box";
const CHAVE_ORDEM: Record<Ordem, string> = { dias: "days", nome: "name", box: "box" };

/** Estado no endereço (separador, filtros, mês) — comum às duas versões. */
function useEstadias() {
  const t = useT();
  const navigate = useNavigate();
  const { tab } = useParams();
  const [params, setParams] = useSearchParams();
  const tipo = (TIPOS_ANIMAL.find((x) => x === params.get("tipo")) ?? null) as TipoAnimal | null;
  const ordem = (["dias", "nome", "box"].find((x) => x === params.get("ordem")) ?? "dias") as Ordem;
  const mes = /^\d{4}-\d{2}$/.test(params.get("mes") ?? "") ? dayjs(`${params.get("mes")}-01`) : dayjs().startOf("month");
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
  const [nova, setNova] = useState(false);
  const [saida, setSaida] = useState<Estadia | null>(null);
  // Pesquisa por nome do animal ou do proprietário — vale para os três separadores.
  const [pesquisa, setPesquisa] = useState("");
  const termo = normalizar(pesquisa.trim());
  return {
    pesquisa,
    setPesquisa,
    filtrar: (itens: Estadia[]) =>
      termo ? itens.filter((x) => normalizar(x.animal).includes(termo) || normalizar(x.proprietario).includes(termo)) : itens,
    /** Mensagem de lista vazia: "sem resultados" quando há pesquisa. */
    vazio: (padrao: string) => (termo ? t("web.common.no_results") : padrao),
    t,
    tab,
    tipo,
    ordem,
    mes,
    nova,
    setNova,
    saida,
    setSaida,
    mudarTab: (id: string) => navigate(`/estadias/${id}?${params}`),
    mudarTipo: (v: TipoAnimal | null) => atualizar("tipo", v),
    mudarOrdem: (v: Ordem) => atualizar("ordem", v === "dias" ? null : v),
    mudarMes: (d: Dayjs) => atualizar("mes", d.isSame(dayjs(), "month") ? null : d.format("YYYY-MM")),
    // A ficha do animal ainda não foi migrada: a rota mostra "em migração".
    verFicha: (e: Estadia) => navigate(`/animais/${e.animal_id}`),
    motivo: (m: string | null) => (m ? t(`web.stays.reason.${m}`) : "—"),
    estado: (s: string | null) => (s ? t(`web.stays.state.${s}`) : "—"),
    nomeMes: (d: Dayjs) => d.toDate().toLocaleDateString(undefined, { month: "long", year: "numeric" }),
  };
}
type E = ReturnType<typeof useEstadias>;

/** Sem acentos nem maiúsculas, para a pesquisa ("joao" encontra "João"). */
const normalizar = (s: string | null | undefined) =>
  (s ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

const ORDENAR: Record<Ordem, (a: Estadia, b: Estadia) => number> = {
  dias: (a, b) => (b.dias_internado ?? -1) - (a.dias_internado ?? -1),
  nome: (a, b) => (a.animal ?? "").localeCompare(b.animal ?? ""),
  box: (a, b) => (a.alojamento_nome ?? "￿").localeCompare(b.alojamento_nome ?? "￿"),
};

export function EstadiasPage() {
  const e = useEstadias();
  const isMobile = useIsMobile();
  if (!e.tab || !TABS.some((x) => x.id === e.tab)) return <Navigate to="/estadias/internadas" replace />;
  return (
    <>
      {isMobile ? <EstadiasMobile e={e} /> : <EstadiasDesktop e={e} />}
      <NovaEstadia aberto={e.nova} onClose={() => e.setNova(false)} />
      <RegistarSaida estadia={e.saida} onClose={() => e.setSaida(null)} />
    </>
  );
}

// ── Computador ──────────────────────────────────────────────────────────────

function FiltroTipo({ e }: { e: E }) {
  const { t } = e;
  return (
    <Select
      style={{ width: 160 }}
      value={e.tipo ?? "todos"}
      onChange={(v) => e.mudarTipo(v === "todos" ? null : (v as TipoAnimal))}
      options={[
        { value: "todos", label: `${t("web.stays.filter.animal_type")}: ${t("web.stays.animals.all")}` },
        ...TIPOS_ANIMAL.map((x) => ({ value: x, label: t(`web.stays.animals.${x}`) })),
      ]}
    />
  );
}

function EstadiasDesktop({ e }: { e: E }) {
  const { t } = e;
  return (
    <Card size="small">
      <Flex justify="space-between" align="center" style={{ marginBottom: 4 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t("web.nav.estadias")}
        </Typography.Title>
        <Flex gap={8}>
          <Input.Search
            allowClear
            placeholder={t("web.stays.search")}
            value={e.pesquisa}
            onChange={(ev) => e.setPesquisa(ev.target.value)}
            style={{ width: 280 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => e.setNova(true)}>
            {t("web.stays.new")}
          </Button>
        </Flex>
      </Flex>
      <Tabs
        activeKey={e.tab}
        onChange={e.mudarTab}
        destroyOnHidden
        items={TABS.map((x) => ({
          key: x.id,
          label: t(x.label),
          children:
            x.id === "internadas" ? (
              <InternadasDesktop e={e} />
            ) : x.id === "movimentos" ? (
              <MovimentosDesktop e={e} />
            ) : (
              <HistoricoDesktop e={e} />
            ),
        }))}
      />
    </Card>
  );
}

function colunasBase(e: E) {
  const { t } = e;
  return [
    {
      title: t("web.stays.col.animal"),
      dataIndex: "animal",
      render: (v: string | null) => <Typography.Text strong>{v ?? "—"}</Typography.Text>,
    },
    { title: t("web.stays.col.owner"), dataIndex: "proprietario", render: (v: string | null) => v ?? "—" },
    { title: t("web.stays.col.box"), dataIndex: "alojamento_nome", render: (v: string | null) => v ?? "—" },
    { title: t("web.stays.col.reason"), dataIndex: "motivo", render: e.motivo },
  ];
}

function InternadasDesktop({ e }: { e: E }) {
  const { t } = e;
  const errorMessage = useErrorMessage();
  const q = useInternadas(e.tipo);
  if (q.isError) return <Alert type="error" showIcon title={errorMessage(q.error)} />;
  const itens = e.filtrar(q.data?.itens ?? []).sort(ORDENAR[e.ordem]);
  const total = q.data?.total ?? 0;
  return (
    <>
      <Flex justify="space-between" align="end" wrap gap={8} style={{ marginBottom: 12 }}>
        <Statistic
          title={t("web.stays.kpi.internal")}
          value={itens.length === total ? total : t("web.stays.kpi.of", { n: itens.length, total })}
        />
        <Flex gap={8}>
          <FiltroTipo e={e} />
          <Select
            style={{ width: 170 }}
            value={e.ordem}
            onChange={e.mudarOrdem}
            options={(["dias", "nome", "box"] as const).map((o) => ({
              value: o,
              label: `${t("web.stays.filter.sort")}: ${t(`web.stays.sort.${CHAVE_ORDEM[o]}`)}`,
            }))}
          />
        </Flex>
      </Flex>
      <Table<Estadia>
        size="small"
        bordered
        rowKey="id"
        loading={q.isFetching}
        dataSource={itens}
        pagination={{ pageSize: 50, hideOnSinglePage: true, size: "small" }}
        locale={{ emptyText: e.vazio(total ? t("web.stays.empty_type") : t("web.stays.empty_internal")) }}
        columns={[
          ...colunasBase(e),
          {
            title: t("web.stays.col.days"),
            dataIndex: "dias_internado",
            width: 80,
            align: "right",
            render: (v) => (v == null ? "—" : Math.max(v, 0)),
          },
          {
            key: "acoes",
            width: 230,
            align: "right",
            render: (_, x) => (
              <Flex gap={4} justify="flex-end">
                <Button size="small" type="link" onClick={() => e.verFicha(x)}>
                  {t("web.stays.view_record")}
                </Button>
                <Button size="small" type="primary" onClick={() => e.setSaida(x)}>
                  {t("web.stays.register_exit")}
                </Button>
              </Flex>
            ),
          },
        ]}
      />
    </>
  );
}

function MovimentosDesktop({ e }: { e: E }) {
  const { t } = e;
  const q = useMovimentos();
  const entram = e.filtrar(q.data?.entram ?? []);
  const saem = e.filtrar(q.data?.saem ?? []);
  const tabela = (itens: Estadia[], campo: "data_entrada" | "data_saida", titulo: string, vazio: string) => (
    <Col xs={24} xl={12}>
      <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
        {titulo}
      </Typography.Text>
      <Table<Estadia>
        size="small"
        bordered
        rowKey="id"
        loading={q.isPending}
        dataSource={itens}
        pagination={false}
        scroll={{ y: 340 }}
        locale={{ emptyText: e.vazio(vazio) }}
        onRow={(x) => ({ onClick: () => e.verFicha(x), style: { cursor: "pointer" } })}
        columns={[
          ...colunasBase(e),
          {
            title: t(campo === "data_entrada" ? "web.stays.col.entry" : "web.stays.col.exit"),
            dataIndex: campo,
            width: 100,
            render: dataCurta,
          },
        ]}
      />
    </Col>
  );
  return (
    <>
      <Flex gap={48} style={{ marginBottom: 12 }}>
        <Statistic title={t("web.stays.kpi.enter")} value={entram.length} />
        <Statistic title={t("web.stays.kpi.exit")} value={saem.length} />
      </Flex>
      <Row gutter={[16, 16]}>
        {tabela(entram, "data_entrada", t("web.stays.enter_week"), t("web.stays.no_entries"))}
        {tabela(saem, "data_saida", t("web.stays.exit_week"), t("web.stays.no_exits"))}
      </Row>
    </>
  );
}

function HistoricoDesktop({ e }: { e: E }) {
  const { t } = e;
  const q = useHistoricoEstadias(e.mes.year(), e.mes.month() + 1, e.tipo);
  const itens = e.filtrar(q.data?.itens ?? []);
  const total = q.data?.total ?? 0;
  return (
    <>
      <Flex justify="space-between" align="end" wrap gap={8} style={{ marginBottom: 12 }}>
        <Flex gap={6} align="center">
          <Button icon={<LeftOutlined />} onClick={() => e.mudarMes(e.mes.subtract(1, "month"))} />
          <DatePicker picker="month" allowClear={false} value={e.mes} onChange={(d) => d && e.mudarMes(d)} format="MM/YYYY" />
          <Button icon={<RightOutlined />} onClick={() => e.mudarMes(e.mes.add(1, "month"))} />
        </Flex>
        <Flex gap={24} align="end">
          <Statistic
            title={t("web.stays.month_passages")}
            value={itens.length === total ? total : t("web.stays.kpi.of", { n: itens.length, total })}
          />
          <FiltroTipo e={e} />
        </Flex>
      </Flex>
      <Table<Estadia>
        size="small"
        bordered
        rowKey="id"
        loading={q.isFetching}
        dataSource={itens}
        pagination={{ pageSize: 50, hideOnSinglePage: true, size: "small" }}
        locale={{ emptyText: e.vazio(total ? t("web.stays.empty_type") : t("web.stays.no_month")) }}
        onRow={(x) => ({ onClick: () => e.verFicha(x), style: { cursor: "pointer" } })}
        columns={[
          colunasBase(e)[0],
          { title: t("web.stays.col.type"), dataIndex: "tipo", width: 90, render: (v) => t(`web.stays.kind.${v}`) },
          ...colunasBase(e).slice(1),
          { title: t("web.stays.col.state"), dataIndex: "estado", width: 110, render: (v) => <Tag>{e.estado(v)}</Tag> },
          { title: t("web.stays.col.entry"), dataIndex: "data_entrada", width: 100, render: dataCurta },
          {
            title: t("web.stays.col.exit"),
            dataIndex: "data_saida",
            width: 100,
            render: (v) => (v ? dataCurta(v) : t("web.stays.in_progress")),
          },
        ]}
      />
    </>
  );
}

// ── Registar saída (as duas versões) ────────────────────────────────────────

interface SaidaForm {
  data_saida: Dayjs | Date;
  estado: EstadoSaida;
  observacoes?: string;
}

function RegistarSaida({ estadia, onClose }: { estadia: Estadia | null; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const registar = useRegistarSaida();
  const [form] = Form.useForm<SaidaForm>();
  const [estado, setEstado] = useState<EstadoSaida>("alta");
  const [dataSaida, setDataSaida] = useState<Date>(new Date());
  const [obs, setObs] = useState("");
  const [calendario, setCalendario] = useState(false);
  const nome = estadia?.animal ?? "—";

  const guardar = async (v: SaidaForm) => {
    if (!estadia) return;
    try {
      await registar.mutateAsync({
        id: estadia.id,
        data_saida: dayjs(v.data_saida).format("YYYY-MM-DD"),
        estado: v.estado,
        observacoes: v.observacoes,
      });
      notifySuccess(t("web.stays.exit.saved"));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };
  const opcoes = ESTADOS_SAIDA.map((s) => ({ value: s, label: t(`web.stays.state.${s}`) }));

  if (isMobile)
    return (
      <Popup
        visible={estadia !== null}
        onMaskClick={onClose}
        onClose={onClose}
        destroyOnClose
        afterShow={() => {
          setEstado("alta");
          setDataSaida(new Date());
          setObs("");
        }}
        bodyStyle={{
          borderTopLeftRadius: 12,
          borderTopRightRadius: 12,
          padding: 16,
          paddingBottom: "calc(16px + env(safe-area-inset-bottom))",
        }}
      >
        <div style={{ fontWeight: 600, fontSize: 15 }}>{t("web.stays.exit.title")}</div>
        <div style={{ color: "#999", marginBottom: 8 }}>{t("web.stays.exit.of", { name: nome })}</div>
        <List style={{ "--border-top": "none", "--prefix-width": "7.5em" } as React.CSSProperties}>
          <List.Item prefix={t("web.stays.exit.date")} arrow onClick={() => setCalendario(true)}>
            {dayjs(dataSaida).format("DD/MM/YYYY")}
          </List.Item>
        </List>
        <div style={{ color: "#999", margin: "10px 0 6px" }}>{t("web.stays.exit.state")}</div>
        <Selector columns={2} showCheckMark={false} value={[estado]} onChange={(v) => v[0] && setEstado(v[0])} options={opcoes} />
        <div style={{ color: "#999", margin: "10px 0 6px" }}>
          {t("web.stays.exit.notes")}
          {estado === "sem_resultado" && " *"}
        </div>
        <TextArea
          value={obs}
          onChange={setObs}
          autoSize={{ minRows: 2, maxRows: 5 }}
          style={{ background: "#f5f5f5", padding: 8, borderRadius: 6 }}
        />
        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <MButton block onClick={onClose}>
            {t("web.common.cancel")}
          </MButton>
          <MButton
            block
            color="primary"
            loading={registar.isPending}
            onClick={() => guardar({ data_saida: dataSaida, estado, observacoes: obs })}
          >
            {t("web.stays.exit.save")}
          </MButton>
        </div>
        <MDatePicker
          visible={calendario}
          onClose={() => setCalendario(false)}
          value={dataSaida}
          max={dayjs().add(1, "year").toDate()}
          onConfirm={setDataSaida}
        />
      </Popup>
    );

  return (
    <Modal
      open={estadia !== null}
      onCancel={onClose}
      title={t("web.stays.exit.title")}
      okText={t("web.stays.exit.save")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={registar.isPending}
      destroyOnHidden
    >
      <Typography.Paragraph type="secondary">{t("web.stays.exit.of", { name: nome })}</Typography.Paragraph>
      <Form form={form} layout="vertical" preserve={false} initialValues={{ data_saida: dayjs(), estado: "alta" }} onFinish={guardar}>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="data_saida" label={t("web.stays.exit.date")} rules={[{ required: true }]}>
              <DatePicker format="DD/MM/YYYY" allowClear={false} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="estado" label={t("web.stays.exit.state")}>
              <Select options={opcoes} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item noStyle shouldUpdate={(a, b) => a.estado !== b.estado}>
          {({ getFieldValue }) => (
            <Form.Item
              name="observacoes"
              label={t("web.stays.exit.notes")}
              extra={getFieldValue("estado") === "sem_resultado" && t("web.stays.exit.notes_help")}
              rules={
                getFieldValue("estado") === "sem_resultado"
                  ? [{ required: true, whitespace: true, message: t("web.stays.error.exit_notes_required") }]
                  : []
              }
            >
              <Input.TextArea autoSize={{ minRows: 2 }} />
            </Form.Item>
          )}
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ── Telemóvel ───────────────────────────────────────────────────────────────

function EstadiasMobile({ e }: { e: E }) {
  const { t } = e;
  return (
    <>
      <CapsuleTabs activeKey={e.tab} onChange={e.mudarTab} style={{ background: "#fff" }}>
        {TABS.map((x) => (
          <CapsuleTabs.Tab key={x.id} title={t(x.label)} />
        ))}
      </CapsuleTabs>
      <div style={{ padding: "8px 12px 0", background: "#fff" }}>
        <SearchBar placeholder={t("web.stays.search")} value={e.pesquisa} onChange={e.setPesquisa} />
      </div>
      {e.tab === "internadas" ? (
        <InternadasMobile e={e} />
      ) : e.tab === "movimentos" ? (
        <MovimentosMobile e={e} />
      ) : (
        <HistoricoMobile e={e} />
      )}
      <div style={{ height: 72 }} />
      <FloatingBubble
        style={
          {
            "--initial-position-bottom": "calc(72px + env(safe-area-inset-bottom))",
            "--initial-position-right": "16px",
            "--edge-distance": "16px",
            "--size": "52px",
          } as React.CSSProperties
        }
        onClick={() => e.setNova(true)}
      >
        <AddOutline fontSize={26} />
      </FloatingBubble>
    </>
  );
}

function FiltroTipoMobile({ e }: { e: E }) {
  const { t } = e;
  return (
    <div style={{ padding: "8px 12px", background: "#fff" }}>
      <Selector
        columns={4}
        showCheckMark={false}
        value={[e.tipo ?? "todos"]}
        onChange={(v) => v[0] && e.mudarTipo(v[0] === "todos" ? null : (v[0] as TipoAnimal))}
        options={[
          { value: "todos", label: t("web.stays.animals.all") },
          ...TIPOS_ANIMAL.map((x) => ({ value: x, label: t(`web.stays.animals.${x}`) })),
        ]}
        style={{ "--padding": "4px 6px" } as React.CSSProperties}
      />
    </div>
  );
}

function LinhaMobile({ e, x, extra }: { e: E; x: Estadia; extra?: React.ReactNode }) {
  return (
    <List.Item
      arrow
      onClick={() => e.verFicha(x)}
      description={[x.proprietario, x.alojamento_nome, e.motivo(x.motivo)].filter(Boolean).join(" · ")}
      extra={extra}
    >
      {x.animal ?? "—"}
    </List.Item>
  );
}

function InternadasMobile({ e }: { e: E }) {
  const { t } = e;
  const errorMessage = useErrorMessage();
  const q = useInternadas(e.tipo);
  if (q.isError) return <ErrorBlock status="default" title={errorMessage(q.error)} description="" />;
  const itens = e.filtrar(q.data?.itens ?? []).sort(ORDENAR[e.ordem]);
  const total = q.data?.total ?? 0;
  return (
    <>
      <FiltroTipoMobile e={e} />
      <List
        header={`${t("web.stays.kpi.internal")}: ${itens.length === total ? total : t("web.stays.kpi.of", { n: itens.length, total })}`}
      >
        {q.isPending ? (
          <List.Item>
            <DotLoading />
          </List.Item>
        ) : !itens.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{e.vazio(total ? t("web.stays.empty_type") : t("web.stays.empty_internal"))}</span>
          </List.Item>
        ) : (
          itens.map((x) => (
            // Deslizar para a esquerda: Registar saída.
            <SwipeAction
              key={x.id}
              rightActions={[{ key: "saida", text: t("web.stays.register_exit"), color: "primary", onClick: () => e.setSaida(x) }]}
            >
              <LinhaMobile
                e={e}
                x={x}
                extra={x.dias_internado != null && <span style={{ fontSize: 12 }}>{Math.max(x.dias_internado, 0)} d</span>}
              />
            </SwipeAction>
          ))
        )}
      </List>
      <div style={{ padding: "8px 12px", fontSize: 11, color: "#999" }}>{t("web.mobile.swipe_hint_stays")}</div>
    </>
  );
}

function MovimentosMobile({ e }: { e: E }) {
  const { t } = e;
  const q = useMovimentos();
  if (q.isPending)
    return (
      <div style={{ textAlign: "center", padding: 24 }}>
        <DotLoading />
      </div>
    );
  const bloco = (titulo: string, itens: Estadia[], campo: "data_entrada" | "data_saida", vazio: string) => (
    <>
      <Cabecalho>
        {titulo} · {itens.length}
      </Cabecalho>
      <List>
        {!itens.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{e.vazio(vazio)}</span>
          </List.Item>
        ) : (
          itens.map((x) => <LinhaMobile key={x.id} e={e} x={x} extra={<span style={{ fontSize: 12 }}>{dataCurta(x[campo])}</span>} />)
        )}
      </List>
    </>
  );
  return (
    <>
      {bloco(t("web.stays.enter_week"), e.filtrar(q.data?.entram ?? []), "data_entrada", t("web.stays.no_entries"))}
      {bloco(t("web.stays.exit_week"), e.filtrar(q.data?.saem ?? []), "data_saida", t("web.stays.no_exits"))}
    </>
  );
}

function HistoricoMobile({ e }: { e: E }) {
  const { t } = e;
  const q = useHistoricoEstadias(e.mes.year(), e.mes.month() + 1, e.tipo);
  const [calendario, setCalendario] = useState(false);
  const itens = e.filtrar(q.data?.itens ?? []);
  const total = q.data?.total ?? 0;
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", background: "#fff" }}>
        <MButton size="small" onClick={() => e.mudarMes(e.mes.subtract(1, "month"))}>
          ‹
        </MButton>
        <MButton size="small" style={{ flex: 1 }} onClick={() => setCalendario(true)}>
          {e.nomeMes(e.mes)}
        </MButton>
        <MButton size="small" onClick={() => e.mudarMes(e.mes.add(1, "month"))}>
          ›
        </MButton>
      </div>
      <MDatePicker
        visible={calendario}
        onClose={() => setCalendario(false)}
        precision="month"
        value={e.mes.toDate()}
        min={dayjs().subtract(15, "year").toDate()}
        max={dayjs().add(2, "year").toDate()}
        onConfirm={(v) => e.mudarMes(dayjs(v).startOf("month"))}
      />
      <FiltroTipoMobile e={e} />
      <List
        header={`${t("web.stays.month_passages")}: ${itens.length === total ? total : t("web.stays.kpi.of", { n: itens.length, total })}`}
      >
        {q.isPending ? (
          <List.Item>
            <DotLoading />
          </List.Item>
        ) : !itens.length ? (
          <List.Item>
            <span style={{ color: "#999" }}>{e.vazio(total ? t("web.stays.empty_type") : t("web.stays.no_month"))}</span>
          </List.Item>
        ) : (
          itens.map((x) => (
            <List.Item
              key={x.id}
              arrow
              onClick={() => e.verFicha(x)}
              description={`${t(`web.stays.kind.${x.tipo}`)} · ${x.proprietario ?? "—"} · ${dataCurta(x.data_entrada)} → ${
                x.data_saida ? dataCurta(x.data_saida) : t("web.stays.in_progress")
              }`}
              extra={<MTag fill="outline">{e.estado(x.estado)}</MTag>}
            >
              {x.animal ?? "—"}
            </List.Item>
          ))
        )}
      </List>
    </>
  );
}
