import { useState, type FormEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  ActionIcon,
  Autocomplete,
  Button,
  Group,
  Input,
  Modal,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";

import type { Owner } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { OwnerFormModal } from "../owners/OwnerFormModal";
import { useEditarLote, useOpcoes, type Lote, type LoteCampos, type LoteEdicao } from "./api";

export const CANISTERS = Array.from({ length: 10 }, (_, i) => String(i + 1));

export function camposVazios(): LoteCampos {
  return {
    garanhao: "",
    dono_id: null,
    data_embriovet: "",
    origem_externa: "",
    qualidade: "",
    concentracao: 0,
    motilidade: 0,
    certificado: "Sim",
    dose: "",
    cor: "",
    contentor_id: null,
    canister: 1,
    andar: 1,
    observacoes: "",
  };
}

export function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <Stack gap="sm">
      <Title order={5} c="dimmed" tt="uppercase" fz="xs" style={{ letterSpacing: "0.04em" }}>
        {titulo}
      </Title>
      {children}
    </Stack>
  );
}

/** Garanhão: escolher da lista ou escrever um nome novo (o servidor cria-o
 *  em `animais`, sem duplicar "Falcao"/"Falcão"). */
export function GaranhaoInput({
  value,
  onChange,
  error,
  autoFocus,
}: {
  value: string;
  onChange: (v: string) => void;
  error?: string;
  autoFocus?: boolean;
}) {
  const t = useT();
  const garanhoes = useOpcoes("garanhoes");
  const nomes = (garanhoes.data ?? []).map((g) => g.nome);
  const nomeNovo =
    value.trim() && !nomes.some((n) => n.toLowerCase() === value.trim().toLowerCase()) ? value.trim() : null;
  return (
    <Autocomplete
      label={t("label.garanhao")}
      withAsterisk
      data={nomes}
      value={value}
      onChange={onChange}
      error={error}
      description={nomeNovo ? t("web.stock.add.new_stallion", { name: nomeNovo }) : t("web.stock.add.stallion_hint")}
      inputWrapperOrder={["label", "input", "description", "error"]}
      limit={50}
      maxDropdownHeight={280}
      autoFocus={autoFocus}
    />
  );
}

