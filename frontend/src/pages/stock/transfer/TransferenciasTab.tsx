import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Flex,
  Input,
  InputNumber,
  Modal,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { CloseOutlined, MinusOutlined, PlusOutlined } from "@ant-design/icons";

import { useT } from "../../../i18n/I18n";
import { useIsMobile } from "../../../components/responsive";
import { notifySuccess, useNotifyError } from "../../../components/errors";
import { ZoneTitle } from "../../../components/ds";
import { useGaranhoesStock, useLotes, useOpcoes, referencia, localizacao, type Lote } from "../api";
import { DonoSelect } from "../LoteForm";
import { HistoricoOperacoes } from "./HistoricoOperacoes";
import { TransferenciasMobile } from "./TransferenciasMobile";
import { MOTIVOS, useCriarOperacao, useEditarOperacao, useOperacao, type LinhaOperacao, type Motivo, type OperacaoIn } from "./api";

/** Uma linha da operação: um lote e quantas palhetas saem dele. */
interface LinhaSel {
  stock_id: number;
  dono_id: number | null;
  proprietario_nome: string | null;
  ref: string;
  local: string;
  max: number;
  qty: number;
  carac: string;
}

type LoteLike = Pick<
  Lote | LinhaOperacao,
  | "dono_id"
  | "proprietario_nome"
  | "origem_externa"
  | "data_embriovet"
  | "contentor_codigo"
  | "local_armazenagem"
  | "canister"
  | "andar"
  | "qualidade"
  | "concentracao"
  | "motilidade"
>;

function paraLinha(l: LoteLike & { stock_id: number; existencia_atual: number | null }, qty?: number): LinhaSel {
  const c = [
    l.qualidade ? `Q: ${l.qualidade}` : null,
    l.concentracao ? `C: ${l.concentracao}` : null,
    l.motilidade ? `M: ${l.motilidade}%` : null,
  ].filter(Boolean);
  const max = l.existencia_atual ?? 0;
  return {
    stock_id: l.stock_id,
    dono_id: l.dono_id,
    proprietario_nome: l.proprietario_nome,
    ref: referencia(l) ?? `#${l.stock_id}`,
    local: localizacao(l) ?? "—",
    max,
    qty: qty ?? max,
    carac: c.join(" · "),
  };
}

const TODOS = "__todos__";

/** Estado e regras de uma transferência (nova ou a editar) — partilhado
 *  pelo ecrã do computador e pelo do telemóvel. */
