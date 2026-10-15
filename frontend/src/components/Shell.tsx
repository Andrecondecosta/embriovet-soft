import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Avatar, Button, Drawer, Dropdown, Flex, Layout, Menu, Typography, theme } from "antd";
import {
  AppstoreOutlined,
  BarChartOutlined,
  CalendarOutlined,
  ExperimentOutlined,
  HomeOutlined,
  LineChartOutlined,
  LogoutOutlined,
  MenuOutlined,
  SettingOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";
import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { BrandMark, ProductSignature, useBrand } from "./Brand";
import { useIsMobile } from "./responsive";

// Os mesmos 7 sítios do menu da app atual (Pedido 7), pela mesma ordem.
export const NAV = [
  { path: "/dashboard", label: "web.nav.dashboard", icon: <AppstoreOutlined /> },
  { path: "/estadias", label: "web.nav.estadias", icon: <HomeOutlined /> },
  { path: "/trabalho-diario", label: "web.nav.trabalho_diario", icon: <CalendarOutlined /> },
  { path: "/stock-semen", label: "web.nav.stock_semen", icon: <ExperimentOutlined /> },
  { path: "/atividade", label: "web.nav.atividade", icon: <LineChartOutlined /> },
  { path: "/relatorios", label: "web.nav.relatorios", icon: <BarChartOutlined /> },
  { path: "/definicoes", label: "web.nav.definicoes", icon: <SettingOutlined /> },
];

export function Shell({ user }: { user: User }) {
  const t = useT();
  const { company_name } = useBrand();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();
  const { token } = theme.useToken();
  const [recolhido, setRecolhido] = useState(false);
  const [menuMovel, setMenuMovel] = useState(false);

  useEffect(() => setMenuMovel(false), [location.pathname]);

  const logout = async () => {
    try {
      await api("/auth/logout", "POST");
    } finally {
      queryClient.clear();
      queryClient.setQueryData(["me"], null);
    }
  };

  const ativo = NAV.find((n) => location.pathname.startsWith(n.path))?.path;
  const menu = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={ativo ? [ativo] : []}
      items={NAV.map((n) => ({ key: n.path, icon: n.icon, label: t(n.label) }))}
      onClick={({ key }) => navigate(key)}
    />
  );

  const marca = (comNome: boolean) => (
    <Flex align="center" gap={10} style={{ height: 48, padding: "0 16px", overflow: "hidden" }}>
      <BrandMark size={28} />
      {comNome && (
        <Typography.Text strong style={{ color: "#fff", whiteSpace: "nowrap" }} ellipsis>
          {company_name}
        </Typography.Text>
      )}
    </Flex>
  );

  const utilizador = (
    <Dropdown
      trigger={["click"]}
      menu={{
        items: [
          { key: "quem", label: `${user.nome || user.username} · ${user.nivel}`, disabled: true },
          { type: "divider" },
          { key: "sair", icon: <LogoutOutlined />, label: t("header.logout"), onClick: logout },
        ],
      }}
    >
      <Button type="text" style={{ paddingInline: 6, height: 40 }}>
        <Avatar size="small" style={{ background: token.colorPrimary }}>
          {(user.nome || user.username)[0]?.toUpperCase()}
        </Avatar>
        {!isMobile && (
          <span>
            <Typography.Text>{user.nome || user.username}</Typography.Text>{" "}
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              ({user.nivel})
            </Typography.Text>
          </span>
        )}
      </Button>
    </Dropdown>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {!isMobile && (
        <Layout.Sider
          width={220}
          collapsible
          collapsed={recolhido}
          onCollapse={setRecolhido}
          collapsedWidth={56}
          style={{ position: "sticky", top: 0, height: "100vh", overflow: "auto" }}
        >
          {marca(!recolhido)}
          {menu}
          {!recolhido && (
            <div style={{ position: "absolute", bottom: 60, left: 16 }}>
              <ProductSignature escuro />
            </div>
          )}
        </Layout.Sider>
      )}

      <Layout>
        <Layout.Header
          style={{
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <Flex align="center" gap={8} style={{ minWidth: 0 }}>
            {isMobile && (
              <>
                <Button type="text" icon={<MenuOutlined />} onClick={() => setMenuMovel(true)} aria-label="Menu" />
                <BrandMark size={24} />
                <Typography.Text strong ellipsis>
                  {company_name}
                </Typography.Text>
              </>
            )}
          </Flex>
          {/* À direita mesmo quando o bloco da esquerda está vazio (computador). */}
          <div style={{ marginLeft: "auto" }}>{utilizador}</div>
        </Layout.Header>

        <Layout.Content style={{ padding: isMobile ? 8 : 16 }}>
          <Outlet />
        </Layout.Content>
      </Layout>

      {/* Telemóvel: o menu entra pela esquerda. */}
      <Drawer
        open={menuMovel}
        onClose={() => setMenuMovel(false)}
        placement="left"
        size={240}
        closable={false}
        styles={{ body: { padding: 0, background: "#001529", display: "flex", flexDirection: "column" } }}
      >
        {marca(true)}
        {menu}
        <div style={{ marginTop: "auto", padding: 16 }}>
          <ProductSignature escuro />
        </div>
      </Drawer>
    </Layout>
  );
}
