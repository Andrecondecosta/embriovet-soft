import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AutoComplete, Button, Col, Divider, Flex, Form, Input, InputNumber, Modal, Row, Segmented, Select, Tooltip, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";

import type { Owner } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { OwnerFormModal } from "../owners/OwnerFormModal";
import { useEditarLote, useOpcoes, type Lote, type LoteCampos, type LoteEdicao } from "./api";

export const CANISTERS = Array.from({ length: 10 }, (_, i) => String(i + 1));

export function camposVazios(): LoteCampos {
  return {
    garanhao: "",
    dono_id: null,
    data_embriovet: "",
    origem_externa: "",
    qualidade: "",
    concentracao: 0,
    motilidade: 0,
    certificado: "Sim",
    dose: "",
    cor: "",
    contentor_id: null,
    canister: 1,
    andar: 1,
    observacoes: "",
  };
}

export function Secao({ titulo, children, primeiro = false }: { titulo: string; children: ReactNode; primeiro?: boolean }) {
  return (
    <>
      <Divider titlePlacement="start" plain style={{ margin: primeiro ? "0 0 8px" : "8px 0" }}>
        <Typography.Text type="secondary" strong style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>
          {titulo}
        </Typography.Text>
      </Divider>
      {children}
    </>
  );
}

/** Garanhão: escolher da lista ou escrever um nome novo (o servidor cria-o
 *  em `animais`, sem duplicar "Falcao"/"Falcão"). Controlado — funciona
 *  dentro de um `Form.Item`. */
export function GaranhaoInput({ value = "", onChange }: { value?: string; onChange?: (v: string) => void }) {
  const t = useT();
  const garanhoes = useOpcoes("garanhoes");
  const nomes = (garanhoes.data ?? []).map((g) => g.nome);
  const q = value.trim().toLowerCase();
  return (
    <AutoComplete
      value={value}
      onChange={onChange}
      options={nomes.filter((n) => !q || n.toLowerCase().includes(q)).slice(0, 50).map((n) => ({ value: n }))}
      placeholder={t("add_stock.stallion_placeholder")}
    />
  );
}

/** Texto de ajuda por baixo do garanhão: diz se o nome é novo. */
export function useAjudaGaranhao(valor: string | undefined) {
  const t = useT();
  const garanhoes = useOpcoes("garanhoes");
  const v = (valor ?? "").trim();
  const novo = v && !(garanhoes.data ?? []).some((g) => g.nome.toLowerCase() === v.toLowerCase());
  return novo ? t("web.stock.add.new_stallion", { name: v }) : t("web.stock.add.stallion_hint");
}

/** Seletor de proprietário com "+" para criar um novo sem sair do formulário.
 *  Controlado — funciona dentro de um `Form.Item`. */
