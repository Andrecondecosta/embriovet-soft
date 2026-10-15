import "./styles.css";

import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { unstableSetRender } from "antd-mobile";

import { App } from "./App";
import { ApiError } from "./api/client";

// O antd-mobile abre janelas por código (Dialog.confirm, Toast) e, com o
// React 19, precisa que lhe digam como as desenhar.
unstableSetRender((node, container) => {
  const c = container as Element & { _raiz?: Root };
  c._raiz ??= createRoot(c);
  c._raiz.render(node);
  return async () => {
    await new Promise((r) => setTimeout(r, 0));
    c._raiz?.unmount();
  };
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Erros de permissão/sessão não se resolvem a repetir.
      retry: (n, err) => !(err instanceof ApiError && err.status < 500) && n < 2,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
