import type { ReactNode } from "react";
import { Badge, Divider, Group, Paper, SimpleGrid, Text, Title } from "@mantine/core";
import { useT } from "../i18n/I18n";

// Peças visuais partilhadas pelas páginas, para todas terem o mesmo aspeto.

/** Título de uma secção dentro da página. Fora a primeira, leva uma linha
 *  por cima a separar da secção anterior. */
export function ZoneTitle({ children, primeiro = false }: { children: ReactNode; primeiro?: boolean }) {
  return (
    <>
      {!primeiro && <Divider my="sm" />}
      <Title order={5} c="dimmed" tt="uppercase" fz="xs" mb={4}>
        {children}
      </Title>
    </>
  );
}

/** Indicadores em pequenos cartões. */
export function KpiRow({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm" mb="md">
      {items.map(([label, valor], i) => (
        <Paper key={i} withBorder radius="md" p="sm">
          <Text size="xs" c="dimmed" fw={500} tt="uppercase">
            {label}
          </Text>
          <Text fw={700} size="xl">
            {valor}
          </Text>
        </Paper>
      ))}
    </SimpleGrid>
  );
}

/** Etiqueta: ok = cinzenta, aviso = tom da marca, critico = cheia. */
export function Pill({ nivel = "ok", children }: { nivel?: "ok" | "aviso" | "critico"; children: ReactNode }) {
  const props =
    nivel === "critico"
      ? { color: "brand", variant: "filled" as const }
      : nivel === "aviso"
        ? { color: "brand", variant: "light" as const }
        : { color: "gray", variant: "light" as const };
  return (
    <Badge {...props} radius="sm" style={{ flexShrink: 0 }}>
      {children}
    </Badge>
  );
}

/** Cabeçalho da página: título e, à direita, as ações. */
export function PageHeader({ titulo, acoes }: { titulo: string; acoes?: ReactNode }) {
  return (
    <Group justify="space-between" align="center" mb="md" gap="sm" wrap="nowrap">
      <Title order={2}>{titulo}</Title>
      {acoes}
    </Group>
  );
}

/** Estado ativo/inativo (proprietários). */
export function StatusPill({ ativo }: { ativo: boolean | null }) {
  const t = useT();
  // `ativo` NULL conta como ativo, como na app atual (`prop.get('ativo', True)`).
  const on = ativo !== false;
  return (
    <Badge color={on ? "teal" : "gray"} variant="light" radius="sm" style={{ flexShrink: 0 }}>
      {on ? t("web.owners.active") : t("web.owners.inactive")}
    </Badge>
  );
}
