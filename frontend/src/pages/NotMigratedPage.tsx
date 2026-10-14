import { useLocation } from "react-router-dom";
import { Center, Paper, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import { IconClockHour4 } from "@tabler/icons-react";

import { useT } from "../i18n/I18n";
import { NAV } from "../components/Shell";

/** Lugar das páginas que ainda só existem na app Streamlit. */
export function NotMigratedPage() {
  const t = useT();
  const { pathname } = useLocation();
  const item = NAV.find((n) => n.path === pathname);

  return (
    <Center mih="60vh">
      <Paper p="xl" radius="lg" withBorder maw={460} w="100%">
        <Stack align="center" gap="sm" ta="center">
          <ThemeIcon size={48} radius="xl" variant="light" color="gray">
            <IconClockHour4 size={26} />
          </ThemeIcon>
          {item && <Title order={3}>{t(item.label)}</Title>}
          <Text fw={600}>{t("web.not_migrated.title")}</Text>
          <Text c="dimmed" size="sm">
            {t("web.not_migrated.text")}
          </Text>
        </Stack>
      </Paper>
    </Center>
  );
}
