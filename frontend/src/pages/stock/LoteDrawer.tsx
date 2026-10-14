import { useState } from "react";
import {
  Accordion,
  Alert,
  Button,
  Checkbox,
  Divider,
  Drawer,
  Group,
  Modal,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconPencil, IconTrash } from "@tabler/icons-react";

import { useT } from "../../i18n/I18n";
import { useIsAdmin } from "../../components/User";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { dataHora } from "../../components/csv";
import { referencia, useApagarLote, type Ligacoes, type Lote, type TransfExterna, type TransfInterna } from "./api";
import { HistoricoTransferencias } from "./LotesTab";
import { LoteFormModal } from "./LoteForm";
import { Pill } from "../../components/ds";

function Campo({ label, valor }: { label: string; valor: string | number | null | undefined }) {
  const t = useT();
  return (
    <div>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {valor === null || valor === undefined || valor === "" ? t("common.na") : valor}
      </Text>
    </div>
  );
}

export function LoteDrawer({
  lote,
  ligacoes,
  internas,
  externas,
  onClose,
}: {
  lote: Lote | null;
  ligacoes: Ligacoes | undefined;
  internas: TransfInterna[];
  externas: TransfExterna[];
  onClose: () => void;
}) {
  const t = useT();
  const isAdmin = useIsAdmin();
  const isMobile = useIsMobile();
  const [editar, setEditar] = useState(false);
  const [apagar, setApagar] = useState(false);

  // Histórico deste lote: transferências do garanhão em que o dono do
  // lote foi origem ou destino (`filter_lot_transfer_history`).
  const dono = lote?.dono_id ?? null;
  const internasLote = internas.filter((x) => x.origem_id === dono || x.destino_id === dono);
  const externasLote = externas.filter((x) => x.origem_id === dono);

  const local = lote?.contentor_codigo
    ? `${lote.contentor_codigo} · ${t("label.canister")} ${lote.canister ?? "—"} · ${lote.andar ?? "—"}º`
    : lote?.local_armazenagem || null;

  const certificado = lote?.certificado === "Sim" ? t("common.yes") : lote?.certificado === "Não" ? t("common.no") : lote?.certificado;

  return (
    <>
      <Drawer
        opened={lote !== null}
        onClose={onClose}
        position={isMobile ? "bottom" : "right"}
        size={isMobile ? "100%" : "lg"}
        padding="lg"
        title={null}
      >
        {lote && (
          <Stack gap="lg">
            <div>
              <Text size="xs" c="dimmed">
                {lote.garanhao_nome} · #{lote.id}
              </Text>
              <Group gap="sm" wrap="nowrap" align="center">
                <Title order={3} style={{ wordBreak: "break-word" }}>
                  {referencia(lote) ?? t("common.no_reference")}
                </Title>
                <Pill nivel="aviso">{t("web.stock.straws_count", { count: lote.existencia_atual ?? 0 })}</Pill>
              </Group>
              <Text size="sm">{lote.proprietario_nome ?? t("common.no_owner")}</Text>
            </div>

            <SimpleGrid cols={{ base: 2 }} spacing="md" verticalSpacing="md">
              <Campo label={t("label.location")} valor={local} />
              <Campo label={t("stock.certificate_label")} valor={certificado} />
              <Campo label={t("stock.quality_label")} valor={lote.qualidade} />
              <Campo label={t("stock.color")} valor={lote.cor} />
              <Campo label={t("stock.concentration_label")} valor={`${lote.concentracao ?? 0} ${t("stock.million_ml")}`} />
              <Campo label={t("stock.motility_label")} valor={`${lote.motilidade ?? 0}%`} />
              <Campo label={t("stock.dose_label")} valor={lote.dose} />
              <Campo label={t("stock.straws_produced_label")} valor={lote.palhetas_produzidas} />
              <Campo label={t("stock.prod_date_label")} valor={lote.data_embriovet} />
              <Campo label={t("stock.external_origin_label")} valor={lote.origem_externa} />
            </SimpleGrid>
            {lote.observacoes && <Campo label={t("label.notes")} valor={lote.observacoes} />}

            <Group gap="lg">
              {lote.data_criacao && (
                <Text size="xs" c="dimmed">
                  {t("stock.created_at_label")}: {dataHora(lote.data_criacao)}
                </Text>
              )}
              {lote.criado_por && (
                <Text size="xs" c="dimmed">
                  {t("stock.created_by_label")}: {lote.criado_por}
                </Text>
              )}
            </Group>

            <Accordion variant="contained" radius="md">
              <Accordion.Item value="hist">
                <Accordion.Control>{t("stock.lot_history")}</Accordion.Control>
                <Accordion.Panel>
                  {internasLote.length || externasLote.length ? (
                    <HistoricoTransferencias garanhao={lote.garanhao_nome} internas={internasLote} externas={externasLote} />
                  ) : (
                    <Text size="sm" c="dimmed">
                      {t("stock.no_transfer_history_lot")}
                    </Text>
                  )}
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>

            {/* Editar/Eliminar só para Administrador, como na app atual. */}
            {isAdmin && (
              <>
                <Divider />
                <Stack gap="xs">
                  <Button size={isMobile ? "md" : "sm"} leftSection={<IconPencil size={16} />} onClick={() => setEditar(true)}>
                    {t("btn.edit")}
                  </Button>
                  <Button
                    size={isMobile ? "md" : "sm"}
                    variant="subtle"
                    color="red"
                    leftSection={<IconTrash size={16} />}
                    onClick={() => setApagar(true)}
                  >
                    {t("stock.tab.delete")}
                  </Button>
                </Stack>
              </>
            )}
          </Stack>
        )}
      </Drawer>

      {lote && isAdmin && (
        <>
          <LoteFormModal opened={editar} lote={lote} onClose={() => setEditar(false)} />
          <ApagarLoteModal
            opened={apagar}
            lote={lote}
            ligacoes={ligacoes}
            onClose={() => setApagar(false)}
            onDeleted={() => {
              setApagar(false);
              onClose();
            }}
          />
        </>
      )}
    </>
  );
}

