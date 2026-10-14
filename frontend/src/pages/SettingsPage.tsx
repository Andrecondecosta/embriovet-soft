import { Navigate, useNavigate, useParams } from "react-router-dom";
import { Tabs, Title } from "@mantine/core";

import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { OwnersTab } from "./owners/OwnersTab";
import { NotMigratedPage } from "./NotMigratedPage";

// Mesmos separadores e permissões que `definicoes_page.py`: Utilizadores e
// Cópia de segurança só para Administrador.
const TABS = [
  { id: "marca", label: "web.settings.tab.brand", admin: false },
  { id: "alojamentos", label: "web.settings.tab.housing", admin: false },
  { id: "proprietarios", label: "web.settings.tab.owners", admin: false },
  { id: "utilizadores", label: "web.settings.tab.users", admin: true },
  { id: "backup", label: "web.settings.tab.backup", admin: true },
  { id: "idioma", label: "web.settings.tab.language", admin: false },
];

export function SettingsPage({ user }: { user: User }) {
  const t = useT();
  const navigate = useNavigate();
  const { tab } = useParams();
  const visiveis = TABS.filter((x) => !x.admin || user.nivel === "Administrador");

  if (!tab || !visiveis.some((x) => x.id === tab)) return <Navigate to="/definicoes/proprietarios" replace />;

  return (
    <>
      <Title order={2} mb="md">
        {t("web.nav.definicoes")}
      </Title>
      <Tabs value={tab} onChange={(v) => v && navigate(`/definicoes/${v}`)} keepMounted={false}>
        <Tabs.List mb="lg" className="tabs-scroll">
          {visiveis.map((x) => (
            <Tabs.Tab key={x.id} value={x.id}>
              {t(x.label)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        {visiveis.map((x) => (
          <Tabs.Panel key={x.id} value={x.id}>
            {x.id === "proprietarios" ? <OwnersTab /> : <NotMigratedPage />}
          </Tabs.Panel>
        ))}
      </Tabs>
    </>
  );
}
