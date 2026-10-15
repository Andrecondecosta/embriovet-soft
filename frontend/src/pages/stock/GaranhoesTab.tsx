import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Input, Table, Typography } from "antd";
import { RightOutlined, SearchOutlined } from "@ant-design/icons";

import { useT } from "../../i18n/I18n";
import { useErrorMessage } from "../../components/errors";
import { useIsMobile } from "../../components/responsive";
import { Lista } from "../../components/Lista";
import { useGaranhoesStock, type GaranhaoStock } from "./api";

/** Separador Garanhões: garanhões com stock disponível. A ficha do
 *  animal ainda não foi migrada — por isso o clique abre os lotes. */
export function GaranhoesTab() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const { data, isPending, isError, error } = useGaranhoesStock();
  const [pesquisa, setPesquisa] = useState("");

  const lista = useMemo(() => {
    const q = pesquisa.trim().toLowerCase();
    return (data ?? []).filter((g) => !q || g.garanhao.toLowerCase().includes(q));
  }, [data, pesquisa]);

  const abrir = (g: GaranhaoStock) => navigate(`/stock-semen/lotes?garanhao=${encodeURIComponent(g.garanhao)}`);
  const vazio = data && !data.length ? t("web.stock.garanhoes.empty") : t("web.common.no_results");

  if (isError) return <Alert type="error" title={errorMessage(error)} showIcon />;

  return (
    <>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
        {t("web.stock.garanhoes.hint")}
      </Typography.Paragraph>
      <Input
        allowClear
        prefix={<SearchOutlined />}
        placeholder={t("web.stock.garanhoes.search")}
        value={pesquisa}
        onChange={(e) => setPesquisa(e.target.value)}
        style={{ width: isMobile ? "100%" : 320, marginBottom: 12 }}
      />
      {isMobile ? (
        <Lista
          itens={lista}
          chave={(g) => `${g.animal_id}-${g.garanhao}`}
          carregando={isPending}
          vazio={vazio}
          onClick={abrir}
          render={(g) => ({
            titulo: g.garanhao,
            descricao: `${g.palhetas} ${t("label.straws")} · ${g.lotes} ${t("web.stock.kpi.lotes").toLowerCase()} · ${g.donos} ${t("web.stock.col.donos").toLowerCase()}`,
            extra: <RightOutlined style={{ color: "#bfbfbf" }} />,
          })}
        />
      ) : (
        <Table<GaranhaoStock>
          size="small"
          bordered
          loading={isPending}
          rowKey={(g) => `${g.animal_id}-${g.garanhao}`}
          dataSource={lista}
          locale={{ emptyText: vazio }}
          pagination={{ pageSize: 50, hideOnSinglePage: true, size: "small" }}
          onRow={(g) => ({ onClick: () => abrir(g), style: { cursor: "pointer" } })}
          columns={[
            {
              title: t("label.garanhao"),
              dataIndex: "garanhao",
              render: (v) => <Typography.Text strong>{v}</Typography.Text>,
              sorter: (a, b) => a.garanhao.localeCompare(b.garanhao),
            },
            { title: t("web.stock.kpi.palhetas"), dataIndex: "palhetas", align: "right", sorter: (a, b) => a.palhetas - b.palhetas },
            { title: t("web.stock.kpi.lotes"), dataIndex: "lotes", align: "right", sorter: (a, b) => a.lotes - b.lotes },
            { title: t("web.stock.col.donos"), dataIndex: "donos", align: "right", sorter: (a, b) => a.donos - b.donos },
          ]}
        />
      )}
    </>
  );
}
