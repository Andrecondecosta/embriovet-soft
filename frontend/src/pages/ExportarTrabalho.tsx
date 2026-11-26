import { useEffect, useState } from "react";
import dayjs, { type Dayjs } from "dayjs";
import { Checkbox, DatePicker, Flex, Modal, Segmented, Select, Typography } from "antd";
import { Button as MButton, Checkbox as MCheckbox, Popup, Selector } from "antd-mobile";

import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { notifySuccess, useNotifyError } from "../components/errors";
import { descarregar } from "../components/download";
import { DataCampo, SeletorPesquisa } from "../components/mobile";
import { FORMATO_DATA } from "../components/datas";
import { useOpcoes } from "./stock/api";

export type TipoTrabalho = "todos" | "tratamentos" | "consultas" | "urgentes";
export const TIPOS_TRABALHO: TipoTrabalho[] = ["todos", "tratamentos", "consultas", "urgentes"];
type Formato = "pdf" | "xlsx";
const ISO = "YYYY-MM-DD";

/** Atalhos de dias: hoje, amanhã, amanhã e depois. */
const ATALHOS = [
  { id: "today", de: 0, ate: 0 },
  { id: "tomorrow", de: 1, ate: 1 },
  { id: "next_two", de: 1, ate: 2 },
] as const;

/**
 * Exportar o Trabalho diário para dar ao tratador: as éguas de um
 * proprietário (ou de todos) a ver nuns dias, em PDF ou Excel — por dia,
 * com as em atraso no topo.
 */
