import { useState } from "react";
import dayjs from "dayjs";
import { Button, DatePicker, Flex, Modal, Radio, Typography } from "antd";
import { ExperimentOutlined } from "@ant-design/icons";
import { Button as MButton, List, Popup, Selector } from "antd-mobile";

import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { useIsAdmin } from "../components/User";
import { useNotifyError } from "../components/errors";
import { descarregar } from "../components/download";
import { DataCampo } from "../components/mobile";

type Formato = "xlsx" | "csv";

/** "Dados para estudo": exames, inseminações (por lote) e diagnósticos por
 *  etapa, com códigos em vez de nomes. Só para Administradores. */
export function DadosEstudo() {
  const t = useT();
  const mobile = useIsMobile();
  const admin = useIsAdmin();
  const notifyError = useNotifyError();
  const [aberto, setAberto] = useState(false);
  const [inicio, setInicio] = useState<string | null>(null);
  const [fim, setFim] = useState<string | null>(null);
  const [formato, setFormato] = useState<Formato>("xlsx");
  const [aDescarregar, setADescarregar] = useState(false);
  if (!admin) return null;

  const descarregarDados = async () => {
    const p = new URLSearchParams({ formato });
    if (inicio) p.set("inicio", inicio);
    if (fim) p.set("fim", fim);
    setADescarregar(true);
    try {
      await descarregar(`/relatorios/estudo?${p}`, `dados_estudo.${formato}`);
      setAberto(false);
    } catch (err) {
      notifyError(err);
    } finally {
      setADescarregar(false);
    }
  };
  const formatos = [
    { value: "xlsx", label: "Excel" },
    { value: "csv", label: "CSV" },
  ];

  if (mobile)
    return (
      <>
        <MButton size="small" onClick={() => setAberto(true)}>
          {t("web.study.button")}
        </MButton>
        <Popup
          visible={aberto}
          onMaskClick={() => setAberto(false)}
          bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16 }}
        >
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>{t("web.study.title")}</div>
          <div style={{ color: "#999", fontSize: 12, marginBottom: 10 }}>{t("web.study.help")}</div>
          <List style={{ "--border-top": "none" } as React.CSSProperties}>
            <List.Item prefix={t("reports.date_start")} arrow>
              <DataCampo value={inicio} limpar onChange={setInicio} />
            </List.Item>
            <List.Item prefix={t("reports.date_end")} arrow>
              <DataCampo value={fim} limpar onChange={setFim} />
            </List.Item>
          </List>
          <Selector columns={2} value={[formato]} onChange={(v) => v[0] && setFormato(v[0] as Formato)} options={formatos} />
          <MButton block color="primary" style={{ marginTop: 12 }} loading={aDescarregar} onClick={descarregarDados}>
            {t("web.reports.export.download")}
          </MButton>
        </Popup>
      </>
    );

  return (
    <>
      <Button icon={<ExperimentOutlined />} onClick={() => setAberto(true)}>
        {t("web.study.button")}
      </Button>
      <Modal
        open={aberto}
        onCancel={() => setAberto(false)}
        onOk={descarregarDados}
        okText={t("web.reports.export.download")}
        cancelText={t("web.common.cancel")}
        okButtonProps={{ loading: aDescarregar }}
        title={t("web.study.title")}
        width={480}
      >
        <Flex vertical gap={12}>
          <Typography.Text type="secondary">{t("web.study.help")}</Typography.Text>
          <DatePicker.RangePicker
            format="DD/MM/YYYY"
            allowEmpty={[true, true]}
            value={[inicio ? dayjs(inicio) : null, fim ? dayjs(fim) : null]}
            onChange={(v) => {
              setInicio(v?.[0]?.format("YYYY-MM-DD") ?? null);
              setFim(v?.[1]?.format("YYYY-MM-DD") ?? null);
            }}
          />
          <Radio.Group optionType="button" value={formato} onChange={(e) => setFormato(e.target.value)} options={formatos} />
        </Flex>
      </Modal>
    </>
  );
}
