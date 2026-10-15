import { Col, Form, Input, Modal, Row } from "antd";

import type { Owner, OwnerInput } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { useIsMobile } from "../../components/responsive";
import { useCreateOwner, useUpdateOwner } from "./api";

const CAMPOS: (keyof OwnerInput)[] = ["nome", "email", "telemovel", "nome_completo", "nif", "morada", "codigo_postal", "cidade"];

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
  const notifyError = useNotifyError();
  const criar = useCreateOwner();
  const editar = useUpdateOwner();
  const [form] = Form.useForm<OwnerInput>();

  const guardar = async (dados: OwnerInput) => {
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
    <Modal
      open={opened}
      onCancel={onClose}
      title={owner ? t("web.owners.edit") : t("web.owners.new")}
      okText={owner ? t("btn.save_changes") : t("btn.add")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={criar.isPending || editar.isPending}
      width={isMobile ? "100%" : 640}
      style={isMobile ? { top: 0, maxWidth: "100%", margin: 0, paddingBottom: 0 } : undefined}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={guardar}
        preserve={false}
        initialValues={Object.fromEntries(CAMPOS.map((k) => [k, owner?.[k] ?? ""]))}
      >
        <Row gutter={12}>
          <Col xs={24} sm={12}>
            <Form.Item name="nome" label={t("label.name")} rules={[{ required: true, whitespace: true, message: t("error.name_required") }]}>
              <Input autoFocus />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="nome_completo" label={t("label.full_name")}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="email" label={t("label.email")}>
              <Input type="email" inputMode="email" autoComplete="email" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="telemovel" label={t("label.phone")}>
              <Input type="tel" inputMode="tel" autoComplete="tel" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="nif" label={t("label.nif")}>
              <Input inputMode="numeric" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="cidade" label={t("label.city")}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="morada" label={t("label.address")}>
              <Input.TextArea autoSize={{ minRows: 2 }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="codigo_postal" label={t("label.postal_code")}>
              <Input />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Modal>
  );
}
