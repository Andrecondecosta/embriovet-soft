import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import {
  Button,
  Checkbox,
  DatePicker,
  Dialog,
  DotLoading,
  ErrorBlock,
  Input,
  List,
  NoticeBar,
  Popup,
  Selector,
  Stepper,
  SwipeAction,
  Tag,
  TextArea,
} from "antd-mobile";
import { AddOutline, LeftOutline, RightOutline } from "antd-mobile-icons";

import type { Owner } from "../../../api/types";
import { useT } from "../../../i18n/I18n";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../../components/errors";
import { Cabecalho, PickerCampo, SeletorPesquisa } from "../../../components/mobile";
import { OwnerFormModal } from "../../owners/OwnerFormModal";
import { localizacao, referencia, type Lote } from "../api";
import { MOTIVOS, useAnular, type Motivo, type OpHistorico } from "./api";
import { hora, useDiaHistorico } from "./HistoricoOperacoes";
import { useTransferencia } from "./TransferenciasTab";

/** Transferências no telemóvel (Ant Design Mobile) — a mesma lógica da
 *  versão de computador (`useTransferencia`). */
export function TransferenciasMobile() {
  const t = useT();
  const queryClient = useQueryClient();
  const x = useTransferencia();
  const [novoDono, setNovoDono] = useState(false);

  if (x.aCarregar)
    return (
      <div style={{ textAlign: "center", padding: 32 }}>
        <DotLoading color="primary" />
      </div>
    );

  const linha = (titulo: string) => <Cabecalho>{titulo}</Cabecalho>;

  return (
    <div>
      {x.edicao && (
        <NoticeBar
          color="alert"
          content={t("web.transfer.edit_mode")}
          wrap
          extra={
            <Button size="mini" onClick={x.sairEdicao}>
              {t("web.transfer.cancel_edit")}
            </Button>
          }
        />
      )}
      {x.edicao && x.operacao.isError && <NoticeBar color="error" content={t("web.transfer.error.not_found")} wrap />}

      {!x.opcoesGaranhao.length && !x.edicao ? (
        <ErrorBlock status="empty" title={t("transfer.no_stock_available")} description="" />
      ) : (
        <List style={{ "--prefix-width": "7.5em" } as React.CSSProperties}>
          {/* 1. Seleção */}
          {linha(t("transfer.zone_selection"))}
          <List.Item prefix={t("label.garanhao")} arrow>
            <SeletorPesquisa<string>
              titulo={t("label.garanhao")}
              value={x.garanhaoAtual}
              onChange={x.mudarGaranhao}
              opcoes={x.listaGaranhoes.map((g) => ({ value: g, label: g }))}
            />
          </List.Item>
          <List.Item prefix={t("label.owner")} arrow>
            <PickerCampo<string> titulo={t("label.owner")} value={x.dono} onChange={x.mudarDono} opcoes={x.opcoesDono} />
          </List.Item>

          {/* 2. Lotes selecionados — deslizar para a esquerda para retirar. */}
          {linha(t("transfer.selected_lots"))}
          {x.linhas.map((l) => (
            <SwipeAction
              key={l.stock_id}
              rightActions={[{ key: "x", text: t("btn.remove"), color: "danger", onClick: () => x.removerLinha(l.stock_id) }]}
            >
              <List.Item
                description={
                  <>
                    {l.local} · {t("web.transfer.available", { count: l.max })}
                    {l.carac && <div>{l.carac}</div>}
                  </>
                }
                extra={
                  <Stepper
                    min={1}
                    max={l.max}
                    digits={0}
                    value={l.qty}
                    onChange={(n) => x.mudarQtd(l.stock_id, n)}
                    style={{ width: 100 }}
                  />
                }
              >
                {x.dono === "__todos__" ? `${l.proprietario_nome ?? t("common.no_owner")} · ${l.ref}` : l.ref}
              </List.Item>
            </SwipeAction>
          ))}
          <List.Item
            onClick={x.garanhaoAtual ? () => x.setModalLotes(true) : undefined}
            disabled={!x.garanhaoAtual}
            extra={x.linhas.length > 0 && <b>{t("web.transfer.total", { count: x.total })}</b>}
            style={{ color: "var(--adm-color-primary)" }}
          >
            <AddOutline /> {x.linhas.length ? t("btn.add_line") : t("btn.select_lots")}
          </List.Item>

          {/* 3. Destino */}
          {x.linhas.length > 0 && (
            <>
              {linha(t("transfer.destination"))}
              <List.Item>
                <Selector
                  columns={2}
                  showCheckMark={false}
                  value={[x.tipo]}
                  onChange={(v) => v[0] && x.setTipo(v[0])}
                  options={[
                    { value: "interna" as const, label: t("transfer.internal") },
                    { value: "externa" as const, label: t("transfer.external") },
                  ]}
                />
              </List.Item>

              {x.tipo === "interna" ? (
                <>
                  {x.destinos.length === 0 && x.donosAtivos.data && (
                    <List.Item>
                      <span style={{ color: "var(--adm-color-warning)" }}>{t("web.transfer.no_other_owners")}</span>
                    </List.Item>
                  )}
                  <List.Item prefix={<Obrigatorio>{t("transfer.destination_owner")}</Obrigatorio>} arrow>
                    <SeletorPesquisa<number>
                      titulo={t("transfer.destination_owner")}
                      value={x.destino}
                      onChange={x.setDestino}
                      opcoes={x.destinos.map((d) => ({ value: d.id, label: d.nome }))}
                      acao={{ texto: t("web.owners.new"), onClick: () => setNovoDono(true) }}
                    />
                  </List.Item>
                  <List.Item>
                    <Selector
                      columns={2}
                      showCheckMark={false}
                      value={[x.mudaLocal ? "nova" : "manter"]}
                      onChange={(v) => v[0] && x.setMudaLocal(v[0] === "nova")}
                      options={[
                        { value: "manter", label: t("transfer.keep_location") },
                        { value: "nova", label: t("transfer.new_location") },
                      ]}
                    />
                  </List.Item>
                  {x.mudaLocal && (
                    <>
                      <List.Item prefix={<Obrigatorio>{t("label.container")}</Obrigatorio>} arrow>
                        <SeletorPesquisa<number>
                          titulo={t("label.container")}
                          value={x.contentor}
                          onChange={x.setContentor}
                          opcoes={(x.contentores.data ?? [])
                            .map((c) => ({ value: c.id, label: c.nome }))
                            .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }))}
                        />
                      </List.Item>
                      <List.Item
                        prefix={t("label.canister")}
                        extra={<Stepper min={1} max={20} digits={0} value={x.canister} onChange={x.setCanister} />}
                      />
                      <List.Item
                        prefix={t("label.floor")}
                        extra={<Stepper min={1} max={20} digits={0} value={x.andar} onChange={x.setAndar} />}
                      />
                    </>
                  )}
                </>
              ) : (
                <>
                  <List.Item prefix={<Obrigatorio>{t("transfer.external_recipient")}</Obrigatorio>}>
                    <Input value={x.destinatario} onChange={x.setDestinatario} clearable />
                  </List.Item>
                  <List.Item prefix={t("transfer.reason")} arrow>
                    <PickerCampo<Motivo>
                      titulo={t("transfer.reason")}
                      value={x.motivo}
                      onChange={x.setMotivo}
                      opcoes={MOTIVOS.map((m) => ({ value: m.value, label: t(m.label) }))}
                    />
                  </List.Item>
                  <List.Item prefix={t("label.notes")}>
                    <TextArea autoSize={{ minRows: 1, maxRows: 5 }} value={x.observacoes} onChange={x.setObservacoes} />
                  </List.Item>
                </>
              )}
            </>
          )}
        </List>
      )}

      {x.linhas.length > 0 && (
        <div style={{ position: "sticky", bottom: 0, zIndex: 2, padding: 12, background: "#f5f5f5", borderTop: "1px solid #eee" }}>
          {x.erro && <div style={{ color: "var(--adm-color-danger)", marginBottom: 8 }}>{x.erro}</div>}
          <Button block color="primary" size="large" loading={x.aGuardar} onClick={x.executar}>
            {x.edicao ? t("web.transfer.update_btn") : t("btn.execute_transfer")}
          </Button>
        </div>
      )}

      {/* Escondido durante a edição, como na app atual. */}
      {!x.edicao && <HistoricoMobile onEditar={x.editarOperacao} />}

      <SelecionarLotesMobile
        visible={x.modalLotes}
        onClose={() => x.setModalLotes(false)}
        lotes={x.lotesDisponiveis}
        carregando={x.lotesACarregar}
        jaSelecionados={new Set(x.linhas.map((l) => l.stock_id))}
        onConfirmar={(novos) => {
          x.adicionarLotes(novos);
          x.setModalLotes(false);
        }}
      />
      <OwnerFormModal
        opened={novoDono}
        owner={null}
        onClose={() => setNovoDono(false)}
        onSaved={async (o: Owner) => {
          await queryClient.invalidateQueries({ queryKey: ["opcoes", "proprietarios"] });
          x.setDestino(o.id);
        }}
      />
    </div>
  );
}

