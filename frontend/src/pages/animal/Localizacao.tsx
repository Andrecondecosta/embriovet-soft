import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Flex, Input, Modal, Typography } from "antd";
import { EnvironmentOutlined } from "@ant-design/icons";
import { Button as MButton, Input as MInput, Popup, TextArea } from "antd-mobile";

import { api } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, notifyWarning, useNotifyError } from "../../components/errors";
import type { Localizacao } from "./api";

/** Abre o caminho até lá no Google Maps (no telemóvel, na app de mapas). */
export const abrirMapa = (link: string) => {
  window.open(link, "_blank", "noopener");
};

/**
 * Égua externa: onde está (texto) e o botão "Abrir no mapa"; "Mudar" deixa
 * escrever o sítio, colar um link do Google Maps ou usar a localização do
 * telemóvel (estando junto da égua).
 */
export function LocalizacaoExterna({ animalId, loc }: { animalId: number; loc: Localizacao }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const queryClient = useQueryClient();
  const [aberto, setAberto] = useState(false);
  const [texto, setTexto] = useState("");
  const [mapa, setMapa] = useState("");
  const [aProcurar, setAProcurar] = useState(false);

  const abrir = () => {
    setTexto(loc.texto ?? "");
    setMapa(loc.mapa ?? "");
    setAberto(true);
  };
  const guardar = useMutation({
    mutationFn: () => api(`/estadias/${loc.estadia_id}/localizacao`, "PUT", { texto, mapa }),
    onSuccess: () => {
      for (const k of [["animal", animalId], ["trabalho"]]) queryClient.invalidateQueries({ queryKey: k });
      notifySuccess(t("web.location.saved"));
      setAberto(false);
    },
    onError: notifyError,
  });
  const usarAqui = () => {
    if (!navigator.geolocation) {
      notifyWarning(t("web.location.error.gps"));
      return;
    }
    setAProcurar(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setMapa(`${p.coords.latitude.toFixed(6)},${p.coords.longitude.toFixed(6)}`);
        setAProcurar(false);
      },
      () => {
        setAProcurar(false);
        notifyWarning(t("web.location.error.gps"));
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const resumo = (
    <span style={{ color: "#666", fontSize: 13 }}>
      <EnvironmentOutlined /> {loc.texto || t("web.location.none")}
      {loc.mapa && <span style={{ color: "#999" }}> · {t("web.location.has_point")}</span>}
    </span>
  );

  if (isMobile)
    return (
      <div style={{ margin: "4px 0 6px" }}>
        {resumo}
        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          {loc.link && (
            <MButton size="small" color="primary" fill="outline" onClick={() => abrirMapa(loc.link!)}>
              {t("web.location.open_map")}
            </MButton>
          )}
          <MButton size="small" fill="outline" onClick={abrir}>
            {t("web.location.change")}
          </MButton>
        </div>
        <Popup visible={aberto} onMaskClick={() => setAberto(false)} bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16 }}>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>{t("web.location.title")}</div>
          <div style={{ color: "#999", margin: "8px 0 4px" }}>{t("web.location.place")}</div>
          <TextArea value={texto} onChange={setTexto} autoSize={{ minRows: 1, maxRows: 3 }} maxLength={300} placeholder={t("web.location.place_help")} />
          <div style={{ color: "#999", margin: "10px 0 4px" }}>{t("web.location.point")}</div>
          <MInput value={mapa} onChange={setMapa} clearable placeholder={t("web.location.point_help")} />
          <MButton block size="small" fill="outline" loading={aProcurar} style={{ marginTop: 8 }} onClick={usarAqui}>
            <EnvironmentOutlined /> {t("web.location.use_here")}
          </MButton>
          <MButton block color="primary" loading={guardar.isPending} style={{ marginTop: 14 }} onClick={() => guardar.mutate()}>
            {t("btn.save")}
          </MButton>
        </Popup>
      </div>
    );

  return (
    <Flex align="center" gap={8} wrap style={{ marginTop: 6 }}>
      {resumo}
      {loc.link && (
        <Button size="small" icon={<EnvironmentOutlined />} onClick={() => abrirMapa(loc.link!)}>
          {t("web.location.open_map")}
        </Button>
      )}
      <Button size="small" type="link" onClick={abrir}>
        {t("web.location.change")}
      </Button>
      <Modal
        open={aberto}
        onCancel={() => setAberto(false)}
        title={t("web.location.title")}
        okText={t("btn.save")}
        cancelText={t("web.common.cancel")}
        onOk={() => guardar.mutate()}
        confirmLoading={guardar.isPending}
        destroyOnHidden
      >
        <Flex vertical gap={12}>
          <div>
            <Typography.Text type="secondary">{t("web.location.place")}</Typography.Text>
            <Input.TextArea value={texto} onChange={(e) => setTexto(e.target.value)} autoSize={{ minRows: 1, maxRows: 3 }} maxLength={300} placeholder={t("web.location.place_help")} />
          </div>
          <div>
            <Typography.Text type="secondary">{t("web.location.point")}</Typography.Text>
            <Flex gap={8}>
              <Input value={mapa} onChange={(e) => setMapa(e.target.value)} allowClear placeholder={t("web.location.point_help")} />
              <Button icon={<EnvironmentOutlined />} loading={aProcurar} onClick={usarAqui}>
                {t("web.location.use_here")}
              </Button>
            </Flex>
          </div>
        </Flex>
      </Modal>
    </Flex>
  );
}
