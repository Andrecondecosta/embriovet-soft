import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { List, NavBar, Popup, TabBar } from "antd-mobile";
import {
  AppstoreOutlined,
  CalendarOutlined,
  EllipsisOutlined,
  ExperimentOutlined,
  HomeOutlined,
  LogoutOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";
import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { BrandMark, ProductSignature, useBrand } from "./Brand";
import { NAV } from "./Shell";

// Barra de baixo: só cabem 5. As restantes secções ficam em "Mais".
const BARRA = ["/dashboard", "/estadias", "/trabalho-diario", "/stock-semen"];
const CURTOS: Record<string, string> = { "/stock-semen": "Stock" };

/** Título da barra de cima e se tem botão "voltar" (páginas dentro de páginas). */
function tituloDaRota(pathname: string, t: (k: string) => string): { titulo: string; voltar: boolean } {
  if (pathname === "/stock-semen/novo") return { titulo: t("web.stock.add"), voltar: true };
  const n = NAV.find((x) => pathname.startsWith(x.path));
  return { titulo: n ? t(n.label) : "", voltar: false };
}

/**
 * Moldura da app no telemóvel (Ant Design Mobile): barra de título em cima
 * e barra de navegação em baixo, à mão do polegar — como numa app nativa.
 */
export function MobileShell({ user }: { user: User }) {
  const t = useT();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const queryClient = useQueryClient();
  const { company_name } = useBrand();
  const [mais, setMais] = useState(false);

  const { titulo, voltar } = tituloDaRota(pathname, t);
  const ativo = BARRA.find((p) => pathname.startsWith(p)) ?? "mais";

  const logout = async () => {
    try {
      await api("/auth/logout", "POST");
    } finally {
      queryClient.clear();
      queryClient.setQueryData(["me"], null);
    }
  };

  return (
    <div style={{ height: "100dvh", display: "flex", flexDirection: "column", background: "#f5f5f5" }}>
      <NavBar
        back={voltar ? "" : null}
        onBack={() => navigate(-1)}
        style={{ background: "#fff", borderBottom: "1px solid #eee", flexShrink: 0, "--height": "46px" } as React.CSSProperties}
      >
        {titulo}
      </NavBar>

      <div data-scroll-raiz style={{ flex: 1, overflowY: "auto", WebkitOverflowScrolling: "touch" }}>
        <Outlet />
      </div>

      <TabBar
        activeKey={ativo}
        onChange={(k) => (k === "mais" ? setMais(true) : navigate(k))}
        safeArea
        style={{ background: "#fff", borderTop: "1px solid #eee", flexShrink: 0 }}
      >
        {NAV.filter((n) => BARRA.includes(n.path)).map((n) => (
          <TabBar.Item key={n.path} icon={iconeBarra(n.path)} title={CURTOS[n.path] ?? t(n.label)} />
        ))}
        <TabBar.Item key="mais" icon={<EllipsisOutlined />} title={t("web.nav.more")} />
      </TabBar>

      <Popup
        visible={mais}
        onMaskClick={() => setMais(false)}
        onClose={() => setMais(false)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 16px 8px" }}>
          <BrandMark size={32} />
          <div>
            <div style={{ fontWeight: 600 }}>{company_name}</div>
            <div style={{ fontSize: 11, color: "#999" }}>
              {user.nome || user.username} · {user.nivel}
            </div>
          </div>
        </div>
        <List>
          {NAV.filter((n) => !BARRA.includes(n.path)).map((n) => (
            <List.Item
              key={n.path}
              prefix={n.icon}
              onClick={() => {
                setMais(false);
                navigate(n.path);
              }}
              arrow
            >
              {t(n.label)}
            </List.Item>
          ))}
          <List.Item prefix={<LogoutOutlined />} onClick={logout} style={{ color: "#ff3141" }}>
            {t("header.logout")}
          </List.Item>
        </List>
        <div style={{ textAlign: "center", padding: 12 }}>
          <ProductSignature />
        </div>
      </Popup>
    </div>
  );
}

function iconeBarra(path: string) {
  switch (path) {
    case "/dashboard":
      return <AppstoreOutlined />;
    case "/estadias":
      return <HomeOutlined />;
    case "/trabalho-diario":
      return <CalendarOutlined />;
    default:
      return <ExperimentOutlined />;
  }
}