export function useTransferencia() {
  const t = useT();
  const notifyError = useNotifyError();
  const [params, setParams] = useSearchParams();

  // Modo de edição vem do endereço (?editar=transfer_internal-123), para
  // um "Atualizar" não perder o que se estava a editar.
  const editarParam = params.get("editar");
  const edicao = useMemo(() => {
    const m = editarParam?.match(/^(transfer_internal|transfer_external)-(\d+)$/);
    return m ? { tipo: m[1], id: Number(m[2]) } : null;
  }, [editarParam]);
  const operacao = useOperacao(edicao);

  const garanhoes = useGaranhoesStock();
  const opcoesGaranhao = (garanhoes.data ?? []).filter((g) => g.no_seletor).map((g) => g.garanhao);
  const [garanhao, setGaranhao] = useState<string | null>(null);
  const [dono, setDono] = useState<string>(TODOS);
  const [linhas, setLinhas] = useState<LinhaSel[]>([]);
  const [modalLotes, setModalLotes] = useState(false);

  const [tipo, setTipo] = useState<"interna" | "externa">("interna");
  const [destino, setDestino] = useState<number | null>(null);
  const [mudaLocal, setMudaLocal] = useState(false);
  const [contentor, setContentor] = useState<number | null>(null);
  const [canister, setCanister] = useState<number>(1);
  const [andar, setAndar] = useState<number>(1);
  const [destinatario, setDestinatario] = useState("");
  const [motivo, setMotivo] = useState<Motivo>("Venda");
  const [observacoes, setObservacoes] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const limpar = () => {
    setLinhas([]);
    setDono(TODOS);
    setTipo("interna");
    setDestino(null);
    setMudaLocal(false);
    setContentor(null);
    setCanister(1);
    setAndar(1);
    setDestinatario("");
    setMotivo("Venda");
    setObservacoes("");
    setErro(null);
  };

  // Garanhão por omissão: o primeiro com stock (como a app atual).
  const garanhaoAtual = garanhao && opcoesGaranhao.includes(garanhao) ? garanhao : (opcoesGaranhao[0] ?? null);
  const lotesGaranhao = useLotes(
    garanhaoAtual ? { garanhao: garanhaoAtual, donos: [], semDono: false, minPalhetas: 0, incluirVazios: false } : null,
  );

  // Pré-preencher a partir da operação a editar.
  useEffect(() => {
    const op = operacao.data;
    if (!op) return;
    limpar();
    if (op.linhas[0]) setGaranhao(op.linhas[0].garanhao);
    setLinhas(op.linhas.map((l) => paraLinha(l, l.quantidade)));
    if (op.tipo === "transfer_internal") {
      setTipo("interna");
      setDestino(op.destino_id);
    } else {
      setTipo("externa");
      setDestinatario(op.destinatario ?? "");
      setMotivo((op.motivo as Motivo) ?? "Venda");
      setObservacoes(op.observacoes ?? "");
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operacao.data]);

  const sairEdicao = () => {
    limpar();
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        r.delete("editar");
        return r;
      },
      { replace: true },
    );
  };

  const mudarGaranhao = (g: string) => {
    if (g === garanhaoAtual) return;
    setGaranhao(g);
    setDono(TODOS);
    setLinhas([]);
  };
  const mudarDono = (d: string) => {
    setDono(d);
    if (d !== TODOS) setLinhas([]);
  };

  // Destinos possíveis: donos ativos, menos o dono de origem quando todos
  // os lotes são do mesmo (como a app atual).
  const donosAtivos = useOpcoes("proprietarios", true);
  const origens = new Set(linhas.map((l) => l.dono_id).filter((x) => x !== null));
  const destinos = (donosAtivos.data ?? []).filter((d) => !(origens.size === 1 && origens.has(d.id)));
  const contentores = useOpcoes("contentores");
  const total = linhas.reduce((s, l) => s + l.qty, 0);

  const criar = useCriarOperacao();
  const editar = useEditarOperacao();

  const executar = async () => {
    setErro(null);
    const finais = linhas.filter((l) => l.qty > 0);
    if (!finais.length) return setErro(t("error.select_lot_line"));
    if (tipo === "interna" && !destino) return setErro(t("transfer.error_no_destination"));
    if (tipo === "interna" && mudaLocal && !contentor) return setErro(t("transfer.error_no_container"));
    if (tipo === "externa" && !destinatario.trim()) return setErro(t("transfer.error_no_recipient"));
    const body: OperacaoIn = {
      tipo,
      linhas: finais.map((l) => ({ stock_id: l.stock_id, quantidade: l.qty })),
      ...(tipo === "interna"
        ? { destino_id: destino, nova_localizacao: mudaLocal && contentor ? { contentor_id: contentor, canister, andar } : null }
        : { destinatario, motivo, observacoes }),
    };
    try {
      if (edicao) await editar.mutateAsync({ ...body, tipoOp: edicao.tipo, id: edicao.id });
      else await criar.mutateAsync(body);
      notifySuccess(edicao ? t("web.transfer.updated") : t("web.transfer.done"));
      if (edicao) sairEdicao();
      else limpar();
    } catch (err) {
      notifyError(err);
    }
  };

  const editarOperacao = (op: { tipo: string; action_id: number }) =>
    setParams((p) => {
      const r = new URLSearchParams(p);
      r.set("editar", `${op.tipo}-${op.action_id}`);
      return r;
    });
  const adicionarLotes = (novos: { lote: Lote; qty: number }[]) =>
    setLinhas((ls) => [
      ...ls,
      ...novos.filter((n) => !ls.some((l) => l.stock_id === n.lote.id)).map((n) => paraLinha({ ...n.lote, stock_id: n.lote.id }, n.qty)),
    ]);
  const mudarQtd = (stockId: number, n: number) => setLinhas((ls) => ls.map((x) => (x.stock_id === stockId ? { ...x, qty: n } : x)));
  const removerLinha = (stockId: number) => setLinhas((ls) => ls.filter((x) => x.stock_id !== stockId));
  const lotesDisponiveis = (lotesGaranhao.data?.items ?? []).filter((l) => dono === TODOS || String(l.dono_id) === dono);
  const opcoesDono = [
    { value: TODOS, label: t("common.all") },
    ...(lotesGaranhao.data?.donos_disponiveis ?? [])
      .filter((d) => d.id !== null)
      .map((d) => ({ value: String(d.id), label: d.nome ?? "" })),
  ];
  const listaGaranhoes = garanhaoAtual && !opcoesGaranhao.includes(garanhaoAtual) ? [garanhaoAtual, ...opcoesGaranhao] : opcoesGaranhao;
  const aCarregar = garanhoes.isPending || (!!edicao && operacao.isPending);
  const aGuardar = criar.isPending || editar.isPending;

  return {
    edicao,
    operacao,
    opcoesGaranhao,
    listaGaranhoes,
    garanhaoAtual,
    mudarGaranhao,
    dono,
    mudarDono,
    opcoesDono,
    linhas,
    mudarQtd,
    removerLinha,
    adicionarLotes,
    lotesDisponiveis,
    lotesACarregar: lotesGaranhao.isPending,
    modalLotes,
    setModalLotes,
    tipo,
    setTipo,
    destino,
    setDestino,
    destinos,
    donosAtivos,
    mudaLocal,
    setMudaLocal,
    contentor,
    setContentor,
    contentores,
    canister,
    setCanister,
    andar,
    setAndar,
    destinatario,
    setDestinatario,
    motivo,
    setMotivo,
    observacoes,
    setObservacoes,
    erro,
    total,
    executar,
    aGuardar,
    aCarregar,
    sairEdicao,
    editarOperacao,
  };
}

