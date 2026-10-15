import { useState } from "react";
import { Alert, Button, Checkbox, Collapse, Descriptions, Drawer, Flex, Modal, Space, Tag, Typography } from "antd";
import { DeleteOutlined, EditOutlined } from "@ant-design/icons";

import { useT } from "../../i18n/I18n";
import { useIsAdmin } from "../../components/User";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { dataHora } from "../../components/csv";
import { referencia, useApagarLote, type Ligacoes, type Lote, type TransfExterna, type TransfInterna } from "./api";
import { HistoricoTransferencias } from "./LotesTab";
import { LoteFormModal } from "./LoteForm";

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

  const na = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? t("common.na") : v);
  const local = lote?.contentor_codigo
    ? `${lote.contentor_codigo} · ${t("label.canister")} ${lote.canister ?? "—"} · ${lote.andar ?? "—"}º`
    : lote?.local_armazenagem || null;
  const certificado = lote?.certificado === "Sim" ? t("common.yes") : lote?.certificado === "Não" ? t("common.no") : lote?.certificado;

  return (
    <>
      <Drawer
        open={lote !== null}
        onClose={onClose}
        placement={isMobile ? "bottom" : "right"}
        size={isMobile ? "90%" : 520}
        title={
          lote && (
            <Flex gap={8} align="center" wrap>
              <span>{referencia(lote) ?? t("common.no_reference")}</span>
              <Tag color="red" style={{ marginInlineEnd: 0 }}>
                {t("web.stock.straws_count", { count: lote.existencia_atual ?? 0 })}
              </Tag>
            </Flex>
          )
        }
        footer={
          lote &&
          isAdmin && (
            // Editar/Eliminar só para Administrador, como na app atual.
            <Space>
              <Button type="primary" icon={<EditOutlined />} onClick={() => setEditar(true)}>
                {t("btn.edit")}
              </Button>
              <Button danger type="text" icon={<DeleteOutlined />} onClick={() => setApagar(true)}>
                {t("stock.tab.delete")}
              </Button>
            </Space>
          )
        }
      >
        {lote && (
          <Space orientation="vertical" size={12} style={{ width: "100%" }}>
            <Typography.Text type="secondary">
              {lote.garanhao_nome} · #{lote.id}
            </Typography.Text>
            <Descriptions
              size="small"
              bordered
              column={1}
              items={[
                { label: t("label.owner"), children: lote.proprietario_nome ?? t("common.no_owner") },
                { label: t("label.location"), children: na(local) },
                { label: t("stock.certificate_label"), children: na(certificado) },
                { label: t("stock.quality_label"), children: na(lote.qualidade) },
                { label: t("stock.color"), children: na(lote.cor) },
                { label: t("stock.concentration_label"), children: `${lote.concentracao ?? 0} ${t("stock.million_ml")}` },
                { label: t("stock.motility_label"), children: `${lote.motilidade ?? 0}%` },
                { label: t("stock.dose_label"), children: na(lote.dose) },
                { label: t("stock.straws_produced_label"), children: na(lote.palhetas_produzidas) },
                { label: t("stock.prod_date_label"), children: na(lote.data_embriovet) },
                { label: t("stock.external_origin_label"), children: na(lote.origem_externa) },
                ...(lote.observacoes
                  ? [{ label: t("label.notes"), children: <span style={{ whiteSpace: "pre-wrap" }}>{lote.observacoes}</span> }]
                  : []),
                { label: t("stock.created_at_label"), children: dataHora(lote.data_criacao) },
                { label: t("stock.created_by_label"), children: na(lote.criado_por) },
              ]}
            />
            <Collapse
              size="small"
              items={[
                {
                  key: "hist",
                  label: t("stock.lot_history"),
                  children:
                    internasLote.length || externasLote.length ? (
                      <HistoricoTransferencias garanhao={lote.garanhao_nome} internas={internasLote} externas={externasLote} />
                    ) : (
                      <Typography.Text type="secondary">{t("stock.no_transfer_history_lot")}</Typography.Text>
                    ),
                },
              ]}
            />
          </Space>
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

export function ApagarLoteModal({
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
      open={opened}
      onCancel={onClose}
      title={t("stock.delete_title")}
      okText={t("stock.delete_btn")}
      cancelText={t("web.common.cancel")}
      okButtonProps={{ danger: true, disabled: !confirmo }}
      confirmLoading={apagar.isPending}
      onOk={confirmar}
      afterClose={() => setConfirmo(false)}
    >
      <Space orientation="vertical" size={12} style={{ width: "100%" }}>
        <Alert
          type="error"
          showIcon
          title={t("stock.delete_warning", { ref: referencia(lote) ?? t("common.no_reference"), qtd: lote.existencia_atual ?? 0 })}
        />
        {temLigacoes ? (
          <Alert
            type="warning"
            showIcon
            title={t("stock.delete_links", {
              insem: ligacoes?.inseminacoes ?? 0,
              transf: ligacoes?.transferencias ?? 0,
              ext: ligacoes?.transferencias_externas ?? 0,
            })}
          />
        ) : (
          <Typography.Text type="secondary">{t("stock.delete_no_links")}</Typography.Text>
        )}
        <Checkbox checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)}>
          {t("stock.delete_confirm")}
        </Checkbox>
      </Space>
    </Modal>
  );
}
