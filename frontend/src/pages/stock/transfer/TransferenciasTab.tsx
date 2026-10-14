import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ActionIcon,
  Alert,
  Box,
  Button,
  Center,
  Checkbox,
  Group,
  Input,
  Loader,
  Modal,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
} from "@mantine/core";
import { IconMinus, IconPlus, IconX } from "@tabler/icons-react";

import { useT } from "../../../i18n/I18n";
import { useIsMobile } from "../../../components/responsive";
import { notifySuccess, useNotifyError } from "../../../components/errors";
import { useGaranhoesStock, useLotes, useOpcoes, referencia, localizacao, type Lote } from "../api";
import { DonoSelect } from "../LoteForm";
import { ZoneTitle } from "../../../components/ds";
import { HistoricoOperacoes } from "./HistoricoOperacoes";
import {
  MOTIVOS,
  useCriarOperacao,
  useEditarOperacao,
  useOperacao,
  type LinhaOperacao,
  type Motivo,
  type OperacaoIn,
} from "./api";

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

export function TransferenciasTab() {
  const t = useT();
  const isMobile = useIsMobile();
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
  const garanhaoAtual = garanhao && opcoesGaranhao.includes(garanhao) ? garanhao : opcoesGaranhao[0] ?? null;
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
  const aGravar = criar.isPending || editar.isPending;

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
        ? {
            destino_id: destino,
            nova_localizacao: mudaLocal && contentor ? { contentor_id: contentor, canister, andar } : null,
          }
        : { destinatario, motivo, observacoes }),
    };
    try {
      if (edicao) {
        await editar.mutateAsync({ ...body, tipoOp: edicao.tipo, id: edicao.id });
      } else {
        await criar.mutateAsync(body);
      }
      notifySuccess(edicao ? t("web.transfer.updated") : t("web.transfer.done"));
      if (edicao) sairEdicao();
      else limpar();
    } catch (err) {
      notifyError(err);
    }
  };

  if (garanhoes.isPending || (edicao && operacao.isPending))
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );

  return (
    <Stack gap="md">
      {edicao && (
        <Alert color="yellow" variant="light">
          <Group justify="space-between" gap="sm">
            <Text size="sm">{t("web.transfer.edit_mode")}</Text>
            <Button size="xs" variant="default" onClick={sairEdicao}>
              {t("web.transfer.cancel_edit")}
            </Button>
          </Group>
        </Alert>
      )}
      {edicao && operacao.isError && <Alert color="red">{t("web.transfer.error.not_found")}</Alert>}

      {!opcoesGaranhao.length && !edicao ? (
        <Text c="dimmed">{t("transfer.no_stock_available")}</Text>
      ) : (
        <Paper withBorder radius="lg" p={{ base: "md", sm: "lg" }}>
          <Stack gap="xs">
            {/* 1. Seleção */}
            <Stack gap="sm">
              <ZoneTitle primeiro>{t("transfer.zone_selection")}</ZoneTitle>
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <Select
                  label={t("label.garanhao")}
                  data={garanhaoAtual && !opcoesGaranhao.includes(garanhaoAtual) ? [garanhaoAtual, ...opcoesGaranhao] : opcoesGaranhao}
                  value={garanhaoAtual}
                  onChange={(v) => v && mudarGaranhao(v)}
                  searchable
                  allowDeselect={false}
                  nothingFoundMessage={t("web.common.no_results")}
                />
                <Select
                  label={t("label.owner")}
                  data={[
                    { value: TODOS, label: t("common.all") },
                    ...(lotesGaranhao.data?.donos_disponiveis ?? [])
                      .filter((d) => d.id !== null)
                      .map((d) => ({ value: String(d.id), label: d.nome ?? "" })),
                  ]}
                  value={dono}
                  onChange={(v) => v && mudarDono(v)}
                  allowDeselect={false}
                />
              </SimpleGrid>
              <Button variant="default" onClick={() => setModalLotes(true)} disabled={!garanhaoAtual}>
                {t("btn.select_lots")}
              </Button>
            </Stack>

            {/* 2. Lotes selecionados */}
            <Stack gap="sm">
              <ZoneTitle>{t("transfer.selected_lots")}</ZoneTitle>
              {!linhas.length ? (
                <Text size="sm" c="dimmed">
                  {t("transfer.no_lotes_selected_hint")}
                </Text>
              ) : (
                <>
                  {linhas.map((l) => (
                    <Paper key={l.stock_id} withBorder radius="md" p="sm" bg="gray.0">
                      <Group wrap={isMobile ? "wrap" : "nowrap"} gap="sm" align="center">
                        <div style={{ flex: 1, minWidth: isMobile ? "calc(100% - 40px)" : 0 }}>
                          {dono === TODOS && (
                            <Text size="sm" fw={600} truncate>
                              {l.proprietario_nome ?? t("common.no_owner")}
                            </Text>
                          )}
                          <Text size="sm" fw={dono === TODOS ? 400 : 600} truncate>
                            {l.ref} · {l.local}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {t("web.transfer.available", { count: l.max })}
                            {l.carac && ` · ${l.carac}`}
                          </Text>
                        </div>
                        <QtdPalhetas
                          valor={l.qty}
                          max={l.max}
                          onChange={(n) => setLinhas((ls) => ls.map((x) => (x.stock_id === l.stock_id ? { ...x, qty: n } : x)))}
                        />
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          onClick={() => setLinhas((ls) => ls.filter((x) => x.stock_id !== l.stock_id))}
                          aria-label={t("btn.remove")}
                        >
                          <IconX size={16} />
                        </ActionIcon>
                      </Group>
                    </Paper>
                  ))}
                  <Group justify="space-between">
                    <Button variant="subtle" size="xs" leftSection={<IconPlus size={14} />} onClick={() => setModalLotes(true)}>
                      {t("btn.add_line")}
                    </Button>
                    <Text fw={600}>{t("web.transfer.total", { count: total })}</Text>
                  </Group>
                </>
              )}
            </Stack>

            {/* 3. Destino */}
            {linhas.length > 0 && (
              <>
                <Stack gap="sm">
                  <ZoneTitle>{t("transfer.destination")}</ZoneTitle>
                  {/* No telemóvel as opções ficam empilhadas — lado a lado os
                      textos não cabem. */}
                  <SegmentedControl
                    fullWidth={isMobile}
                    orientation={isMobile ? "vertical" : "horizontal"}
                    value={tipo}
                    onChange={(v) => setTipo(v as "interna" | "externa")}
                    data={[
                      { value: "interna", label: t("transfer.internal") },
                      { value: "externa", label: t("transfer.external") },
                    ]}
                    style={{ alignSelf: isMobile ? "stretch" : "flex-start" }}
                  />

                  {tipo === "interna" ? (
                    <>
                      {destinos.length === 0 && donosAtivos.data && (
                        <Alert color="yellow" variant="light">
                          {t("web.transfer.no_other_owners")}
                        </Alert>
                      )}
                      <DestinoSelect
                        opcoes={destinos.map((d) => ({ value: String(d.id), label: d.nome }))}
                        value={destino}
                        onChange={setDestino}
                      />
                      <Input.Wrapper label={t("transfer.change_location")}>
                        <SegmentedControl
                          fullWidth
                          orientation={isMobile ? "vertical" : "horizontal"}
                          value={mudaLocal ? "nova" : "manter"}
                          onChange={(v) => setMudaLocal(v === "nova")}
                          data={[
                            { value: "manter", label: t("transfer.keep_location") },
                            { value: "nova", label: t("transfer.new_location") },
                          ]}
                        />
                      </Input.Wrapper>
                      {mudaLocal && (
                        <SimpleGrid cols={{ base: 1, xs: 3 }}>
                          <Select
                            label={t("label.container")}
                            withAsterisk
                            data={(contentores.data ?? []).map((c) => ({ value: String(c.id), label: c.nome }))}
                            value={contentor !== null ? String(contentor) : null}
                            onChange={(v) => setContentor(v ? Number(v) : null)}
                            searchable
                          />
                          <NumberInput label={t("label.canister")} min={1} max={20} value={canister} onChange={(v) => setCanister(Number(v) || 1)} />
                          <NumberInput label={t("label.floor")} min={1} max={20} value={andar} onChange={(v) => setAndar(Number(v) || 1)} />
                        </SimpleGrid>
                      )}
                    </>
                  ) : (
                    <SimpleGrid cols={{ base: 1, sm: 2 }}>
                      <TextInput
                        label={t("transfer.external_recipient")}
                        withAsterisk
                        value={destinatario}
                        onChange={(e) => setDestinatario(e.currentTarget.value)}
                      />
                      <Select
                        label={t("transfer.reason")}
                        data={MOTIVOS.map((m) => ({ value: m.value, label: t(m.label) }))}
                        value={motivo}
                        onChange={(v) => v && setMotivo(v as Motivo)}
                        allowDeselect={false}
                      />
                      <Textarea
                        label={t("label.notes")}
                        autosize
                        minRows={2}
                        value={observacoes}
                        onChange={(e) => setObservacoes(e.currentTarget.value)}
                        style={{ gridColumn: "1 / -1" }}
                      />
                    </SimpleGrid>
                  )}

                  {erro && (
                    <Alert color="red" variant="light">
                      {erro}
                    </Alert>
                  )}
                  <Button size="md" onClick={executar} loading={aGravar} fullWidth={isMobile} style={{ alignSelf: "flex-end" }}>
                    {edicao ? t("web.transfer.update_btn") : t("btn.execute_transfer")}
                  </Button>
                </Stack>
              </>
            )}
          </Stack>
        </Paper>
      )}

      {/* Escondido durante a edição, como na app atual. */}
      {!edicao && (
        <HistoricoOperacoes
          onEditar={(op) =>
            setParams((p) => {
              const r = new URLSearchParams(p);
              r.set("editar", `${op.tipo}-${op.action_id}`);
              return r;
            })
          }
        />
      )}

      <SelecionarLotesModal
        opened={modalLotes}
        onClose={() => setModalLotes(false)}
        lotes={(lotesGaranhao.data?.items ?? []).filter((l) => dono === TODOS || String(l.dono_id) === dono)}
        carregando={lotesGaranhao.isPending}
        jaSelecionados={new Set(linhas.map((l) => l.stock_id))}
        onConfirmar={(novos) => {
          setLinhas((ls) => [
            ...ls,
            ...novos
              .filter((n) => !ls.some((l) => l.stock_id === n.lote.id))
              .map((n) => paraLinha({ ...n.lote, stock_id: n.lote.id }, n.qty)),
          ]);
          setModalLotes(false);
        }}
      />
    </Stack>
  );
}

