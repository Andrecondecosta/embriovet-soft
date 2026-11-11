import dayjs, { type Dayjs } from "dayjs";
import { Alert, DatePicker, Form, Modal, Select, Typography } from "antd";
import { Button as MButton, Form as MForm, Popup } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { DataCampo, PickerCampo, abrirAoTocar } from "../../components/mobile";
import { useMudarTipo, useOpcoesEstadia, type TipoRegisto } from "./api";

/** "Interno" (estadia) ou "Externo" (acompanhada fora da clínica). */
export type Destino = "estadia" | "externo";

/** A entrada em aberto a mudar (vem da lista das Estadias ou da ficha) e para onde. */
export interface EntradaAberta {
  id: number;
  animal: string | null;
  tipo: TipoRegisto;
  para: Destino;
}

/** Botões a mostrar: externo → interno; estadia → externo; visita → os dois. */
export const destinos = (tipo: TipoRegisto | null | undefined): Destino[] =>
  tipo === "externo" ? ["estadia"] : tipo === "estadia" ? ["externo"] : tipo === "visita" ? ["estadia", "externo"] : [];

/** "Mudar para interno" / "Mudar para externo". */
export const rotuloDestino = (t: (k: string) => string, para: Destino) => t(`web.stays.change.to_${para}`);

interface Valores {
  data: Dayjs | string;
  alojamento_id?: number | null;
}

/**
 * Passar a interno (estadia) ou a externo na MESMA entrada (ex.: égua
 * acompanhada em casa do cliente que vem para a clínica). O trabalho clínico
 * continua igual; a Faturação só conta os dias na clínica.
 */
export function MudarTipo({ entrada, onClose }: { entrada: EntradaAberta | null; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const mudar = useMudarTipo();
  const opcoes = useOpcoesEstadia();
  const [form] = Form.useForm<Valores>();
  const [mform] = MForm.useForm<Valores>();
  const interno = entrada?.para === "estadia";
  // Para interno escolhe-se o alojamento (se a clínica os usa).
  const usarAloj = interno && (opcoes.data?.usar_alojamentos ?? true);
  const alojamentos = (opcoes.data?.alojamentos ?? []).filter((a) => (a.ocupados ?? 0) < (a.capacidade || 1));
  const rotuloAloj = (a: { nome: string; tipo: string }) => `${a.nome} (${t(`web.housing.type.${a.tipo}`)})`;

  const guardar = async (v: Valores) => {
    if (!entrada) return;
    try {
      await mudar.mutateAsync({
        id: entrada.id,
        tipo_registo: entrada.para,
        data: dayjs(v.data).format("YYYY-MM-DD"),
        alojamento_id: interno ? (v.alojamento_id ?? null) : null,
      });
      notifySuccess(t("web.stays.change.saved"));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };
  const titulo = entrada ? rotuloDestino(t, entrada.para) : "";
  const agora = entrada ? t("web.stays.change.now", { name: entrada.animal ?? "—", tipo: t(`web.stays.kind.${entrada.tipo}`) }) : "";
  const regraAloj = [{ required: true, message: t("web.stays.error.housing_required") }];

  if (isMobile)
    return (
      <Popup
        visible={entrada !== null}
        onMaskClick={onClose}
        onClose={onClose}
        destroyOnClose
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16, paddingBottom: "calc(16px + env(safe-area-inset-bottom))" }}
      >
        <div style={{ fontWeight: 600, fontSize: 15 }}>{titulo}</div>
        <div style={{ color: "#999", marginBottom: 8 }}>{agora}</div>
        <MForm
          form={mform}
          layout="horizontal"
          initialValues={{ data: dayjs().format("YYYY-MM-DD"), alojamento_id: null }}
          onFinish={guardar}
          style={{ "--prefix-width": "6em" } as React.CSSProperties}
        >
          <MForm.Item name="data" label={t("web.stays.change.date")} rules={[{ required: true }]} arrow onClick={abrirAoTocar}>
            <DataCampo max={new Date()} />
          </MForm.Item>
          {usarAloj && (
            <MForm.Item name="alojamento_id" label={t("web.stays.form.housing")} rules={regraAloj} arrow onClick={abrirAoTocar}>
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
      title={titulo}
      okText={t("btn.save")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={mudar.isPending}
      destroyOnHidden
    >
      <Typography.Paragraph type="secondary">{agora}</Typography.Paragraph>
      <Form form={form} layout="vertical" preserve={false} initialValues={{ data: dayjs(), alojamento_id: null }} onFinish={guardar}>
        <Form.Item name="data" label={t("web.stays.change.date")} rules={[{ required: true }]}>
          <DatePicker format="DD/MM/YYYY" allowClear={false} style={{ width: "100%" }} disabledDate={(d) => d.isAfter(dayjs(), "day")} />
        </Form.Item>
        {usarAloj && (
          <Form.Item name="alojamento_id" label={t("web.stays.form.housing")} rules={regraAloj}>
            <Select allowClear options={alojamentos.map((a) => ({ value: a.id, label: rotuloAloj(a) }))} />
          </Form.Item>
        )}
      </Form>
      <Alert type="info" showIcon title={t("web.stays.change.help")} />
    </Modal>
  );
}
