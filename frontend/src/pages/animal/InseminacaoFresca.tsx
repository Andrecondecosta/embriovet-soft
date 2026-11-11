import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import dayjs, { type Dayjs } from "dayjs";
import { Button, DatePicker, Flex, Form, Input, Modal, TimePicker, Typography } from "antd";
import { ActionSheet, Dialog, Form as MForm, TextArea } from "antd-mobile";

import { api, ApiError } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { confirmar, notifySuccess, useNotifyError } from "../../components/errors";
import { DataCampo, FolhaEcraInteiro, SeletorPesquisa, abrirAoTocar } from "../../components/mobile";
import { GaranhaoInput } from "../stock/LoteForm";
import { useOpcoes } from "../stock/api";

/**
 * INS no registo clínico: pergunta se o sémen é fresco ou congelado.
 * Congelado abre a inseminação do stock (lotes, palhetas); fresco abre
 * `InseminacaoFresca` (só o garanhão).
 */
export function EscolherSemen({ eguaId, aberto, onClose }: { eguaId: number; aberto: boolean; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const [fresco, setFresco] = useState(false);
  const congelado = () => {
    onClose();
    navigate(`/trabalho-diario/inseminacao?egua=${eguaId}`);
  };
  const escolherFresco = () => {
    onClose();
    setFresco(true);
  };
  const janelaFresco = <InseminacaoFresca eguaId={eguaId} aberto={fresco} onClose={() => setFresco(false)} />;

  if (isMobile)
    return (
      <>
        <ActionSheet
          visible={aberto}
          onClose={onClose}
          extra={t("web.insem.kind.question")}
          cancelText={t("web.common.cancel")}
          actions={[
            { key: "fresco", text: t("web.insem.kind.fresh"), description: t("web.insem.kind.fresh_help"), onClick: escolherFresco },
            { key: "congelado", text: t("web.insem.kind.frozen"), description: t("web.insem.kind.frozen_help"), onClick: congelado },
          ]}
        />
        {janelaFresco}
      </>
    );
  return (
    <>
      <Modal open={aberto} onCancel={onClose} title={t("web.insem.kind.title")} footer={null} width={420} destroyOnHidden>
        <Typography.Paragraph>{t("web.insem.kind.question")}</Typography.Paragraph>
        <Flex gap={12}>
          <Button block size="large" onClick={escolherFresco} style={{ height: "auto", padding: "10px 12px", whiteSpace: "normal" }}>
            <Flex vertical>
              <b>{t("web.insem.kind.fresh")}</b>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {t("web.insem.kind.fresh_help")}
              </Typography.Text>
            </Flex>
          </Button>
          <Button block size="large" onClick={congelado} style={{ height: "auto", padding: "10px 12px", whiteSpace: "normal" }}>
            <Flex vertical>
              <b>{t("web.insem.kind.frozen")}</b>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {t("web.insem.kind.frozen_help")}
              </Typography.Text>
            </Flex>
          </Button>
        </Flex>
      </Modal>
      {janelaFresco}
    </>
  );
}

interface Valores {
  garanhao?: string;
  data: Dayjs | string;
  hora: Dayjs | string;
  observacoes?: string;
}

/** Inicial de uma operação a corrigir (vem da Atividade). */
export interface FrescaEditar {
  ref: string;
  garanhao: string;
  data_inseminacao: string;
  hora_inseminacao: string | null;
  observacoes: string | null;
}

/**
 * Inseminação com sémen fresco: só o nome do garanhão (não gasta palhetas).
 * Segue os mesmos passos que a do congelado (D+1, DG ao D+14…).
 */
export function InseminacaoFresca({
  eguaId,
  aberto,
  onClose,
  editar,
}: {
  eguaId: number;
  aberto: boolean;
  onClose: () => void;
  editar?: FrescaEditar;
}) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const queryClient = useQueryClient();
  const garanhoes = useOpcoes("garanhoes");
  const [form] = Form.useForm<Valores>();
  const [mform] = MForm.useForm<Valores>();
  const [pedidoId] = useState(() => crypto.randomUUID());
  const garanhaoAtual = (isMobile ? MForm.useWatch("garanhao", mform) : Form.useWatch("garanhao", form)) as string | undefined;
  // Garanhão escrito à mão que ainda não existe: fica criado ao gravar.
  const nomeNovo = (garanhaoAtual ?? "").trim();
  const ajudaGaranhao =
    nomeNovo && !(garanhoes.data ?? []).some((g) => g.nome.toLowerCase() === nomeNovo.toLowerCase())
      ? t("web.insem.fresh.new_stallion", { name: nomeNovo })
      : undefined;

  const gravar = useMutation({
    mutationFn: ({ v, confirmarGestante }: { v: Valores; confirmarGestante: boolean }) => {
      const corpo = {
        animal_id_egua: eguaId,
        fresco: true,
        linhas: [],
        garanhao: v.garanhao?.trim(),
        data_inseminacao: dayjs(v.data).format("YYYY-MM-DD"),
        hora_inseminacao: typeof v.hora === "string" ? v.hora : v.hora.format("HH:mm"),
        observacoes: v.observacoes,
        pedido_id: editar ? null : pedidoId,
        confirmar_gestante: confirmarGestante,
      };
      return editar ? api(`/inseminacoes/operacao/${editar.ref}`, "PUT", corpo) : api("/inseminacoes", "POST", corpo);
    },
    onSuccess: () => {
      for (const k of ["inseminacoes", "trabalho", "dashboard", "animal", "atividade"]) queryClient.invalidateQueries({ queryKey: [k] });
    },
  });

  /** A égua está dada como gestante: pergunta antes (como no congelado). */
  const perguntarGestante = (dataGestacao: string) =>
    new Promise<boolean>((resolve) => {
      const texto = t("web.insem.confirm_pregnant", { data: dataGestacao });
      if (isMobile)
        void Dialog.confirm({
          content: texto,
          confirmText: t("web.insem.confirm_pregnant_ok"),
          cancelText: t("web.common.cancel"),
          onConfirm: () => resolve(true),
          onCancel: () => resolve(false),
        });
      else
        confirmar({
          titulo: t("web.insem.pregnant_title"),
          texto,
          ok: t("web.insem.confirm_pregnant_ok"),
          cancelar: t("web.common.cancel"),
          perigo: true,
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
    });

  const guardar = async (v: Valores, confirmarGestante = false): Promise<void> => {
    try {
      await gravar.mutateAsync({ v, confirmarGestante });
      notifySuccess(t(editar ? "web.insem.updated" : "web.insem.fresh.saved"));
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.code === "web.insem.error.mare_pregnant") {
        if (await perguntarGestante(String(err.params.data ?? ""))) return guardar(v, true);
        return;
      }
      notifyError(err);
    }
  };

  const titulo = t(editar ? "web.insem.edit_title" : "web.insem.fresh.title");
  const obrigatorio = (msg: string) => [{ required: true, whitespace: true, message: t(msg) }];

  if (isMobile)
    return (
      <FolhaEcraInteiro visible={aberto} titulo={titulo} onCancel={onClose} onOk={() => mform.submit()} okText={t("btn.save")} loading={gravar.isPending}>
        <MForm
          form={mform}
          layout="horizontal"
          style={{ "--prefix-width": "6.5em" } as React.CSSProperties}
          initialValues={{
            garanhao: editar?.garanhao,
            data: editar?.data_inseminacao ?? dayjs().format("YYYY-MM-DD"),
            hora: editar?.hora_inseminacao ?? dayjs().format("HH:mm"),
            observacoes: editar?.observacoes ?? undefined,
          }}
          onFinish={(v: Valores) => guardar(v)}
        >
          <MForm.Item
            name="garanhao"
            label={t("label.garanhao")}
            rules={obrigatorio("warning.select_garanhao_first")}
            description={ajudaGaranhao}
            arrow
            onClick={abrirAoTocar}
          >
            <SeletorPesquisa<string>
              titulo={t("label.garanhao")}
              opcoes={(garanhoes.data ?? []).map((g) => ({ value: g.nome, label: g.nome }))}
              novo={(texto) => texto}
            />
          </MForm.Item>
          <MForm.Item name="data" label={t("label.date")} rules={[{ required: true }]} arrow onClick={abrirAoTocar}>
            <DataCampo max={new Date()} />
          </MForm.Item>
          <MForm.Item name="hora" label={t("web.insem.time")} rules={[{ required: true, message: t("web.insem.error.time_required") }]}>
            <input type="time" className="adm-input-element" style={{ width: "100%" }} />
          </MForm.Item>
          <MForm.Item name="observacoes" label={t("web.stays.form.notes")}>
            <TextArea autoSize={{ minRows: 1, maxRows: 4 }} />
          </MForm.Item>
        </MForm>
      </FolhaEcraInteiro>
    );

  return (
    <Modal
      open={aberto}
      onCancel={onClose}
      title={titulo}
      okText={t("btn.save")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={gravar.isPending}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={{
          garanhao: editar?.garanhao,
          data: editar ? dayjs(editar.data_inseminacao) : dayjs(),
          hora: editar?.hora_inseminacao ? dayjs(editar.hora_inseminacao, "HH:mm") : dayjs(),
          observacoes: editar?.observacoes ?? undefined,
        }}
        onFinish={(v) => guardar(v)}
      >
        <Form.Item name="garanhao" label={t("label.garanhao")} extra={ajudaGaranhao} rules={obrigatorio("warning.select_garanhao_first")}>
          <GaranhaoInput />
        </Form.Item>
        <Flex gap={12}>
          <Form.Item name="data" label={t("label.date")} rules={[{ required: true }]} style={{ flex: 1 }}>
            <DatePicker format="DD/MM/YYYY" allowClear={false} style={{ width: "100%" }} disabledDate={(d) => d.isAfter(dayjs(), "day")} />
          </Form.Item>
          <Form.Item name="hora" label={t("web.insem.time")} rules={[{ required: true, message: t("web.insem.error.time_required") }]} style={{ flex: 1 }}>
            <TimePicker format="HH:mm" allowClear={false} style={{ width: "100%" }} />
          </Form.Item>
        </Flex>
        <Form.Item name="observacoes" label={t("web.stays.form.notes")} style={{ marginBottom: 0 }}>
          <Input.TextArea autoSize={{ minRows: 2 }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