function ApagarLoteModal({
  opened,
  lote,
  ligacoes,
  onClose,
  onDeleted,
}: {
  opened: boolean;
  lote: Lote;
  ligacoes: Ligacoes | undefined;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const t = useT();
  const notifyError = useNotifyError();
  const apagar = useApagarLote();
  const [confirmo, setConfirmo] = useState(false);

  const temLigacoes = !!ligacoes && Object.values(ligacoes).some((n) => n);

  const confirmar = async () => {
    try {
      await apagar.mutateAsync(lote.id);
      notifySuccess(t("web.stock.deleted"));
      onDeleted();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={t("stock.delete_title")}
      radius="lg"
      onExitTransitionEnd={() => setConfirmo(false)}
    >
      <Stack>
        <Alert color="red" variant="light">
          {t("stock.delete_warning", { ref: referencia(lote) ?? t("common.no_reference"), qtd: lote.existencia_atual ?? 0 })}
        </Alert>
        {temLigacoes ? (
          <Alert color="yellow" variant="light">
            {t("stock.delete_links", {
              insem: ligacoes?.inseminacoes ?? 0,
              transf: ligacoes?.transferencias ?? 0,
              ext: ligacoes?.transferencias_externas ?? 0,
            })}
          </Alert>
        ) : (
          <Text size="sm" c="dimmed">
            {t("stock.delete_no_links")}
          </Text>
        )}
        <Checkbox label={t("stock.delete_confirm")} checked={confirmo} onChange={(e) => setConfirmo(e.currentTarget.checked)} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t("web.common.cancel")}
          </Button>
          <Button color="red" disabled={!confirmo} loading={apagar.isPending} onClick={confirmar}>
            {t("stock.delete_btn")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
