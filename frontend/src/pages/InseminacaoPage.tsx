import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { Alert, Button, Card, Checkbox, Col, DatePicker, Empty, Flex, Input, Result, Row, Select, Space, Spin, Typography } from "antd";
import { CloseOutlined, PlusOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  Checkbox as MCheckbox,
  DotLoading,
  ErrorBlock,
  List,
  NoticeBar,
  Result as MResult,
  Stepper,
  SwipeAction,
  TextArea,
} from "antd-mobile";
import { AddOutline } from "antd-mobile-icons";

import { api } from "../api/client";
import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { dataCurta } from "../components/csv";
import { notifySuccess, useErrorMessage, useNotifyError } from "../components/errors";
import { Cabecalho, DataCampo, PickerCampo, SeletorPesquisa } from "../components/mobile";
import { localizacao, referencia, type Lote } from "./stock/api";
import { QtdPalhetas, SelecionarLotesModal } from "./stock/transfer/TransferenciasTab";
import { SelecionarLotesMobile } from "./stock/transfer/TransferenciasMobile";

interface LoteInsem {
  id: number;
  garanhao_nome: string | null;
  dono_id: number | null;
  proprietario_nome: string | null;
  data_embriovet: string | null;
  origem_externa: string | null;
  contentor_codigo: string | null;
  local_armazenagem: string | null;
  canister: number | null;
  andar: number | null;
  motilidade: number | null;
  dose: string | null;
  cor: string | null;
  concentracao: number | null;
  existencia_atual: number;
}
interface Egua {
  animal_id: number;
  nome: string;
  estadia_id: number;
  alojamento_nome: string | null;
  alojamento_tipo: string | null;
  dono_id: number | null;
  dono_nome: string | null;
}
interface Linha {
  stock_id: number;
  qty: number;
  max: number;
  ref: string;
  local: string;
  dono: string | null;
}
interface Confirmacao {
  egua: string;
  animal_id_egua: number;
  garanhao: string;
  total_palhetas: number;
  num_lotes: number;
  data_inseminacao: string;
  data_ver_ovulacao: string | null;
  data_1o_diagnostico: string;
}
interface Operacao {
  ref: string;
  animal_id_egua: number | null;
  egua: string | null;
  garanhao: string | null;
  data_inseminacao: string;
  observacoes: string | null;
  linhas: { stock_id: number; palhetas: number; max: number }[];
}

const TODOS = "__todos__";