function Obrigatorio({ children }: { children: string }) {
  return (
    <>
      <span style={{ color: "var(--adm-color-danger)" }}>* </span>
      {children}
    </>
  );
}

/** Escolher lotes: folha de baixo; os marcados mostram quantas palhetas enviar. */
export function SelecionarLotesMobile({
  visible,
  onClose,
  lotes,
  carregando,
  jaSelecionados,
  onConfirmar,
  qtdInicial,
  rotuloQtd,
}: {
  visible: boolean;
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
  const [sel, setSel] = useState<Map<number, number>>(new Map());
  useEffect(() => {
    if (visible) setSel(new Map());
  }, [visible]);
  // Mais recentes primeiro (data de produção), como a app atual.
  const ordenados = [...lotes].sort((a, b) => (b.data_embriovet ?? "").localeCompare(a.data_embriovet ?? ""));

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      onClose={onClose}
      bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, height: "85dvh", display: "flex", flexDirection: "column" }}
    >
      <div style={{ padding: "14px 16px 8px", fontWeight: 600, fontSize: 15 }}>{t("transfer.select_lots_title")}</div>
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
        {carregando ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <DotLoading />
          </div>
        ) : !ordenados.length ? (
          <ErrorBlock status="empty" title={t("transfer.no_lotes_for_filters")} description="" />
        ) : (
          <List>
            {ordenados.map((l) => {
              const ja = jaSelecionados.has(l.id);
              const qty = sel.get(l.id);
              const alternar = () =>
                !ja &&
                setSel((s) => {
                  const n = new Map(s);
                  if (n.has(l.id)) n.delete(l.id);
                  else n.set(l.id, qtdInicial ? qtdInicial(l) : (l.existencia_atual ?? 0));
                  return n;
                });
              return (
                <List.Item
                  key={l.id}
                  disabled={ja}
                  onClick={alternar}
                  arrow={false}
                  prefix={<Checkbox checked={ja || qty !== undefined} disabled={ja} />}
                  description={
                    <>
                      {l.proprietario_nome ?? t("common.no_owner")}
                      {l.qualidade ? ` · Q: ${l.qualidade}` : ""}
                      {l.concentracao ? ` · C: ${l.concentracao}` : ""}
                      {l.motilidade ? ` · M: ${l.motilidade}%` : ""}
                      {qty !== undefined && (
                        <div onClick={(e) => e.stopPropagation()} style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 8 }}>
                          <span>{rotuloQtd ?? t("web.transfer.qty_to_send")}</span>
                          <Stepper
                            min={1}
                            max={l.existencia_atual ?? 0}
                            digits={0}
                            value={qty}
                            onChange={(n) => setSel((s) => new Map(s).set(l.id, n))}
                          />
                        </div>
                      )}
                    </>
                  }
                  extra={
                    <Tag color="primary" fill="outline">
                      {t("web.stock.straws_count", { count: l.existencia_atual ?? 0 })}
                    </Tag>
                  }
                >
                  {referencia(l) ?? `#${l.id}`} · {localizacao(l) ?? "—"}
                </List.Item>
              );
            })}
          </List>
        )}
      </div>
      <div
        style={{
          display: "flex",
          gap: 8,
          padding: 12,
          paddingBottom: "calc(12px + env(safe-area-inset-bottom))",
          borderTop: "1px solid #eee",
        }}
      >
        <Button block onClick={onClose}>
          {t("btn.close")}
        </Button>
        <Button
          block
          color="primary"
          disabled={!sel.size}
          onClick={() => onConfirmar(ordenados.filter((l) => sel.has(l.id)).map((l) => ({ lote: l, qty: sel.get(l.id)! })))}
        >
          {t("btn.confirm_selection")}
        </Button>
      </div>
    </Popup>
  );
}

