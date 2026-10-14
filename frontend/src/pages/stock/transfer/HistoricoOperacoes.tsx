import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ActionIcon,
  Alert,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Paper,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";

import { useT } from "../../../i18n/I18n";
import { useIsMobile } from "../../../components/responsive";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../../components/errors";
import { useAnular, useHistorico, type OpHistorico } from "./api";
import { ZoneTitle } from "../../../components/ds";

const hojeIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

function somarDias(iso: string, n: number) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

const hora = (iso: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" }) : "—";

/** Histórico de operações do dia (transferências e inseminações), com
 *  Editar (só transferências — as inseminações editam-se na sua página)
 *  e Anular. Igual a `_render_historico_operacoes` da app atual. */
export function HistoricoOperacoes({ onEditar }: { onEditar: (op: OpHistorico) => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const [params, setParams] = useSearchParams();
  const dia = /^\d{4}-\d{2}-\d{2}$/.test(params.get("dia") ?? "") ? params.get("dia")! : hojeIso();
  const ehHoje = dia === hojeIso();
  const { data, isPending, isError, error } = useHistorico(dia);
  const [anular, setAnular] = useState<OpHistorico | null>(null);

  const irPara = (d: string) =>
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        if (d === hojeIso()) r.delete("dia");
        else r.set("dia", d);
        return r;
      },
      { replace: true },
    );

  return (
    <Paper withBorder radius="lg" p={{ base: "md", sm: "lg" }}>
      <Stack gap="sm">
        <ZoneTitle primeiro>{t("web.transfer.history")}</ZoneTitle>

        <Group gap="xs" wrap="nowrap">
          <ActionIcon variant="default" size={36} onClick={() => irPara(somarDias(dia, -1))} aria-label="◀">
            <IconChevronLeft size={18} />
          </ActionIcon>
          <TextInput
            type="date"
            value={dia}
            onChange={(e) => e.currentTarget.value && irPara(e.currentTarget.value)}
            style={{ flex: isMobile ? 1 : undefined }}
            w={isMobile ? undefined : 170}
            aria-label={t("label.date")}
          />
          <ActionIcon variant="default" size={36} onClick={() => irPara(somarDias(dia, 1))} aria-label="▶">
            <IconChevronRight size={18} />
          </ActionIcon>
          {!ehHoje && (
            <Button variant="subtle" onClick={() => irPara(hojeIso())}>
              {t("web.transfer.today")}
            </Button>
          )}
        </Group>

        {isError ? (
          <Alert color="red">{errorMessage(error)}</Alert>
        ) : isPending ? (
          <Center py="md">
            <Loader size="sm" />
          </Center>
        ) : !data.length ? (
          <Text size="sm" c="dimmed">
            {t("web.transfer.history.empty")}
          </Text>
        ) : (
          <Stack gap={0} mah={460} style={{ overflowY: "auto" }}>
            {data.map((op, i) => (
              <Group
                key={`${op.tipo}-${op.operation_id ?? op.action_id}`}
                wrap={isMobile ? "wrap" : "nowrap"}
                gap="xs"
                py={8}
                px="xs"
                bg={i % 2 ? "gray.0" : undefined}
                style={{ borderRadius: 6 }}
              >
                <div style={{ flex: 1, minWidth: isMobile ? "100%" : 0 }}>
                  <Text size="sm" truncate={!isMobile}>
                    <b>{hora(op.ts)}</b> · <Text span c="dimmed">{op.acao}</Text> — {op.detalhe}
                  </Text>
                </div>
                {op.tipo !== "insemination" && (
                  <Button size="compact-sm" variant="subtle" onClick={() => onEditar(op)}>
                    {t("btn.edit")}
                  </Button>
                )}
                <Button size="compact-sm" variant="default" onClick={() => setAnular(op)}>
                  {t("web.transfer.undo")}
                </Button>
              </Group>
            ))}
          </Stack>
        )}
      </Stack>

      <AnularModal op={anular} onClose={() => setAnular(null)} />
    </Paper>
  );
}

function AnularModal({ op, onClose }: { op: OpHistorico | null; onClose: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const anular = useAnular();

  const confirmar = async () => {
    if (!op) return;
    try {
      await anular.mutateAsync({ tipo: op.tipo, action_id: op.action_id, operation_id: op.operation_id });
      notifySuccess(t("web.transfer.undo.done"));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Modal opened={op !== null} onClose={onClose} title={t("web.transfer.undo.title")} radius="lg">
      {op && (
        <Stack>
          <Text size="sm">
            {op.acao} — {op.detalhe}
          </Text>
          <Alert color="red" variant="light">
            {t("web.transfer.undo.confirm", { qty: op.quantidade })}{" "}
            {op.num_lotes > 1 && t("web.transfer.undo.multi", { n: op.num_lotes })}{" "}
            <b>{t("web.transfer.undo.irreversible")}</b>
          </Alert>
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t("web.common.cancel")}
            </Button>
            <Button color="red" onClick={confirmar} loading={anular.isPending}>
              {t("web.transfer.undo.confirm_btn")}
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
