import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Form, Input, Selector, TextArea } from "antd-mobile";

import type { Owner } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { abrirAoTocar, Cabecalho, irParaErro, FolhaEcraInteiro, NumeroCampo, PickerCampo, SeletorPesquisa } from "../../components/mobile";
import { OwnerFormModal } from "../owners/OwnerFormModal";
import { useOpcoes, type Lote, type LoteEdicao, type LoteNovo } from "./api";
import { CANISTERS, camposVazios, inicialEdicao, useAjudaGaranhao, useGuardarEdicao } from "./LoteForm";
import { useGuardarNovo } from "./AddLotePage";

type FormInstance = ReturnType<typeof Form.useForm>[0];

/* Formulários de lote no telemóvel (Ant Design Mobile): os mesmos campos e
 * regras que as versões de computador em `LoteForm`/`AddLotePage`. */

/** Garanhão (escolher ou escrever um novo) e proprietário (com "+ novo"). */
function Identificacao({
  form,
  apenasAtivos,
  donoLabel,
  donoAjuda,
}: {
  form: FormInstance;
  apenasAtivos: boolean;
  donoLabel: string;
  donoAjuda?: string;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const garanhoes = useOpcoes("garanhoes");
  const donos = useOpcoes("proprietarios", apenasAtivos);
  const ajuda = useAjudaGaranhao(Form.useWatch("garanhao", form));
  const [novoDono, setNovoDono] = useState(false);

  return (
    <>
      <Cabecalho>{t("web.stock.add.identification")}</Cabecalho>
      <Form.Item
        name="garanhao"
        label={t("label.garanhao")}
        description={ajuda}
        rules={[{ required: true, whitespace: true, message: t("error.stallion_required") }]}
        arrow
        onClick={abrirAoTocar}
      >
        <SeletorPesquisa<string>
          titulo={t("label.garanhao")}
          placeholder={t("add_stock.stallion_placeholder")}
          opcoes={(garanhoes.data ?? []).map((g) => ({ value: g.nome, label: g.nome }))}
          novo={(texto) => texto}
        />
      </Form.Item>
      <Form.Item
        name="dono_id"
        label={donoLabel}
        description={donoAjuda}
        rules={[{ required: true, message: t("web.stock.error.owner_required") }]}
        arrow
        onClick={abrirAoTocar}
      >
        <SeletorPesquisa<number>
          titulo={donoLabel}
          opcoes={(donos.data ?? []).map((d) => ({ value: d.id, label: d.nome }))}
          acao={{ texto: t("web.owners.new"), onClick: () => setNovoDono(true) }}
        />
      </Form.Item>
      <OwnerFormModal
        opened={novoDono}
        owner={null}
        onClose={() => setNovoDono(false)}
        onSaved={async (o: Owner) => {
          await queryClient.invalidateQueries({ queryKey: ["opcoes", "proprietarios"] });
          form.setFieldValue("dono_id", o.id);
        }}
      />
    </>
  );
}

/** Dados técnicos, produção (varia entre novo/editar), localização e notas. */
function Campos({ producao }: { producao: ReactNode }) {
  const t = useT();
  const contentores = useOpcoes("contentores");
  const simNao = [
    { value: "Sim", label: t("common.yes") },
    { value: "Não", label: t("common.no") },
  ];
  // Selector devolve listas; o formulário guarda o valor simples.
  const umSo = { getValueProps: (v: unknown) => ({ value: v == null ? [] : [v] }), normalize: (v: unknown[]) => v[0] };

  return (
    <>
      <Cabecalho>{t("add_stock.section.technical")}</Cabecalho>
      <Form.Item name="motilidade" label={t("stock.motility_pct")}>
        <NumeroCampo max={100} />
      </Form.Item>
      <Form.Item name="concentracao" label={t("stock.concentration")}>
        <NumeroCampo />
      </Form.Item>
      <Form.Item name="qualidade" label={t("stock.quality_text")}>
        <Input clearable />
      </Form.Item>
      <Form.Item name="cor" label={t("stock.color")}>
        <Input clearable />
      </Form.Item>
      <Form.Item name="dose" label={t("stock.dose")}>
        <Input clearable />
      </Form.Item>
      <Form.Item name="certificado" label={t("stock.certificate")} {...umSo}>
        <Selector options={simNao} showCheckMark={false} style={{ "--padding": "4px 14px" } as React.CSSProperties} />
      </Form.Item>

      <Cabecalho>{t("add_stock.section.production")}</Cabecalho>
      {producao}

      <Cabecalho>{t("web.stock.add.location")}</Cabecalho>
      {contentores.data && contentores.data.length === 0 ? (
        <Form.Item>
          <span style={{ color: "var(--adm-color-danger)" }}>{t("add_stock.no_containers")}</span>
        </Form.Item>
      ) : (
        <>
          <Form.Item
            name="contentor_id"
            label={t("label.container")}
            rules={[{ required: true, message: t("error.container_required") }]}
            arrow
            onClick={abrirAoTocar}
          >
            <SeletorPesquisa<number>
              titulo={t("label.container")}
              opcoes={(contentores.data ?? [])
                .map((c) => ({ value: c.id, label: c.nome }))
                .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }))}
            />
          </Form.Item>
          <Form.Item name="canister" label={t("label.canister")} rules={[{ required: true }]} arrow onClick={abrirAoTocar}>
            <PickerCampo<number> titulo={t("label.canister")} opcoes={CANISTERS.map((c) => ({ value: Number(c), label: c }))} />
          </Form.Item>
          <Form.Item
            name="andar"
            label={t("label.floor_required").replace(" *", "")}

            rules={[{ required: true }]}
            {...umSo}
          >
            <Selector
              showCheckMark={false}
              style={{ "--padding": "4px 14px" } as React.CSSProperties}
              options={[
                { value: 1, label: t("web.stock.floor", { n: 1 }) },
                { value: 2, label: t("web.stock.floor", { n: 2 }) },
              ]}
            />
          </Form.Item>
        </>
      )}

      <Cabecalho>{t("label.notes")}</Cabecalho>
      <Form.Item name="observacoes">
        <TextArea autoSize={{ minRows: 2, maxRows: 6 }} placeholder={t("label.notes")} />
      </Form.Item>
    </>
  );
}