/** Histórico do dia: ‹ data › em cima; deslizar uma operação para Editar/Anular. */
export function HistoricoMobile({
  onEditar,
  comUtilizador = false,
  titulo,
  editarInseminacoes = false,
}: {
  onEditar: (op: OpHistorico) => void;
  comUtilizador?: boolean;
  titulo?: string;
  editarInseminacoes?: boolean;
}) {
  const t = useT();
  const errorMessage = useErrorMessage();
  const notifyError = useNotifyError();
  const anular = useAnular();
  const { dia, ehHoje, irPara, historico } = useDiaHistorico();
  const [calendario, setCalendario] = useState(false);

  const confirmarAnular = (op: OpHistorico) =>
    Dialog.confirm({
      title: t("web.transfer.undo.title"),
      content: (
        <>
          <div style={{ marginBottom: 8 }}>
            {op.acao} — {op.detalhe}
          </div>
          <div style={{ color: "var(--adm-color-danger)" }}>
            {t("web.transfer.undo.confirm", { qty: op.quantidade })} {op.num_lotes > 1 && t("web.transfer.undo.multi", { n: op.num_lotes })}{" "}
            <b>{t("web.transfer.undo.irreversible")}</b>
          </div>
        </>
      ),
      confirmText: <span style={{ color: "var(--adm-color-danger)" }}>{t("web.transfer.undo.confirm_btn")}</span>,
      cancelText: t("web.common.cancel"),
      onConfirm: async () => {
        try {
          await anular.mutateAsync({ tipo: op.tipo, action_id: op.action_id, operation_id: op.operation_id });
          notifySuccess(t("web.transfer.undo.done"));
        } catch (err) {
          notifyError(err);
        }
      },
    });

  return (
    <>
      <Cabecalho>{titulo ?? t("web.transfer.history")}</Cabecalho>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", background: "#fff" }}>
        <Button size="small" onClick={() => irPara(dia.subtract(1, "day"))} aria-label="◀">
          <LeftOutline />
        </Button>
        <Button size="small" style={{ flex: 1 }} onClick={() => setCalendario(true)}>
          {dia.format("DD/MM/YYYY")}
        </Button>
        <Button size="small" onClick={() => irPara(dia.add(1, "day"))} aria-label="▶">
          <RightOutline />
        </Button>
        {!ehHoje && (
          <Button size="small" color="primary" fill="none" onClick={() => irPara(dayjs())}>
            {t("web.transfer.today")}
          </Button>
        )}
      </div>
      <DatePicker
        visible={calendario}
        onClose={() => setCalendario(false)}
        value={dia.toDate()}
        max={dayjs().add(1, "year").toDate()}
        min={dayjs().subtract(10, "year").toDate()}
        onConfirm={(d) => irPara(dayjs(d))}
      />
      {historico.isError ? (
        <ErrorBlock status="default" title={errorMessage(historico.error)} description="" />
      ) : (
        <List>
          {historico.isPending ? (
            <List.Item>
              <DotLoading />
            </List.Item>
          ) : !historico.data?.length ? (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.transfer.history.empty")}</span>
            </List.Item>
          ) : (
            historico.data.map((op) => (
              <SwipeAction
                key={`${op.tipo}-${op.operation_id ?? op.action_id}`}
                rightActions={[
                  // Inseminações editam-se na sua página, como na app atual.
                  ...(editarInseminacoes || op.tipo !== "insemination"
                    ? [{ key: "e", text: t("btn.edit"), color: "primary" as const, onClick: () => onEditar(op) }]
                    : []),
                  { key: "a", text: t("web.transfer.undo"), color: "danger" as const, onClick: () => confirmarAnular(op) },
                ]}
              >
                <List.Item
                  description={comUtilizador ? `${op.usuario ?? "—"} · ${op.detalhe ?? ""}` : op.detalhe}
                  extra={<span style={{ fontSize: 12 }}>{hora(op.ts)}</span>}
                >
                  {op.acao}
                </List.Item>
              </SwipeAction>
            ))
          )}
        </List>
      )}
      <div style={{ padding: "8px 12px 16px", fontSize: 11, color: "#999" }}>{t("web.mobile.swipe_hint")}</div>
    </>
  );
}
