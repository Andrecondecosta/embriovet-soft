import { Col, Form, Input, Modal, Row } from "antd";
import { Form as MForm, Input as MInput, TextArea } from "antd-mobile";

import type { Owner, OwnerInput } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { useIsMobile } from "../../components/responsive";
import { FolhaEcraInteiro, irParaErro } from "../../components/mobile";
import { useCreateOwner, useUpdateOwner } from "./api";

const CAMPOS: (keyof OwnerInput)[] = ["nome", "email", "telemovel", "nome_completo", "nif", "morada", "codigo_postal", "cidade"];

interface Props {
  opened: boolean;
  owner: Owner | null;
  onClose: () => void;
  onSaved?: (o: Owner) => void;
}

/** Guardar — partilhado pelo computador e pelo telemóvel. */
function useGuardarOwner({ owner, onClose, onSaved }: Props) {
  const t = useT();
  const notifyError = useNotifyError();
  const criar = useCreateOwner();
  const editar = useUpdateOwner();
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
  return { guardar, aGuardar: criar.isPending || editar.isPending };
}

const valoresIniciais = (owner: Owner | null) => Object.fromEntries(CAMPOS.map((k) => [k, owner?.[k] ?? ""]));

/** Criar (owner = null) ou editar um proprietário. O formulário só existe
 *  enquanto o modal está aberto, por isso começa sempre com os dados certos. */
export function OwnerFormModal(props: Props) {
  return useIsMobile() ? <OwnerFormMobile {...props} /> : <OwnerFormDesktop {...props} />;
}

function OwnerFormMobile(props: Props) {
  const t = useT();
  const { opened, owner, onClose } = props;
  const { guardar, aGuardar } = useGuardarOwner(props);
  const [form] = MForm.useForm<OwnerInput>();
  return (
    <FolhaEcraInteiro
      visible={opened}
      titulo={owner ? t("web.owners.edit") : t("web.owners.new")}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText={owner ? t("btn.save") : t("btn.add")}
      loading={aGuardar}
    >
      <MForm
        form={form}
        layout="horizontal"
        style={{ "--prefix-width": "7.5em" } as React.CSSProperties}
        onFinish={guardar}
        onFinishFailed={irParaErro}
        initialValues={valoresIniciais(owner)}
      >
        <MForm.Item name="nome" label={t("label.name")} rules={[{ required: true, whitespace: true, message: t("error.name_required") }]}>
          <MInput clearable />
        </MForm.Item>
        <MForm.Item name="nome_completo" label={t("label.full_name")}>
          <MInput clearable />
        </MForm.Item>
        <MForm.Item name="email" label={t("label.email")}>
          <MInput type="email" inputMode="email" autoComplete="email" clearable />
        </MForm.Item>
        <MForm.Item name="telemovel" label={t("label.phone")}>
          <MInput type="tel" inputMode="tel" autoComplete="tel" clearable />
        </MForm.Item>
        <MForm.Item name="nif" label={t("label.nif")}>
          <MInput inputMode="numeric" clearable />
        </MForm.Item>
        <MForm.Item name="morada" label={t("label.address")}>
          <TextArea autoSize={{ minRows: 1, maxRows: 4 }} />
        </MForm.Item>
        <MForm.Item name="codigo_postal" label={t("label.postal_code")}>
          <MInput clearable />
        </MForm.Item>
        <MForm.Item name="cidade" label={t("label.city")}>
          <MInput clearable />
        </MForm.Item>
      </MForm>
    </FolhaEcraInteiro>
  );
}

function OwnerFormDesktop(props: Props) {
  const t = useT();
  const { opened, owner, onClose } = props;
  const { guardar, aGuardar } = useGuardarOwner(props);
  const [form] = Form.useForm<OwnerInput>();

  return (
    <Modal
      open={opened}
      onCancel={onClose}
      title={owner ? t("web.owners.edit") : t("web.owners.new")}
      okText={owner ? t("btn.save_changes") : t("btn.add")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={aGuardar}
      width={640}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={guardar}
        onFinishFailed={irParaErro}
        preserve={false}
        initialValues={valoresIniciais(owner)}
      >
        <Row gutter={12}>
          <Col xs={24} sm={12}>
            <Form.Item
              name="nome"
              label={t("label.name")}
              rules={[{ required: true, whitespace: true, message: t("error.name_required") }]}
            >
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
