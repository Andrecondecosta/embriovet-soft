import { createContext, useCallback, useContext, type ReactNode } from "react";

type Params = Record<string, string | number>;
type TFn = (key: string, params?: Params) => string;

const I18nContext = createContext<TFn>((key) => key);

// Muitos textos herdados da app Streamlit começam com emoji ("❌ Nome é
// obrigatório", "👥 Gestão de Proprietários") ou vêm em markdown (**…**).
// Na app nova os ícones vêm dos componentes, por isso tiram-se aqui.
function limpar(texto: string) {
  return texto.replace(/\*\*/g, "").replace(/^[^\p{L}\p{N}«"“„(]+/u, "").trim();
}

export function I18nProvider({ messages, children }: { messages: Record<string, string>; children: ReactNode }) {
  const t = useCallback<TFn>(
    (key, params) => {
      let texto = messages[key] ?? key;
      if (params) for (const [k, v] of Object.entries(params)) texto = texto.replaceAll(`{${k}}`, String(v));
      return limpar(texto);
    },
    [messages],
  );
  return <I18nContext.Provider value={t}>{children}</I18nContext.Provider>;
}

export const useT = () => useContext(I18nContext);
