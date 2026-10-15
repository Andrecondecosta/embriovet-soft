import { useState } from "react";
import dayjs from "dayjs";
import { Alert, Button, Checkbox, Col, DatePicker, Flex, Form, Input, InputNumber, Modal, Row, Select, Table } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Button as MButton, Checkbox as MCheckbox, Dialog, Form as MForm, List, SwipeAction, TextArea } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { dataCurta } from "../../components/csv";
import { confirmar, notifySuccess, useNotifyError } from "../../components/errors";
import { DataCampo, FolhaEcraInteiro, NumeroCampo, PickerCampo, abrirAoTocar, irParaErro } from "../../components/mobile";
import {
  COMPORTAMENTOS,
  useApagarRegisto,
  useDiario,
  useEditarRegisto,
  useNovoRegisto,
  type Animal,
  type Registo,
  type RegistoIn,
} from "./api";

const VAZIO: RegistoIn = {
  data_registo: dayjs().format("YYYY-MM-DD"),
  foliculo_mm: null,
  edema_grau: 0,
  fluido_uterino: false,
  comportamento: "cio_ativo",
  temperatura: null,
  tratamentos: null,
  proxima_observacao: null,
  observacoes: null,
};

/** Estado e ações do diário — comum às duas versões. */
function useDiarioTab(animal: Animal) {
  const t = useT();
  const notifyError = useNotifyError();
  const lista = useDiario(animal.id);
  const novo = useNovoRegisto(animal.id);
  const editar = useEditarRegisto(animal.id);
  const apagar = useApagarRegisto(animal.id);
  // null = fechado; "novo" = registo de hoje; Registo = a editar.
  const [aberto, setAberto] = useState<"novo" | Registo | null>(null);

  const guardar = async (d: RegistoIn) => {
    try {
      if (aberto === "novo") {
        const r = await novo.mutateAsync(d);
        notifySuccess(r.tarefas_concluidas > 0 ? t("web.animal.record_saved_task") : t("web.animal.record_saved"));
      } else if (aberto) {
        await editar.mutateAsync({ ...d, rid: aberto.id });
        notifySuccess(t("web.animal.record_updated"));
      }
      setAberto(null);
    } catch (err) {
      notifyError(err);
    }
  };
  const fazerApagar = async (r: Registo) => {
    try {
      await apagar.mutateAsync(r.id);
      notifySuccess(t("web.animal.record_deleted"));
    } catch (err) {
      notifyError(err);
    }
  };
  return { t, lista, aberto, setAberto, guardar, aGuardar: novo.isPending || editar.isPending, fazerApagar };
}

