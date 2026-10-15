/**
 * AMOSTRA — a página dos Lotes no telemóvel feita com Ant Design Mobile
 * (aspeto de app nativa), para comparar com a versão atual no telemóvel.
 * Mesmos dados e API; só leitura. Endereço: /amostra-mobile
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  CapsuleTabs,
  Collapse,
  ConfigProvider,
  DotLoading,
  ErrorBlock,
  FloatingBubble,
  Grid,
  List,
  NavBar,
  Picker,
  Popup,
  Selector,
  Stepper,
  SwipeAction,
  Switch,
  TabBar,
  Tag,
  Toast,
} from "antd-mobile";
import ptBR from "antd-mobile/es/locales/pt-BR";
import { AddOutline, FilterOutline, RightOutline } from "antd-mobile-icons";
import {
  AppstoreOutlined,
  CalendarOutlined,
  EllipsisOutlined,
  ExperimentOutlined,
  HomeOutlined,
} from "@ant-design/icons";

import { useT } from "../../i18n/I18n";
import { useBrand } from "../../components/Brand";
import { dataCurta, dataHora } from "../../components/csv";
import { localizacao, referencia, useGaranhoesStock, useLotes, type Lote } from "../stock/api";

export default function AmostraMobile() {
  const { primary_color } = useBrand();
  // As janelas que sobem de baixo são desenhadas fora desta página: a cor
  // da marca tem de estar no documento, não só neste bloco.
  useEffect(() => {
    const raiz = document.documentElement.style;
    // Letra mais pequena do que o padrão do iPhone (17 px nas listas):
    // linhas a 13 px, descrições a 11 px — mais informação por ecrã. Não
    // descer mais: abaixo disto custa a ler na coudelaria/ao sol.
    const vars: Record<string, string> = {
      "--adm-color-primary": primary_color,
      "--adm-font-size-10": "15px",
      "--adm-font-size-9": "13px",
      "--adm-font-size-8": "13px",
      "--adm-font-size-7": "12px",
      "--adm-font-size-6": "12px",
      "--adm-font-size-main": "11px",
    };
    Object.entries(vars).forEach(([k, v]) => raiz.setProperty(k, v));
    return () => {
      Object.keys(vars).forEach((k) => raiz.removeProperty(k));
    };
  }, [primary_color]);
  return (
    <ConfigProvider locale={ptBR}>
      <div
        style={
          {
            height: "100dvh",
            display: "flex",
            flexDirection: "column",
            background: "#f5f5f5",
            maxWidth: 520,
            margin: "0 auto",
            boxShadow: "0 0 0 1px #eee",
          } as React.CSSProperties
        }
      >
        <App />
      </div>
    </ConfigProvider>
  );
}

function App() {
  const t = useT();
  const navigate = useNavigate();
  const [filtrosAbertos, setFiltrosAbertos] = useState(false);

  return (
    <>
      <NavBar
        back={null}
        right={<FilterOutline fontSize={22} onClick={() => setFiltrosAbertos(true)} />}
        style={{ background: "#fff", borderBottom: "1px solid #eee", flexShrink: 0 }}
      >
        {t("web.nav.stock_semen")}
      </NavBar>

      <div style={{ flex: 1, overflowY: "auto" }}>
        <CapsuleTabs defaultActiveKey="lotes" style={{ background: "#fff" }}>
          <CapsuleTabs.Tab title={t("web.stock.tab.lotes")} key="lotes" />
          <CapsuleTabs.Tab title={t("web.stock.tab.garanhoes")} key="garanhoes" disabled />
          <CapsuleTabs.Tab title={t("web.stock.tab.mapa")} key="mapa" disabled />
          <CapsuleTabs.Tab title={t("web.stock.tab.transferencias")} key="transferencias" disabled />
        </CapsuleTabs>
        <Lotes filtrosAbertos={filtrosAbertos} fecharFiltros={() => setFiltrosAbertos(false)} />
        <div style={{ textAlign: "center", padding: "16px 0 24px" }}>
          <Button size="small" fill="none" color="primary" onClick={() => navigate("/stock-semen/lotes")}>
            Voltar à versão atual
          </Button>
        </div>
      </div>

      {/* Barra de navegação em baixo, à mão do polegar. Cabem 5: as outras
          secções ficam em "Mais". */}
      <TabBar activeKey="stock" style={{ background: "#fff", borderTop: "1px solid #eee", flexShrink: 0 }} safeArea>
        <TabBar.Item key="dashboard" icon={<AppstoreOutlined />} title={t("web.nav.dashboard")} />
        <TabBar.Item key="estadias" icon={<HomeOutlined />} title={t("web.nav.estadias")} />
        <TabBar.Item key="trabalho" icon={<CalendarOutlined />} title={t("web.nav.trabalho_diario")} />
        <TabBar.Item key="stock" icon={<ExperimentOutlined />} title="Stock" />
        <TabBar.Item key="mais" icon={<EllipsisOutlined />} title="Mais" />
      </TabBar>
    </>
  );
}

