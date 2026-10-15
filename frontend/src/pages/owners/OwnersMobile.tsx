import { useState } from "react";
import { ActionSheet, Button, DotLoading, ErrorBlock, FloatingBubble, List, Popup, SearchBar, Tabs, Tag } from "antd-mobile";
import { AddOutline } from "antd-mobile-icons";

import type { Owner, Page } from "../../api/types";
import { useT } from "../../i18n/I18n";
import type { Estado, Ordem } from "./api";
import { useOwnerAcoes } from "./OwnerDrawer";

/** Proprietários no telemóvel (Ant Design Mobile). Os filtros e a página
 *  vêm de `OwnersTab`, que os guarda no endereço. */
export function OwnersMobile({
  pesquisa,
  setPesquisa,
  estado,
  ordem,
  pagina,
  totalPaginas,
  atualizar,
  data,
  carregando,
  selecionado,
  setSelecionado,
  onNovo,
  onEditar,
}: {
  pesquisa: string;
  setPesquisa: (v: string) => void;
  estado: Estado;
  ordem: Ordem;
  pagina: number;
  totalPaginas: number;
  atualizar: (novo: Record<string, string | number | null>) => void;
  data: Page<Owner> | undefined;
  carregando: boolean;
  selecionado: Owner | null;
  setSelecionado: (o: Owner | null) => void;
  onNovo: () => void;
  onEditar: (o: Owner) => void;
}) {
  const t = useT();
  const [ordenar, setOrdenar] = useState(false);
  const fechar = () => setSelecionado(null);
  const { ativo, alternando, alternarEstado, confirmarApagar } = useOwnerAcoes(selecionado, setSelecionado, fechar);
  const na = (v: string | null) => v || t("common.na");

  const ORDENS: [Ordem, string][] = [
    ["nome", t("owners.sort.name")],
    ["id", t("owners.sort.id")],
    ["status", t("web.owners.status")],
  ];
  const mudarPagina = (p: number) => {
    atualizar({ pagina: p });
    document.querySelector("[data-scroll-raiz]")?.scrollTo({ top: 0 });
  };

  return (
    <>
      <div style={{ background: "#fff", padding: "8px 8px 0" }}>
        <SearchBar placeholder={t("web.owners.search")} value={pesquisa} onChange={setPesquisa} />
      </div>
      <Tabs
        activeKey={estado}
        onChange={(v) => atualizar({ estado: v === "todos" ? null : v, pagina: 1 })}
        style={{ background: "#fff", "--title-font-size": "13px" } as React.CSSProperties}
      >
        <Tabs.Tab key="todos" title={t("owners.filter.all")} />
        <Tabs.Tab key="ativos" title={t("owners.filter.active")} />
        <Tabs.Tab key="inativos" title={t("owners.filter.inactive")} />
      </Tabs>

      <List
        header={
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>{data ? t("web.owners.count", { count: data.total }) : ""}</span>
            <a onClick={() => setOrdenar(true)}>
              {t("owners.sort_by")} {ORDENS.find(([o]) => o === ordem)?.[1]} ▾
            </a>
          </div>
        }
      >
        {carregando && !data ? (
          <List.Item>
            <DotLoading />
          </List.Item>
        ) : !data?.items.length ? (
          <ErrorBlock status="empty" title={t("web.owners.empty")} description="" />
        ) : (
          data.items.map((o) => (
            <List.Item
              key={o.id}
              arrow
              onClick={() => setSelecionado(o)}
              description={[o.cidade, o.telemovel, o.email].filter(Boolean).join(" · ") || `#${o.id}`}
              extra={!o.ativo && <Tag fill="outline">{t("owners.filter.inactive")}</Tag>}
            >
              {o.nome}
            </List.Item>
          ))
        )}
      </List>

      {totalPaginas > 1 && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 16, padding: 12 }}>
          <Button size="small" disabled={pagina <= 1} onClick={() => mudarPagina(pagina - 1)}>
            ‹
          </Button>
          <span style={{ color: "#666" }}>
            {Math.min(pagina, totalPaginas)} / {totalPaginas}
          </span>
          <Button size="small" disabled={pagina >= totalPaginas} onClick={() => mudarPagina(pagina + 1)}>
            ›
          </Button>
        </div>
      )}
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
        onClick={onNovo}
      >
        <AddOutline fontSize={26} />
      </FloatingBubble>

      <ActionSheet
        visible={ordenar}
        onClose={() => setOrdenar(false)}
        cancelText={t("web.common.cancel")}
        actions={ORDENS.map(([o, label]) => ({
          key: o,
          text: o === ordem ? <b>{label}</b> : label,
          onClick: () => {
            atualizar({ ordem: o === "nome" ? null : o, pagina: 1 });
            setOrdenar(false);
          },
        }))}
      />

      {/* Ficha do proprietário: folha que sobe de baixo. */}
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
              <div style={{ fontSize: 11, color: "#999" }}>#{selecionado.id}</div>
              <div style={{ fontSize: 15, fontWeight: 700, display: "flex", gap: 8, alignItems: "center" }}>
                {selecionado.nome}
                <Tag color={ativo ? "success" : "default"} fill="outline">
                  {ativo ? t("owners.filter.active") : t("owners.filter.inactive")}
                </Tag>
              </div>
            </div>
            {/* Só o meio desliza: o "X" e os botões ficam sempre à vista. */}
            <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
              <List>
                {(
                  [
                    [t("label.full_name"), na(selecionado.nome_completo)],
                    [t("label.nif"), na(selecionado.nif)],
                    [t("label.email"), na(selecionado.email)],
                    [t("label.phone"), na(selecionado.telemovel)],
                    [t("label.address"), na(selecionado.morada)],
                    [t("label.postal_code"), na(selecionado.codigo_postal)],
                    [t("label.city"), na(selecionado.cidade)],
                  ] as [string, string][]
                ).map(([label, valor]) => (
                  <List.Item key={label} extra={<span style={{ whiteSpace: "pre-wrap" }}>{valor}</span>}>
                    {label}
                  </List.Item>
                ))}
              </List>
            </div>
            <div style={{ display: "flex", gap: 8, padding: 16, paddingBottom: "calc(16px + env(safe-area-inset-bottom))" }}>
              <Button block color="primary" onClick={() => onEditar(selecionado)}>
                {t("btn.edit")}
              </Button>
              <Button block loading={alternando} onClick={alternarEstado}>
                {ativo ? t("web.owners.deactivate") : t("web.owners.activate")}
              </Button>
              <Button block color="danger" fill="outline" onClick={() => void confirmarApagar()}>
                {t("btn.delete").replace(/^\W+/, "")}
              </Button>
            </div>
          </>
        )}
      </Popup>
    </>
  );
}