export function DiarioTab({ animal }: { animal: Animal }) {
  const x = useDiarioTab(animal);
  const { t } = x;
  const isMobile = useIsMobile();
  const semEstadia = animal.estadia_ativa === null;
  const comp = (c: string | null) => (c ? t(`web.animal.behaviour.${c}`) : "—");
  const perguntarApagar = (r: Registo) =>
    isMobile
      ? void Dialog.confirm({
          content: t("web.animal.delete_record", { data: dataCurta(r.data_registo) }),
          confirmText: <span style={{ color: "var(--adm-color-danger)" }}>{t("btn.delete")}</span>,
          cancelText: t("web.common.cancel"),
          onConfirm: () => x.fazerApagar(r),
        })
      : confirmar({
          titulo: t("btn.delete"),
          texto: t("web.animal.delete_record", { data: dataCurta(r.data_registo) }),
          ok: t("btn.delete"),
          cancelar: t("web.common.cancel"),
          perigo: true,
          onOk: () => x.fazerApagar(r),
        });

  const aviso = semEstadia && <Alert type="warning" showIcon title={t("web.animal.error.no_active_stay")} style={{ marginBottom: 12 }} />;
  const formulario = <FormRegisto x={x} />;

  if (isMobile)
    return (
      <>
        {semEstadia ? (
          <div style={{ padding: 12, color: "var(--adm-color-warning)" }}>{t("web.animal.error.no_active_stay")}</div>
        ) : (
          <div style={{ padding: 12 }}>
            <MButton block color="primary" onClick={() => x.setAberto("novo")}>
              + {t("web.animal.today_record")}
            </MButton>
          </div>
        )}
        <List>
          {!x.lista.data?.length ? (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.animal.no_records")}</span>
            </List.Item>
          ) : (
            x.lista.data.map((r) => (
              <SwipeAction
                key={r.id}
                rightActions={[
                  { key: "e", text: t("btn.edit"), color: "primary", onClick: () => x.setAberto(r) },
                  { key: "a", text: t("btn.delete"), color: "danger", onClick: () => perguntarApagar(r) },
                ]}
              >
                <List.Item
                  onClick={() => x.setAberto(r)}
                  description={
                    <>
                      {[
                        r.foliculo_mm != null && `${t("web.animal.col.follicle")}: ${r.foliculo_mm}`,
                        r.edema_grau != null && `${t("web.animal.col.edema")}: ${r.edema_grau}`,
                        r.fluido_uterino && t("web.animal.col.fluid"),
                        comp(r.comportamento),
                        r.temperatura && `${r.temperatura} °C`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                      {r.tratamentos && <div>{r.tratamentos}</div>}
                      {r.observacoes && <div>{r.observacoes}</div>}
                    </>
                  }
                  extra={r.proxima_observacao && <span style={{ fontSize: 11 }}>→ {dataCurta(r.proxima_observacao)}</span>}
                >
                  {dataCurta(r.data_registo)}
                </List.Item>
              </SwipeAction>
            ))
          )}
        </List>
        {formulario}
      </>
    );

  return (
    <>
      {aviso}
      {!semEstadia && (
        <Button type="primary" icon={<PlusOutlined />} onClick={() => x.setAberto("novo")} style={{ marginBottom: 12 }}>
          {t("web.animal.today_record")}
        </Button>
      )}
      <Table<Registo>
        size="small"
        bordered
        rowKey="id"
        loading={x.lista.isPending}
        dataSource={x.lista.data ?? []}
        pagination={{ pageSize: 30, hideOnSinglePage: true, size: "small" }}
        scroll={{ x: true }}
        locale={{ emptyText: t("web.animal.no_records") }}
        columns={[
          { title: t("web.animal.col.date"), dataIndex: "data_registo", width: 100, render: dataCurta },
          { title: t("web.animal.col.follicle"), dataIndex: "foliculo_mm", width: 90, align: "right", render: (v) => v ?? "—" },
          { title: t("web.animal.col.edema"), dataIndex: "edema_grau", width: 70, align: "right", render: (v) => v ?? "—" },
          {
            title: t("web.animal.col.fluid"),
            dataIndex: "fluido_uterino",
            width: 90,
            render: (v) => (v ? t("web.animal.yes") : t("web.animal.no")),
          },
          { title: t("web.animal.col.behaviour"), dataIndex: "comportamento", width: 120, render: comp },
          { title: t("web.animal.col.temperature"), dataIndex: "temperatura", width: 100, align: "right", render: (v) => v ?? "—" },
          { title: t("web.animal.col.treatments"), dataIndex: "tratamentos", ellipsis: true, render: (v) => v ?? "—" },
          { title: t("web.animal.col.next"), dataIndex: "proxima_observacao", width: 110, render: (v) => (v ? dataCurta(v) : "—") },
          { title: t("web.animal.col.notes"), dataIndex: "observacoes", ellipsis: true, render: (v) => v ?? "—" },
          {
            key: "acoes",
            width: 150,
            align: "right",
            render: (_, r) => (
              <Flex gap={4} justify="flex-end">
                <Button size="small" type="link" onClick={() => x.setAberto(r)}>
                  {t("btn.edit")}
                </Button>
                <Button size="small" danger type="text" onClick={() => perguntarApagar(r)}>
                  {t("btn.delete")}
                </Button>
              </Flex>
            ),
          },
        ]}
      />
      {formulario}
    </>
  );
}

type X = ReturnType<typeof useDiarioTab>;

/** Formulário do registo (novo ou editar). */
function FormRegisto({ x }: { x: X }) {
  const { t } = x;
  const isMobile = useIsMobile();
  const [form] = Form.useForm();
  const [mform] = MForm.useForm();
  const registo = x.aberto === "novo" ? VAZIO : x.aberto;
  const titulo = x.aberto === "novo" ? t("web.animal.today_record") : t("web.animal.edit_record");
  const edemas = [0, 1, 2, 3].map((n) => ({ value: n, label: t(`web.animal.edema.${n}`) }));
  const comps = COMPORTAMENTOS.map((c) => ({ value: c, label: t(`web.animal.behaviour.${c}`) }));
  const iso = (v: unknown) => (v ? dayjs(v as string).format("YYYY-MM-DD") : null);

  if (isMobile)
    return (
      <FolhaEcraInteiro
        visible={x.aberto !== null}
        titulo={titulo}
        onCancel={() => x.setAberto(null)}
        onOk={() => mform.submit()}
        okText={t("btn.save")}
        loading={x.aGuardar}
      >
        {registo && (
          <MForm
            form={mform}
            layout="horizontal"
            style={{ "--prefix-width": "8em" } as React.CSSProperties}
            initialValues={registo}
            onFinish={(v) => x.guardar({ ...registo, ...v })}
            onFinishFailed={irParaErro}
          >
            <MForm.Item name="data_registo" label={t("web.animal.col.date")} rules={[{ required: true }]} arrow onClick={abrirAoTocar}>
              <DataCampo />
            </MForm.Item>
            <MForm.Item name="foliculo_mm" label={t("web.animal.col.follicle")}>
              <NumeroCampo max={99} />
            </MForm.Item>
            <MForm.Item name="edema_grau" label={t("web.animal.col.edema")} arrow onClick={abrirAoTocar}>
              <PickerCampo<number> opcoes={edemas} />
            </MForm.Item>
            <MForm.Item name="comportamento" label={t("web.animal.col.behaviour")} arrow onClick={abrirAoTocar}>
              <PickerCampo<string> opcoes={comps} />
            </MForm.Item>
            <MForm.Item name="temperatura" label={t("web.animal.col.temperature")}>
              <NumeroCampo max={45} />
            </MForm.Item>
            <MForm.Item name="fluido_uterino" valuePropName="checked">
              <MCheckbox>{t("web.animal.col.fluid")}</MCheckbox>
            </MForm.Item>
            <MForm.Item
              name="proxima_observacao"
              label={t("web.animal.col.next")}
              description={t("web.animal.next_help")}
              arrow
              onClick={abrirAoTocar}
            >
              <DataCampo limpar min={new Date()} />
            </MForm.Item>
            <MForm.Item name="tratamentos" label={t("web.animal.col.treatments")}>
              <TextArea autoSize={{ minRows: 1, maxRows: 5 }} />
            </MForm.Item>
            <MForm.Item name="observacoes" label={t("web.animal.col.notes")}>
              <TextArea autoSize={{ minRows: 1, maxRows: 5 }} />
            </MForm.Item>
          </MForm>
        )}
      </FolhaEcraInteiro>
    );

  return (
    <Modal
      open={x.aberto !== null}
      onCancel={() => x.setAberto(null)}
      title={titulo}
      okText={t("btn.save")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={x.aGuardar}
      width={720}
      destroyOnHidden
    >
      {registo && (
        <Form
          form={form}
          layout="vertical"
          preserve={false}
          initialValues={{
            ...registo,
            data_registo: dayjs(registo.data_registo),
            proxima_observacao: registo.proxima_observacao ? dayjs(registo.proxima_observacao) : null,
          }}
          onFinish={(v) => x.guardar({ ...v, data_registo: iso(v.data_registo)!, proxima_observacao: iso(v.proxima_observacao) })}
        >
          <Row gutter={12}>
            <Col xs={12} sm={8}>
              <Form.Item name="data_registo" label={t("web.animal.col.date")} rules={[{ required: true }]}>
                <DatePicker format="DD/MM/YYYY" allowClear={false} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={12} sm={8}>
              <Form.Item name="foliculo_mm" label={t("web.animal.col.follicle")}>
                <InputNumber min={0} max={99} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={12} sm={8}>
              <Form.Item name="temperatura" label={t("web.animal.col.temperature")}>
                <InputNumber min={0} max={45} step={0.1} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={12} sm={8}>
              <Form.Item name="edema_grau" label={t("web.animal.col.edema")}>
                <Select options={edemas} />
              </Form.Item>
            </Col>
            <Col xs={12} sm={8}>
              <Form.Item name="comportamento" label={t("web.animal.col.behaviour")}>
                <Select options={comps} />
              </Form.Item>
            </Col>
            <Col xs={12} sm={8}>
              <Form.Item name="fluido_uterino" valuePropName="checked" label=" ">
                <Checkbox>{t("web.animal.col.fluid")}</Checkbox>
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="proxima_observacao" label={t("web.animal.col.next")} extra={t("web.animal.next_help")}>
                <DatePicker format="DD/MM/YYYY" style={{ width: "100%" }} disabledDate={(d) => !d.isAfter(dayjs(), "day")} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={16}>
              <Form.Item name="tratamentos" label={t("web.animal.col.treatments")}>
                <Input.TextArea autoSize={{ minRows: 2 }} />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item name="observacoes" label={t("web.animal.col.notes")} style={{ marginBottom: 0 }}>
                <Input.TextArea autoSize={{ minRows: 2 }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      )}
    </Modal>
  );
}
