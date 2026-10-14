import { Button, Divider, Drawer, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconPencil, IconPlayerPause, IconPlayerPlay, IconTrash } from "@tabler/icons-react";

import type { Owner } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { useDeleteOwner, useToggleOwner } from "./api";
import { StatusPill } from "../../components/ds";
import { useIsMobile } from "../../components/responsive";

export function StatusBadge({ ativo }: { ativo: boolean | null }) {
  return <StatusPill ativo={ativo} />;
}

function Campo({ label, valor }: { label: string; valor: string | number | null }) {
  const t = useT();
  return (
    <div>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {valor === null || valor === "" ? t("common.na") : valor}
      </Text>
    </div>
  );
}

export function OwnerDrawer({
  owner,
  onClose,
  onEdit,
  onChanged,
}: {
  owner: Owner | null;
  onClose: () => void;
  onEdit: (o: Owner) => void;
  onChanged: (o: Owner) => void;
}) {
  const t = useT();
  const notifyError = useNotifyError();
  const isMobile = useIsMobile();
  const alternar = useToggleOwner();
  const apagar = useDeleteOwner();

  const ativo = owner?.ativo !== false;

  const alternarEstado = async () => {
    if (!owner) return;
    try {
      const atualizado = (await alternar.mutateAsync(owner.id)) as Owner;
      notifySuccess(atualizado.ativo ? t("web.owners.now_active") : t("web.owners.now_inactive"));
      onChanged(atualizado);
    } catch (err) {
      notifyError(err);
    }
  };

  const confirmarApagar = () => {
    if (!owner) return;
    modals.openConfirmModal({
      title: t("web.owners.delete_title"),
      children: <Text size="sm">{t("web.owners.delete_confirm", { name: owner.nome })}</Text>,
      labels: { confirm: t("btn.delete"), cancel: t("web.common.cancel") },
      confirmProps: { color: "red" },
      onConfirm: async () => {
        try {
          await apagar.mutateAsync(owner.id);
          notifySuccess(t("web.owners.deleted"));
          onClose();
        } catch (err) {
          notifyError(err);
        }
      },
    });
  };

  return (
    <Drawer opened={owner !== null} onClose={onClose} position={isMobile ? "bottom" : "right"} size={isMobile ? "100%" : "md"} padding="lg" title={null} radius={isMobile ? "lg" : 0}>
      {owner && (
        <Stack gap="lg">
          <div>
            <Text size="xs" c="dimmed">
              #{owner.id}
            </Text>
            <Group gap="sm" align="center" wrap="nowrap">
              <Title order={3} style={{ wordBreak: "break-word" }}>
                {owner.nome}
              </Title>
              <StatusBadge ativo={owner.ativo} />
            </Group>
          </div>

          <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="md" verticalSpacing="md">
            <Campo label={t("label.full_name")} valor={owner.nome_completo} />
            <Campo label={t("label.nif")} valor={owner.nif} />
            <Campo label={t("label.email")} valor={owner.email} />
            <Campo label={t("label.phone")} valor={owner.telemovel} />
            <Campo label={t("label.address")} valor={owner.morada} />
            <Campo label={t("label.postal_code")} valor={owner.codigo_postal} />
            <Campo label={t("label.city")} valor={owner.cidade} />
          </SimpleGrid>

          <Divider />

          <Stack gap="xs">
            <Button size={isMobile ? "md" : "sm"} leftSection={<IconPencil size={16} />} onClick={() => onEdit(owner)}>
              {t("btn.edit")}
            </Button>
            <Button
              size={isMobile ? "md" : "sm"}
              variant="default"
              leftSection={ativo ? <IconPlayerPause size={16} /> : <IconPlayerPlay size={16} />}
              onClick={alternarEstado}
              loading={alternar.isPending}
            >
              {ativo ? t("web.owners.deactivate") : t("web.owners.activate")}
            </Button>
            <Button size={isMobile ? "md" : "sm"} variant="subtle" color="red" leftSection={<IconTrash size={16} />} onClick={confirmarApagar}>
              {t("btn.delete")}
            </Button>
          </Stack>
        </Stack>
      )}
    </Drawer>
  );
}
