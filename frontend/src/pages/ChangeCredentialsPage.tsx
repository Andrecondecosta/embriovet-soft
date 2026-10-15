import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Flex, Form, Input, Typography } from "antd";

import { api } from "../api/client";
import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { notifySuccess, useErrorMessage } from "../components/errors";
import { ProductSignature } from "../components/Brand";

/** Alteração obrigatória de credenciais no primeiro acesso
 *  (equivalente a `render_change_credentials` em app.py). */
export function ChangeCredentialsPage({ user }: { user: User }) {
  const t = useT();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [erro, setErro] = useState<string | null>(null);
  const [aGuardar, setAGuardar] = useState(false);

  const submeter = async (v: { username?: string; password?: string; confirmar?: string }) => {
    if (!v.username?.trim()) return setErro(t("error.username_required"));
    if (!v.password || !v.confirmar) return setErro(t("error.password_required"));
    if (v.password !== v.confirmar) return setErro(t("error.passwords_mismatch"));
    setErro(null);
    setAGuardar(true);
    try {
      const r = await api<{ user: User }>("/auth/change-credentials", "POST", {
        username: v.username,
        password: v.password,
        confirm_password: v.confirmar,
      });
      notifySuccess(t("security.success"));
      queryClient.setQueryData(["me"], r.user);
    } catch (err) {
      setErro(errorMessage(err));
      setAGuardar(false);
    }
  };

  return (
    <Flex vertical align="center" justify="center" gap={16} style={{ minHeight: "100vh", padding: 16, background: "#f0f2f5" }}>
      <Card style={{ width: "100%", maxWidth: 420 }} title={t("security.title")}>
        <Typography.Paragraph type="secondary">{t("security.info")}</Typography.Paragraph>
        <Form layout="vertical" onFinish={submeter} initialValues={{ username: user.username }} requiredMark={false}>
          <Form.Item name="username" label={t("security.username")}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label={t("security.new_password")}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="confirmar" label={t("security.confirm_password")}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          {erro && <Alert type="error" title={erro} showIcon style={{ marginBottom: 16 }} />}
          <Button type="primary" htmlType="submit" block loading={aGuardar}>
            {t("security.save")}
          </Button>
        </Form>
      </Card>
      <ProductSignature />
    </Flex>
  );
}
