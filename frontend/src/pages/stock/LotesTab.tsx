import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Accordion,
  ActionIcon,
  Affix,
  Alert,
  Badge,
  Box,
  Button,
  Center,
  Collapse,
  Group,
  Loader,
  MultiSelect,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { IconAdjustmentsHorizontal, IconChevronRight, IconDownload, IconMapPin, IconPlus } from "@tabler/icons-react";

import { useT } from "../../i18n/I18n";
import { useErrorMessage } from "../../components/errors";
import { baixarCsv, dataCurta } from "../../components/csv";
import { useGaranhoesStock, useLotes, useTransferencias, localizacao, referencia, type Lote } from "./api";
import { LoteDrawer } from "./LoteDrawer";
import { KpiRow, Pill } from "../../components/ds";

const SEM_DONO = "sem-dono";

export function LotesTab({ onNovoLote }: { onNovoLote: () => void }) {
  const t = useT();
  const errorMessage = useErrorMessage();
  const [params, setParams] = useSearchParams();
  const [filtrosAbertos, setFiltrosAbertos] = useState(false);

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

  const mudarGaranhao = (g: string) =>
    atualizar((p) => {
      p.set("garanhao", g);
      p.delete("dono");
      p.delete("lote");
    });

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

  if (garanhoes.isError) return <Alert color="red">{errorMessage(garanhoes.error)}</Alert>;
  if (garanhoes.isPending)
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  if (!garanhao)
    return (
      <Paper withBorder radius="md" p="xl">
        <Stack align="center" gap="sm">
          <Text c="dimmed">{t("stock.none_registered")}</Text>
          <Button leftSection={<IconPlus size={16} />} onClick={onNovoLote}>
            {t("web.stock.add")}
          </Button>
        </Stack>
      </Paper>
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

  return (
    <>
      {/* Seleção do garanhão + filtros */}
      <Group align="flex-end" gap="sm" mb="sm" wrap="nowrap">
        <Select
          label={t("label.garanhao")}
          data={opcoesGaranhao}
          value={garanhao}
          onChange={(v) => v && mudarGaranhao(v)}
          searchable
          allowDeselect={false}
          nothingFoundMessage={t("web.common.no_results")}
          style={{ flex: 1 }}
          maw={{ sm: 360 }}
        />
        <Button
          variant={nFiltros ? "light" : "default"}
          leftSection={<IconAdjustmentsHorizontal size={16} />}
          onClick={() => setFiltrosAbertos((o) => !o)}
          rightSection={nFiltros ? <Badge size="xs" circle>{nFiltros}</Badge> : null}
        >
          <Box component="span" visibleFrom="xs">
            {t("common.filters")}
          </Box>
        </Button>
      </Group>

      <Collapse in={filtrosAbertos}>
        <Paper withBorder radius="md" p="md" mb="md">
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
            <MultiSelect
              label={t("label.owner_plural")}
              data={opcoesDonos}
              value={donosSel}
              onChange={(v) =>
                atualizar((p) => {
                  p.delete("dono");
                  v.forEach((d) => p.append("dono", d));
                })
              }
              searchable
              clearable
            />
            <NumberInput
              label={t("stock.min_straws")}
              min={0}
              value={minPalhetas}
              onChange={(v) => atualizar((p) => (Number(v) ? p.set("min", String(v)) : p.delete("min")))}
              inputMode="numeric"
            />
            <Switch
              label={t("stock.include_empty")}
              checked={incluirVazios}
              onChange={(e) => {
                const on = e.currentTarget.checked;
                atualizar((p) => (on ? p.set("vazios", "1") : p.delete("vazios")));
              }}
              mt={{ sm: 30 }}
            />
          </SimpleGrid>
          {nFiltros > 0 && (
            <Button
              variant="subtle"
              size="xs"
              mt="sm"
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
        </Paper>
      </Collapse>

      {lotes.isError ? (
        <Alert color="red">{errorMessage(lotes.error)}</Alert>
      ) : !lotes.data ? (
        <Center py="xl">
          <Loader />
        </Center>
      ) : (
        <Box style={{ opacity: lotes.isFetching ? 0.7 : 1, transition: "opacity 120ms" }}>
          {/* Indicadores (render_kpi_strip) */}
          <KpiRow
            items={[
              [t("web.stock.kpi.lotes"), k!.lotes],
              [t("web.stock.kpi.palhetas"), k!.palhetas],
              [t("web.stock.kpi.proprietarios"), k!.proprietarios],
              [t("web.stock.kpi.qualidade"), k!.qualidade_media !== null ? `${k!.qualidade_media}%` : "—"],
            ]}
          />

          {/* Palhetas por proprietário + histórico do garanhão, fechados por
              omissão para a lista de lotes ficar logo à vista no telemóvel. */}
          <Accordion variant="separated" radius="md" mb="md" multiple>
            {lotes.data.por_proprietario.length > 0 && (
              <Accordion.Item value="donos">
                <Accordion.Control>{t("web.stock.by_owner")}</Accordion.Control>
                <Accordion.Panel>
                  <Table>
                    <Table.Tbody>
                      {lotes.data.por_proprietario.map((r) => (
                        <Table.Tr key={r.dono_id ?? "sem"}>
                          <Table.Td>{r.proprietario_nome ?? t("common.no_owner")}</Table.Td>
                          <Table.Td ta="right" fw={600}>
                            {r.palhetas}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Accordion.Panel>
              </Accordion.Item>
            )}
            <Accordion.Item value="historico">
              <Accordion.Control>{t("stock.transfer_history")}</Accordion.Control>
              <Accordion.Panel>
                <HistoricoTransferencias garanhao={garanhao} internas={internas} externas={externas} comExportar />
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>

          <Text fw={600} mb="xs">
            {t("stock.lots_detailed")}
          </Text>
          {lotes.data.items.length === 0 ? (
            <Text c="dimmed">{t("stock.no_lots_filter")}</Text>
          ) : (
            <Stack gap="xs">
              {lotes.data.items.map((l) => (
                <LoteCartao key={l.id} lote={l} onClick={() => setSelecionado(l)} />
              ))}
            </Stack>
          )}
        </Box>
      )}

      {/* Espaço para o botão "+" flutuante não tapar o último lote. */}
      <Box h={80} hiddenFrom="sm" />
      <Affix position={{ bottom: 20, right: 20 }} hiddenFrom="sm" zIndex={150}>
        <ActionIcon size={56} radius="xl" onClick={onNovoLote} aria-label={t("web.stock.add")} style={{ boxShadow: "var(--mantine-shadow-lg)" }}>
          <IconPlus size={26} />
        </ActionIcon>
      </Affix>

      <LoteDrawer
        lote={selecionado}
        ligacoes={selecionado ? lotes.data?.ligacoes[String(selecionado.id)] : undefined}
        internas={transf.data?.internas ?? []}
        externas={transf.data?.externas ?? []}
        onClose={fecharLote}
      />
    </>
  );
}

function LoteCartao({ lote: l, onClick }: { lote: Lote; onClick: () => void }) {
  const t = useT();
  const local = localizacao(l);
  const existencia = l.existencia_atual ?? 0;
  return (
    <Paper withBorder radius="md" p={0}>
      <UnstyledButton onClick={onClick} w="100%" p="md">
        <Group wrap="nowrap" gap="sm" align="flex-start">
          <div style={{ flex: 1, minWidth: 0 }}>
            <Group gap={8} wrap="nowrap" justify="space-between">
              <Text fw={600} truncate>
                {referencia(l) ?? t("common.no_reference")}
              </Text>
              <Pill nivel={existencia > 0 ? "aviso" : "ok"}>{t("web.stock.straws_count", { count: existencia })}</Pill>
            </Group>
            <Text size="sm" truncate>
              {l.proprietario_nome ?? t("common.no_owner")}
            </Text>
            <Group gap="xs" mt={4} c="dimmed" style={{ fontSize: "var(--mantine-font-size-xs)" }}>
              <Group gap={2} wrap="nowrap">
                <IconMapPin size={12} />
                <span>{local ?? "—"}</span>
              </Group>
              {l.cor && <span>· {l.cor}</span>}
              <span>· M {l.motilidade ?? 0}%</span>
              <span>· {l.concentracao ?? 0} M/ml</span>
            </Group>
          </div>
          <IconChevronRight size={18} color="var(--mantine-color-gray-5)" style={{ marginTop: 2, flexShrink: 0 }} />
        </Group>
      </UnstyledButton>
    </Paper>
  );
}

export function HistoricoTransferencias({
  garanhao,
  internas,
  externas,
  comExportar = false,
}: {
  garanhao: string;
  internas: import("./api").TransfInterna[];
  externas: import("./api").TransfExterna[];
  comExportar?: boolean;
}) {
  const t = useT();
  if (!internas.length && !externas.length) return <Text size="sm" c="dimmed">{t("stock.no_transfers")}</Text>;

  return (
    <Stack gap="md">
      {comExportar && (
        <Group gap="xs">
          {internas.length > 0 && (
            <Button
              size="xs"
              variant="default"
              leftSection={<IconDownload size={14} />}
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
              size="xs"
              variant="default"
              leftSection={<IconDownload size={14} />}
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
        </Group>
      )}

      {internas.length > 0 && (
        <div>
          <Text size="sm" fw={600} mb={4}>
            {t("web.stock.history.internal")}
          </Text>
          <Table.ScrollContainer minWidth={360}>
            <Table fz="sm" verticalSpacing={6}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t("label.date")}</Table.Th>
                  <Table.Th>{t("label.from")}</Table.Th>
                  <Table.Th>{t("label.to")}</Table.Th>
                  <Table.Th ta="right">{t("web.stock.kpi.palhetas")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {internas.map((x) => (
                  <Table.Tr key={x.id}>
                    <Table.Td>{dataCurta(x.data)}</Table.Td>
                    <Table.Td>{x.origem ?? "—"}</Table.Td>
                    <Table.Td>{x.destino ?? "—"}</Table.Td>
                    <Table.Td ta="right">{x.quantidade}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </div>
      )}

      {externas.length > 0 && (
        <div>
          <Text size="sm" fw={600} mb={4}>
            {t("web.stock.history.external")}
          </Text>
          <Table.ScrollContainer minWidth={480}>
            <Table fz="sm" verticalSpacing={6}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t("label.date")}</Table.Th>
                  <Table.Th>{t("label.from")}</Table.Th>
                  <Table.Th>{t("label.to")}</Table.Th>
                  <Table.Th>{t("label.type")}</Table.Th>
                  <Table.Th ta="right">{t("web.stock.kpi.palhetas")}</Table.Th>
                  <Table.Th>{t("label.notes")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {externas.map((x) => (
                  <Table.Tr key={x.id}>
                    <Table.Td>{dataCurta(x.data)}</Table.Td>
                    <Table.Td>{x.origem ?? "—"}</Table.Td>
                    <Table.Td>{x.destinatario}</Table.Td>
                    <Table.Td>{x.tipo ?? "—"}</Table.Td>
                    <Table.Td ta="right">{x.quantidade}</Table.Td>
                    <Table.Td>{x.observacoes ?? ""}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </div>
      )}
    </Stack>
  );
}
