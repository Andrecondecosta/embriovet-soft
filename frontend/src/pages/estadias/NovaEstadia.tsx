import { useState } from "react";
import dayjs, { type Dayjs } from "dayjs";
import { Alert, Checkbox, Col, Collapse, DatePicker, Form, Input, InputNumber, Modal, Row, Segmented, Select, Tag, Typography } from "antd";
import {
  Checkbox as MCheckbox,
  DatePicker as MDatePicker,
  Form as MForm,
  Input as MInput,
  List,
  Popup,
  SearchBar,
  Selector,
  TextArea,
} from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile, useDebounced } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { Cabecalho, FolhaEcraInteiro, NumeroCampo, PickerCampo, SeletorPesquisa, abrirAoTocar, irParaErro } from "../../components/mobile";
import { DonoSelect } from "../stock/LoteForm";
import {
  MOTIVOS,
  TIPOS_ANIMAL,
  TIPOS_REGISTO,
  useCriarEstadia,
  useOpcoesEstadia,
  usePesquisaAnimais,
  type AnimalNovo,
  type AnimalPesquisa,
  type EstadiaIn,
  type Motivo,
  type TipoRegisto,
} from "./api";

const FMT = "YYYY-MM-DD";

/** Valores do formulário (comuns às duas versões). */
interface Valores {
  modo: "existente" | "novo";
  animal?: AnimalPesquisa | null;
  novo?: Partial<AnimalNovo> & { data_nascimento?: Dayjs | Date | null };
  tipo_registo: TipoRegisto;
  motivo: Motivo;
  dono_id: number | null;
  data_entrada: Dayjs | Date;
  alojamento_id: number | null;
  observacoes?: string;
}

const INICIAIS: Valores = {
  modo: "existente",
  animal: null,
  novo: { tipo: "egua" },
  tipo_registo: "estadia",
  motivo: "inseminacao",
  dono_id: null,
  data_entrada: dayjs(),
  alojamento_id: null,
};

const data = (v: Dayjs | Date | null | undefined) => (v ? dayjs(v).format(FMT) : null);

