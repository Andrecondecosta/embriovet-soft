import { Navigate, useNavigate, useParams } from "react-router-dom";
import { Card, Tabs } from "antd";
import { CapsuleTabs } from "antd-mobile";

import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { PageHeader } from "../components/ds";
import { useIsMobile } from "../components/responsive";
import { OwnersTab } from "./owners/OwnersTab";
import { MarcaTab, IdiomaTab } from "./settings/MarcaTab";
import { AlojamentosTab } from "./settings/AlojamentosTab";
import { UtilizadoresTab } from "./settings/UtilizadoresTab";
import { BackupTab } from "./settings/BackupTab";

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
  const isMobile = useIsMobile();
  const { tab } = useParams();
  const visiveis = TABS.filter((x) => !x.admin || user.nivel === "Administrador");

  if (!tab || !visiveis.some((x) => x.id === tab)) return <Navigate to="/definicoes/proprietarios" replace />;

  const conteudo = (id: string) =>
    ({
      marca: <MarcaTab />,
      alojamentos: <AlojamentosTab />,
      proprietarios: <OwnersTab />,
      utilizadores: <UtilizadoresTab />,
      backup: <BackupTab />,
      idioma: <IdiomaTab />,
    })[id];

  if (isMobile)
    // Telemóvel: o título está na barra de cima; separadores em "cápsula".
    return (
      <>
        <CapsuleTabs activeKey={tab} onChange={(v) => navigate(`/definicoes/${v}`)} style={{ background: "#fff" }}>
          {visiveis.map((x) => (
            <CapsuleTabs.Tab key={x.id} title={t(x.label)} />
          ))}
        </CapsuleTabs>
        <div>{conteudo(tab)}</div>
      </>
    );

  return (
    <Card size="small">
      <PageHeader titulo={t("web.nav.definicoes")} />
      <Tabs
        activeKey={tab}
        onChange={(v) => navigate(`/definicoes/${v}`)}
        destroyOnHidden
        items={visiveis.map((x) => ({
          key: x.id,
          label: t(x.label),
          children: conteudo(x.id),
        }))}
      />
    </Card>
  );
}