/** Seletor de proprietário com "+" para criar um novo sem sair do formulário. */
export function DonoSelect({
  value,
  onChange,
  apenasAtivos,
  label,
  error,
  description,
}: {
  value: number | null;
  onChange: (id: number | null) => void;
  apenasAtivos: boolean;
  label: string;
  error?: string | null;
  description?: string;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const donos = useOpcoes("proprietarios", apenasAtivos);
  const [novo, setNovo] = useState(false);
  return (
    <>
      <Group gap="xs" wrap="nowrap" align="flex-start">
        <Select
          label={label}
          withAsterisk
          data={(donos.data ?? []).map((d) => ({ value: String(d.id), label: d.nome }))}
          value={value !== null ? String(value) : null}
          onChange={(v) => onChange(v ? Number(v) : null)}
          searchable
          nothingFoundMessage={t("web.common.no_results")}
          error={error}
          description={description}
          inputWrapperOrder={["label", "input", "description", "error"]}
          style={{ flex: 1 }}
        />
        <Tooltip label={t("web.owners.new")}>
          <ActionIcon
            variant="default"
            size={36}
            onClick={() => setNovo(true)}
            aria-label={t("web.owners.new")}
            style={{ marginTop: 25 }}
          >
            <IconPlus size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
      <OwnerFormModal
        opened={novo}
        owner={null}
        onClose={() => setNovo(false)}
        onSaved={async (o: Owner) => {
          await queryClient.invalidateQueries({ queryKey: ["opcoes", "proprietarios"] });
          onChange(o.id);
        }}
      />
    </>
  );
}

/** Campos técnicos, de produção e de localização — comuns a "Adicionar
 *  lote" e "Editar lote" (mesmos campos que os dois formulários da app atual). */
export function CamposLote<T extends LoteCampos>({
  dados,
  set,
  producao,
  erros,
}: {
  dados: T;
  set: (patch: Partial<T>) => void;
  producao: ReactNode;
  erros: Partial<Record<keyof LoteCampos, string>>;
}) {
  const t = useT();
  const contentores = useOpcoes("contentores");
  const txt = (k: keyof LoteCampos) => ({
    value: (dados[k] as string) ?? "",
    onChange: (e: { currentTarget: { value: string } }) => set({ [k]: e.currentTarget.value } as Partial<T>),
  });

  return (
    <>
      <Secao titulo={t("add_stock.section.technical")}>
        <SimpleGrid cols={{ base: 2, sm: 4 }}>
          <NumberInput
            label={t("stock.motility_pct")}
            min={0}
            max={100}
            clampBehavior="strict"
            value={dados.motilidade}
            onChange={(v) => set({ motilidade: Number(v) || 0 } as Partial<T>)}
            inputMode="numeric"
          />
          <NumberInput
            label={t("stock.concentration")}
            min={0}
            value={dados.concentracao}
            onChange={(v) => set({ concentracao: Number(v) || 0 } as Partial<T>)}
            inputMode="numeric"
          />
          <TextInput label={t("stock.quality_text")} {...txt("qualidade")} />
          <TextInput label={t("stock.color")} {...txt("cor")} />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, xs: 2 }}>
          <Input.Wrapper label={t("stock.certificate")}>
            <SegmentedControl
              fullWidth
              data={[
                { value: "Sim", label: t("common.yes") },
                { value: "Não", label: t("common.no") },
              ]}
              value={dados.certificado}
              onChange={(v) => set({ certificado: v as "Sim" | "Não" } as Partial<T>)}
            />
          </Input.Wrapper>
          <TextInput label={t("stock.dose")} {...txt("dose")} />
        </SimpleGrid>
      </Secao>

      <Secao titulo={t("add_stock.section.production")}>{producao}</Secao>

      <Secao titulo={t("web.stock.add.location")}>
        {contentores.data && contentores.data.length === 0 ? (
          <Text c="red" size="sm">
            {t("add_stock.no_containers")}
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, xs: 3 }}>
            <Select
              label={t("label.container")}
              withAsterisk
              data={(contentores.data ?? []).map((c) => ({ value: String(c.id), label: c.nome }))}
              value={dados.contentor_id !== null ? String(dados.contentor_id) : null}
              onChange={(v) => set({ contentor_id: v ? Number(v) : null } as Partial<T>)}
              searchable
              error={erros.contentor_id}
            />
            <Select
              label={t("label.canister")}
              withAsterisk
              data={CANISTERS}
              value={String(dados.canister)}
              onChange={(v) => v && set({ canister: Number(v) } as Partial<T>)}
              allowDeselect={false}
            />
            <Input.Wrapper label={t("label.floor_required").replace(" *", "")} withAsterisk>
              <SegmentedControl
                fullWidth
                data={[
                  { value: "1", label: t("web.stock.floor", { n: 1 }) },
                  { value: "2", label: t("web.stock.floor", { n: 2 }) },
                ]}
                value={String(dados.andar)}
                onChange={(v) => set({ andar: Number(v) as 1 | 2 } as Partial<T>)}
              />
            </Input.Wrapper>
          </SimpleGrid>
        )}
      </Secao>

      <Secao titulo={t("label.notes")}>
        <Textarea autosize minRows={2} {...txt("observacoes")} aria-label={t("label.notes")} />
      </Secao>
    </>
  );
}