/** Gravar — partilhado pelo computador e pelo telemóvel. */
function useGuardar(onClose: () => void) {
  const t = useT();
  const notifyError = useNotifyError();
  const criar = useCriarEstadia();
  const guardar = async (v: Valores) => {
    const corpo: EstadiaIn = {
      tipo_registo: v.tipo_registo,
      motivo: v.motivo,
      dono_id: v.dono_id,
      data_entrada: data(v.data_entrada)!,
      alojamento_id: v.tipo_registo === "externo" ? null : v.alojamento_id,
      observacoes: v.observacoes,
      ...(v.modo === "existente"
        ? { animal_id: v.animal?.id }
        : { animal: { ...(v.novo as AnimalNovo), data_nascimento: data(v.novo?.data_nascimento) } }),
    };
    try {
      await criar.mutateAsync(corpo);
      notifySuccess(t("web.stays.created"));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };
  return { guardar, aGuardar: criar.isPending };
}

/** Aviso (não bloqueia): o mesmo nome já existe noutro proprietário. */
function useAvisoNome(nome: string | undefined, donoId: number | null) {
  const n = (nome ?? "").trim();
  const pesquisa = usePesquisaAnimais(useDebounced(n, 400));
  return n.length > 1 && (pesquisa.data ?? []).some((a) => a.nome.toLowerCase() === n.toLowerCase() && a.dono_id !== donoId);
}

export function NovaEstadia({ aberto, onClose }: { aberto: boolean; onClose: () => void }) {
  return useIsMobile() ? <NovaEstadiaMobile aberto={aberto} onClose={onClose} /> : <NovaEstadiaDesktop aberto={aberto} onClose={onClose} />;
}

// ── Computador ──────────────────────────────────────────────────────────────

function PesquisaAnimal({ value, onChange }: { value?: AnimalPesquisa | null; onChange?: (a: AnimalPesquisa | null) => void }) {
  const t = useT();
  const [q, setQ] = useState("");
  const pesquisa = usePesquisaAnimais(useDebounced(q, 250));
  const lista = pesquisa.data ?? [];
  const opcoes = value && !lista.some((a) => a.id === value.id) ? [value, ...lista] : lista;
  return (
    <Select
      showSearch
      allowClear
      filterOption={false}
      onSearch={setQ}
      loading={pesquisa.isFetching}
      placeholder={t("web.stays.form.search")}
      value={value?.id}
      onChange={(id) => onChange?.(opcoes.find((a) => a.id === id) ?? null)}
      notFoundContent={t("web.common.no_results")}
      options={opcoes.map((a) => ({
        value: a.id,
        // Um animal com estadia em aberto não pode ter outra (como a app atual).
        disabled: !!a.em_aberto,
        label: (
          <span>
            {a.nome}{" "}
            <Typography.Text type="secondary">
              · {t(`web.stays.animal.${a.tipo}`)} · {a.proprietario ?? "—"}
            </Typography.Text>
            {a.em_aberto && (
              <Tag style={{ marginLeft: 6 }}>{t("web.stays.form.open", { kind: t(`web.stays.kind.${a.em_aberto}`).toLowerCase() })}</Tag>
            )}
          </span>
        ),
      }))}
    />
  );
}

function NovaEstadiaDesktop({ aberto, onClose }: { aberto: boolean; onClose: () => void }) {
  const t = useT();
  const [form] = Form.useForm<Valores>();
  const opcoes = useOpcoesEstadia();
  const { guardar, aGuardar } = useGuardar(onClose);
  const modo = Form.useWatch("modo", form) ?? "existente";
  const tipoRegisto = Form.useWatch("tipo_registo", form) ?? "estadia";
  const tipoAnimal = Form.useWatch(["novo", "tipo"], form);
  const aviso = useAvisoNome(Form.useWatch(["novo", "nome"], form), Form.useWatch("dono_id", form) ?? null);
  const alojamentos = opcoes.data?.alojamentos ?? [];
  const r = (msg: string) => [{ required: true, message: t(msg) }];

  return (
    <Modal
      open={aberto}
      onCancel={onClose}
      title={t("web.stays.new")}
      okText={t("btn.save")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={aGuardar}
      width={760}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" preserve={false} initialValues={INICIAIS} onFinish={guardar}>
        <Form.Item name="modo" style={{ marginBottom: 12 }}>
          <Segmented
            options={[
              { value: "existente", label: t("web.stays.form.existing") },
              { value: "novo", label: t("web.stays.form.new_animal") },
            ]}
          />
        </Form.Item>

        {modo === "existente" ? (
          <Form.Item name="animal" label={t("web.stays.form.animal")} rules={r("web.stays.error.animal_required")}>
            <PesquisaAnimal
              onChange={(a) => {
                // O dono do animal por omissão (como a app atual).
                if (a?.dono_id) form.setFieldValue("dono_id", a.dono_id);
              }}
            />
          </Form.Item>
        ) : (
          <>
            <Row gutter={12}>
              <Col xs={24} sm={14}>
                <Form.Item
                  name={["novo", "nome"]}
                  label={t("web.stays.form.name")}
                  rules={[{ required: true, whitespace: true, message: t("web.stays.error.animal_name_required") }]}
                >
                  <Input autoFocus />
                </Form.Item>
              </Col>
              <Col xs={24} sm={10}>
                <Form.Item name={["novo", "tipo"]} label={t("web.stays.col.type")}>
                  <Segmented block options={TIPOS_ANIMAL.map((x) => ({ value: x, label: t(`web.stays.animal.${x}`) }))} />
                </Form.Item>
              </Col>
            </Row>
            {aviso && <Alert type="warning" showIcon title={t("web.stays.form.other_owner")} style={{ marginBottom: 12 }} />}
            <Collapse
              size="small"
              style={{ marginBottom: 12 }}
              items={[
                {
                  key: "id",
                  label: t("web.stays.form.identification"),
                  children: (
                    <Row gutter={12}>
                      {(
                        [
                          ["raca", "form.breed"],
                          ["pelagem", "form.coat"],
                          ["numero_registo", "form.registration"],
                          ["chip", "form.chip"],
                        ] as const
                      ).map(([n, l]) => (
                        <Col key={n} xs={12} sm={8}>
                          <Form.Item name={["novo", n]} label={t(`web.stays.${l}`)}>
                            <Input />
                          </Form.Item>
                        </Col>
                      ))}
                      <Col xs={12} sm={8}>
                        <Form.Item name={["novo", "data_nascimento"]} label={t("web.stays.form.birth")}>
                          <DatePicker format="DD/MM/YYYY" style={{ width: "100%" }} />
                        </Form.Item>
                      </Col>
                      <Col xs={12} sm={4}>
                        <Form.Item name={["novo", "altura"]} label={t("web.stays.form.height")}>
                          <InputNumber min={0} style={{ width: "100%" }} />
                        </Form.Item>
                      </Col>
                      <Col xs={12} sm={4}>
                        <Form.Item name={["novo", "peso"]} label={t("web.stays.form.weight")}>
                          <InputNumber min={0} style={{ width: "100%" }} />
                        </Form.Item>
                      </Col>
                      {tipoAnimal === "egua" && (
                        <Col span={24}>
                          <Form.Item name={["novo", "is_receptora"]} valuePropName="checked" style={{ marginBottom: 0 }}>
                            <Checkbox>{t("web.stays.form.is_recipient")}</Checkbox>
                          </Form.Item>
                        </Col>
                      )}
                    </Row>
                  ),
                },
                {
                  key: "gen",
                  label: t("web.stays.form.genealogy"),
                  children: (
                    <Row gutter={12}>
                      {(
                        [
                          ["pai", "form.sire"],
                          ["avo_paterno", "form.sire_sire"],
                          ["mae", "form.dam"],
                          ["avo_materno", "form.dam_sire"],
                        ] as const
                      ).map(([n, l]) => (
                        <Col key={n} xs={12}>
                          <Form.Item name={["novo", n]} label={t(`web.stays.${l}`)}>
                            <Input />
                          </Form.Item>
                        </Col>
                      ))}
                    </Row>
                  ),
                },
              ]}
            />
          </>
        )}

        <Form.Item name="tipo_registo" label={t("web.stays.form.kind")} extra={t(`web.stays.kind_help.${tipoRegisto}`)}>
          <Segmented block options={TIPOS_REGISTO.map((x) => ({ value: x, label: t(`web.stays.kind.${x}`) }))} />
        </Form.Item>
        <Row gutter={12}>
          <Col xs={24} sm={12}>
            <Form.Item name="motivo" label={tipoRegisto === "externo" ? t("web.stays.form.reason_optional") : t("web.stays.col.reason")}>
              <Select options={MOTIVOS.map((m) => ({ value: m, label: t(`web.stays.reason.${m}`) }))} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="dono_id" label={t("label.owner")} rules={r("web.stays.error.owner_required")}>
              <DonoSelect apenasAtivos />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="data_entrada"
              label={tipoRegisto === "externo" ? t("web.stays.form.service_date") : t("web.stays.form.entry_date")}
              rules={[{ required: true }]}
            >
              <DatePicker format="DD/MM/YYYY" allowClear={false} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          {tipoRegisto !== "externo" && (
            <Col xs={24} sm={12}>
              {opcoes.data && !alojamentos.length && tipoRegisto === "estadia" ? (
                <Alert type="warning" showIcon title={t("web.stays.form.no_housing")} style={{ marginTop: 22 }} />
              ) : (
                <Form.Item
                  name="alojamento_id"
                  label={tipoRegisto === "estadia" ? t("web.stays.form.housing") : t("web.stays.form.housing_optional")}
                  rules={tipoRegisto === "estadia" ? r("web.stays.error.housing_required") : []}
                >
                  <Select
                    allowClear
                    options={alojamentos.map((a) => ({ value: a.id, label: `${a.nome} (${t(`web.housing.type.${a.tipo}`)})` }))}
                  />
                </Form.Item>
              )}
            </Col>
          )}
        </Row>
        <Form.Item name="observacoes" label={t("web.stays.form.notes")} style={{ marginBottom: 0 }}>
          <Input.TextArea autoSize={{ minRows: 2 }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ── Telemóvel ───────────────────────────────────────────────────────────────

/** Escolher o animal: folha com pesquisa no servidor. */
function PesquisaAnimalMobile({ value, onChange }: { value?: AnimalPesquisa | null; onChange?: (a: AnimalPesquisa | null) => void }) {
  const t = useT();
  const [aberto, setAberto] = useState(false);
  const [q, setQ] = useState("");
  const pesquisa = usePesquisaAnimais(useDebounced(q, 250));
  return (
    <>
      <div onClick={() => setAberto(true)} style={{ minHeight: 22 }}>
        {value ? value.nome : <span style={{ color: "#ccc" }}>{t("web.stays.form.search")}</span>}
      </div>
      <Popup
        visible={aberto}
        onMaskClick={() => setAberto(false)}
        onClose={() => setAberto(false)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, height: "80dvh", display: "flex", flexDirection: "column" }}
      >
        <div style={{ padding: "14px 16px 8px", fontWeight: 600, fontSize: 15 }}>{t("web.stays.form.animal")}</div>
        <div style={{ padding: "0 12px 8px" }}>
          <SearchBar value={q} onChange={setQ} placeholder={t("web.stays.form.search")} />
        </div>
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
          <List>
            {(pesquisa.data ?? []).map((a) => (
              <List.Item
                key={a.id}
                disabled={!!a.em_aberto}
                description={`${t(`web.stays.animal.${a.tipo}`)} · ${a.proprietario ?? "—"}${
                  a.em_aberto ? ` · ${t("web.stays.form.open", { kind: t(`web.stays.kind.${a.em_aberto}`).toLowerCase() })}` : ""
                }`}
                onClick={() => {
                  onChange?.(a);
                  setAberto(false);
                }}
                arrow={false}
              >
                {a.nome}
              </List.Item>
            ))}
          </List>
        </div>
      </Popup>
    </>
  );
}

function NovaEstadiaMobile({ aberto, onClose }: { aberto: boolean; onClose: () => void }) {
  const t = useT();
  const [form] = MForm.useForm<Valores>();
  const opcoes = useOpcoesEstadia();
  const { guardar, aGuardar } = useGuardar(onClose);
  const modo = MForm.useWatch("modo", form) ?? "existente";
  const tipoRegisto = MForm.useWatch("tipo_registo", form) ?? "estadia";
  const tipoAnimal = MForm.useWatch(["novo", "tipo"], form);
  const aviso = useAvisoNome(MForm.useWatch(["novo", "nome"], form), MForm.useWatch("dono_id", form) ?? null);
  const [dataAberta, setDataAberta] = useState<"entrada" | "nascimento" | null>(null);
  const umSo = { getValueProps: (v: unknown) => ({ value: v == null ? [] : [v] }), normalize: (v: unknown[]) => v[0] };
  const alojamentos = opcoes.data?.alojamentos ?? [];
  const dataTexto = (v: Dayjs | Date | null | undefined) => (v ? dayjs(v).format("DD/MM/YYYY") : "—");

  return (
    <FolhaEcraInteiro
      visible={aberto}
      titulo={t("web.stays.new")}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText={t("btn.save")}
      loading={aGuardar}
    >
      <MForm
        form={form}
        layout="horizontal"
        style={{ "--prefix-width": "7.5em" } as React.CSSProperties}
        initialValues={{ ...INICIAIS, data_entrada: new Date() }}
        onFinish={(v: Valores) => guardar({ ...form.getFieldsValue(true), ...v })}
        onFinishFailed={irParaErro}
      >
        <MForm.Item name="modo" {...umSo}>
          <Selector
            columns={2}
            showCheckMark={false}
            options={[
              { value: "existente", label: t("web.stays.form.existing") },
              { value: "novo", label: t("web.stays.form.new_animal") },
            ]}
          />
        </MForm.Item>
        {modo === "existente" ? (
          <MForm.Item
            name="animal"
            label={t("web.stays.form.animal")}
            rules={[{ required: true, message: t("web.stays.error.animal_required") }]}
            arrow
          >
            <PesquisaAnimalMobile onChange={(a) => a?.dono_id && form.setFieldValue("dono_id", a.dono_id)} />
          </MForm.Item>
        ) : (
          <>
            <MForm.Item
              name={["novo", "nome"]}
              label={t("web.stays.form.name")}
              rules={[{ required: true, whitespace: true, message: t("web.stays.error.animal_name_required") }]}
              description={aviso && <span style={{ color: "var(--adm-color-warning)" }}>{t("web.stays.form.other_owner")}</span>}
            >
              <MInput clearable />
            </MForm.Item>
            <MForm.Item name={["novo", "tipo"]} label={t("web.stays.col.type")} {...umSo}>
              <Selector
                showCheckMark={false}
                columns={3}
                options={TIPOS_ANIMAL.map((x) => ({ value: x, label: t(`web.stays.animal.${x}`) }))}
              />
            </MForm.Item>
            {tipoAnimal === "egua" && (
              <MForm.Item name={["novo", "is_receptora"]} valuePropName="checked">
                <MCheckbox>{t("web.stays.form.is_recipient")}</MCheckbox>
              </MForm.Item>
            )}
            <Cabecalho>{t("web.stays.form.identification")}</Cabecalho>
            {(
              [
                ["raca", "form.breed"],
                ["pelagem", "form.coat"],
                ["numero_registo", "form.registration"],
                ["chip", "form.chip"],
              ] as const
            ).map(([n, l]) => (
              <MForm.Item key={n} name={["novo", n]} label={t(`web.stays.${l}`)}>
                <MInput clearable />
              </MForm.Item>
            ))}
            <MForm.Item label={t("web.stays.form.birth")} arrow onClick={() => setDataAberta("nascimento")} shouldUpdate>
              {() => dataTexto(form.getFieldValue(["novo", "data_nascimento"]))}
            </MForm.Item>
            <MForm.Item name={["novo", "altura"]} label={t("web.stays.form.height")}>
              <NumeroCampo />
            </MForm.Item>
            <MForm.Item name={["novo", "peso"]} label={t("web.stays.form.weight")}>
              <NumeroCampo />
            </MForm.Item>
            <Cabecalho>{t("web.stays.form.genealogy")}</Cabecalho>
            {(
              [
                ["pai", "form.sire"],
                ["avo_paterno", "form.sire_sire"],
                ["mae", "form.dam"],
                ["avo_materno", "form.dam_sire"],
              ] as const
            ).map(([n, l]) => (
              <MForm.Item key={n} name={["novo", n]} label={t(`web.stays.${l}`)}>
                <MInput clearable />
              </MForm.Item>
            ))}
          </>
        )}

        <Cabecalho>{t("web.stays.form.stay")}</Cabecalho>
        <MForm.Item name="tipo_registo" label={t("web.stays.form.kind")} description={t(`web.stays.kind_help.${tipoRegisto}`)} {...umSo}>
          <Selector showCheckMark={false} columns={3} options={TIPOS_REGISTO.map((x) => ({ value: x, label: t(`web.stays.kind.${x}`) }))} />
        </MForm.Item>
        <MForm.Item
          name="motivo"
          label={tipoRegisto === "externo" ? t("web.stays.form.reason_optional") : t("web.stays.col.reason")}
          arrow
          onClick={abrirAoTocar}
        >
          <PickerCampo<Motivo> opcoes={MOTIVOS.map((m) => ({ value: m, label: t(`web.stays.reason.${m}`) }))} />
        </MForm.Item>
        <MForm.Item
          name="dono_id"
          label={t("label.owner")}
          rules={[{ required: true, message: t("web.stays.error.owner_required") }]}
          arrow
          onClick={abrirAoTocar}
        >
          <SeletorPesquisa<number>
            titulo={t("label.owner")}
            opcoes={(opcoes.data?.donos ?? []).map((d) => ({ value: d.id, label: d.nome }))}
          />
        </MForm.Item>
        <MForm.Item
          label={tipoRegisto === "externo" ? t("web.stays.form.service_date") : t("web.stays.form.entry_date")}
          arrow
          onClick={() => setDataAberta("entrada")}
          shouldUpdate
        >
          {() => dataTexto(form.getFieldValue("data_entrada"))}
        </MForm.Item>
        {tipoRegisto !== "externo" &&
          (opcoes.data && !alojamentos.length && tipoRegisto === "estadia" ? (
            <MForm.Item>
              <span style={{ color: "var(--adm-color-warning)" }}>{t("web.stays.form.no_housing")}</span>
            </MForm.Item>
          ) : (
            <MForm.Item
              name="alojamento_id"
              label={tipoRegisto === "estadia" ? t("web.stays.form.housing") : t("web.stays.form.housing_optional")}
              rules={tipoRegisto === "estadia" ? [{ required: true, message: t("web.stays.error.housing_required") }] : []}
              arrow
              onClick={abrirAoTocar}
            >
              <PickerCampo<number>
                opcoes={alojamentos.map((a) => ({ value: a.id, label: `${a.nome} (${t(`web.housing.type.${a.tipo}`)})` }))}
              />
            </MForm.Item>
          ))}
        <MForm.Item name="observacoes" label={t("web.stays.form.notes")}>
          <TextArea autoSize={{ minRows: 1, maxRows: 5 }} />
        </MForm.Item>
      </MForm>
      <MDatePicker
        visible={dataAberta !== null}
        onClose={() => setDataAberta(null)}
        min={dayjs().subtract(40, "year").toDate()}
        max={dayjs().add(2, "year").toDate()}
        value={
          dataAberta === "entrada"
            ? dayjs(form.getFieldValue("data_entrada")).toDate()
            : form.getFieldValue(["novo", "data_nascimento"])
              ? dayjs(form.getFieldValue(["novo", "data_nascimento"])).toDate()
              : new Date()
        }
        onConfirm={(v) => {
          if (dataAberta === "entrada") form.setFieldValue("data_entrada", v);
          else form.setFieldValue(["novo", "data_nascimento"], v);
        }}
      />
    </FolhaEcraInteiro>
  );
}
