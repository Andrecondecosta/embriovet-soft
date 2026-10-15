import { Button, Descriptions, Drawer, Flex, Space, Typography } from "antd";
import { DeleteOutlined, EditOutlined, PauseCircleOutlined, PlayCircleOutlined } from "@ant-design/icons";

import type { Owner } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { confirmar, notifySuccess, useNotifyError } from "../../components/errors";
import { useIsMobile } from "../../components/responsive";
import { StatusPill } from "../../components/ds";
import { useDeleteOwner, useToggleOwner } from "./api";

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
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const alternar = useToggleOwner();
  const apagar = useDeleteOwner();
  const ativo = owner?.ativo !== false;
  const na = (v: string | null) => v || t("common.na");

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

  const confirmarApagar = () =>
    owner &&
    confirmar({
      titulo: t("web.owners.delete_title"),
      texto: t("web.owners.delete_confirm", { name: owner.nome }),
      ok: t("btn.delete"),
      cancelar: t("web.common.cancel"),
      perigo: true,
      onOk: async () => {
        try {
          await apagar.mutateAsync(owner.id);
          notifySuccess(t("web.owners.deleted"));
          onClose();
        } catch (err) {
          notifyError(err);
        }
      },
    });

  return (
    <Drawer
      open={owner !== null}
      onClose={onClose}
      placement={isMobile ? "bottom" : "right"}
      size={isMobile ? "85%" : 440}
      title={
        owner && (
          <Flex gap={8} align="center" wrap>
            <Typography.Text type="secondary">#{owner.id}</Typography.Text>
            <span>{owner.nome}</span>
            <StatusPill ativo={owner.ativo} />
          </Flex>
        )
      }
      footer={
        owner && (
          <Space wrap>
            <Button type="primary" icon={<EditOutlined />} onClick={() => onEdit(owner)}>
              {t("btn.edit")}
            </Button>
            <Button icon={ativo ? <PauseCircleOutlined /> : <PlayCircleOutlined />} onClick={alternarEstado} loading={alternar.isPending}>
              {ativo ? t("web.owners.deactivate") : t("web.owners.activate")}
            </Button>
            <Button danger type="text" icon={<DeleteOutlined />} onClick={confirmarApagar}>
              {t("btn.delete")}
            </Button>
          </Space>
        )
      }
    >
      {owner && (
        <Descriptions
          size="small"
          bordered
          column={1}
          items={[
            { label: t("label.full_name"), children: na(owner.nome_completo) },
            { label: t("label.nif"), children: na(owner.nif) },
            { label: t("label.email"), children: na(owner.email) },
            { label: t("label.phone"), children: na(owner.telemovel) },
            { label: t("label.address"), children: <span style={{ whiteSpace: "pre-wrap" }}>{na(owner.morada)}</span> },
            { label: t("label.postal_code"), children: na(owner.codigo_postal) },
            { label: t("label.city"), children: na(owner.cidade) },
          ]}
        />
      )}
    </Drawer>
  );
}