/** Estado e regras — comum ao computador e ao telemóvel. */
function useInseminacao() {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notifyError = useNotifyError();
  const [params] = useSearchParams();
  const editarRef = params.get("editar");
  const prefillEgua = Number(params.get("egua")) || null;

  const lotes = useQuery({ queryKey: ["inseminacoes", "lotes"], queryFn: () => api<LoteInsem[]>("/inseminacoes/lotes") });
  const eguas = useQuery({ queryKey: ["inseminacoes", "eguas"], queryFn: () => api<Egua[]>("/inseminacoes/eguas") });
  const operacao = useQuery({
    queryKey: ["inseminacoes", "operacao", editarRef],
    queryFn: () => api<Operacao>(`/inseminacoes/operacao/${editarRef}`),
    enabled: !!editarRef,
  });

  const garanhoes = useMemo(
    () => [...new Set((lotes.data ?? []).map((l) => l.garanhao_nome).filter(Boolean) as string[])].sort(),
    [lotes.data],
  );
  const [garanhao, setGaranhao] = useState<string | null>(null);
  const [dono, setDono] = useState(TODOS);
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [egua, setEgua] = useState<number | null>(prefillEgua);
  const [data, setData] = useState(dayjs().format("YYYY-MM-DD"));
  const [observacoes, setObservacoes] = useState("");
  const [d1, setD1] = useState(true);
  const [modal, setModal] = useState(false);
  const [confirmacao, setConfirmacao] = useState<Confirmacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const garanhaoAtual = garanhao ?? operacao.data?.garanhao ?? garanhoes[0] ?? null;
  const doGaranhao = (lotes.data ?? []).filter((l) => l.garanhao_nome === garanhaoAtual);
  const donos = [...new Set(doGaranhao.map((l) => l.proprietario_nome).filter(Boolean) as string[])].sort();
  const disponiveis = doGaranhao.filter((l) => dono === TODOS || l.proprietario_nome === dono);

  const paraLinha = (l: LoteInsem, qty: number, max?: number): Linha => ({
    stock_id: l.id,
    qty,
    max: max ?? l.existencia_atual,
    ref: referencia(l as unknown as Lote) ?? `#${l.id}`,
    local: localizacao(l as unknown as Lote) ?? "—",
    dono: l.proprietario_nome,
  });

  // Edição: preencher a partir da operação (o lote pode já estar a 0).
  useEffect(() => {
    const op = operacao.data;
    if (!op || !lotes.data) return;
    setGaranhao(op.garanhao);
    setData(op.data_inseminacao.slice(0, 10));
    setObservacoes(op.observacoes ?? "");
    setEgua(op.animal_id_egua);
    setLinhas(
      op.linhas.map((x) => {
        const l = lotes.data.find((y) => y.id === x.stock_id);
        return l
          ? paraLinha(l, x.palhetas, x.max)
          : { stock_id: x.stock_id, qty: x.palhetas, max: x.max, ref: `#${x.stock_id}`, local: "—", dono: null };
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operacao.data, lotes.data]);

  const total = linhas.reduce((s, l) => s + l.qty, 0);
  const corpo = () => ({
    animal_id_egua: egua,
    garanhao: garanhaoAtual,
    data_inseminacao: data,
    linhas: linhas.filter((l) => l.qty > 0).map((l) => ({ stock_id: l.stock_id, palhetas: l.qty })),
    observacoes,
    criar_tarefa_d1: d1,
  });
  const invalidar = () => {
    for (const k of ["inseminacoes", "trabalho", "dashboard", "animal", "stock", "transferencias"])
      queryClient.invalidateQueries({ queryKey: [k] });
  };
  const gravar = useMutation({
    mutationFn: () =>
      editarRef ? api(`/inseminacoes/operacao/${editarRef}`, "PUT", corpo()) : api<Confirmacao>("/inseminacoes", "POST", corpo()),
    onSuccess: invalidar,
  });

  const submeter = async () => {
    setErro(null);
    if (!linhas.some((l) => l.qty > 0)) return setErro(t("error.select_lot_line"));
    if (!egua) return setErro(t("error.mare_required"));
    try {
      const r = await gravar.mutateAsync();
      if (editarRef) {
        notifySuccess(t("web.insem.updated"));
        navigate("/atividade");
      } else {
        setConfirmacao(r as Confirmacao);
        setLinhas([]);
        setObservacoes("");
      }
    } catch (err) {
      notifyError(err);
    }
  };

  return {
    t,
    navigate,
    editarRef,
    lotes,
    eguas,
    operacao,
    garanhoes,
    garanhaoAtual,
    donos,
    dono,
    disponiveis,
    linhas,
    egua,
    data,
    observacoes,
    d1,
    modal,
    setModal,
    confirmacao,
    erro,
    total,
    submeter,
    aGravar: gravar.isPending,
    mudarGaranhao: (g: string) => {
      if (g === garanhaoAtual) return;
      setGaranhao(g);
      setDono(TODOS);
      setLinhas([]);
    },
    mudarDono: (d: string) => {
      setDono(d);
      if (d !== TODOS) setLinhas([]);
    },
    adicionar: (novos: { lote: Lote; qty: number }[]) => {
      setLinhas((ls) => [
        ...ls,
        ...novos.filter((n) => !ls.some((l) => l.stock_id === n.lote.id)).map((n) => paraLinha(n.lote as unknown as LoteInsem, n.qty)),
      ]);
      setModal(false);
    },
    mudarQtd: (id: number, n: number) => setLinhas((ls) => ls.map((l) => (l.stock_id === id ? { ...l, qty: n } : l))),
    remover: (id: number) => setLinhas((ls) => ls.filter((l) => l.stock_id !== id)),
    setEgua,
    setData,
    setObservacoes,
    setD1,
    outra: () => setConfirmacao(null),
    rotuloEgua: (e: Egua) =>
      `${e.nome} — ${e.alojamento_nome ? `${e.alojamento_nome}${e.alojamento_tipo ? ` (${t(`web.housing.type.${e.alojamento_tipo}`)})` : ""}` : t("web.insem.no_housing")} — ${e.dono_nome ?? "—"}`,
  };
}
type X = ReturnType<typeof useInseminacao>;

export function InseminacaoPage() {
  const x = useInseminacao();
  return useIsMobile() ? <InseminacaoMobile x={x} /> : <InseminacaoDesktop x={x} />;
}

// ── Computador ──────────────────────────────────────────────────────────────

function ConfirmacaoDesktop({ x, c }: { x: X; c: Confirmacao }) {
  const { t } = x;
  return (
    <Card>
      <Result
        status="success"
        title={`${t("web.insem.done")} — ${c.egua} × ${c.garanhao}`}
        subTitle={t("web.insem.done_summary", { n: c.total_palhetas, l: c.num_lotes, data: dataCurta(c.data_inseminacao) })}
        extra={[
          <Button key="t" type="primary" onClick={() => x.navigate("/trabalho-diario")}>
            {t("web.insem.go_daily")}
          </Button>,
          <Button key="f" onClick={() => x.navigate(`/animais/${c.animal_id_egua}?tab=reprodutivo`)}>
            {t("web.insem.go_mare")}
          </Button>,
          <Button key="o" onClick={x.outra}>
            {t("web.insem.another")}
          </Button>,
        ]}
      >
        <Typography.Text strong>{t("web.insem.tasks_created")}</Typography.Text>
        <ul style={{ marginTop: 6 }}>
          {c.data_ver_ovulacao && (
            <li>
              <b>{dataCurta(c.data_ver_ovulacao)}</b> — {t("web.insem.task_d1")}
            </li>
          )}
          <li>
            <b>{dataCurta(c.data_1o_diagnostico)}</b> — {t("web.insem.task_d14")}
          </li>
        </ul>
      </Result>
    </Card>
  );
}

function InseminacaoDesktop({ x }: { x: X }) {
  const { t } = x;
  const errorMessage = useErrorMessage();
  if (x.confirmacao) return <ConfirmacaoDesktop x={x} c={x.confirmacao} />;
  if (x.lotes.isPending || x.eguas.isPending || (x.editarRef && x.operacao.isPending))
    return <Spin style={{ display: "block", margin: 48 }} />;
  if (x.operacao.isError) return <Alert type="error" showIcon title={errorMessage(x.operacao.error)} />;
  const eguaEditar = x.editarRef && x.operacao.data?.egua;

  return (
    <Card size="small">
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {x.editarRef ? t("web.insem.edit_title") : t("web.insem.title")}
      </Typography.Title>
      {!x.garanhoes.length ? (
        <Empty description={t("insemination.no_lotes_available")} />
      ) : (
        <Space orientation="vertical" size={16} style={{ width: "100%" }}>
          <Row gutter={[12, 8]}>
            <Col xs={24} md={12}>
              <Typography.Text type="secondary">{t("label.garanhao")}</Typography.Text>
              <Select
                showSearch
                style={{ width: "100%" }}
                value={x.garanhaoAtual ?? undefined}
                onChange={x.mudarGaranhao}
                options={x.garanhoes.map((g) => ({ value: g, label: g }))}
              />
            </Col>
            <Col xs={24} md={12}>
              <Typography.Text type="secondary">{t("label.owner")}</Typography.Text>
              <Select
                style={{ width: "100%" }}
                value={x.dono}
                onChange={x.mudarDono}
                options={[{ value: TODOS, label: t("common.all") }, ...x.donos.map((d) => ({ value: d, label: d }))]}
              />
            </Col>
          </Row>

          <div>
            <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
              {t("insemination.lines_title")}
            </Typography.Text>
            {!x.linhas.length ? (
              <Button block onClick={() => x.setModal(true)}>
                {t("btn.select_lots")}
              </Button>
            ) : (
              <Space orientation="vertical" size={6} style={{ width: "100%" }}>
                {x.linhas.map((l) => (
                  <Card key={l.stock_id} size="small" styles={{ body: { padding: "8px 12px", background: "#fafafa" } }}>
                    <Flex gap={12} align="center">
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <Typography.Text strong ellipsis style={{ display: "block" }}>
                          {l.ref} · {l.local}
                        </Typography.Text>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {l.dono ?? t("common.no_owner")} · {t("web.transfer.available", { count: l.max })}
                        </Typography.Text>
                      </div>
                      <QtdPalhetas rotulo={t("web.insem.qty")} valor={l.qty} max={l.max} onChange={(n) => x.mudarQtd(l.stock_id, n)} />
                      <Button type="text" icon={<CloseOutlined />} onClick={() => x.remover(l.stock_id)} aria-label={t("btn.remove")} />
                    </Flex>
                  </Card>
                ))}
                <Flex justify="space-between" align="center">
                  <Button type="link" icon={<PlusOutlined />} onClick={() => x.setModal(true)} style={{ paddingInline: 0 }}>
                    {t("btn.add_line")}
                  </Button>
                  <Typography.Text strong>{t("web.insem.total", { n: x.total, l: x.linhas.length })}</Typography.Text>
                </Flex>
              </Space>
            )}
          </div>

          <div>
            <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
              {t("insemination.zone_details")}
            </Typography.Text>
            {!x.eguas.data?.length && !eguaEditar ? (
              <Alert type="warning" showIcon title={t("web.insem.no_mares")} />
            ) : (
              <Row gutter={[12, 8]}>
                <Col xs={24} md={14}>
                  <Typography.Text type="secondary">{t("web.insem.mare")}</Typography.Text>
                  {eguaEditar ? (
                    <Input value={eguaEditar} disabled />
                  ) : (
                    <Select
                      showSearch
                      optionFilterProp="label"
                      style={{ width: "100%" }}
                      value={x.egua ?? undefined}
                      onChange={x.setEgua}
                      placeholder={t("web.insem.mare_help")}
                      options={(x.eguas.data ?? []).map((e) => ({ value: e.animal_id, label: x.rotuloEgua(e) }))}
                    />
                  )}
                </Col>
                <Col xs={24} md={10}>
                  <Typography.Text type="secondary">{t("label.insemination_date")}</Typography.Text>
                  <DatePicker
                    style={{ width: "100%" }}
                    format="DD/MM/YYYY"
                    allowClear={false}
                    value={dayjs(x.data)}
                    onChange={(d) => d && x.setData(d.format("YYYY-MM-DD"))}
                  />
                </Col>
                <Col span={24}>
                  <Input.TextArea
                    autoSize={{ minRows: 3 }}
                    value={x.observacoes}
                    onChange={(e) => x.setObservacoes(e.target.value)}
                    placeholder={t("web.insem.notes_placeholder")}
                  />
                </Col>
                {!x.editarRef && (
                  <Col span={24}>
                    <Checkbox checked={x.d1} onChange={(e) => x.setD1(e.target.checked)}>
                      {t("web.insem.d1")}
                    </Checkbox>
                    <div>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {t("web.insem.d1_help")}
                      </Typography.Text>
                    </div>
                  </Col>
                )}
              </Row>
            )}
          </div>

          {x.erro && <Alert type="error" showIcon title={x.erro} />}
          <Button type="primary" size="large" block loading={x.aGravar} onClick={x.submeter}>
            {x.editarRef ? t("web.insem.update") : t("web.insem.title")}
          </Button>
        </Space>
      )}
      <SelecionarLotesModal
        opened={x.modal}
        onClose={() => x.setModal(false)}
        lotes={x.disponiveis as unknown as Lote[]}
        carregando={false}
        jaSelecionados={new Set(x.linhas.map((l) => l.stock_id))}
        onConfirmar={x.adicionar}
        qtdInicial={() => 1}
        rotuloQtd={t("web.insem.qty")}
      />
    </Card>
  );
}

// ── Telemóvel ───────────────────────────────────────────────────────────────

function InseminacaoMobile({ x }: { x: X }) {
  const { t } = x;
  const errorMessage = useErrorMessage();
  const c = x.confirmacao;

  if (c)
    return (
      <>
        <MResult
          status="success"
          title={`${c.egua} × ${c.garanhao}`}
          description={t("web.insem.done_summary", { n: c.total_palhetas, l: c.num_lotes, data: dataCurta(c.data_inseminacao) })}
        />
        <List header={t("web.insem.tasks_created")}>
          {c.data_ver_ovulacao && <List.Item extra={dataCurta(c.data_ver_ovulacao)}>{t("web.insem.task_d1")}</List.Item>}
          <List.Item extra={dataCurta(c.data_1o_diagnostico)}>{t("web.insem.task_d14")}</List.Item>
        </List>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 12 }}>
          <MButton block color="primary" onClick={() => x.navigate("/trabalho-diario")}>
            {t("web.insem.go_daily")}
          </MButton>
          <MButton block onClick={() => x.navigate(`/animais/${c.animal_id_egua}?tab=reprodutivo`)}>
            {t("web.insem.go_mare")}
          </MButton>
          <MButton block onClick={x.outra}>
            {t("web.insem.another")}
          </MButton>
        </div>
      </>
    );
  if (x.lotes.isPending || x.eguas.isPending || (x.editarRef && x.operacao.isPending))
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <DotLoading color="primary" />
      </div>
    );
  if (x.operacao.isError) return <ErrorBlock status="default" title={errorMessage(x.operacao.error)} description="" />;
  if (!x.garanhoes.length) return <ErrorBlock status="empty" title={t("insemination.no_lotes_available")} description="" />;
  const eguaEditar = x.editarRef && x.operacao.data?.egua;

  return (
    <>
      {x.editarRef && <NoticeBar color="alert" content={t("web.insem.edit_title")} />}
      <List style={{ "--prefix-width": "7em" } as React.CSSProperties}>
        <Cabecalho>{t("insemination.zone_selection")}</Cabecalho>
        <List.Item prefix={t("label.garanhao")} arrow>
          <SeletorPesquisa<string>
            titulo={t("label.garanhao")}
            value={x.garanhaoAtual}
            onChange={x.mudarGaranhao}
            opcoes={x.garanhoes.map((g) => ({ value: g, label: g }))}
          />
        </List.Item>
        <List.Item prefix={t("label.owner")} arrow>
          <PickerCampo<string>
            value={x.dono}
            onChange={x.mudarDono}
            opcoes={[{ value: TODOS, label: t("common.all") }, ...x.donos.map((d) => ({ value: d, label: d }))]}
          />
        </List.Item>

        <Cabecalho>{t("insemination.lines_title")}</Cabecalho>
        {x.linhas.map((l) => (
          <SwipeAction
            key={l.stock_id}
            rightActions={[{ key: "x", text: t("btn.remove"), color: "danger", onClick: () => x.remover(l.stock_id) }]}
          >
            <List.Item
              description={`${l.dono ?? t("common.no_owner")} · ${t("web.transfer.available", { count: l.max })}`}
              extra={
                <Stepper min={1} max={l.max} digits={0} value={l.qty} onChange={(n) => x.mudarQtd(l.stock_id, n)} style={{ width: 100 }} />
              }
            >
              {l.ref} · {l.local}
            </List.Item>
          </SwipeAction>
        ))}
        <List.Item
          onClick={() => x.setModal(true)}
          extra={x.linhas.length > 0 && <b>{t("web.insem.total", { n: x.total, l: x.linhas.length })}</b>}
        >
          <span style={{ color: "var(--adm-color-primary)" }}>
            <AddOutline /> {x.linhas.length ? t("btn.add_line") : t("btn.select_lots")}
          </span>
        </List.Item>

        <Cabecalho>{t("insemination.zone_details")}</Cabecalho>
        {!x.eguas.data?.length && !eguaEditar ? (
          <List.Item>
            <span style={{ color: "var(--adm-color-warning)" }}>{t("web.insem.no_mares")}</span>
          </List.Item>
        ) : (
          <>
            <List.Item prefix={t("web.insem.mare")} arrow={!eguaEditar} description={!eguaEditar && t("web.insem.mare_help")}>
              {eguaEditar ? (
                eguaEditar
              ) : (
                <SeletorPesquisa<number>
                  titulo={t("web.insem.mare")}
                  value={x.egua}
                  onChange={x.setEgua}
                  opcoes={(x.eguas.data ?? []).map((e) => ({ value: e.animal_id, label: x.rotuloEgua(e) }))}
                />
              )}
            </List.Item>
            <List.Item prefix={t("label.insemination_date")} arrow>
              <DataCampo value={x.data} onChange={(v) => v && x.setData(v)} />
            </List.Item>
            <List.Item>
              <TextArea
                value={x.observacoes}
                onChange={x.setObservacoes}
                autoSize={{ minRows: 2, maxRows: 6 }}
                placeholder={t("web.insem.notes_placeholder")}
              />
            </List.Item>
            {!x.editarRef && (
              <List.Item description={t("web.insem.d1_help")}>
                <MCheckbox checked={x.d1} onChange={x.setD1}>
                  {t("web.insem.d1")}
                </MCheckbox>
              </List.Item>
            )}
          </>
        )}
      </List>
      <div style={{ position: "sticky", bottom: 0, zIndex: 2, padding: 12, background: "#f5f5f5", borderTop: "1px solid #eee" }}>
        {x.erro && <div style={{ color: "var(--adm-color-danger)", marginBottom: 8 }}>{x.erro}</div>}
        <MButton block color="primary" size="large" loading={x.aGravar} onClick={x.submeter}>
          {x.editarRef ? t("web.insem.update") : t("web.insem.title")}
        </MButton>
      </div>
      <SelecionarLotesMobile
        visible={x.modal}
        onClose={() => x.setModal(false)}
        lotes={x.disponiveis as unknown as Lote[]}
        carregando={false}
        jaSelecionados={new Set(x.linhas.map((l) => l.stock_id))}
        onConfirmar={x.adicionar}
        qtdInicial={() => 1}
        rotuloQtd={t("web.insem.qty")}
      />
    </>
  );
}