export function TransferenciasTab() {
  return useIsMobile() ? <TransferenciasMobile /> : <TransferenciasDesktop />;
}

function TransferenciasDesktop() {
  const t = useT();
  const {
    edicao,
    operacao,
    opcoesGaranhao,
    listaGaranhoes,
    garanhaoAtual,
    mudarGaranhao,
    dono,
    mudarDono,
    opcoesDono,
    linhas,
    mudarQtd,
    removerLinha,
    adicionarLotes,
    lotesDisponiveis,
    lotesACarregar,
    modalLotes,
    setModalLotes,
    tipo,
    setTipo,
    destino,
    setDestino,
    destinos,
    donosAtivos,
    mudaLocal,
    setMudaLocal,
    contentor,
    setContentor,
    contentores,
    canister,
    setCanister,
    andar,
    setAndar,
    destinatario,
    setDestinatario,
    motivo,
    setMotivo,
    observacoes,
    setObservacoes,
    erro,
    total,
    executar,
    aGuardar,
    aCarregar,
    sairEdicao,
    editarOperacao,
  } = useTransferencia();

  if (aCarregar) return <Spin style={{ display: "block", margin: 32 }} />;

  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      {edicao && (
        <Alert
          type="warning"
          showIcon
          title={t("web.transfer.edit_mode")}
          action={
            <Button size="small" onClick={sairEdicao}>
              {t("web.transfer.cancel_edit")}
            </Button>
          }
        />
      )}
      {edicao && operacao.isError && <Alert type="error" showIcon title={t("web.transfer.error.not_found")} />}

      {!opcoesGaranhao.length && !edicao ? (
        <Empty description={t("transfer.no_stock_available")} />
      ) : (
        <Card size="small">
          {/* 1. Seleção */}
          <ZoneTitle primeiro>{t("transfer.zone_selection")}</ZoneTitle>
          <Row gutter={[12, 8]}>
            <Col xs={24} md={12}>
              <Typography.Text type="secondary">{t("label.garanhao")}</Typography.Text>
              <Select
                showSearch
                style={{ width: "100%" }}
                value={garanhaoAtual ?? undefined}
                onChange={mudarGaranhao}
                options={listaGaranhoes.map((g) => ({ value: g, label: g }))}
                notFoundContent={t("web.common.no_results")}
              />
            </Col>
            <Col xs={24} md={12}>
              <Typography.Text type="secondary">{t("label.owner")}</Typography.Text>
              <Select style={{ width: "100%" }} value={dono} onChange={mudarDono} options={opcoesDono} />
            </Col>
            <Col span={24}>
              <Button block onClick={() => setModalLotes(true)} disabled={!garanhaoAtual}>
                {t("btn.select_lots")}
              </Button>
            </Col>
          </Row>

          {/* 2. Lotes selecionados */}
          <ZoneTitle>{t("transfer.selected_lots")}</ZoneTitle>
          {!linhas.length ? (
            <Typography.Text type="secondary">{t("transfer.no_lotes_selected_hint")}</Typography.Text>
          ) : (
            <Space orientation="vertical" size={6} style={{ width: "100%" }}>
              {linhas.map((l) => (
                <Card key={l.stock_id} size="small" styles={{ body: { padding: "8px 12px", background: "#fafafa" } }}>
                  <Flex gap={12} align="center">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {dono === TODOS && (
                        <Typography.Text strong ellipsis style={{ display: "block" }}>
                          {l.proprietario_nome ?? t("common.no_owner")}
                        </Typography.Text>
                      )}
                      <Typography.Text strong={dono !== TODOS} ellipsis style={{ display: "block" }}>
                        {l.ref} · {l.local}
                      </Typography.Text>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {t("web.transfer.available", { count: l.max })}
                        {l.carac && ` · ${l.carac}`}
                      </Typography.Text>
                    </div>
                    <QtdPalhetas valor={l.qty} max={l.max} onChange={(n) => mudarQtd(l.stock_id, n)} />
                    <Button type="text" icon={<CloseOutlined />} onClick={() => removerLinha(l.stock_id)} aria-label={t("btn.remove")} />
                  </Flex>
                </Card>
              ))}
              <Flex justify="space-between" align="center">
                <Button type="link" icon={<PlusOutlined />} onClick={() => setModalLotes(true)} style={{ paddingInline: 0 }}>
                  {t("btn.add_line")}
                </Button>
                <Typography.Text strong>{t("web.transfer.total", { count: total })}</Typography.Text>
              </Flex>
            </Space>
          )}

          {/* 3. Destino */}
          {linhas.length > 0 && (
            <>
              <ZoneTitle>{t("transfer.destination")}</ZoneTitle>
              <Space orientation="vertical" size={12} style={{ width: "100%" }}>
                <Segmented
                  value={tipo}
                  onChange={(v) => setTipo(v as "interna" | "externa")}
                  options={[
                    { value: "interna", label: t("transfer.internal") },
                    { value: "externa", label: t("transfer.external") },
                  ]}
                />

                {tipo === "interna" ? (
                  <>
                    {destinos.length === 0 && donosAtivos.data && (
                      <Alert type="warning" showIcon title={t("web.transfer.no_other_owners")} />
                    )}
                    <div>
                      <Typography.Text type="secondary">{t("transfer.destination_owner")} *</Typography.Text>
                      <DonoSelect
                        apenasAtivos
                        value={destino}
                        onChange={setDestino}
                        dataOverride={destinos.map((d) => ({ value: String(d.id), label: d.nome }))}
                      />
                    </div>
                    <div>
                      <Typography.Text type="secondary">{t("transfer.change_location")}</Typography.Text>
                      <Segmented
                        block
                        value={mudaLocal ? "nova" : "manter"}
                        onChange={(v) => setMudaLocal(v === "nova")}
                        options={[
                          { value: "manter", label: t("transfer.keep_location") },
                          { value: "nova", label: t("transfer.new_location") },
                        ]}
                      />
                    </div>
                    {mudaLocal && (
                      <Row gutter={12}>
                        <Col xs={24} sm={8}>
                          <Typography.Text type="secondary">{t("label.container")} *</Typography.Text>
                          <Select
                            showSearch
                            optionFilterProp="label"
                            style={{ width: "100%" }}
                            value={contentor ?? undefined}
                            onChange={(v) => setContentor(v)}
                            options={(contentores.data ?? []).map((c) => ({ value: c.id, label: c.nome }))}
                          />
                        </Col>
                        <Col xs={12} sm={8}>
                          <Typography.Text type="secondary">{t("label.canister")}</Typography.Text>
                          <InputNumber
                            min={1}
                            max={20}
                            style={{ width: "100%" }}
                            value={canister}
                            onChange={(v) => setCanister(Number(v) || 1)}
                          />
                        </Col>
                        <Col xs={12} sm={8}>
                          <Typography.Text type="secondary">{t("label.floor")}</Typography.Text>
                          <InputNumber
                            min={1}
                            max={20}
                            style={{ width: "100%" }}
                            value={andar}
                            onChange={(v) => setAndar(Number(v) || 1)}
                          />
                        </Col>
                      </Row>
                    )}
                  </>
                ) : (
                  <Row gutter={[12, 8]}>
                    <Col xs={24} sm={12}>
                      <Typography.Text type="secondary">{t("transfer.external_recipient")} *</Typography.Text>
                      <Input value={destinatario} onChange={(e) => setDestinatario(e.target.value)} />
                    </Col>
                    <Col xs={24} sm={12}>
                      <Typography.Text type="secondary">{t("transfer.reason")}</Typography.Text>
                      <Select
                        style={{ width: "100%" }}
                        value={motivo}
                        onChange={(v) => setMotivo(v)}
                        options={MOTIVOS.map((m) => ({ value: m.value, label: t(m.label) }))}
                      />
                    </Col>
                    <Col span={24}>
                      <Typography.Text type="secondary">{t("label.notes")}</Typography.Text>
                      <Input.TextArea autoSize={{ minRows: 2 }} value={observacoes} onChange={(e) => setObservacoes(e.target.value)} />
                    </Col>
                  </Row>
                )}

                {erro && <Alert type="error" showIcon title={erro} />}
                <Flex justify="flex-end">
                  <Button type="primary" onClick={executar} loading={aGuardar}>
                    {edicao ? t("web.transfer.update_btn") : t("btn.execute_transfer")}
                  </Button>
                </Flex>
              </Space>
            </>
          )}
        </Card>
      )}

      {/* Escondido durante a edição, como na app atual. */}
      {!edicao && <HistoricoOperacoes onEditar={editarOperacao} />}

      <SelecionarLotesModal
        opened={modalLotes}
        onClose={() => setModalLotes(false)}
        lotes={lotesDisponiveis}
        carregando={lotesACarregar}
        jaSelecionados={new Set(linhas.map((l) => l.stock_id))}
        onConfirmar={(novos) => {
          adicionarLotes(novos);
          setModalLotes(false);
        }}
      />
    </Space>
  );
}

