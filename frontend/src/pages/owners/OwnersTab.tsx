import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ActionIcon,
  Affix,
  Alert,
  Box,
  Button,
  Center,
  Group,
  Loader,
  Pagination,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  UnstyledButton,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconChevronRight, IconPlus, IconSearch } from "@tabler/icons-react";

import type { Owner } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { useErrorMessage } from "../../components/errors";
import { useIsMobile } from "../../components/responsive";
import { POR_PAGINA, useOwners, type Estado, type Ordem } from "./api";
import { OwnerDrawer, StatusBadge } from "./OwnerDrawer";
import { OwnerFormModal } from "./OwnerFormModal";

const ESTADOS: Estado[] = ["todos", "ativos", "inativos"];
const ORDENS: Ordem[] = ["nome", "id", "status"];

export function OwnersTab() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const isMobile = useIsMobile();

  // Filtros no endereço: um "Atualizar" ou o botão "Voltar" mantêm a
  // pesquisa e a página onde se estava.
  const [params, setParams] = useSearchParams();
  const estado = (ESTADOS.find((e) => e === params.get("estado")) ?? "todos") as Estado;
  const ordem = (ORDENS.find((o) => o === params.get("ordem")) ?? "nome") as Ordem;
  const pagina = Math.max(1, Number(params.get("pagina")) || 1);
  const [pesquisa, setPesquisa] = useState(params.get("q") ?? "");
  const [q] = useDebouncedValue(pesquisa.trim(), 300);

  const atualizar = (novo: Record<string, string | number | null>) => {
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        for (const [k, v] of Object.entries(novo)) {
          if (v === null || v === "" || (k === "pagina" && v === 1)) r.delete(k);
          else r.set(k, String(v));
        }
        return r;
      },
      { replace: true },
    );
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) atualizar({ q, pagina: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { data, isPending, isError, error, isFetching } = useOwners({ q, estado, ordem, pagina });

  const [selecionado, setSelecionado] = useState<Owner | null>(null);
  const [form, setForm] = useState<{ aberto: boolean; owner: Owner | null }>({ aberto: false, owner: null });

  const totalPaginas = data ? Math.max(1, Math.ceil(data.total / POR_PAGINA)) : 1;

  // Se apagar o último da última página, recua uma página.
  useEffect(() => {
    if (data && pagina > totalPaginas) atualizar({ pagina: totalPaginas });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, pagina, totalPaginas]);

  const estadosData = [
    { value: "todos", label: t("owners.filter.all") },
    { value: "ativos", label: t("owners.filter.active") },
    { value: "inativos", label: t("owners.filter.inactive") },
  ];
  const contagem = data ? (
    <Text size="sm" c="dimmed" style={{ whiteSpace: "nowrap" }}>
      {t("web.owners.count", { count: data.total })}
    </Text>
  ) : (
    <span />
  );
  const ordenacao = (
    <Select
      aria-label={t("owners.sort_by")}
      value={ordem}
      onChange={(v) => v && atualizar({ ordem: v === "nome" ? null : v, pagina: 1 })}
      data={[
        { value: "nome", label: `${t("owners.sort_by")} ${t("owners.sort.name")}` },
        { value: "id", label: `${t("owners.sort_by")} ${t("owners.sort.id")}` },
        { value: "status", label: `${t("owners.sort_by")} ${t("web.owners.status")}` },
      ]}
      allowDeselect={false}
      w={190}
    />
  );
  const abrirNovo = () => setForm({ aberto: true, owner: null });
  const vazio = (v: string | null) => v || <Text span c="dimmed">—</Text>;

  return (
    <>
      {/* Pesquisa + novo. No telemóvel o "Novo" passa a botão flutuante
          (sempre à mão do polegar, mesmo depois de deslizar a lista). */}
      <Group justify="space-between" mb="md" gap="sm" wrap="nowrap">
        <TextInput
          placeholder={t("web.owners.search")}
          leftSection={<IconSearch size={16} />}
          rightSection={isFetching && !isPending ? <Loader size={14} /> : null}
          value={pesquisa}
          onChange={(e) => setPesquisa(e.currentTarget.value)}
          type="search"
          enterKeyHint="search"
          style={{ flex: 1 }}
          maw={{ sm: 420 }}
        />
        <Button leftSection={<IconPlus size={16} />} onClick={abrirNovo} visibleFrom="sm">
          {t("web.owners.new")}
        </Button>
      </Group>

      <Stack gap="sm" mb="sm" hiddenFrom="sm">
        <SegmentedControl
          fullWidth
          value={estado}
          onChange={(v) => atualizar({ estado: v === "todos" ? null : v, pagina: 1 })}
          data={estadosData}
        />
        <Group justify="space-between" wrap="nowrap" gap="sm">
          {contagem}
          {ordenacao}
        </Group>
      </Stack>
      <Group justify="space-between" mb="sm" gap="sm" visibleFrom="sm">
        <SegmentedControl
          value={estado}
          onChange={(v) => atualizar({ estado: v === "todos" ? null : v, pagina: 1 })}
          data={estadosData}
        />
        <Group gap="sm">
          {contagem}
          {ordenacao}
        </Group>
      </Group>

      {isError ? (
        <Alert color="red" variant="light">
          {errorMessage(error)}
        </Alert>
      ) : isPending ? (
        <Center py="xl">
          <Loader />
        </Center>
      ) : data.items.length === 0 ? (
        <Paper withBorder radius="md" p="xl">
          <Text c="dimmed" ta="center">
            {t("web.owners.empty")}
          </Text>
        </Paper>
      ) : (
        <Box style={{ opacity: isFetching ? 0.7 : 1, transition: "opacity 120ms" }}>
          {/* Telemóvel: cartões tocáveis, um por proprietário. */}
          <Stack gap="xs" hiddenFrom="sm">
            {data.items.map((o) => (
              <Paper key={o.id} withBorder radius="md" p={0}>
                <UnstyledButton onClick={() => setSelecionado(o)} w="100%" p="md" style={{ minHeight: 64 }}>
                  <Group wrap="nowrap" gap="sm">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Group gap={8} wrap="nowrap">
                        <Text fw={600} truncate>
                          {o.nome}
                        </Text>
                        <StatusBadge ativo={o.ativo} />
                      </Group>
                      <Text size="sm" c="dimmed" truncate>
                        {[o.cidade, o.telemovel, o.email].filter(Boolean).join(" · ") || `#${o.id}`}
                      </Text>
                    </div>
                    <IconChevronRight size={18} color="var(--mantine-color-gray-5)" />
                  </Group>
                </UnstyledButton>
              </Paper>
            ))}
          </Stack>

          {/* Tablet e computador: tabela. A coluna Telemóvel só aparece a
              partir de 992px, para a tabela caber num tablet ao alto. */}
          <Paper withBorder radius="md" style={{ overflow: "hidden" }} visibleFrom="sm">
            <Table.ScrollContainer minWidth={560} type="native">
            <Table highlightOnHover verticalSpacing="sm" horizontalSpacing="md">
              <Table.Thead bg="gray.0">
                <Table.Tr>
                  <Table.Th w={70}>{t("label.id")}</Table.Th>
                  <Table.Th>{t("label.name")}</Table.Th>
                  <Table.Th>{t("label.email")}</Table.Th>
                  <Table.Th visibleFrom="md">{t("label.phone")}</Table.Th>
                  <Table.Th>{t("label.city")}</Table.Th>
                  <Table.Th w={110}>{t("web.owners.status")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.items.map((o) => (
                  <Table.Tr
                    key={o.id}
                    onClick={() => setSelecionado(o)}
                    style={{ cursor: "pointer" }}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && setSelecionado(o)}
                  >
                    <Table.Td c="dimmed">{o.id}</Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={600} style={{ wordBreak: "break-word" }}>
                        {o.nome}
                      </Text>
                      {o.nome_completo && o.nome_completo !== o.nome && (
                        <Text size="xs" c="dimmed">
                          {o.nome_completo}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td style={{ wordBreak: "break-all" }}>{vazio(o.email)}</Table.Td>
                    <Table.Td visibleFrom="md">{vazio(o.telemovel)}</Table.Td>
                    <Table.Td>{vazio(o.cidade)}</Table.Td>
                    <Table.Td>
                      <StatusBadge ativo={o.ativo} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            </Table.ScrollContainer>
          </Paper>
        </Box>
      )}

      {data && totalPaginas > 1 && (
        <Group justify="center" mt="md" mb={isMobile ? 80 : 0}>
          <Pagination
            total={totalPaginas}
            value={Math.min(pagina, totalPaginas)}
            onChange={(p) => {
              atualizar({ pagina: p });
              window.scrollTo({ top: 0 });
            }}
            siblings={isMobile ? 0 : 1}
            boundaries={1}
          />
        </Group>
      )}

      <Affix position={{ bottom: 20, right: 20 }} hiddenFrom="sm" zIndex={150}>
        <ActionIcon size={56} radius="xl" onClick={abrirNovo} aria-label={t("web.owners.new")} style={{ boxShadow: "var(--mantine-shadow-lg)" }}>
          <IconPlus size={26} />
        </ActionIcon>
      </Affix>

      <OwnerDrawer
        owner={selecionado}
        onClose={() => setSelecionado(null)}
        onEdit={(o) => setForm({ aberto: true, owner: o })}
        onChanged={setSelecionado}
      />
      <OwnerFormModal
        opened={form.aberto}
        owner={form.owner}
        onClose={() => setForm((f) => ({ ...f, aberto: false }))}
        onSaved={(o) => {
          if (selecionado) setSelecionado(o);
        }}
      />
    </>
  );
}
