import { useState } from "react";
import { Alert, Button, Col, Flex, Form, Input, InputNumber, Modal, Row, Segmented, Table, Tag, Typography } from "antd";
import { EditOutlined, PlusOutlined } from "@ant-design/icons";
import {
  DotLoading,
  ErrorBlock,
  FloatingBubble,
  Form as MForm,
  Input as MInput,
  List,
  Selector,
  SwipeAction,
  Tag as MTag,
} from "antd-mobile";
import { AddOutline } from "antd-mobile-icons";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../components/errors";
import { FolhaEcraInteiro, NumeroCampo, irParaErro } from "../../components/mobile";
import {
  TIPOS_ALOJAMENTO,
  useAlojamentos,
  useAlternarAlojamento,
  useCriarAlojamento,
  useEditarAlojamento,
  type Alojamento,
  type AlojamentoIn,
} from "./api";

/** Estado do formulário: fechado, novo (null) ou a editar um alojamento. */
type Aberto = { aloj: Alojamento | null } | null;

const VAZIO: AlojamentoIn = { nome: "", tipo: "box", capacidade: 1, observacoes: "" };

/** Criar/editar e ativar/desativar — comum ao computador e ao telemóvel. */
function useAcoesAlojamento(fechar: () => void) {
  const t = useT();
  const notifyError = useNotifyError();
  const criar = useCriarAlojamento();
  const editar = useEditarAlojamento();
  const alternar = useAlternarAlojamento();
  const guardar = async (aloj: Alojamento | null, d: AlojamentoIn) => {
    try {
      if (aloj) await editar.mutateAsync({ id: aloj.id, ...d });
      else await criar.mutateAsync(d);
      notifySuccess(aloj ? t("web.housing.updated") : t("web.housing.created"));
      fechar();
    } catch (err) {
      notifyError(err);
    }
  };
  const fazerAlternar = async (a: Alojamento) => {
    try {
      await alternar.mutateAsync(a.id);
    } catch (err) {
      notifyError(err);
    }
  };
  return { guardar, aGuardar: criar.isPending || editar.isPending, fazerAlternar };
}

export function AlojamentosTab() {
  return useIsMobile() ? <AlojamentosMobile /> : <AlojamentosDesktop />;
}

function AlojamentosDesktop() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const { data, isPending, isError, error } = useAlojamentos();
  const [aberto, setAberto] = useState<Aberto>(null);
  const { guardar, aGuardar, fazerAlternar } = useAcoesAlojamento(() => setAberto(null));

  if (isError) return <Alert type="error" showIcon title={errorMessage(error)} />;

  return (
    <>
      <Flex justify="space-between" align="center" style={{ marginBottom: 12 }}>
        <Typography.Text type="secondary">{t("web.housing.help")}</Typography.Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setAberto({ aloj: null })}>
          {t("web.housing.new")}
        </Button>
      </Flex>
      <Table<Alojamento>
        size="small"
        bordered
        rowKey="id"
        loading={isPending}
        dataSource={data ?? []}
        pagination={false}
        locale={{ emptyText: t("web.housing.empty") }}
        columns={[
          {
            title: t("web.housing.name"),
            dataIndex: "nome",
            render: (v, a) => (
              <>
                <Typography.Text strong>{v}</Typography.Text>
                {a.observacoes && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {a.observacoes}
                    </Typography.Text>
                  </div>
                )}
              </>
            ),
          },
          { title: t("web.housing.type"), dataIndex: "tipo", width: 120, render: (v) => t(`web.housing.type.${v}`) },
          { title: t("web.housing.capacity"), dataIndex: "capacidade", width: 110, align: "right" },
          {
            title: t("web.common.status"),
            dataIndex: "ativo",
            width: 110,
            render: (v) => <Tag color={v ? "success" : "default"}>{v ? t("web.common.active") : t("web.common.inactive")}</Tag>,
          },
          {
            key: "acoes",
            width: 200,
            align: "right",
            render: (_, a) => (
              <Flex gap={4} justify="flex-end">
                <Button size="small" type="link" icon={<EditOutlined />} onClick={() => setAberto({ aloj: a })}>
                  {t("btn.edit")}
                </Button>
                <Button size="small" onClick={() => fazerAlternar(a)}>
                  {a.ativo ? t("web.common.deactivate") : t("web.common.activate")}
                </Button>
              </Flex>
            ),
          },
        ]}
      />
      <AlojamentoModal aberto={aberto} onClose={() => setAberto(null)} onGuardar={guardar} aGuardar={aGuardar} />
    </>
  );
}

