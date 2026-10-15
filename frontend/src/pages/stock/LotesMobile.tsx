import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Button,
  Collapse,
  DotLoading,
  ErrorBlock,
  FloatingBubble,
  Grid,
  List,
  Picker,
  Popup,
  Selector,
  Stepper,
  SwipeAction,
  Switch,
  Tag,
} from "antd-mobile";
import { AddOutline, DownlandOutline, FilterOutline } from "antd-mobile-icons";

import { useT } from "../../i18n/I18n";
import { useIsAdmin } from "../../components/User";
import { dataCurta, dataHora } from "../../components/csv";
import { localizacao, referencia, useGaranhoesStock, useLotes, useTransferencias, type Lote } from "./api";
import { LoteFormModal } from "./LoteForm";
import { ApagarLoteModal } from "./LoteDrawer";

const SEM_DONO = "sem-dono";

/** Lotes no telemóvel (Ant Design Mobile) — mesma lógica da versão de
 *  computador (`LotesTab`): garanhão, filtros e lote aberto no endereço. */
export function LotesMobile({ onNovoLote }: { onNovoLote: () => void }) {
  const t = useT();
  const isAdmin = useIsAdmin();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [roda, setRoda] = useState(false);
  const [filtros, setFiltros] = useState(false);
  const [editar, setEditar] = useState<Lote | null>(null);
  const [apagar, setApagar] = useState<Lote | null>(null);

  const garanhoes = useGaranhoesStock();
  const opcoes = useMemo(() => (garanhoes.data ?? []).filter((g) => g.no_seletor).map((g) => g.garanhao), [garanhoes.data]);
  const pedido = params.get("garanhao");
  const garanhao = pedido && opcoes.includes(pedido) ? pedido : (opcoes[0] ?? null);
  const donosSel = params.getAll("dono");
  const minPalhetas = Number(params.get("min")) || 0;
  const incluirVazios = params.get("vazios") === "1";
  const loteAberto = Number(params.get("lote")) || null;

  const atualizar = (fn: (p: URLSearchParams) => void) =>
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        fn(r);
        return r;
      },
      { replace: true },
    );

  const lotes = useLotes(
    garanhao
      ? {
          garanhao,
          donos: donosSel.filter((d) => d !== SEM_DONO).map(Number),
          semDono: donosSel.includes(SEM_DONO),
          minPalhetas,
          incluirVazios,
        }
      : null,
  );
  const transf = useTransferencias(garanhao);

  const [selecionado, setSelecionado] = useState<Lote | null>(null);
  useEffect(() => {
    if (loteAberto && lotes.data) {
      const l = lotes.data.items.find((x) => x.id === loteAberto);
      if (l) setSelecionado(l);
    }
  }, [loteAberto, lotes.data]);
  useEffect(() => {
    if (selecionado && lotes.data) {
      const novo = lotes.data.items.find((x) => x.id === selecionado.id);
      if (novo && novo !== selecionado) setSelecionado(novo);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotes.data]);
  const fechar = () => {
    setSelecionado(null);
    if (loteAberto) atualizar((p) => p.delete("lote"));
  };

  if (garanhoes.isPending)
    return (
      <div style={{ textAlign: "center", padding: 32 }}>
        <DotLoading color="primary" />
      </div>
    );
  if (!garanhao)
    return (
      <ErrorBlock status="empty" title={t("stock.none_registered")} description="">
        <Button color="primary" onClick={onNovoLote}>
          {t("web.stock.add")}
        </Button>
      </ErrorBlock>
    );

  const k = lotes.data?.kpis;
  const nFiltros = (donosSel.length ? 1 : 0) + (minPalhetas ? 1 : 0) + (incluirVazios ? 1 : 0);
  // Histórico do lote aberto: transferências em que o dono foi origem ou destino.
  const dono = selecionado?.dono_id ?? null;
  const historico = (transf.data?.internas ?? []).filter((x) => x.origem_id === dono || x.destino_id === dono);

  return (
    <>
      {/* Garanhão (roda) e filtros. */}
      <List style={{ "--border-top": "none" } as React.CSSProperties}>
        <List.Item extra={garanhao} onClick={() => setRoda(true)}>
          {t("label.garanhao")}
        </List.Item>
        <List.Item
          prefix={<FilterOutline />}
          extra={nFiltros ? t("web.stock.filters_active", { count: nFiltros }) : ""}
          onClick={() => setFiltros(true)}
        >
          {t("common.filters")}
        </List.Item>
        <List.Item prefix={<DownlandOutline />} arrow onClick={() => navigate("/stock-semen/importar")}>
          {t("web.stock.import")}
        </List.Item>
      </List>
      <Picker
        columns={[opcoes.map((g) => ({ label: g, value: g }))]}
        visible={roda}
        onClose={() => setRoda(false)}
        value={[garanhao]}
        title={t("web.stock.select_stallion")}
        onConfirm={(v) =>
          v[0] &&
          atualizar((p) => {
            p.set("garanhao", String(v[0]));
            p.delete("dono");
            p.delete("lote");
          })
        }
      />

      {/* Indicadores numa faixa só. */}
      <Grid columns={4} style={{ background: "#fff", margin: "8px 0", padding: "10px 4px" }}>
        {[
          [t("web.stock.kpi.lotes"), k?.lotes ?? "—"],
          [t("web.stock.kpi.palhetas"), k?.palhetas ?? "—"],
          [t("web.stock.kpi.proprietarios"), k?.proprietarios ?? "—"],
          [t("stock.quality_label"), k?.qualidade_media != null ? `${k.qualidade_media}%` : "—"],
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
            <div key={String(r.dono_id)} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
              <span>{r.proprietario_nome ?? t("common.no_owner")}</span>
              <b>{r.palhetas}</b>
            </div>
          ))}
        </Collapse.Panel>
        <Collapse.Panel key="hist" title={t("stock.transfer_history")}>
          {!(transf.data?.internas.length || transf.data?.externas.length) ? (
            <span style={{ color: "#999" }}>{t("stock.no_transfers")}</span>
          ) : (
            <>
              {(transf.data?.internas ?? []).map((x) => (
                <div key={`i${x.id}`} style={{ padding: "3px 0" }}>
                  {dataCurta(x.data)} · {x.origem ?? "—"} → {x.destino ?? "—"} · <b>{x.quantidade}</b>
                </div>
              ))}
              {(transf.data?.externas ?? []).map((x) => (
                <div key={`e${x.id}`} style={{ padding: "3px 0" }}>
                  {dataCurta(x.data)} · {x.origem ?? "—"} → {x.destinatario} ({x.tipo}) · <b>{x.quantidade}</b>
                </div>
              ))}
            </>
          )}
        </Collapse.Panel>
      </Collapse>

      {/* Lotes. O Administrador pode deslizar para a esquerda para editar/eliminar. */}
      <List header={t("stock.lots_detailed")} style={{ marginTop: 8 }}>
        {!lotes.data ? (
          <List.Item>
            <DotLoading />
          </List.Item>
        ) : !lotes.data.items.length ? (
          <List.Item>{t("stock.no_lots_filter")}</List.Item>
        ) : (
          lotes.data.items.map((l) => {
            const item = (
              <List.Item
                key={l.id}
                onClick={() => setSelecionado(l)}
                description={`${l.proprietario_nome ?? t("common.no_owner")} · ${localizacao(l) ?? "—"} · M ${l.motilidade ?? 0}%`}
                extra={
                  <Tag color={(l.existencia_atual ?? 0) > 0 ? "primary" : "default"} fill="outline">
                    {t("web.stock.straws_count", { count: l.existencia_atual ?? 0 })}
                  </Tag>
                }
              >
                {referencia(l) ?? t("common.no_reference")}
              </List.Item>
            );
            return isAdmin ? (
              <SwipeAction
                key={l.id}
                rightActions={[
                  { key: "editar", text: t("btn.edit"), color: "primary", onClick: () => setEditar(l) },
                  { key: "apagar", text: t("btn.delete").replace(/^\W+/, ""), color: "danger", onClick: () => setApagar(l) },
                ]}
              >
                {item}
              </SwipeAction>
            ) : (
              item
            );
          })
        )}
      </List>
      <div style={{ height: 72 }} />

      <FloatingBubble
        style={
          {
            "--initial-position-bottom": "calc(72px + env(safe-area-inset-bottom))",
            "--initial-position-right": "16px",
            "--edge-distance": "16px",
            "--size": "52px",
          } as React.CSSProperties
        }
        onClick={onNovoLote}
      >
        <AddOutline fontSize={26} />
      </FloatingBubble>

      {/* Filtros: sobem de baixo. */}
      <Popup
        visible={filtros}
        onMaskClick={() => setFiltros(false)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16 }}
      >
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 12 }}>{t("common.filters")}</div>
        <div style={{ color: "#999", marginBottom: 6 }}>{t("label.owner_plural")}</div>
        <Selector
          multiple
          columns={2}
          value={donosSel}
          onChange={(v) =>
            atualizar((p) => {
              p.delete("dono");
              v.forEach((d) => p.append("dono", d));
            })
          }
          options={(lotes.data?.donos_disponiveis ?? []).map((d) => ({
            label: d.nome ?? t("common.no_owner"),
            value: d.id === null ? SEM_DONO : String(d.id),
          }))}
        />
        <List style={{ marginTop: 12, "--border-top": "none", "--border-bottom": "none" } as React.CSSProperties}>
          <List.Item
            extra={
              <Stepper min={0} value={minPalhetas} onChange={(v) => atualizar((p) => (v ? p.set("min", String(v)) : p.delete("min")))} />
            }
          >
            {t("stock.min_straws")}
          </List.Item>
          <List.Item
            extra={<Switch checked={incluirVazios} onChange={(on) => atualizar((p) => (on ? p.set("vazios", "1") : p.delete("vazios")))} />}
          >
            {t("stock.include_empty")}
          </List.Item>
        </List>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          {nFiltros > 0 && (
            <Button
              block
              onClick={() =>
                atualizar((p) => {
                  p.delete("dono");
                  p.delete("min");
                  p.delete("vazios");
                })
              }
            >
              {t("web.stock.clear_filters")}
            </Button>
          )}
          <Button block color="primary" onClick={() => setFiltros(false)}>
            OK
          </Button>
        </div>
      </Popup>

      {/* Detalhe do lote: folha que sobe de baixo. */}
      <Popup
        visible={selecionado !== null}
        onMaskClick={fechar}
        onClose={fechar}
        showCloseButton
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, maxHeight: "88vh", display: "flex", flexDirection: "column" }}
      >
        {selecionado && (
          <>
            <div style={{ padding: "16px 16px 4px" }}>
              <div style={{ fontSize: 11, color: "#999" }}>
                {selecionado.garanhao_nome} · #{selecionado.id}
              </div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>{referencia(selecionado) ?? t("common.no_reference")}</div>
            </div>
            {/* Só o meio desliza: o "X" e os botões ficam sempre à vista. */}
            <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
              <List>
                {(
                  [
                    [t("label.owner"), selecionado.proprietario_nome ?? t("common.no_owner")],
                    [t("web.stock.kpi.palhetas"), selecionado.existencia_atual ?? 0],
                    [t("label.location"), localizacao(selecionado) ?? "—"],
                    [t("stock.certificate_label"), selecionado.certificado ?? "—"],
                    [t("stock.quality_label"), selecionado.qualidade || "—"],
                    [t("stock.color"), selecionado.cor || "—"],
                    [t("stock.concentration_label"), `${selecionado.concentracao ?? 0} ${t("stock.million_ml")}`],
                    [t("stock.motility_label"), `${selecionado.motilidade ?? 0}%`],
                    [t("stock.dose_label"), selecionado.dose || "—"],
                    [t("stock.straws_produced_label"), selecionado.palhetas_produzidas ?? "—"],
                    [t("stock.prod_date_label"), selecionado.data_embriovet || "—"],
                    [t("stock.external_origin_label"), selecionado.origem_externa || "—"],
                    ...(selecionado.observacoes ? [[t("label.notes"), selecionado.observacoes]] : []),
                    [t("stock.created_at_label"), dataHora(selecionado.data_criacao)],
                    [t("stock.created_by_label"), selecionado.criado_por || "—"],
                  ] as [string, string | number][]
                ).map(([label, valor]) => (
                  <List.Item key={label} extra={valor}>
                    {label}
                  </List.Item>
                ))}
              </List>
              {historico.length > 0 && (
                <Collapse>
                  <Collapse.Panel key="h" title={t("stock.lot_history")}>
                    {historico.map((x) => (
                      <div key={x.id} style={{ padding: "3px 0" }}>
                        {dataCurta(x.data)} · {x.origem ?? "—"} → {x.destino ?? "—"} · <b>{x.quantidade}</b>
                      </div>
                    ))}
                  </Collapse.Panel>
                </Collapse>
              )}
            </div>
            {/* Editar/Eliminar só para Administrador, como na app atual. */}
            {isAdmin && (
              <div style={{ display: "flex", gap: 8, padding: 16, paddingBottom: "calc(16px + env(safe-area-inset-bottom))" }}>
                <Button block color="primary" onClick={() => setEditar(selecionado)}>
                  {t("btn.edit")}
                </Button>
                <Button block color="danger" fill="outline" onClick={() => setApagar(selecionado)}>
                  {t("stock.tab.delete").replace(/^\W+/, "")}
                </Button>
              </div>
            )}
          </>
        )}
      </Popup>

      {editar && <LoteFormModal opened lote={editar} onClose={() => setEditar(null)} />}
      {apagar && (
        <ApagarLoteModal
          opened
          lote={apagar}
          ligacoes={lotes.data?.ligacoes[String(apagar.id)]}
          onClose={() => setApagar(null)}
          onDeleted={() => {
            setApagar(null);
            fechar();
          }}
        />
      )}
    </>
  );
}
