import { useState, type FormEvent } from "react";
import { Button, Group, Modal, SimpleGrid, Stack, TextInput, Textarea } from "@mantine/core";

import type { Owner, OwnerInput } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { useCreateOwner, useUpdateOwner } from "./api";
import { useIsMobile } from "../../components/responsive";

const VAZIO: OwnerInput = {
  nome: "",
  email: "",
  telemovel: "",
  nome_completo: "",
  nif: "",
  morada: "",
  codigo_postal: "",
  cidade: "",
};

function paraForm(o: Owner | null): OwnerInput {
  if (!o) return VAZIO;
  const r = { ...VAZIO };
  for (const k of Object.keys(VAZIO) as (keyof OwnerInput)[]) r[k] = o[k] ?? "";
  return r;
}

/** Criar (owner = null) ou editar um proprietário. O formulário só existe
 *  enquanto o modal está aberto, por isso começa sempre com os dados certos. */
export function OwnerFormModal({
  opened,
  owner,
  onClose,
  onSaved,
}: {
  opened: boolean;
  owner: Owner | null;
  onClose: () => void;
  onSaved?: (o: Owner) => void;
}) {
  const t = useT();
  const isMobile = useIsMobile();
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={owner ? t("web.owners.edit") : t("web.owners.new")}
      size="lg"
      radius="lg"
      fullScreen={isMobile}
    >
      <OwnerForm owner={owner} onClose={onClose} onSaved={onSaved} />
    </Modal>
  );
}

function OwnerForm({
  owner,
  onClose,
  onSaved,
}: {
  owner: Owner | null;
  onClose: () => void;
  onSaved?: (o: Owner) => void;
}) {
  const t = useT();
  const notifyError = useNotifyError();
  const criar = useCreateOwner();
  const editar = useUpdateOwner();
  const [dados, setDados] = useState<OwnerInput>(() => paraForm(owner));
  const [erroNome, setErroNome] = useState<string | null>(null);
  const isMobile = useIsMobile();
  const campo = (k: keyof OwnerInput) => ({
    value: dados[k] ?? "",
    onChange: (e: { currentTarget: { value: string } }) => {
      const v = e.currentTarget.value;
      setDados((d) => ({ ...d, [k]: v }));
    },
  });

  const submeter = async (e: FormEvent) => {
    e.preventDefault();
    if (!dados.nome?.trim()) {
      setErroNome(t("error.name_required"));
      return;
    }
    try {
      const guardado = owner ? await editar.mutateAsync({ id: owner.id, ...dados }) : await criar.mutateAsync(dados);
      notifySuccess(owner ? t("web.owners.updated") : t("web.owners.added", { name: (guardado as Owner).nome }));
      onSaved?.(guardado as Owner);
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
      <form onSubmit={submeter}>
        <Stack>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput label={t("label.name")} withAsterisk data-autofocus error={erroNome} {...campo("nome")} />
            <TextInput label={t("label.full_name")} {...campo("nome_completo")} />
            <TextInput label={t("label.email")} type="email" inputMode="email" autoComplete="email" {...campo("email")} />
            <TextInput label={t("label.phone")} type="tel" inputMode="tel" autoComplete="tel" {...campo("telemovel")} />
            <TextInput label={t("label.nif")} inputMode="numeric" {...campo("nif")} />
            <TextInput label={t("label.city")} {...campo("cidade")} />
            <Textarea label={t("label.address")} autosize minRows={2} {...campo("morada")} />
            <TextInput label={t("label.postal_code")} {...campo("codigo_postal")} />
          </SimpleGrid>
          {/* No telemóvel os botões ficam presos ao fundo do ecrã,
              sempre visíveis enquanto se preenche o formulário. */}
          <Group
            justify="flex-end"
            mt="sm"
            grow={isMobile}
            style={
              isMobile
                ? {
                    position: "sticky",
                    bottom: 0,
                    background: "var(--mantine-color-body)",
                    padding: "12px 0 calc(12px + env(safe-area-inset-bottom))",
                    borderTop: "1px solid var(--mantine-color-gray-2)",
                    zIndex: 1,
                  }
                : undefined
            }
          >
            <Button variant="default" onClick={onClose}>
              {t("web.common.cancel")}
            </Button>
            <Button type="submit" loading={criar.isPending || editar.isPending}>
              {owner ? t("btn.save_changes") : t("btn.add")}
            </Button>
          </Group>
        </Stack>
      </form>
  );
}
