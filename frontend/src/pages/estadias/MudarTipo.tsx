import dayjs, { type Dayjs } from "dayjs";
import { Alert, DatePicker, Form, Modal, Segmented, Select, Typography } from "antd";
import { Button as MButton, Form as MForm, Popup, Selector } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { DataCampo, PickerCampo, abrirAoTocar } from "../../components/mobile";
import { TIPOS_REGISTO, useMudarTipo, useOpcoesEstadia, type TipoRegisto } from "./api";

/** A entrada em aberto a mudar (vem da lista das Estadias ou da ficha). */
export interface EntradaAberta {
  id: number;
  animal: string | null;
  tipo: TipoRegisto;
}

interface Valores {
  tipo_registo: TipoRegisto;
  data: Dayjs | string;
  alojamento_id?: number | null;
}

/**
 * Externo ⇄ estadia ⇄ visita na mesma entrada (ex.: égua acompanhada em casa
 * do cliente que passa a estar internada). O trabalho clínico continua igual;
 * a Faturação só conta os dias na clínica.
 */
export function MudarTipo({ entrada, onClose }: { entrada: EntradaAberta | null; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const mudar = useMudarTipo();
  const opcoes = useOpcoesEstadia();
  const [form] = Form.useForm<Valores>();
  const [mform] = MForm.useForm<Valores>();
  const outros = TIPOS_REGISTO.filter((x) => x !== entrada?.tipo);
  const iniciais: Valores = { tipo_registo: entrada?.tipo === "externo" ? "estadia" : "externo", data: dayjs(), alojamento_id: null };
  const paraM = MForm.useWatch("tipo_registo", mform) as TipoRegisto | undefined;
  const paraD = Form.useWatch("tipo_registo", form) as TipoRegisto | undefined;
  const para = isMobile ? paraM : paraD;
  const usarAloj = (opcoes.data?.usar_alojamentos ?? true) && para !== undefined && para !== "externo";
  const alojamentos = (opcoes.data?.alojamentos ?? []).filter((a) => (a.ocupados ?? 0) < (a.capacidade || 1));
  const rotuloAloj = (a: { nome: string; tipo: string }) => `${a.nome} (${t(`web.housing.type.${a.tipo}`)})`;

  const guardar = async (v: Valores) => {
    if (!entrada) return;
    try {
      await mudar.mutateAsync({
        id: entrada.id,
        tipo_registo: v.tipo_registo,
        data: dayjs(v.data).format("YYYY-MM-DD"),
        alojamento_id: v.tipo_registo === "externo" ? null : (v.alojamento_id ?? null),
      });
      notifySuccess(t("web.stays.change.saved"));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };
  const agora = entrada ? t("web.stays.change.now", { name: entrada.animal ?? "—", tipo: t(`web.stays.kind.${entrada.tipo}`) }) : "";
  const obrigatorioAloj = para === "estadia";

  if (isMobile)
    return (
      <Popup
        visible={entrada !== null}
        onMaskClick={onClose}
        onClose={onClose}
        destroyOnClose
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16, paddingBottom: "calc(16px + env(safe-area-inset-bottom))" }}
      >
        <div style={{ fontWeight: 600, fontSize: 15 }}>{t("web.stays.change.title")}</div>
        <div style={{ color: "#999", marginBottom: 8 }}>{agora}</div>
        <MForm
          form={mform}
          layout="horizontal"
          initialValues={{ ...iniciais, data: dayjs().format("YYYY-MM-DD") }}
          onFinish={guardar} style={{ "--prefix-width": "6em" } as React.CSSProperties}>
          <MForm.Item
            name="tipo_registo"
            label={t("web.stays.change.to")}
            getValueProps={(v) => ({ value: v == null ? [] : [v] })}
            normalize={(v: unknown[]) => v[0]}
          >
            <Selector showCheckMark={false} columns={2} options={outros.map((x) => ({ value: x, label: t(`web.stays.kind.${x}`) }))} />
          </MForm.Item>
          <MForm.Item name="data" label={t("web.stays.change.date")} rules={[{ required: true }]} arrow onClick={abrirAoTocar}>
            <DataCampo max={new Date()} />
          </MForm.Item>
          {usarAloj && (
            <MForm.Item
              key="aloj"
              name="alojamento_id"
              label={obrigatorioAloj ? t("web.stays.form.housing") : t("web.stays.form.housing_optional")}
              rules={obrigatorioAloj ? [{ required: true, message: t("web.stays.error.housing_required") }] : []}
              arrow
              onClick={abrirAoTocar}
            >
              <PickerCampo<number> opcoes={alojamentos.map((a) => ({ value: a.id, label: rotuloAloj(a) }))} />
            </MForm.Item>
          )}
        </MForm>
        <div style={{ color: "#999", fontSize: 12, margin: "8px 0" }}>{t("web.stays.change.help")}</div>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <MButton block onClick={onClose}>
            {t("web.common.cancel")}
          </MButton>
          <MButton block color="primary" loading={mudar.isPending} onClick={() => mform.submit()}>
            {t("btn.save")}
          </MButton>
        </div>
      </Popup>
    );

  return (
    <Modal
      open={entrada !== null}
      onCancel={onClose}
      title={t("web.stays.change.title")}
      okText={t("btn.save")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={mudar.isPending}
      destroyOnHidden
    >
      <Typography.Paragraph type="secondary">{agora}</Typography.Paragraph>
      <Form form={form} layout="vertical" preserve={false} initialValues={iniciais} onFinish={guardar}>
        <Form.Item name="tipo_registo" label={t("web.stays.change.to")}>
          <Segmented block options={outros.map((x) => ({ value: x, label: t(`web.stays.kind.${x}`) }))} />
        </Form.Item>
        <Form.Item name="data" label={t("web.stays.change.date")} rules={[{ required: true }]}>
          <DatePicker format="DD/MM/YYYY" allowClear={false} style={{ width: "100%" }} disabledDate={(d) => d.isAfter(dayjs(), "day")} />
        </Form.Item>
        {usarAloj && (
          <Form.Item
            name="alojamento_id"
            label={obrigatorioAloj ? t("web.stays.form.housing") : t("web.stays.form.housing_optional")}
            rules={obrigatorioAloj ? [{ required: true, message: t("web.stays.error.housing_required") }] : []}
          >
            <Select allowClear options={alojamentos.map((a) => ({ value: a.id, label: rotuloAloj(a) }))} />
          </Form.Item>
        )}
      </Form>
      <Alert type="info" showIcon title={t("web.stays.change.help")} />
    </Modal>
  );
}