/** "Adicionar lote" no telemóvel: página com o botão Guardar preso ao fundo. */
export function NovoLoteMobile() {
  const t = useT();
  const [params] = useSearchParams();
  const { guardar, aGuardar } = useGuardarNovo();
  const [form] = Form.useForm<LoteNovo>();

  return (
    <>
      <Form
        form={form}
        layout="horizontal"
        style={{ "--prefix-width": "7.5em" } as React.CSSProperties}
        onFinish={guardar}
        onFinishFailed={irParaErro}
        initialValues={{ ...camposVazios(), garanhao: params.get("garanhao") ?? "", palhetas: 0 }}
      >
        <Identificacao form={form} apenasAtivos={false} donoLabel={t("add_stock.owner_semen").replace(" *", "")} />
        <Campos
          producao={
            <>
              <Form.Item name="data_embriovet" label={t("stock.prod_date")}>
                <Input clearable />
              </Form.Item>
              <Form.Item
                name="palhetas"
                label={t("stock.straws_produced")}
                rules={[{ required: true, type: "number", min: 1, message: t("error.straws_positive") }]}
              >
                <NumeroCampo />
              </Form.Item>
              <Form.Item name="origem_externa" label={t("stock.external_origin")}>
                <Input clearable />
              </Form.Item>
            </>
          }
        />
      </Form>
      {/* Fora do Form, para ficar preso ao fundo enquanto se desliza. */}
      <div style={{ position: "sticky", bottom: 0, padding: 12, background: "#f5f5f5", borderTop: "1px solid #eee" }}>
        <Button block color="primary" size="large" loading={aGuardar} onClick={() => form.submit()}>
          {t("btn.save")}
        </Button>
      </div>
    </>
  );
}

/** "Editar lote" no telemóvel (só Administrador): ecrã inteiro. */
export function EditarLoteMobile({ opened, lote, onClose }: { opened: boolean; lote: Lote; onClose: () => void }) {
  const t = useT();
  const { guardar, aGuardar } = useGuardarEdicao(lote, onClose);
  const [form] = Form.useForm<LoteEdicao>();

  return (
    <FolhaEcraInteiro
      visible={opened}
      titulo={t("stock.edit_title")}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText={t("btn.save")}
      loading={aGuardar}
    >
      <Form
        form={form}
        layout="horizontal"
        style={{ "--prefix-width": "7.5em" } as React.CSSProperties}
        onFinish={guardar}
        onFinishFailed={irParaErro}
        initialValues={inicialEdicao(lote)}
      >
        <Identificacao form={form} apenasAtivos donoLabel={t("label.owner")} donoAjuda={t("web.stock.edit_owner_only_active")} />
        <Campos
          producao={
            <>
              <Form.Item name="data_embriovet" label={t("stock.prod_date")}>
                <Input clearable />
              </Form.Item>
              <Form.Item name="origem_externa" label={t("stock.external_origin")}>
                <Input clearable />
              </Form.Item>
              <Form.Item name="palhetas_produzidas" label={t("stock.straws_produced")}>
                <NumeroCampo />
              </Form.Item>
              <Form.Item name="existencia_atual" label={t("stock.current_stock")}>
                <NumeroCampo />
              </Form.Item>
            </>
          }
        />
      </Form>
    </FolhaEcraInteiro>
  );
}
