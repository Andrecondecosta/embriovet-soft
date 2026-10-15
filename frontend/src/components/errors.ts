import { useCallback } from "react";
import type { ReactNode } from "react";
import type { App } from "antd";
import { ApiError } from "../api/client";
import { useT } from "../i18n/I18n";

// Avisos e confirmações do Ant Design precisam do contexto do tema (cor da
// marca, idioma). O `FeedbackBridge` (em App.tsx, dentro do <App> do antd)
// entrega aqui as instâncias, para se poderem chamar de qualquer sítio.
type AppApi = ReturnType<typeof App.useApp>;
let mensagens: AppApi["message"] | null = null;
let modais: AppApi["modal"] | null = null;

export function ligarFeedback(m: AppApi["message"], md: AppApi["modal"]) {
  mensagens = m;
  modais = md;
}

export const notifySuccess = (texto: string) => mensagens?.success(texto);

/** Mensagem traduzida para um erro da API (ou genérica). */
export function useErrorMessage() {
  const t = useT();
  return useCallback(
    (err: unknown) => {
      if (err instanceof ApiError) {
        if (err.code === "not_authenticated") return t("web.error.session_expired");
        if (err.status < 500 && err.code !== "web.error.generic") return t(err.code, err.params);
      }
      return t("web.error.generic");
    },
    [t],
  );
}

export function useNotifyError() {
  const message = useErrorMessage();
  return useCallback((err: unknown) => mensagens?.error(message(err)), [message]);
}

/** Pergunta de confirmação (ex.: apagar). `perigo` pinta o botão a vermelho. */
export function confirmar(o: {
  titulo: string;
  texto: ReactNode;
  ok: string;
  cancelar: string;
  perigo?: boolean;
  onOk: () => Promise<unknown> | void;
}) {
  modais?.confirm({
    title: o.titulo,
    content: o.texto,
    okText: o.ok,
    cancelText: o.cancelar,
    okButtonProps: o.perigo ? { danger: true } : undefined,
    onOk: o.onOk,
  });
}
