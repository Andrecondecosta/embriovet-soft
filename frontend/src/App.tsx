import { lazy, Suspense, useEffect, useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider, Spin } from "antd";
import ptPT from "antd/locale/pt_PT";
import enUS from "antd/locale/en_US";
import frFR from "antd/locale/fr_FR";
import deDE from "antd/locale/de_DE";

import { api, setUnauthorizedHandler } from "./api/client";
import { criarTema } from "./theme";
import type { PublicSettings, User } from "./api/types";
import { I18nProvider } from "./i18n/I18n";
import { BrandContext, PRODUCT_NAME } from "./components/Brand";
import { NAV, Shell } from "./components/Shell";
import { UserContext } from "./components/User";
import { ligarFeedback } from "./components/errors";
import { useIsMobile } from "./components/responsive";
import { StockPage } from "./pages/stock/StockPage";
import { AddLotePage } from "./pages/stock/AddLotePage";
import { LoginPage } from "./pages/LoginPage";
import { ChangeCredentialsPage } from "./pages/ChangeCredentialsPage";
import { NotMigratedPage } from "./pages/NotMigratedPage";
import { SettingsPage } from "./pages/SettingsPage";

// Amostra do Ant Design Mobile — carregada à parte, só quando se abre.
const AmostraMobile = lazy(() => import("./pages/amostra/AmostraMobile"));

const LOCALES = { "pt-PT": ptPT, en: enUS, fr: frFR, de: deDE } as const;

function FullPageLoader() {
  return (
    <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Spin size="large" />
    </div>
  );
}

/** Entrega ao `errors.ts` os avisos/confirmações do antd com o tema certo. */
function FeedbackBridge() {
  const { message, modal } = AntApp.useApp();
  useEffect(() => ligarFeedback(message, modal), [message, modal]);
  return null;
}

export function App() {
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();

  const settings = useQuery({
    queryKey: ["settings", "public"],
    queryFn: () => api<PublicSettings>("/settings/public"),
    staleTime: Infinity,
  });
  const lang = settings.data?.language ?? "pt-PT";
  const messages = useQuery({
    queryKey: ["i18n", lang],
    queryFn: () => api<Record<string, string>>(`/i18n/${lang}`),
    enabled: settings.isSuccess,
    staleTime: Infinity,
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ user: User }>("/auth/me").then((r) => r.user),
    retry: false,
  });

  useEffect(() => {
    // Sessão expirada a meio: volta ao login sem recarregar a página.
    setUnauthorizedHandler(() => queryClient.setQueryData(["me"], null));
  }, [queryClient]);

  useEffect(() => {
    if (settings.data) {
      document.title = `${settings.data.company_name} · ${PRODUCT_NAME}`;
      document.documentElement.lang = lang.slice(0, 2);
    }
  }, [settings.data, lang]);

  const primary = settings.data?.primary_color ?? "#E85D4A";
  const tema = useMemo(() => criarTema(primary, isMobile), [primary, isMobile]);

  const loading = settings.isPending || messages.isPending || me.isPending;
  const user = me.data ?? null;

  return (
    <ConfigProvider theme={tema} locale={LOCALES[lang as keyof typeof LOCALES] ?? ptPT}>
      <AntApp message={{ top: 56, maxCount: 3 }}>
        <FeedbackBridge />
        {loading ? (
          <FullPageLoader />
        ) : (
          <I18nProvider messages={messages.data ?? {}}>
            <BrandContext.Provider value={settings.data!}>
              <Routes>
                {!user ? (
                  <>
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="*" element={<Navigate to="/login" replace />} />
                  </>
                ) : user.must_change_password ? (
                  <>
                    <Route path="/alterar-credenciais" element={<ChangeCredentialsPage user={user} />} />
                    <Route path="*" element={<Navigate to="/alterar-credenciais" replace />} />
                  </>
                ) : (
                  <>
                  <Route
                    path="/amostra-mobile"
                    element={
                      <Suspense fallback={<FullPageLoader />}>
                        <AmostraMobile />
                      </Suspense>
                    }
                  />
                  <Route
                    element={
                      <UserContext.Provider value={user}>
                        <Shell user={user} />
                      </UserContext.Provider>
                    }
                  >
                    <Route path="/definicoes/:tab?" element={<SettingsPage user={user} />} />
                    <Route path="/stock-semen/novo" element={<AddLotePage />} />
                    <Route path="/stock-semen/:tab?" element={<StockPage />} />
                    {NAV.filter((n) => !["/definicoes", "/stock-semen"].includes(n.path)).map((n) => (
                      <Route key={n.path} path={n.path} element={<NotMigratedPage />} />
                    ))}
                    <Route path="*" element={<Navigate to="/definicoes/proprietarios" replace />} />
                  </Route>
                  </>
                )}
              </Routes>
            </BrandContext.Provider>
          </I18nProvider>
        )}
      </AntApp>
    </ConfigProvider>
  );
}