/** Quantas palhetas saem de um lote: − [n] + "de N". */
function QtdPalhetas({ valor, max, onChange }: { valor: number; max: number; onChange: (n: number) => void }) {
  const t = useT();
  const definir = (n: number) => onChange(Math.max(1, Math.min(max, n || 1)));
  return (
    <div onClick={(e) => e.stopPropagation()}>
      <Text size="xs" c="dimmed" mb={2}>
        {t("web.transfer.qty_to_send")}
      </Text>
      <Group gap={6} wrap="nowrap">
        <ActionIcon variant="default" size={34} onClick={() => definir(valor - 1)} disabled={valor <= 1} aria-label="−">
          <IconMinus size={16} />
        </ActionIcon>
        <NumberInput
          aria-label={t("web.transfer.qty_to_send")}
          value={valor}
          onChange={(v) => definir(Number(v))}
          min={1}
          max={max}
          clampBehavior="strict"
          hideControls
          w={64}
          styles={{ input: { textAlign: "center", fontWeight: 700 } }}
          inputMode="numeric"
        />
        <ActionIcon variant="default" size={34} onClick={() => definir(valor + 1)} disabled={valor >= max} aria-label="+">
          <IconPlus size={16} />
        </ActionIcon>
        <Text size="sm" c="dimmed" style={{ whiteSpace: "nowrap" }}>
          {t("web.transfer.of_max", { max })}
        </Text>
      </Group>
    </div>
  );
}

