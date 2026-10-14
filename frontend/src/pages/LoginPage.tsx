import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Center, Paper, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { IconLock } from "@tabler/icons-react";

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
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aEntrar, setAEntrar] = useState(false);

  const submeter = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
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
    <Center mih="100vh" bg="gray.1" p="md">
      <Stack w="100%" maw={400} gap="lg">
        <Stack align="center" gap={6}>
          <BrandMark size={56} />
          <Title order={2} ta="center" mt={8}>
            {company_name}
          </Title>
          <Text c="dimmed" size="sm">
            {t("login.subtitle")}
          </Text>
        </Stack>

        <Paper component="form" onSubmit={submeter} p="xl" radius="lg" shadow="md" withBorder>
          <Stack>
            <TextInput
              label={t("auth.username")}
              placeholder={t("auth.username_placeholder")}
              value={username}
              onChange={(e) => setUsername(e.currentTarget.value)}
              autoComplete="username"
              autoFocus
              size="md"
            />
            <PasswordInput
              label={t("auth.password")}
              placeholder={t("auth.password_placeholder")}
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              autoComplete="current-password"
              size="md"
            />
            {erro && (
              <Alert color="red" variant="light" py="xs">
                {erro}
              </Alert>
            )}
            <Button type="submit" size="md" loading={aEntrar} fullWidth mt={4}>
              {t("auth.login")}
            </Button>
          </Stack>
        </Paper>

        <Text c="dimmed" size="xs" ta="center">
          <IconLock size={12} style={{ verticalAlign: -1, marginRight: 4 }} />
          {t("login.secure")}
        </Text>

        <ProductSignature />
      </Stack>
    </Center>
  );
}