/** Editar lote (só Administrador). */
export function LoteFormModal({ opened, lote, onClose }: { opened: boolean; lote: Lote; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  return (
    <Modal opened={opened} onClose={onClose} title={t("stock.edit_title")} size="xl" radius="lg" fullScreen={isMobile}>
      <EditarLoteForm lote={lote} onClose={onClose} />
    </Modal>
  );
}

function EditarLoteForm({ lote, onClose }: { lote: Lote; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const editar = useEditarLote();
  const [, setParams] = useSearchParams();
  const [dados, setDados] = useState<LoteEdicao>(() => ({
    ...camposVazios(),
    garanhao: lote.garanhao_nome ?? "",
    dono_id: lote.dono_id,
    data_embriovet: lote.data_embriovet ?? "",
    origem_externa: lote.origem_externa ?? "",
    qualidade: lote.qualidade ?? "",
    concentracao: lote.concentracao ?? 0,
    motilidade: lote.motilidade ?? 0,
    certificado: lote.certificado === "Sim" ? "Sim" : "Não",
    dose: lote.dose ?? "",
    cor: lote.cor ?? "",
    contentor_id: lote.contentor_id,
    canister: lote.canister ?? 1,
    andar: lote.andar === 2 ? 2 : 1,
    observacoes: lote.observacoes ?? "",
    palhetas_produzidas: lote.palhetas_produzidas ?? 0,
    existencia_atual: lote.existencia_atual ?? 0,
  }));
  const [erros, setErros] = useState<Partial<Record<keyof LoteCampos, string>>>({});
  const set = (patch: Partial<LoteEdicao>) => {
    setDados((d) => ({ ...d, ...patch }));
    setErros((e) => Object.fromEntries(Object.entries(e).filter(([k]) => !(k in patch))));
  };

  const submeter = async (e: FormEvent) => {
    e.preventDefault();
    const novos: typeof erros = {};
    if (!dados.garanhao.trim()) novos.garanhao = t("error.stallion_required");
    if (!dados.dono_id) novos.dono_id = t("web.stock.error.owner_required");
    if (!dados.contentor_id) novos.contentor_id = t("error.container_required");
    setErros(novos);
    if (Object.keys(novos).length) return;
    try {
      const atualizado = await editar.mutateAsync({ id: lote.id, ...dados });
      notifySuccess(t("web.stock.updated"));
      onClose();
      // Mudou de garanhão: a lista passa para o garanhão novo, com o lote aberto.
      if (atualizado.garanhao_nome !== lote.garanhao_nome) {
        setParams(
          (p) => {
            const r = new URLSearchParams(p);
            r.set("garanhao", atualizado.garanhao_nome);
            r.set("lote", String(lote.id));
            r.delete("dono");
            return r;
          },
          { replace: true },
        );
      }
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <form onSubmit={submeter}>
      <Stack gap="lg">
        <Secao titulo={t("web.stock.add.identification")}>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <GaranhaoInput value={dados.garanhao} onChange={(v) => set({ garanhao: v })} error={erros.garanhao} />
            <DonoSelect
              label={t("label.owner")}
              apenasAtivos
              value={dados.dono_id}
              onChange={(id) => set({ dono_id: id })}
              error={erros.dono_id}
              description={t("web.stock.edit_owner_only_active")}
            />
          </SimpleGrid>
        </Secao>
        <CamposLote
          dados={dados}
          set={set}
          erros={erros}
          producao={
            <SimpleGrid cols={{ base: 2, sm: 4 }}>
              <TextInput label={t("stock.prod_date")} value={dados.data_embriovet} onChange={(e) => set({ data_embriovet: e.currentTarget.value })} />
              <TextInput label={t("stock.external_origin")} value={dados.origem_externa} onChange={(e) => set({ origem_externa: e.currentTarget.value })} />
              <NumberInput
                label={t("stock.straws_produced")}
                min={0}
                value={dados.palhetas_produzidas}
                onChange={(v) => set({ palhetas_produzidas: Number(v) || 0 })}
                inputMode="numeric"
              />
              <NumberInput
                label={t("stock.current_stock")}
                min={0}
                value={dados.existencia_atual}
                onChange={(v) => set({ existencia_atual: Number(v) || 0 })}
                inputMode="numeric"
              />
            </SimpleGrid>
          }
        />
        <BotoesForm isMobile={isMobile} onCancel={onClose} loading={editar.isPending} label={t("btn.save_changes")} />
      </Stack>
    </form>
  );
}

export function BotoesForm({
  isMobile,
  onCancel,
  loading,
  label,
}: {
  isMobile: boolean;
  onCancel: () => void;
  loading: boolean;
  label: string;
}) {
  const t = useT();
  return (
    <Group
      justify="flex-end"
      grow={isMobile}
      style={
        isMobile
          ? {
              position: "sticky",
              bottom: 0,
              background: "var(--mantine-color-body)",
              padding: "12px 0 calc(12px + env(safe-area-inset-bottom))",
              borderTop: "1px solid var(--mantine-color-gray-2)",
              zIndex: 2,
            }
          : undefined
      }
    >
      <Button variant="default" onClick={onCancel}>
        {t("web.common.cancel")}
      </Button>
      <Button type="submit" loading={loading}>
        {label}
      </Button>
    </Group>
  );
}