/** Quantas palhetas saem de um lote: − [n] + "de N". */
export function QtdPalhetas({
  valor,
  max,
  onChange,
  rotulo,
}: {
  valor: number;
  max: number;
  onChange: (n: number) => void;
  rotulo?: string;
}) {
  const t = useT();
  const definir = (n: number) => onChange(Math.max(1, Math.min(max, n || 1)));
  return (
    <div onClick={(e) => e.stopPropagation()}>
      <Typography.Text type="secondary" style={{ fontSize: 12, display: "block" }}>
        {rotulo ?? t("web.transfer.qty_to_send")}
      </Typography.Text>
      <Space.Compact>
        <Button icon={<MinusOutlined />} onClick={() => definir(valor - 1)} disabled={valor <= 1} aria-label="−" />
        <InputNumber
          aria-label={rotulo ?? t("web.transfer.qty_to_send")}
          value={valor}
          onChange={(v) => definir(Number(v))}
          min={1}
          max={max}
          controls={false}
          style={{ width: 64, textAlign: "center" }}
          inputMode="numeric"
        />
        <Button icon={<PlusOutlined />} onClick={() => definir(valor + 1)} disabled={valor >= max} aria-label="+" />
      </Space.Compact>
      <Typography.Text type="secondary" style={{ marginLeft: 8, whiteSpace: "nowrap" }}>
        {t("web.transfer.of_max", { max })}
      </Typography.Text>
    </div>
  );
}