function AlojamentoModal({
  aberto,
  onClose,
  onGuardar,
  aGuardar,
}: {
  aberto: Aberto;
  onClose: () => void;
  onGuardar: (a: Alojamento | null, d: AlojamentoIn) => void;
  aGuardar: boolean;
}) {
  const t = useT();
  const [form] = Form.useForm<AlojamentoIn>();
  const aloj = aberto?.aloj ?? null;
  return (
    <Modal
      open={aberto !== null}
      onCancel={onClose}
      title={aloj ? t("web.housing.edit") : t("web.housing.new")}
      okText={t("btn.save")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={aGuardar}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={aloj ? { ...aloj, observacoes: aloj.observacoes ?? "" } : VAZIO}
        onFinish={(d) => onGuardar(aloj, d)}
      >
        <Row gutter={12}>
          <Col span={24}>
            <Form.Item
              name="nome"
              label={t("web.housing.name")}
              rules={[{ required: true, whitespace: true, message: t("error.name_required") }]}
            >
              <Input autoFocus maxLength={80} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={14}>
            <Form.Item name="tipo" label={t("web.housing.type")}>
              <Segmented block options={TIPOS_ALOJAMENTO.map((x) => ({ value: x, label: t(`web.housing.type.${x}`) }))} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={10}>
            <Form.Item name="capacidade" label={t("web.housing.capacity")} rules={[{ required: true }]}>
              <InputNumber min={1} max={999} style={{ width: "100%" }} inputMode="numeric" />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item name="observacoes" label={t("web.housing.notes")}>
              <Input />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Modal>
  );
}

function AlojamentosMobile() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const { data, isPending, isError, error } = useAlojamentos();
  const [aberto, setAberto] = useState<Aberto>(null);
  const { guardar, aGuardar, fazerAlternar } = useAcoesAlojamento(() => setAberto(null));
  const [form] = MForm.useForm<AlojamentoIn>();
  const aloj = aberto?.aloj ?? null;
  const umSo = { getValueProps: (v: unknown) => ({ value: v == null ? [] : [v] }), normalize: (v: unknown[]) => v[0] };

  if (isError) return <ErrorBlock status="default" title={errorMessage(error)} description="" />;

  return (
    <>
      <List header={t("web.housing.help")}>
        {isPending ? (
          <List.Item>
            <DotLoading />
          </List.Item>
        ) : !data?.length ? (
          <ErrorBlock status="empty" title={t("web.housing.empty")} description="" />
        ) : (
          data.map((a) => (
            <SwipeAction
              key={a.id}
              rightActions={[
                {
                  key: "estado",
                  text: a.ativo ? t("web.common.deactivate") : t("web.common.activate"),
                  color: a.ativo ? "warning" : "success",
                  onClick: () => fazerAlternar(a),
                },
              ]}
            >
              <List.Item
                onClick={() => setAberto({ aloj: a })}
                description={[t(`web.housing.type.${a.tipo}`), `${t("web.housing.capacity")} ${a.capacidade}`, a.observacoes]
                  .filter(Boolean)
                  .join(" · ")}
                extra={!a.ativo && <MTag fill="outline">{t("web.common.inactive")}</MTag>}
              >
                {a.nome}
              </List.Item>
            </SwipeAction>
          ))
        )}
      </List>
      <div style={{ padding: "8px 12px", fontSize: 11, color: "#999" }}>{t("web.mobile.swipe_hint_housing")}</div>
      <div style={{ height: 72 }} />
      <FloatingBubble
        style={
          {
            "--initial-position-bottom": "calc(72px + env(safe-area-inset-bottom))",
            "--initial-position-right": "16px",
            "--edge-distance": "16px",
            "--size": "52px",
          } as React.CSSProperties
        }
        onClick={() => setAberto({ aloj: null })}
      >
        <AddOutline fontSize={26} />
      </FloatingBubble>

      <FolhaEcraInteiro
        visible={aberto !== null}
        titulo={aloj ? t("web.housing.edit") : t("web.housing.new")}
        onCancel={() => setAberto(null)}
        onOk={() => form.submit()}
        okText={t("btn.save")}
        loading={aGuardar}
      >
        <MForm
          form={form}
          layout="horizontal"
          style={{ "--prefix-width": "7.5em" } as React.CSSProperties}
          initialValues={aloj ? { ...aloj, observacoes: aloj.observacoes ?? "" } : VAZIO}
          onFinish={(d) => guardar(aloj, d)}
          onFinishFailed={irParaErro}
        >
          <MForm.Item
            name="nome"
            label={t("web.housing.name")}
            rules={[{ required: true, whitespace: true, message: t("error.name_required") }]}
          >
            <MInput clearable maxLength={80} />
          </MForm.Item>
          <MForm.Item name="tipo" label={t("web.housing.type")} {...umSo}>
            <Selector showCheckMark={false} options={TIPOS_ALOJAMENTO.map((x) => ({ value: x, label: t(`web.housing.type.${x}`) }))} />
          </MForm.Item>
          <MForm.Item
            name="capacidade"
            label={t("web.housing.capacity")}
            rules={[{ required: true, type: "number", min: 1, max: 999, message: t("web.settings.error.capacity", { min: 1, max: 999 }) }]}
          >
            <NumeroCampo min={0} max={999} />
          </MForm.Item>
          <MForm.Item name="observacoes" label={t("web.housing.notes")}>
            <MInput clearable />
          </MForm.Item>
        </MForm>
      </FolhaEcraInteiro>
    </>
  );
}
