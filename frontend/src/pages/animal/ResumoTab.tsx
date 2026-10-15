import { useState } from "react";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import {
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Descriptions,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Segmented,
  Space,
  Table,
  Typography,
} from "antd";
import { EditOutlined } from "@ant-design/icons";
import { Button as MButton, Checkbox as MCheckbox, Dialog, Form as MForm, Input as MInput, List, Selector, TextArea } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { dataCurta } from "../../components/csv";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { Cabecalho, DataCampo, FolhaEcraInteiro, semNulos, NumeroCampo, abrirAoTocar, irParaErro } from "../../components/mobile";
import { useAgendarColheita, useCancelarColheita, useColheitas, useEditarAnimal, type Animal, type AnimalIn } from "./api";

const TIPOS = ["egua", "garanhao", "receptora"] as const;
const TEXTOS: [keyof AnimalIn, string][] = [
  ["raca", "web.stays.form.breed"],
  ["pelagem", "web.stays.form.coat"],
  ["chip", "web.stays.form.chip"],
  ["numero_registo", "web.stays.form.registration"],
];
const PEDIGREE: [keyof AnimalIn, string][] = [
  ["pai", "web.stays.form.sire"],
  ["avo_paterno", "web.stays.form.sire_sire"],
  ["mae", "web.stays.form.dam"],
  ["avo_materno", "web.stays.form.dam_sire"],
];

/** Idade a partir da data de nascimento (anos, ou meses se < 1 ano). */
function useIdade() {
  const t = useT();
  return (iso: string | null) => {
    if (!iso) return null;
    const anos = dayjs().diff(dayjs(iso), "year");
    if (anos < 1) return t("web.animal.age_months", { n: Math.max(dayjs().diff(dayjs(iso), "month"), 0) });
    return anos === 1 ? t("web.animal.age_year") : t("web.animal.age_years", { n: anos });
  };
}

