import { useEffect } from "react";
import { NavLink as RouterLink, Outlet, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { AppShell, Avatar, Box, Burger, Group, NavLink, ScrollArea, Stack, Text, UnstyledButton } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconActivity,
  IconCalendarEvent,
  IconChartBar,
  IconFlask,
  IconHome,
  IconLayoutDashboard,
  IconLogout,
  IconSettings,
} from "@tabler/icons-react";

import { api } from "../api/client";
import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { BrandMark, ProductSignature, useBrand } from "./Brand";

// Os mesmos 7 sítios do menu da app atual (Pedido 7), pela mesma ordem.
export const NAV = [
  { path: "/dashboard", label: "web.nav.dashboard", icon: IconLayoutDashboard },
  { path: "/estadias", label: "web.nav.estadias", icon: IconHome },
  { path: "/trabalho-diario", label: "web.nav.trabalho_diario", icon: IconCalendarEvent },
  { path: "/stock-semen", label: "web.nav.stock_semen", icon: IconFlask },
  { path: "/atividade", label: "web.nav.atividade", icon: IconActivity },
  { path: "/relatorios", label: "web.nav.relatorios", icon: IconChartBar },
  { path: "/definicoes", label: "web.nav.definicoes", icon: IconSettings },
] as const;

export function Shell({ user }: { user: User }) {
  const t = useT();
  const { company_name } = useBrand();
  const [opened, { toggle, close }] = useDisclosure();
  const location = useLocation();
  const queryClient = useQueryClient();

  useEffect(close, [location.pathname, close]);

  const logout = async () => {
    try {
      await api("/auth/logout", "POST");
    } finally {
      queryClient.clear();
      queryClient.setQueryData(["me"], null);
    }
  };

  return (
    <AppShell
      header={{ height: { base: 56, md: 0 } }}
      // Telemóvel e tablet ao alto (< 992px): menu escondido atrás do botão ☰,
      // para o conteúdo ter a largura toda.
      navbar={{ width: 248, breakpoint: "md", collapsed: { mobile: !opened } }}
      padding={{ base: "sm", sm: "lg" }}
    >
      <AppShell.Header hiddenFrom="md">
        <Group h="100%" px="md" gap="sm">
          <Burger opened={opened} onClick={toggle} size="sm" aria-label="Menu" />
          <BrandMark size={28} />
          <Text fw={700}>{company_name}</Text>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <Group gap="sm" mb="lg" visibleFrom="md">
          <BrandMark size={36} />
          <Text fw={700} size="lg" lineClamp={1}>
            {company_name}
          </Text>
        </Group>

        <AppShell.Section grow component={ScrollArea}>
          <Stack gap={2}>
            {NAV.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                component={RouterLink}
                to={path}
                label={t(label)}
                leftSection={<Icon size={18} stroke={1.6} />}
                active={location.pathname.startsWith(path)}
                variant="light"
                style={{ borderRadius: "var(--mantine-radius-md)" }}
              />
            ))}
          </Stack>
        </AppShell.Section>

        <AppShell.Section pt="md" style={{ borderTop: "1px solid var(--mantine-color-gray-2)" }}>
          <Group gap="sm" wrap="nowrap">
            <Avatar color="brand" radius="xl" size={34}>
              {user.nome?.[0]?.toUpperCase() ?? user.username[0]?.toUpperCase()}
            </Avatar>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Text size="sm" fw={600} truncate>
                {user.nome || user.username}
              </Text>
              <Text size="xs" c="dimmed" truncate>
                {user.nivel}
              </Text>
            </div>
            <UnstyledButton onClick={logout} aria-label={t("web.nav.logout")} title={t("web.nav.logout")} p={6}>
              <IconLogout size={18} stroke={1.6} />
            </UnstyledButton>
          </Group>
          <Box mt="sm">
            <ProductSignature />
          </Box>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main bg="gray.0" style={{ minHeight: "100vh" }}>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