export function DonoSelect({
  value,
  onChange,
  apenasAtivos,
  dataOverride,
}: {
  value?: number | null;
  onChange?: (id: number | null) => void;
  apenasAtivos: boolean;
  /** Lista já filtrada (ex.: destinos sem o dono de origem). */
  dataOverride?: { value: string; label: string }[];
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const donos = useOpcoes("proprietarios", apenasAtivos);
  const [novo, setNovo] = useState(false);
  const opcoes = dataOverride ?? (donos.data ?? []).map((d) => ({ value: String(d.id), label: d.nome }));
  return (
    <>
      <Flex gap={6}>
        <Select
          showSearch
          optionFilterProp="label"
          value={value != null ? String(value) : undefined}
          onChange={(v) => onChange?.(v ? Number(v) : null)}
          options={opcoes}
          notFoundContent={t("web.common.no_results")}
          style={{ flex: 1, minWidth: 0 }}
        />
        <Tooltip title={t("web.owners.new")}>
          <Button icon={<PlusOutlined />} onClick={() => setNovo(true)} aria-label={t("web.owners.new")} />
        </Tooltip>
      </Flex>
      <OwnerFormModal
        opened={novo}
        owner={null}
        onClose={() => setNovo(false)}
        onSaved={async (o: Owner) => {
          await queryClient.invalidateQueries({ queryKey: ["opcoes", "proprietarios"] });
          onChange?.(o.id);
        }}
      />
    </>
  );
}

/** Campos técnicos, de produção e de localização — comuns a "Adicionar
 *  lote" e "Editar lote" (mesmos campos que os dois formulários da app atual).
 *  Tem de estar dentro de um `<Form>`. */
export function CamposLote({ producao }: { producao: ReactNode }) {
  const t = useT();
  const contentores = useOpcoes("contentores");
  return (
    <>
      <Secao titulo={t("add_stock.section.technical")}>
        <Row gutter={12}>
          <Col xs={12} md={6}>
            <Form.Item name="motilidade" label={t("stock.motility_pct")}>
              <InputNumber min={0} max={100} style={{ width: "100%" }} inputMode="numeric" />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="concentracao" label={t("stock.concentration")}>
              <InputNumber min={0} style={{ width: "100%" }} inputMode="numeric" />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="qualidade" label={t("stock.quality_text")}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="cor" label={t("stock.color")}>
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="certificado" label={t("stock.certificate")}>
              <Segmented
                block
                options={[
                  { value: "Sim", label: t("common.yes") },
                  { value: "Não", label: t("common.no") },
                ]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="dose" label={t("stock.dose")}>
              <Input />
            </Form.Item>
          </Col>
        </Row>
      </Secao>

      <Secao titulo={t("add_stock.section.production")}>{producao}</Secao>

      <Secao titulo={t("web.stock.add.location")}>
        {contentores.data && contentores.data.length === 0 ? (
          <Typography.Text type="danger">{t("add_stock.no_containers")}</Typography.Text>
        ) : (
          <Row gutter={12}>
            <Col xs={24} sm={8}>
              <Form.Item name="contentor_id" label={t("label.container")} rules={[{ required: true, message: t("error.container_required") }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  options={(contentores.data ?? []).map((c) => ({ value: c.id, label: c.nome }))}
                />
              </Form.Item>
            </Col>
            <Col xs={12} sm={8}>
              <Form.Item name="canister" label={t("label.canister")} rules={[{ required: true }]}>
                <Select options={CANISTERS.map((c) => ({ value: Number(c), label: c }))} />
              </Form.Item>
            </Col>
            <Col xs={12} sm={8}>
              <Form.Item name="andar" label={t("label.floor_required").replace(" *", "")} rules={[{ required: true }]}>
                <Segmented
                  block
                  options={[
                    { value: 1, label: t("web.stock.floor", { n: 1 }) },
                    { value: 2, label: t("web.stock.floor", { n: 2 }) },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
        )}
      </Secao>

      <Secao titulo={t("label.notes")}>
        <Form.Item name="observacoes">
          <Input.TextArea autoSize={{ minRows: 2 }} aria-label={t("label.notes")} />
        </Form.Item>
      </Secao>
    </>
  );
}

/** Editar lote (só Administrador). */
export function LoteFormModal({ opened, lote, onClose }: { opened: boolean; lote: Lote; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const editar = useEditarLote();
  const [, setParams] = useSearchParams();
  const [form] = Form.useForm<LoteEdicao>();
  const garanhaoAtual = Form.useWatch("garanhao", form);
  const ajuda = useAjudaGaranhao(garanhaoAtual);

  const inicial: LoteEdicao = {
    ...camposVazios(),
    garanhao: lote.garanhao_nome ?? "",
    dono_id: lote.dono_id,
    data_embriovet: lote.data_embriovet ?? "",
    origem_externa: lote.origem_externa ?? "",
    qualidade: lote.qualidade ?? "",
    concentracao: lote.concentracao ?? 0,
    motilidade: lote.motilidade ?? 0,
    certificado: lote.certificado === "Sim" ? "Sim" : "Não",
    dose: lote.dose ?? "",
    cor: lote.cor ?? "",
    contentor_id: lote.contentor_id,
    canister: lote.canister ?? 1,
    andar: lote.andar === 2 ? 2 : 1,
    observacoes: lote.observacoes ?? "",
    palhetas_produzidas: lote.palhetas_produzidas ?? 0,
    existencia_atual: lote.existencia_atual ?? 0,
  };

  const guardar = async (dados: LoteEdicao) => {
    try {
      const atualizado = await editar.mutateAsync({ id: lote.id, ...inicial, ...dados });
      notifySuccess(t("web.stock.updated"));
      onClose();
      // Mudou de garanhão: a lista passa para o garanhão novo, com o lote aberto.
      if (atualizado.garanhao_nome !== lote.garanhao_nome) {
        setParams(
          (p) => {
            const r = new URLSearchParams(p);
            r.set("garanhao", atualizado.garanhao_nome);
            r.set("lote", String(lote.id));
            r.delete("dono");
            return r;
          },
          { replace: true },
        );
      }
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Modal
      open={opened}
      onCancel={onClose}
      title={t("stock.edit_title")}
      okText={t("btn.save_changes")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={editar.isPending}
      width={isMobile ? "100%" : 860}
      style={isMobile ? { top: 0, maxWidth: "100%", margin: 0, paddingBottom: 0 } : undefined}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={guardar} initialValues={inicial} preserve={false}>
        <Secao titulo={t("web.stock.add.identification")} primeiro>
          <Row gutter={12}>
            <Col xs={24} sm={12}>
              <Form.Item
                name="garanhao"
                label={t("label.garanhao")}
                extra={ajuda}
                rules={[{ required: true, whitespace: true, message: t("error.stallion_required") }]}
              >
                <GaranhaoInput />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item
                name="dono_id"
                label={t("label.owner")}
                extra={t("web.stock.edit_owner_only_active")}
                rules={[{ required: true, message: t("web.stock.error.owner_required") }]}
              >
                <DonoSelect apenasAtivos />
              </Form.Item>
            </Col>
          </Row>
        </Secao>
        <CamposLote
          producao={
            <Row gutter={12}>
              <Col xs={12} md={6}>
                <Form.Item name="data_embriovet" label={t("stock.prod_date")}>
                  <Input />
                </Form.Item>
              </Col>
              <Col xs={12} md={6}>
                <Form.Item name="origem_externa" label={t("stock.external_origin")}>
                  <Input />
                </Form.Item>
              </Col>
              <Col xs={12} md={6}>
                <Form.Item name="palhetas_produzidas" label={t("stock.straws_produced")}>
                  <InputNumber min={0} style={{ width: "100%" }} inputMode="numeric" />
                </Form.Item>
              </Col>
              <Col xs={12} md={6}>
                <Form.Item name="existencia_atual" label={t("stock.current_stock")}>
                  <InputNumber min={0} style={{ width: "100%" }} inputMode="numeric" />
                </Form.Item>
              </Col>
            </Row>
          }
        />
      </Form>
    </Modal>
  );
}
