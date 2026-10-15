import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button, Card, Space, Tabs, Tooltip } from "antd";
import { ImportOutlined, PlusOutlined } from "@ant-design/icons";

import { useT } from "../../i18n/I18n";
import { PageHeader } from "../../components/ds";
import { useIsMobile } from "../../components/responsive";
import { LotesTab } from "./LotesTab";
import { GaranhoesTab } from "./GaranhoesTab";
import { TransferenciasTab } from "./transfer/TransferenciasTab";
import { MapaTab } from "./mapa/MapaTab";

// Os mesmos 4 separadores de `stock_semen_page.py`, pela mesma ordem.
const TABS = [
  { id: "lotes", label: "web.stock.tab.lotes" },
  { id: "garanhoes", label: "web.stock.tab.garanhoes" },
  { id: "mapa", label: "web.stock.tab.mapa" },
  { id: "transferencias", label: "web.stock.tab.transferencias" },
];

export function StockPage() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { tab } = useParams();
  const [params] = useSearchParams();

  if (!tab || !TABS.some((x) => x.id === tab)) return <Navigate to="/stock-semen/lotes" replace />;

  const novoLote = () => {
    const g = params.get("garanhao");
    navigate(`/stock-semen/novo${g ? `?garanhao=${encodeURIComponent(g)}` : ""}`);
  };

  const conteudo = (id: string) =>
    id === "lotes" ? (
      <LotesTab onNovoLote={novoLote} />
    ) : id === "garanhoes" ? (
      <GaranhoesTab />
    ) : id === "mapa" ? (
      <MapaTab />
    ) : (
      <TransferenciasTab />
    );

  return (
    <Card size="small">
      <PageHeader
        titulo={t("web.nav.stock_semen")}
        acoes={
          // "Adicionar lote"/"Importar" só no separador Lotes, como na app atual.
          tab === "lotes" &&
          !isMobile && (
            <Space>
              <Tooltip title={t("web.not_migrated.title")}>
                <Button icon={<ImportOutlined />} disabled>
                  {t("web.stock.import")}
                </Button>
              </Tooltip>
              <Button type="primary" icon={<PlusOutlined />} onClick={novoLote}>
                {t("web.stock.add")}
              </Button>
            </Space>
          )
        }
      />
      <Tabs
        activeKey={tab}
        onChange={(v) => navigate(`/stock-semen/${v}`)}
        destroyOnHidden
        items={TABS.map((x) => ({ key: x.id, label: t(x.label), children: conteudo(x.id) }))}
      />
    </Card>
  );
}
