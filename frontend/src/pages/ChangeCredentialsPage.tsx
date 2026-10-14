import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";

import { api } from "../api/client";
import type { User } from "../api/types";
import { useT } from "../i18n/I18n";
import { useErrorMessage, notifySuccess } from "../components/errors";
import { ProductSignature } from "../components/Brand";

/** Alteração obrigatória de credenciais no primeiro acesso
 *  (equivalente a `render_change_credentials` em app.py). */
export function ChangeCredentialsPage({ user }: { user: User }) {
  const t = useT();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const [username, setUsername] = useState(user.username);
  const [password, setPassword] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aGuardar, setAGuardar] = useState(false);

  const submeter = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return setErro(t("error.username_required"));
    if (!password || !confirmar) return setErro(t("error.password_required"));
    if (password !== confirmar) return setErro(t("error.passwords_mismatch"));
    setErro(null);
    setAGuardar(true);
    try {
      const r = await api<{ user: User }>("/auth/change-credentials", "POST", {
        username,
        password,
        confirm_password: confirmar,
      });
      notifySuccess(t("security.success"));
      queryClient.setQueryData(["me"], r.user);
    } catch (err) {
      setErro(errorMessage(err));
      setAGuardar(false);
    }
  };

  return (
    <Center mih="100vh" bg="gray.1" p="md" style={{ flexDirection: "column", gap: 20 }}>
      <Paper component="form" onSubmit={submeter} p="xl" radius="lg" shadow="md" withBorder w="100%" maw={440}>
        <Stack>
          <div>
            <Title order={3}>{t("security.title")}</Title>
            <Text c="dimmed" size="sm" mt={4}>
              {t("security.info")}
            </Text>
          </div>
          <TextInput label={t("security.username")} value={username} onChange={(e) => setUsername(e.currentTarget.value)} />
          <PasswordInput
            label={t("security.new_password")}
            value={password}
            onChange={(e) => setPassword(e.currentTarget.value)}
            autoComplete="new-password"
          />
          <PasswordInput
            label={t("security.confirm_password")}
            value={confirmar}
            onChange={(e) => setConfirmar(e.currentTarget.value)}
            autoComplete="new-password"
          />
          {erro && (
            <Alert color="red" variant="light" py="xs">
              {erro}
            </Alert>
          )}
          <Button type="submit" loading={aGuardar}>
            {t("security.save")}
          </Button>
        </Stack>
      </Paper>
      <ProductSignature />
    </Center>
  );
}