function Lotes({ filtrosAbertos, fecharFiltros }: { filtrosAbertos: boolean; fecharFiltros: () => void }) {
  const t = useT();
  const garanhoes = useGaranhoesStock();
  const opcoes = useMemo(() => (garanhoes.data ?? []).filter((g) => g.no_seletor).map((g) => g.garanhao), [garanhoes.data]);
  const [garanhao, setGaranhao] = useState<string | null>(null);
  const [rodaAberta, setRodaAberta] = useState(false);
  const [donos, setDonos] = useState<string[]>([]);
  const [minimo, setMinimo] = useState(0);
  const [vazios, setVazios] = useState(false);
  const [aberto, setAberto] = useState<Lote | null>(null);

  const atual = garanhao && opcoes.includes(garanhao) ? garanhao : opcoes[0] ?? null;
  const lotes = useLotes(
    atual
      ? { garanhao: atual, donos: donos.filter((d) => d !== "sem").map(Number), semDono: donos.includes("sem"), minPalhetas: minimo, incluirVazios: vazios }
      : null,
  );
  const k = lotes.data?.kpis;

  if (garanhoes.isPending)
    return (
      <div style={{ textAlign: "center", padding: 32 }}>
        <DotLoading color="primary" />
      </div>
    );
  if (!atual) return <ErrorBlock status="empty" title={t("stock.none_registered")} description="" />;

  const amostra = () => {
    Toast.show({ content: "Amostra: só leitura" });
  };

  return (
    <>
      {/* Garanhão: toca e escolhe na roda, como nas apps do telemóvel. */}
      <List style={{ "--border-top": "none" } as React.CSSProperties}>
        <List.Item extra={atual} onClick={() => setRodaAberta(true)} arrow={<RightOutline />}>
          {t("label.garanhao")}
        </List.Item>
      </List>
      <Picker
        columns={[opcoes.map((g) => ({ label: g, value: g }))]}
        visible={rodaAberta}
        onClose={() => setRodaAberta(false)}
        value={[atual]}
        onConfirm={(v) => {
          if (v[0]) setGaranhao(String(v[0]));
          setDonos([]);
        }}
        title={t("web.stock.select_stallion")}
      />

      {/* Indicadores numa faixa só, sem caixas. */}
      <Grid columns={4} style={{ background: "#fff", margin: "8px 0", padding: "12px 4px" }}>
        {[
          [t("web.stock.kpi.lotes"), k?.lotes ?? "—"],
          [t("web.stock.kpi.palhetas"), k?.palhetas ?? "—"],
          [t("web.stock.kpi.proprietarios"), k?.proprietarios ?? "—"],
          ["Qualidade", k?.qualidade_media != null ? `${k.qualidade_media}%` : "—"],
        ].map(([label, valor]) => (
          <Grid.Item key={String(label)} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{valor}</div>
            <div style={{ fontSize: 10, color: "#999" }}>{label}</div>
          </Grid.Item>
        ))}
      </Grid>

      <Collapse>
        <Collapse.Panel key="donos" title={t("web.stock.by_owner")}>
          {(lotes.data?.por_proprietario ?? []).map((r) => (
            <div key={String(r.dono_id)} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
              <span>{r.proprietario_nome ?? t("common.no_owner")}</span>
              <b>{r.palhetas}</b>
            </div>
          ))}
        </Collapse.Panel>
      </Collapse>

      {/* Lotes: deslizar para a esquerda mostra as ações. */}
      <List header={t("stock.lots_detailed")} style={{ marginTop: 8 }}>
        {!lotes.data ? (
          <List.Item>
            <DotLoading />
          </List.Item>
        ) : !lotes.data.items.length ? (
          <List.Item>{t("stock.no_lots_filter")}</List.Item>
        ) : (
          lotes.data.items.map((l) => (
            <SwipeAction
              key={l.id}
              rightActions={[
                { key: "transferir", text: "Transferir", color: "primary", onClick: amostra },
                { key: "editar", text: t("btn.edit"), color: "warning", onClick: amostra },
              ]}
            >
              <List.Item
                onClick={() => setAberto(l)}
                description={`${l.proprietario_nome ?? t("common.no_owner")} · ${localizacao(l) ?? "—"} · M ${l.motilidade ?? 0}%`}
                extra={
                  <Tag color="primary" fill="outline">
                    {t("web.stock.straws_count", { count: l.existencia_atual ?? 0 })}
                  </Tag>
                }
              >
                {referencia(l) ?? t("common.no_reference")}
              </List.Item>
            </SwipeAction>
          ))
        )}
      </List>

      <FloatingBubble
        style={{ "--initial-position-bottom": "84px", "--initial-position-right": "20px", "--edge-distance": "20px" } as React.CSSProperties}
        onClick={amostra}
      >
        <AddOutline fontSize={28} />
      </FloatingBubble>

      {/* Filtros: janela que sobe de baixo. */}
      <Popup visible={filtrosAbertos} onMaskClick={fecharFiltros} bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16 }}>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 12 }}>{t("common.filters")}</div>
        <div style={{ color: "#999", fontSize: 13, marginBottom: 6 }}>{t("label.owner_plural")}</div>
        <Selector
          multiple
          columns={2}
          value={donos}
          onChange={setDonos}
          options={(lotes.data?.donos_disponiveis ?? []).map((d) => ({
            label: d.nome ?? t("common.no_owner"),
            value: d.id === null ? "sem" : String(d.id),
          }))}
        />
        <List style={{ marginTop: 12, "--border-top": "none", "--border-bottom": "none" } as React.CSSProperties}>
          <List.Item extra={<Stepper min={0} value={minimo} onChange={setMinimo} />}>{t("stock.min_straws")}</List.Item>
          <List.Item extra={<Switch checked={vazios} onChange={setVazios} />}>{t("stock.include_empty")}</List.Item>
        </List>
        <Button block color="primary" size="large" style={{ marginTop: 12 }} onClick={fecharFiltros}>
          OK
        </Button>
      </Popup>

      {/* Detalhe do lote: folha que sobe de baixo. */}
      <Popup
        visible={aberto !== null}
        onMaskClick={() => setAberto(null)}
        onClose={() => setAberto(null)}
        showCloseButton
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, maxHeight: "85vh", overflowY: "auto" }}
      >
        {aberto && (
          <>
            <div style={{ padding: "16px 16px 4px" }}>
              <div style={{ fontSize: 12, color: "#999" }}>
                {aberto.garanhao_nome} · #{aberto.id}
              </div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>{referencia(aberto) ?? t("common.no_reference")}</div>
            </div>
            <List>
              {(
                [
                  [t("label.owner"), aberto.proprietario_nome ?? t("common.no_owner")],
                  [t("web.stock.kpi.palhetas"), aberto.existencia_atual ?? 0],
                  [t("label.location"), localizacao(aberto) ?? "—"],
                  [t("stock.quality_label"), aberto.qualidade || "—"],
                  [t("stock.color"), aberto.cor || "—"],
                  [t("stock.concentration_label"), `${aberto.concentracao ?? 0} ${t("stock.million_ml")}`],
                  [t("stock.motility_label"), `${aberto.motilidade ?? 0}%`],
                  [t("stock.dose_label"), aberto.dose || "—"],
                  [t("stock.prod_date_label"), aberto.data_embriovet || "—"],
                  [t("stock.created_at_label"), dataHora(aberto.data_criacao)],
                ] as [string, string | number][]
              ).map(([label, valor]) => (
                <List.Item key={label} extra={valor}>
                  {label}
                </List.Item>
              ))}
            </List>
            <div style={{ display: "flex", gap: 8, padding: 16 }}>
              <Button block color="primary" onClick={amostra}>
                {t("btn.edit")}
              </Button>
              <Button block onClick={amostra}>
                Transferir
              </Button>
            </div>
            <div style={{ fontSize: 11, color: "#bbb", textAlign: "center", paddingBottom: 12 }}>{dataCurta(aberto.data_criacao)}</div>
          </>
        )}
      </Popup>
    </>
  );
}
