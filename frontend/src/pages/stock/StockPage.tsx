import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button, Group, Tabs, Tooltip } from "@mantine/core";
import { PageHeader } from "../../components/ds";
import { IconFileImport, IconPlus } from "@tabler/icons-react";

import { useT } from "../../i18n/I18n";
import { NotMigratedPage } from "../NotMigratedPage";
import { LotesTab } from "./LotesTab";
import { GaranhoesTab } from "./GaranhoesTab";
import { TransferenciasTab } from "./transfer/TransferenciasTab";

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
  const { tab } = useParams();
  const [params] = useSearchParams();

  if (!tab || !TABS.some((x) => x.id === tab)) return <Navigate to="/stock-semen/lotes" replace />;

  const novoLote = () => {
    const g = params.get("garanhao");
    navigate(`/stock-semen/novo${g ? `?garanhao=${encodeURIComponent(g)}` : ""}`);
  };

  return (
    <>
      <PageHeader
        titulo={t("web.nav.stock_semen")}
        acoes={
          // "Adicionar lote"/"Importar" só no separador Lotes, como na app atual.
          tab === "lotes" && (
          <Group gap="xs" visibleFrom="sm" wrap="nowrap">
            <Tooltip label={t("web.not_migrated.title")}>
              <Button variant="default" leftSection={<IconFileImport size={16} />} data-disabled onClick={(e) => e.preventDefault()}>
                {t("web.stock.import")}
              </Button>
            </Tooltip>
            <Button leftSection={<IconPlus size={16} />} onClick={novoLote}>
              {t("web.stock.add")}
            </Button>
          </Group>
          )
        }
      />

      <Tabs value={tab} onChange={(v) => v && navigate(`/stock-semen/${v}`)} keepMounted={false}>
        <Tabs.List mb="lg" className="tabs-scroll">
          {TABS.map((x) => (
            <Tabs.Tab key={x.id} value={x.id}>
              {t(x.label)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        <Tabs.Panel value="lotes">
          <LotesTab onNovoLote={novoLote} />
        </Tabs.Panel>
        <Tabs.Panel value="garanhoes">
          <GaranhoesTab />
        </Tabs.Panel>
        <Tabs.Panel value="mapa">
          <NotMigratedPage />
        </Tabs.Panel>
        <Tabs.Panel value="transferencias">
          <TransferenciasTab />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