export function ExportarTrabalho({ aberto, onClose }: { aberto: boolean; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const donos = useOpcoes("proprietarios", true);
  const [dono, setDono] = useState<number | null>(null);
  const [periodo, setPeriodo] = useState<[Dayjs, Dayjs]>([dayjs().add(1, "day"), dayjs().add(2, "day")]);
  const [tipo, setTipo] = useState<TipoTrabalho>("todos");
  const [formato, setFormato] = useState<Formato>("pdf");
  // Incluir (no topo) as éguas com tarefas em atraso.
  const [atrasadas, setAtrasadas] = useState(true);
  const [aExportar, setAExportar] = useState(false);

  useEffect(() => {
    if (aberto) setPeriodo([dayjs().add(1, "day"), dayjs().add(2, "day")]);
  }, [aberto]);

  const atalho = ATALHOS.find((a) => periodo[0].isSame(dayjs().add(a.de, "day"), "day") && periodo[1].isSame(dayjs().add(a.ate, "day"), "day"));
  const escolherAtalho = (id: string) => {
    const a = ATALHOS.find((x) => x.id === id);
    if (a) setPeriodo([dayjs().add(a.de, "day"), dayjs().add(a.ate, "day")]);
  };

  const exportar = async () => {
    setAExportar(true);
    try {
      const q = new URLSearchParams({
        inicio: periodo[0].format(ISO),
        fim: periodo[1].format(ISO),
        formato,
        tipo,
        atrasadas: String(atrasadas),
      });
      if (dono !== null) q.set("dono_id", String(dono));
      await descarregar(`/trabalho/exportar?${q}`, "trabalho");
      notifySuccess(t("web.reports.downloaded"));
      onClose();
    } catch (err) {
      notifyError(err);
    } finally {
      setAExportar(false);
    }
  };

  const opcoesDonos = (donos.data ?? []).map((d) => ({ value: d.id, label: d.nome }));
  const opcoesTipo = TIPOS_TRABALHO.map((x) => ({ value: x, label: t(`web.daily.type.${x}`) }));
  const opcoesAtalho = ATALHOS.map((a) => ({ value: a.id, label: t(`web.daily.export.${a.id}`) }));
  const opcoesFormato = [
    { value: "pdf", label: "PDF" },
    { value: "xlsx", label: "Excel" },
  ];

  if (isMobile)
    return (
      <Popup visible={aberto} onMaskClick={onClose} bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16, maxHeight: "85dvh", overflowY: "auto" }}>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>{t("web.daily.export.button")}</div>
        <div style={{ color: "#999", margin: "10px 0 6px" }}>{t("web.dashboard.owner")}</div>
        <SeletorPesquisa<number>
          titulo={t("web.dashboard.owner")}
          value={dono}
          onChange={(v) => setDono(v ?? null)}
          opcoes={opcoesDonos}
          placeholder={t("web.stays.animals.all")}
        />
        {dono !== null && (
          <a style={{ fontSize: 12 }} onClick={() => setDono(null)}>
            {t("web.stays.animals.all")}
          </a>
        )}
        <div style={{ color: "#999", margin: "10px 0 6px" }}>{t("web.daily.export.days")}</div>
        <Selector columns={3} value={atalho ? [atalho.id] : []} onChange={(v) => v[0] && escolherAtalho(v[0])} options={opcoesAtalho} />
        <Flex gap={8} align="center" style={{ marginTop: 8 }}>
          <DataCampo value={periodo[0].format(ISO)} onChange={(v) => v && setPeriodo([dayjs(v), dayjs(v).isAfter(periodo[1]) ? dayjs(v) : periodo[1]])} />
          –
          <DataCampo value={periodo[1].format(ISO)} min={periodo[0].toDate()} onChange={(v) => v && setPeriodo([periodo[0], dayjs(v)])} />
        </Flex>
        <div style={{ color: "#999", margin: "10px 0 6px" }}>{t("web.daily.type.label")}</div>
        <Selector columns={2} value={[tipo]} onChange={(v) => v[0] && setTipo(v[0])} options={opcoesTipo} />
        <div style={{ color: "#999", margin: "10px 0 6px" }}>{t("web.daily.export.format")}</div>
        <Selector columns={2} value={[formato]} onChange={(v) => v[0] && setFormato(v[0] as Formato)} options={opcoesFormato} />
        <div style={{ marginTop: 12 }}>
          <MCheckbox checked={atrasadas} onChange={setAtrasadas}>
            {t("web.daily.export.with_overdue")}
          </MCheckbox>
        </div>
        <MButton block color="primary" loading={aExportar} style={{ marginTop: 14 }} onClick={exportar}>
          {t("web.daily.export.button")}
        </MButton>
      </Popup>
    );

  return (
    <Modal
      open={aberto}
      onCancel={onClose}
      title={t("web.daily.export.button")}
      okText={t("web.daily.export.button")}
      cancelText={t("web.common.cancel")}
      onOk={exportar}
      confirmLoading={aExportar}
      width={520}
      destroyOnHidden
    >
      <Flex vertical gap={12}>
        <div>
          <Typography.Text type="secondary">{t("web.dashboard.owner")}</Typography.Text>
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            style={{ width: "100%", marginTop: 4 }}
            placeholder={t("web.stays.animals.all")}
            value={dono}
            onChange={(v) => setDono(v ?? null)}
            options={opcoesDonos}
          />
        </div>
        <div>
          <Typography.Text type="secondary">{t("web.daily.export.days")}</Typography.Text>
          <Segmented block style={{ marginTop: 4 }} value={atalho?.id ?? ""} onChange={(v) => escolherAtalho(String(v))} options={opcoesAtalho} />
          <DatePicker.RangePicker
            style={{ width: "100%", marginTop: 8 }}
            format={FORMATO_DATA}
            allowClear={false}
            value={periodo}
            onChange={(v) => v?.[0] && v[1] && setPeriodo([v[0], v[1]])}
          />
        </div>
        <div>
          <Typography.Text type="secondary">{t("web.daily.type.label")}</Typography.Text>
          <Segmented block style={{ marginTop: 4 }} value={tipo} onChange={(v) => setTipo(v as TipoTrabalho)} options={opcoesTipo} />
        </div>
        <div>
          <Typography.Text type="secondary">{t("web.daily.export.format")}</Typography.Text>
          <div style={{ marginTop: 4 }}>
            <Segmented value={formato} onChange={(v) => setFormato(v as Formato)} options={opcoesFormato} />
          </div>
        </div>
        <Checkbox checked={atrasadas} onChange={(e) => setAtrasadas(e.target.checked)}>
          {t("web.daily.export.with_overdue")}
        </Checkbox>
      </Flex>
    </Modal>
  );
}
