import { useEffect, useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider, Spin } from "antd";
import { ConfigProvider as MobileConfig } from "antd-mobile";
import mobilePtBR from "antd-mobile/es/locales/pt-BR";
import mobileEnUS from "antd-mobile/es/locales/en-US";
import mobileFrFR from "antd-mobile/es/locales/fr-FR";
import mobileDeDE from "antd-mobile/es/locales/de-DE";
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
import { AtividadePage } from "./pages/AtividadePage";
import { DashboardPage } from "./pages/DashboardPage";
import { RelatoriosPage } from "./pages/RelatoriosPage";
import { EstadiasPage } from "./pages/estadias/EstadiasPage";
import { TrabalhoPage } from "./pages/TrabalhoPage";
import { AnimalPage } from "./pages/animal/AnimalPage";
import { InseminacaoPage } from "./pages/InseminacaoPage";
import { ImportarPage } from "./pages/stock/ImportarPage";
import { SettingsPage } from "./pages/SettingsPage";

// Páginas do menu que já existem na app nova (as outras mostram "ainda não migrado").
const MIGRADAS = ["/definicoes", "/stock-semen", "/atividade", "/dashboard", "/relatorios", "/estadias", "/trabalho-diario"];

const LOCALES = { "pt-PT": ptPT, en: enUS, fr: frFR, de: deDE } as const;
// O Ant Design Mobile não tem português de Portugal; o do Brasil só aparece
// nos botões internos das janelas (Confirmar/Cancelar).
const LOCALES_MOBILE = { "pt-PT": mobilePtBR, en: mobileEnUS, fr: mobileFrFR, de: mobileDeDE } as const;

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

  useEffect(() => {
    // Ant Design Mobile (telemóvel): cor da marca e letra mais pequena do
    // que o padrão do iPhone — linhas a 13 px, descrições a 11 px. Não
    // descer mais: abaixo disto custa a ler na coudelaria/ao sol.
    const raiz = document.documentElement.style;
    const vars: Record<string, string> = {
      "--adm-color-primary": primary,
      "--adm-font-size-10": "15px",
      "--adm-font-size-9": "13px",
      "--adm-font-size-8": "13px",
      "--adm-font-size-7": "12px",
      "--adm-font-size-6": "12px",
      "--adm-font-size-main": "11px",
    };
    Object.entries(vars).forEach(([k, v]) => raiz.setProperty(k, v));
  }, [primary]);
  const tema = useMemo(() => criarTema(primary, isMobile), [primary, isMobile]);

  const loading = settings.isPending || messages.isPending || me.isPending;
  const user = me.data ?? null;

  return (
    <ConfigProvider theme={tema} locale={LOCALES[lang as keyof typeof LOCALES] ?? ptPT}>
      <MobileConfig locale={LOCALES_MOBILE[lang as keyof typeof LOCALES_MOBILE] ?? mobilePtBR}>
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
                        element={
                          <UserContext.Provider value={user}>
                            <Shell user={user} />
                          </UserContext.Provider>
                        }
                      >
                        <Route path="/definicoes/:tab?" element={<SettingsPage user={user} />} />
                        <Route path="/dashboard" element={<DashboardPage />} />
                        <Route path="/atividade" element={<AtividadePage />} />
                        <Route path="/relatorios" element={<RelatoriosPage />} />
                        <Route path="/estadias/:tab?" element={<EstadiasPage />} />
                        <Route path="/trabalho-diario" element={<TrabalhoPage />} />
                        <Route path="/animais/:id" element={<AnimalPage />} />
                        <Route path="/trabalho-diario/inseminacao" element={<InseminacaoPage />} />
                        <Route path="/stock-semen/novo" element={<AddLotePage />} />
                        <Route path="/stock-semen/importar" element={<ImportarPage />} />
                        <Route path="/stock-semen/:tab?" element={<StockPage />} />
                        {NAV.filter((n) => !MIGRADAS.includes(n.path)).map((n) => (
                          <Route key={n.path} path={n.path} element={<NotMigratedPage />} />
                        ))}
                        <Route path="*" element={<Navigate to="/dashboard" replace />} />
                      </Route>
                    </>
                  )}
                </Routes>
              </BrandContext.Provider>
            </I18nProvider>
          )}
        </AntApp>
      </MobileConfig>
    </ConfigProvider>
  );
}