function DestinoSelect({
  opcoes,
  value,
  onChange,
}: {
  opcoes: { value: string; label: string }[];
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  const t = useT();
  // O "+" cria um proprietário novo e escolhe-o logo como destino.
  return (
    <DonoSelect
      label={t("transfer.destination_owner")}
      apenasAtivos
      value={value}
      onChange={onChange}
      dataOverride={opcoes}
    />
  );
}

function SelecionarLotesModal({
  opened,
  onClose,
  lotes,
  carregando,
  jaSelecionados,
  onConfirmar,
}: {
  opened: boolean;
  onClose: () => void;
  lotes: Lote[];
  carregando: boolean;
  jaSelecionados: Set<number>;
  onConfirmar: (l: { lote: Lote; qty: number }[]) => void;
}) {
  const t = useT();
  const isMobile = useIsMobile();
  // Lotes marcados → palhetas a enviar de cada um (começa no total do lote).
  const [sel, setSel] = useState<Map<number, number>>(new Map());
  useEffect(() => {
    if (opened) setSel(new Map());
  }, [opened]);

  // Mais recentes primeiro (data de produção), como a app atual.
  const ordenados = [...lotes].sort((a, b) => (b.data_embriovet ?? "").localeCompare(a.data_embriovet ?? ""));

  return (
    <Modal opened={opened} onClose={onClose} title={t("transfer.select_lots_title")} size="lg" radius="lg" fullScreen={isMobile}>
      {carregando ? (
        <Center py="xl">
          <Loader />
        </Center>
      ) : !ordenados.length ? (
        <Text c="dimmed">{t("transfer.no_lotes_for_filters")}</Text>
      ) : (
        <Stack gap="xs">
          {ordenados.map((l) => {
            const ja = jaSelecionados.has(l.id);
            const marcado = ja || sel.has(l.id);
            return (
              <Paper
                key={l.id}
                withBorder
                radius="md"
                p="sm"
                style={{ cursor: ja ? "default" : "pointer", opacity: ja ? 0.6 : 1 }}
                onClick={() =>
                  !ja &&
                  setSel((s) => {
                    const n = new Map(s);
                    if (n.has(l.id)) n.delete(l.id);
                    else n.set(l.id, l.existencia_atual ?? 0);
                    return n;
                  })
                }
              >
                <Group wrap="nowrap" gap="sm">
                  <Checkbox checked={marcado} disabled={ja} readOnly aria-label={t("btn.select")} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text size="sm" fw={600} truncate>
                      {referencia(l) ?? `#${l.id}`} · {localizacao(l) ?? "—"}
                    </Text>
                    <Text size="xs" c="dimmed" truncate>
                      {l.proprietario_nome ?? t("common.no_owner")}
                      {l.qualidade ? ` · Q: ${l.qualidade}` : ""}
                      {l.concentracao ? ` · C: ${l.concentracao}` : ""}
                      {l.motilidade ? ` · M: ${l.motilidade}%` : ""}
                    </Text>
                  </div>
                  <Text size="sm" fw={600} style={{ flexShrink: 0 }}>
                    {t("web.stock.straws_count", { count: l.existencia_atual ?? 0 })}
                  </Text>
                </Group>
                {sel.has(l.id) && (
                  <Box mt="sm" pl={34}>
                    <QtdPalhetas
                      valor={sel.get(l.id)!}
                      max={l.existencia_atual ?? 0}
                      onChange={(n) => setSel((s) => new Map(s).set(l.id, n))}
                    />
                  </Box>
                )}
              </Paper>
            );
          })}
          <Group justify="flex-end" mt="sm" grow={isMobile}>
            <Button variant="default" onClick={onClose}>
              {t("btn.close")}
            </Button>
            <Button
              disabled={!sel.size}
              onClick={() => onConfirmar(ordenados.filter((l) => sel.has(l.id)).map((l) => ({ lote: l, qty: sel.get(l.id)! })))}
            >
              {t("btn.confirm_selection")}
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
