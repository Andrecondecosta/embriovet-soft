import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Flex, Form, Input, Typography } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";

import { api } from "../api/client";
import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { BrandMark, ProductSignature, useBrand } from "../components/Brand";
import { useErrorMessage } from "../components/errors";

export function LoginPage() {
  const t = useT();
  const { company_name } = useBrand();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [erro, setErro] = useState<string | null>(null);
  const [aEntrar, setAEntrar] = useState(false);

  const submeter = async ({ username, password }: { username?: string; password?: string }) => {
    if (!username?.trim() || !password) {
      setErro(t("login.missing"));
      return;
    }
    setErro(null);
    setAEntrar(true);
    try {
      const { user } = await api<{ user: User }>("/auth/login", "POST", { username, password });
      queryClient.setQueryData(["me"], user);
    } catch (err) {
      setErro(errorMessage(err));
      setAEntrar(false);
    }
  };

  return (
    <Flex vertical align="center" justify="center" gap={16} style={{ minHeight: "100vh", padding: 16, background: "#f0f2f5" }}>
      <Flex vertical align="center" gap={4}>
        <BrandMark size={52} />
        <Typography.Title level={3} style={{ margin: "8px 0 0" }}>
          {company_name}
        </Typography.Title>
        <Typography.Text type="secondary">{t("login.subtitle")}</Typography.Text>
      </Flex>

      <Card style={{ width: "100%", maxWidth: 380 }}>
        <Form layout="vertical" onFinish={submeter} requiredMark={false}>
          <Form.Item name="username" label={t("auth.username")}>
            <Input prefix={<UserOutlined />} placeholder={t("auth.username_placeholder")} autoComplete="username" autoFocus size="large" />
          </Form.Item>
          <Form.Item name="password" label={t("auth.password")}>
            <Input.Password
              prefix={<LockOutlined />}
              placeholder={t("auth.password_placeholder")}
              autoComplete="current-password"
              size="large"
            />
          </Form.Item>
          {erro && <Alert type="error" title={erro} showIcon style={{ marginBottom: 16 }} />}
          <Button type="primary" htmlType="submit" block size="large" loading={aEntrar}>
            {t("auth.login")}
          </Button>
        </Form>
      </Card>

      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        <LockOutlined /> {t("login.secure")}
      </Typography.Text>
      <ProductSignature />
    </Flex>
  );
}