export function ResumoTab({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const idade = useIdade();
  const [editar, setEditar] = useState(false);
  const na = (v: string | number | null) => (v === null || v === "" ? "—" : String(v));
  const nasc = animal.data_nascimento ? `${dataCurta(animal.data_nascimento)} (${idade(animal.data_nascimento)})` : "—";
  const campos: [string, string][] = [
    [t("web.stays.form.name"), animal.nome],
    [t("web.stays.col.type"), t(`web.stays.animal.${animal.tipo}`)],
    ...TEXTOS.map(([k, l]) => [t(l), na(animal[k] as string | null)] as [string, string]),
    [t("web.stays.form.height"), na(animal.altura)],
    [t("web.stays.form.weight"), na(animal.peso)],
    [t("web.stays.form.birth"), nasc],
  ];
  const pedigree: [string, string][] = PEDIGREE.map(([k, l]) => [t(l), na(animal[k] as string | null)]);
  // Atalho "Registar inseminação" (só éguas), como na app atual.
  const inseminar = animal.tipo === "egua" && (() => navigate(`/trabalho-diario/inseminacao?egua=${animal.id}`));

  if (isMobile)
    return (
      <>
        <List header={t("web.stays.form.identification")}>
          {campos.map(([l, v]) => (
            <List.Item key={l} extra={v}>
              {l}
            </List.Item>
          ))}
        </List>
        <List header={t("web.stays.form.genealogy")}>
          {pedigree.map(([l, v]) => (
            <List.Item key={l} extra={v}>
              {l}
            </List.Item>
          ))}
        </List>
        {animal.observacoes && (
          <List header={t("web.stays.form.notes")}>
            <List.Item>
              <span style={{ whiteSpace: "pre-wrap" }}>{animal.observacoes}</span>
            </List.Item>
          </List>
        )}
        <div style={{ display: "flex", gap: 8, padding: 12 }}>
          <MButton block onClick={() => setEditar(true)}>
            {t("web.animal.edit")}
          </MButton>
          {inseminar && (
            <MButton block color="primary" onClick={inseminar}>
              {t("web.animal.register_insemination")}
            </MButton>
          )}
        </div>
        {animal.tipo === "garanhao" && <Colheitas animal={animal} />}
        <EditarAnimal animal={animal} aberto={editar} onClose={() => setEditar(false)} />
      </>
    );

  return (
    <Space orientation="vertical" size={16} style={{ width: "100%" }}>
      <Flex justify="flex-end" gap={8}>
        {inseminar && (
          <Button type="primary" onClick={inseminar}>
            {t("web.animal.register_insemination")}
          </Button>
        )}
        <Button icon={<EditOutlined />} onClick={() => setEditar(true)}>
          {t("web.animal.edit")}
        </Button>
      </Flex>
      <Descriptions
        size="small"
        bordered
        title={t("web.stays.form.identification")}
        column={{ xs: 1, md: 2, xl: 3 }}
        items={campos.map(([label, children]) => ({ label, children }))}
      />
      <Descriptions
        size="small"
        bordered
        title={t("web.stays.form.genealogy")}
        column={{ xs: 1, md: 2 }}
        items={pedigree.map(([label, children]) => ({ label, children }))}
      />
      {animal.observacoes && (
        <Descriptions
          size="small"
          bordered
          column={1}
          items={[{ label: t("web.stays.form.notes"), children: <span style={{ whiteSpace: "pre-wrap" }}>{animal.observacoes}</span> }]}
        />
      )}
      {animal.tipo === "garanhao" && <Colheitas animal={animal} />}
      <EditarAnimal animal={animal} aberto={editar} onClose={() => setEditar(false)} />
    </Space>
  );
}

/** Editar ficha — modal no computador, ecrã inteiro no telemóvel. */
function EditarAnimal({ animal, aberto, onClose }: { animal: Animal; aberto: boolean; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const editar = useEditarAnimal(animal.id);
  const [form] = Form.useForm();
  const [mform] = MForm.useForm();
  const umSo = { getValueProps: (v: unknown) => ({ value: v == null ? [] : [v] }), normalize: (v: unknown[]) => v[0] };

  const guardar = async (v: AnimalIn & { data_nascimento: unknown }) => {
    try {
      await editar.mutateAsync({
        ...v,
        data_nascimento: v.data_nascimento ? dayjs(v.data_nascimento as string).format("YYYY-MM-DD") : null,
      });
      notifySuccess(t("web.animal.saved"));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };
  const nome = [{ required: true, whitespace: true, message: t("web.stays.error.animal_name_required") }];

  if (isMobile)
    return (
      <FolhaEcraInteiro
        visible={aberto}
        titulo={t("web.animal.edit")}
        onCancel={onClose}
        onOk={() => mform.submit()}
        okText={t("btn.save")}
        loading={editar.isPending}
      >
        <MForm
          form={mform}
          layout="horizontal"
          style={{ "--prefix-width": "7.5em" } as React.CSSProperties}
          initialValues={semNulos(animal)}
          onFinish={guardar}
          onFinishFailed={irParaErro}
        >
          <MForm.Item name="nome" label={t("web.stays.form.name")} rules={nome}>
            <MInput clearable />
          </MForm.Item>
          <MForm.Item name="tipo" label={t("web.stays.col.type")} {...umSo}>
            <Selector showCheckMark={false} columns={3} options={TIPOS.map((x) => ({ value: x, label: t(`web.stays.animal.${x}`) }))} />
          </MForm.Item>
          <MForm.Item name="is_receptora" valuePropName="checked">
            <MCheckbox>{t("web.stays.form.is_recipient")}</MCheckbox>
          </MForm.Item>
          <Cabecalho>{t("web.stays.form.identification")}</Cabecalho>
          {TEXTOS.map(([k, l]) => (
            <MForm.Item key={k} name={k} label={t(l)}>
              <MInput clearable />
            </MForm.Item>
          ))}
          <MForm.Item name="data_nascimento" label={t("web.stays.form.birth")} arrow onClick={abrirAoTocar}>
            <DataCampo limpar max={new Date()} />
          </MForm.Item>
          <MForm.Item name="altura" label={t("web.stays.form.height")}>
            <NumeroCampo />
          </MForm.Item>
          <MForm.Item name="peso" label={t("web.stays.form.weight")}>
            <NumeroCampo />
          </MForm.Item>
          <Cabecalho>{t("web.stays.form.genealogy")}</Cabecalho>
          {PEDIGREE.map(([k, l]) => (
            <MForm.Item key={k} name={k} label={t(l)}>
              <MInput clearable />
            </MForm.Item>
          ))}
          <MForm.Item name="observacoes" label={t("web.stays.form.notes")}>
            <TextArea autoSize={{ minRows: 1, maxRows: 6 }} />
          </MForm.Item>
        </MForm>
      </FolhaEcraInteiro>
    );

  return (
    <Modal
      open={aberto}
      onCancel={onClose}
      title={t("web.animal.edit")}
      okText={t("btn.save_changes")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={editar.isPending}
      width={760}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={{ ...animal, data_nascimento: animal.data_nascimento ? dayjs(animal.data_nascimento) : null }}
        onFinish={guardar}
      >
        <Row gutter={12}>
          <Col xs={24} sm={12}>
            <Form.Item name="nome" label={t("web.stays.form.name")} rules={nome}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="tipo" label={t("web.stays.col.type")}>
              <Segmented block options={TIPOS.map((x) => ({ value: x, label: t(`web.stays.animal.${x}`) }))} />
            </Form.Item>
          </Col>
          {TEXTOS.map(([k, l]) => (
            <Col key={k} xs={12} sm={6}>
              <Form.Item name={k} label={t(l)}>
                <Input />
              </Form.Item>
            </Col>
          ))}
          <Col xs={12} sm={8}>
            <Form.Item name="data_nascimento" label={t("web.stays.form.birth")}>
              <DatePicker format="DD/MM/YYYY" style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} sm={8}>
            <Form.Item name="altura" label={t("web.stays.form.height")}>
              <InputNumber min={0} max={999.9} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} sm={8}>
            <Form.Item name="peso" label={t("web.stays.form.weight")}>
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          {PEDIGREE.map(([k, l]) => (
            <Col key={k} xs={12}>
              <Form.Item name={k} label={t(l)}>
                <Input />
              </Form.Item>
            </Col>
          ))}
          <Col span={24}>
            <Form.Item name="observacoes" label={t("web.stays.form.notes")}>
              <Input.TextArea autoSize={{ minRows: 2 }} />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item name="is_receptora" valuePropName="checked" style={{ marginBottom: 0 }}>
              <Checkbox>{t("web.stays.form.is_recipient")}</Checkbox>
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Modal>
  );
}

/** Colheitas agendadas do garanhão (painel da app atual). */
function Colheitas({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const lista = useColheitas(animal.id);
  const agendar = useAgendarColheita(animal.id);
  const cancelar = useCancelarColheita(animal.id);
  const [data, setData] = useState<string | null>(dayjs().add(1, "day").format("YYYY-MM-DD"));

  const fazerAgendar = async () => {
    if (!data) return;
    try {
      await agendar.mutateAsync(data);
      notifySuccess(t("web.animal.collections.scheduled", { data: dataCurta(data) }));
    } catch (err) {
      notifyError(err);
    }
  };
  const fazerCancelar = async (id: number) => {
    try {
      await cancelar.mutateAsync(id);
      notifySuccess(t("web.animal.collections.cancelled"));
    } catch (err) {
      notifyError(err);
    }
  };
  const urg = (u: string | null) => (u ? t(`web.dashboard.urg.${u}`) : "—");

  if (isMobile)
    return (
      <>
        <List header={t("web.animal.collections")}>
          <List.Item description={t("web.animal.collections_help")} arrow>
            <DataCampo value={data} onChange={setData} min={new Date()} />
          </List.Item>
          <List.Item>
            <MButton block color="primary" loading={agendar.isPending} onClick={fazerAgendar}>
              {t("web.animal.collections.schedule")}
            </MButton>
          </List.Item>
          {!lista.data?.length ? (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.animal.collections.none")}</span>
            </List.Item>
          ) : (
            lista.data.map((c) => (
              <List.Item
                key={c.id}
                extra={
                  <MButton
                    size="mini"
                    color="danger"
                    fill="none"
                    onClick={() =>
                      void Dialog.confirm({
                        content: `${t("web.common.cancel")} ${dataCurta(c.data_tarefa)}?`,
                        confirmText: "OK",
                        cancelText: t("web.common.close"),
                        onConfirm: () => fazerCancelar(c.id),
                      })
                    }
                  >
                    {t("web.common.cancel")}
                  </MButton>
                }
                description={urg(c.urgencia)}
              >
                {dataCurta(c.data_tarefa)}
              </List.Item>
            ))
          )}
        </List>
      </>
    );

  return (
    <Card size="small" title={t("web.animal.collections")}>
      <Typography.Paragraph type="secondary">{t("web.animal.collections_help")}</Typography.Paragraph>
      <Flex gap={8} style={{ marginBottom: 12 }}>
        <DatePicker
          value={data ? dayjs(data) : null}
          onChange={(d) => setData(d ? d.format("YYYY-MM-DD") : null)}
          format="DD/MM/YYYY"
          disabledDate={(d) => d.isBefore(dayjs(), "day")}
        />
        <Button type="primary" loading={agendar.isPending} onClick={fazerAgendar} disabled={!data}>
          {t("web.animal.collections.schedule")}
        </Button>
      </Flex>
      <Table
        size="small"
        rowKey="id"
        dataSource={lista.data ?? []}
        loading={lista.isPending}
        pagination={false}
        locale={{ emptyText: t("web.animal.collections.none") }}
        columns={[
          { title: t("web.animal.col.date"), dataIndex: "data_tarefa", render: dataCurta },
          { title: t("web.dashboard.urgency"), dataIndex: "urgencia", render: urg },
          {
            key: "x",
            align: "right",
            render: (_, c) => (
              <Button size="small" danger type="text" onClick={() => fazerCancelar(c.id)}>
                {t("web.common.cancel")}
              </Button>
            ),
          },
        ]}
      />
    </Card>
  );
}
