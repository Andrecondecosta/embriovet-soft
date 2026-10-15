import { useState } from "react";
import { Alert, Button, Flex, Space, Spin, Statistic, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { Button as MButton, DotLoading, Grid } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { useNotifyError } from "../../components/errors";
import { baixarBackup, useResumoBackup } from "./api";

/** Cópia de segurança (só Administrador): ZIP com todos os dados, gerado
 *  na hora — como o separador da app atual. */
export function BackupTab() {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const resumo = useResumoBackup();
  const [aGerar, setAGerar] = useState(false);

  const descarregar = async () => {
    setAGerar(true);
    try {
      await baixarBackup();
    } catch (err) {
      notifyError(err);
    } finally {
      setAGerar(false);
    }
  };

  const numeros = resumo.data
    ? [
        [t("backup.count.lots"), resumo.data.lotes],
        [t("backup.count.owners"), resumo.data.proprietarios],
        [t("backup.count.animals"), resumo.data.animais],
        [t("backup.count.inseminations"), resumo.data.inseminacoes],
        [t("backup.count.stays"), resumo.data.estadias],
      ]
    : [];

  if (isMobile)
    return (
      <div style={{ padding: 12 }}>
        <div style={{ color: "#666", marginBottom: 12 }}>{t("backup.help")}</div>
        {resumo.isPending ? (
          <DotLoading />
        ) : (
          <Grid columns={3} gap={8} style={{ marginBottom: 12 }}>
            {numeros.map(([label, n]) => (
              <Grid.Item key={String(label)} style={{ background: "#fff", borderRadius: 8, padding: "10px 4px", textAlign: "center" }}>
                <div style={{ fontSize: 16, fontWeight: 700 }}>{n}</div>
                <div style={{ fontSize: 10, color: "#999" }}>{label}</div>
              </Grid.Item>
            ))}
          </Grid>
        )}
        <MButton block color="primary" size="large" loading={aGerar} loadingText={t("web.backup.preparing")} onClick={descarregar}>
          {t("backup.download")}
        </MButton>
        <div style={{ color: "#999", fontSize: 12, marginTop: 12 }}>{t("backup.advice")}</div>
      </div>
    );

  return (
    <Space orientation="vertical" size={16} style={{ width: "100%", maxWidth: 760 }}>
      <Typography.Text type="secondary">{t("backup.help")}</Typography.Text>
      {resumo.isPending ? (
        <Spin />
      ) : (
        <Flex gap={32} wrap>
          {numeros.map(([label, n]) => (
            <Statistic key={String(label)} title={label} value={n} />
          ))}
        </Flex>
      )}
      {resumo.data && (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t("backup.count.tables", { n: resumo.data.tabelas })}
        </Typography.Text>
      )}
      <div>
        <Button type="primary" icon={<DownloadOutlined />} loading={aGerar} onClick={descarregar}>
          {aGerar ? t("web.backup.preparing") : t("backup.download")}
        </Button>
      </div>
      <Alert type="info" showIcon title={t("backup.advice")} />
    </Space>
  );
}
