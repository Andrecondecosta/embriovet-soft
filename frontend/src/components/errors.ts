import { useCallback } from "react";
import { notifications } from "@mantine/notifications";
import { ApiError } from "../api/client";
import { useT } from "../i18n/I18n";

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
  return useCallback(
    (err: unknown) => notifications.show({ color: "red", message: message(err) }),
    [message],
  );
}

export const notifySuccess = (message: string) => notifications.show({ color: "teal", message });
