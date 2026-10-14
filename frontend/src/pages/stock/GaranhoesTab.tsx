import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Center, Group, Loader, Paper, Stack, Table, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconChevronRight, IconSearch } from "@tabler/icons-react";

import { useT } from "../../i18n/I18n";
import { useErrorMessage } from "../../components/errors";
import { useGaranhoesStock } from "./api";

/** Separador Garanhões: garanhões com stock disponível. A ficha do
 *  animal ainda não foi migrada — por isso o clique abre os lotes. */
export function GaranhoesTab() {
  const t = useT();
  const navigate = useNavigate();
  const errorMessage = useErrorMessage();
  const { data, isPending, isError, error } = useGaranhoesStock();
  const [pesquisa, setPesquisa] = useState("");

  const lista = useMemo(() => {
    const q = pesquisa.trim().toLowerCase();
    return (data ?? []).filter((g) => !q || g.garanhao.toLowerCase().includes(q));
  }, [data, pesquisa]);

  const abrir = (garanhao: string) => navigate(`/stock-semen/lotes?garanhao=${encodeURIComponent(garanhao)}`);

  if (isError) return <Alert color="red">{errorMessage(error)}</Alert>;
  if (isPending)
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  if (!data.length) return <Text c="dimmed">{t("web.stock.garanhoes.empty")}</Text>;

  return (
    <>
      <Text size="sm" c="dimmed" mb="sm">
        {t("web.stock.garanhoes.hint")}
      </Text>
      <TextInput
        placeholder={t("web.stock.garanhoes.search")}
        leftSection={<IconSearch size={16} />}
        value={pesquisa}
        onChange={(e) => setPesquisa(e.currentTarget.value)}
        type="search"
        maw={{ sm: 360 }}
        mb="md"
      />

      {!lista.length ? (
        <Text c="dimmed">{t("web.common.no_results")}</Text>
      ) : (
        <>
          <Stack gap="xs" hiddenFrom="sm">
            {lista.map((g) => (
              <Paper key={`${g.animal_id}-${g.garanhao}`} withBorder radius="md" p={0}>
                <UnstyledButton onClick={() => abrir(g.garanhao)} w="100%" p="md">
                  <Group wrap="nowrap">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Text fw={600} truncate>
                        {g.garanhao}
                      </Text>
                      <Text size="sm" c="dimmed">
                        {g.palhetas} {t("label.straws")} · {g.lotes} {t("web.stock.kpi.lotes").toLowerCase()} · {g.donos}{" "}
                        {t("web.stock.col.donos").toLowerCase()}
                      </Text>
                    </div>
                    <IconChevronRight size={18} color="var(--mantine-color-gray-5)" />
                  </Group>
                </UnstyledButton>
              </Paper>
            ))}
          </Stack>

          <Paper withBorder radius="md" style={{ overflow: "hidden" }} visibleFrom="sm">
            <Table highlightOnHover verticalSpacing="sm" horizontalSpacing="md">
              <Table.Thead bg="gray.0">
                <Table.Tr>
                  <Table.Th>{t("label.garanhao")}</Table.Th>
                  <Table.Th ta="right">{t("web.stock.kpi.palhetas")}</Table.Th>
                  <Table.Th ta="right">{t("web.stock.kpi.lotes")}</Table.Th>
                  <Table.Th ta="right">{t("web.stock.col.donos")}</Table.Th>
                  <Table.Th w={40} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {lista.map((g) => (
                  <Table.Tr
                    key={`${g.animal_id}-${g.garanhao}`}
                    onClick={() => abrir(g.garanhao)}
                    style={{ cursor: "pointer" }}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && abrir(g.garanhao)}
                  >
                    <Table.Td fw={600}>{g.garanhao}</Table.Td>
                    <Table.Td ta="right">{g.palhetas}</Table.Td>
                    <Table.Td ta="right">{g.lotes}</Table.Td>
                    <Table.Td ta="right">{g.donos}</Table.Td>
                    <Table.Td>
                      <IconChevronRight size={16} color="var(--mantine-color-gray-5)" />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </>
      )}
    </>
  );
}