export function SelecionarLotesModal({
  opened,
  onClose,
  lotes,
  carregando,
  jaSelecionados,
  onConfirmar,
  qtdInicial,
  rotuloQtd,
}: {
  opened: boolean;
  onClose: () => void;
  lotes: Lote[];
  carregando: boolean;
  jaSelecionados: Set<number>;
  onConfirmar: (l: { lote: Lote; qty: number }[]) => void;
  /** Palhetas ao marcar um lote (por omissão, o lote todo). */
  qtdInicial?: (l: Lote) => number;
  rotuloQtd?: string;
}) {
  const t = useT();
  // Lotes marcados → palhetas a enviar de cada um (começa no total do lote).
  const [sel, setSel] = useState<Map<number, number>>(new Map());
  useEffect(() => {
    if (opened) setSel(new Map());
  }, [opened]);

  // Mais recentes primeiro (data de produção), como a app atual.
  const ordenados = [...lotes].sort((a, b) => (b.data_embriovet ?? "").localeCompare(a.data_embriovet ?? ""));

  return (
    <Modal
      open={opened}
      onCancel={onClose}
      title={t("transfer.select_lots_title")}
      width={680}
      okText={t("btn.confirm_selection")}
      cancelText={t("btn.close")}
      okButtonProps={{ disabled: !sel.size }}
      onOk={() => onConfirmar(ordenados.filter((l) => sel.has(l.id)).map((l) => ({ lote: l, qty: sel.get(l.id)! })))}
    >
      {carregando ? (
        <Spin style={{ display: "block", margin: 24 }} />
      ) : !ordenados.length ? (
        <Empty description={t("transfer.no_lotes_for_filters")} />
      ) : (
        <Space orientation="vertical" size={6} style={{ width: "100%" }}>
          {ordenados.map((l) => {
            const ja = jaSelecionados.has(l.id);
            const marcado = ja || sel.has(l.id);
            const alternar = () =>
              !ja &&
              setSel((s) => {
                const n = new Map(s);
                if (n.has(l.id)) n.delete(l.id);
                else n.set(l.id, qtdInicial ? qtdInicial(l) : (l.existencia_atual ?? 0));
                return n;
              });
            return (
              <Card
                key={l.id}
                size="small"
                hoverable={!ja}
                onClick={alternar}
                style={{ opacity: ja ? 0.55 : 1, borderColor: sel.has(l.id) ? undefined : undefined }}
                styles={{ body: { padding: "8px 12px" } }}
              >
                <Flex gap={10} align="center">
                  <Checkbox checked={marcado} disabled={ja} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Typography.Text strong ellipsis style={{ display: "block" }}>
                      {referencia(l) ?? `#${l.id}`} · {localizacao(l) ?? "—"}
                    </Typography.Text>
                    <Typography.Text type="secondary" ellipsis style={{ fontSize: 12, display: "block" }}>
                      {l.proprietario_nome ?? t("common.no_owner")}
                      {l.qualidade ? ` · Q: ${l.qualidade}` : ""}
                      {l.concentracao ? ` · C: ${l.concentracao}` : ""}
                      {l.motilidade ? ` · M: ${l.motilidade}%` : ""}
                    </Typography.Text>
                  </div>
                  <Tag color="red" style={{ marginInlineEnd: 0 }}>
                    {t("web.stock.straws_count", { count: l.existencia_atual ?? 0 })}
                  </Tag>
                </Flex>
                {sel.has(l.id) && (
                  <div style={{ marginTop: 8, paddingLeft: 26 }}>
                    <QtdPalhetas rotulo={rotuloQtd}
                      valor={sel.get(l.id)!}
                      max={l.existencia_atual ?? 0}
                      onChange={(n) => setSel((s) => new Map(s).set(l.id, n))}
                    />
                  </div>
                )}
              </Card>
            );
          })}
        </Space>
      )}
    </Modal>
  );
}
