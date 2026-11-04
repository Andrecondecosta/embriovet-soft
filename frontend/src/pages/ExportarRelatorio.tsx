import { useEffect, useState } from "react";
import { Alert, Button, Card, Checkbox, Flex, Modal, Radio, Space, Typography } from "antd";
import { Button as MButton, CheckList, Checkbox as MCheckbox, List, Popup, SearchBar, Selector } from "antd-mobile";

import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { Cabecalho } from "../components/mobile";

export type Formato = "csv" | "pdf" | "xlsx";
export type Linha = Record<string, string | number | null>;
export interface Tabela {
  titulo: string;
  /** As do ecrã. */
  colunas: string[];
  /** As que se podem pôr no ficheiro (inclui as do ecrã). */
  disponiveis: string[];
  linhas: Linha[];
}
/** Escolha enviada à API; sem ela sai o ficheiro de sempre. */
export interface CorpoExportar {
  formato: Formato;
  resumo: boolean;
  tabelas: { titulo: string; colunas: string[]; ids: number[] | null }[];
}

type Linhas = "todas" | "pesquisa" | "selecionadas";
interface EscolhaTab {
  incluir: boolean;
  colunas: string[];
  linhas: Linhas;
}
interface Estado {
  formato: Formato;
  resumo: boolean;
  tabelas: Record<string, EscolhaTab>;
}

export const FORMATOS: Record<Formato, string> = { pdf: "PDF", xlsx: "Excel", csv: "CSV" };

const ARMAZEM = "equicore.relatorios.exportar.";

function lerGuardado(chave: string): Partial<Estado> | null {
  try {
    return JSON.parse(localStorage.getItem(ARMAZEM + chave) ?? "null");
  } catch {
    return null;
  }
}

function guardar(chave: string, e: Estado) {
  try {
    // As linhas escolhidas não ficam guardadas: dependem do momento.
    localStorage.setItem(ARMAZEM + chave, JSON.stringify(e));
  } catch {
    // sem armazenamento (janela privada): fica só para esta vez
  }
}

function igual(a: string[], b: string[]) {
  return a.length === b.length && a.every((x) => b.includes(x));
}

interface Props {
  aberto: boolean;
  fechar: () => void;
  /** Um conjunto de escolhas guardadas por tipo de relatório. */
  chave: string;
  temResumo: boolean;
  tabelas: Tabela[];
  filtrar: (tab: Tabela) => Linha[];
  pesquisa: string;
  selecao: Record<string, number[]>;
  setSelecao: (titulo: string, ids: number[]) => void;
  aExportar: boolean;
  exportar: (formato: Formato, corpo?: CorpoExportar) => Promise<void>;
  celula: (v: string | number | null) => string;
}

/** Estado da janela + o que se manda à API — comum ao computador e ao telemóvel. */
function useExportar(p: Props) {
  const [e, setE] = useState<Estado | null>(null);

  const selecionadas = (tab: Tabela) => {
    const ids = new Set(p.selecao[tab.titulo] ?? []);
    return tab.linhas.filter((l) => ids.has(l._id as number));
  };

  // Ao abrir: o que ficou guardado, com as linhas a seguir o ecrã
  // (selecionadas > pesquisa > todas).
  useEffect(() => {
    if (!p.aberto) return;
    const g = lerGuardado(p.chave);
    setE({
      formato: g?.formato ?? "pdf",
      resumo: g?.resumo ?? true,
      tabelas: Object.fromEntries(
        p.tabelas.map((tab) => {
          const gt = g?.tabelas?.[tab.titulo];
          const colunas = gt?.colunas?.filter((c) => tab.disponiveis.includes(c)) ?? tab.colunas;
          const linhas: Linhas = selecionadas(tab).length ? "selecionadas" : p.pesquisa.trim() ? "pesquisa" : "todas";
          return [tab.titulo, { incluir: gt?.incluir ?? true, colunas: colunas.length ? colunas : tab.colunas, linhas }];
        }),
      ),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.aberto]);

  const mudar = (titulo: string, m: Partial<EscolhaTab>) =>
    setE((x) => x && { ...x, tabelas: { ...x.tabelas, [titulo]: { ...x.tabelas[titulo], ...m } } });

  const ids = (tab: Tabela, linhas: Linhas): number[] | null =>
    linhas === "todas" ? null : (linhas === "pesquisa" ? p.filtrar(tab) : selecionadas(tab)).map((l) => l._id as number);

  const descarregar = async () => {
    if (!e) return;
    guardar(p.chave, e);
    const alterado =
      !e.resumo ||
      p.tabelas.some((tab) => {
        const et = e.tabelas[tab.titulo];
        return !et.incluir || et.linhas !== "todas" || !igual(et.colunas, tab.colunas);
      });
    // Sem nada mudado sai o ficheiro de sempre (o PDF do garanhão, o stock completo…).
    const corpo: CorpoExportar | undefined = alterado
      ? {
          formato: e.formato,
          resumo: e.resumo && p.temResumo,
          tabelas: p.tabelas
            .filter((tab) => e.tabelas[tab.titulo].incluir)
            .map((tab) => ({ titulo: tab.titulo, colunas: e.tabelas[tab.titulo].colunas, ids: ids(tab, e.tabelas[tab.titulo].linhas) })),
        }
      : undefined;
    await p.exportar(e.formato, corpo);
    p.fechar();
  };

  const vazio =
    !!e && !(e.resumo && p.temResumo) && !p.tabelas.some((tab) => e.tabelas[tab.titulo].incluir && e.tabelas[tab.titulo].colunas.length);

  return { e, setE, mudar, selecionadas, descarregar, vazio };
}

export function ExportarRelatorio(p: Props) {
  return useIsMobile() ? <ExportarMobile {...p} /> : <ExportarDesktop {...p} />;
}

function ExportarDesktop(p: Props) {
  const t = useT();
  const x = useExportar(p);
  const e = x.e;

  return (
    <Modal
      open={p.aberto}
      onCancel={p.fechar}
      title={t("web.reports.export.title")}
      width={620}
      okText={t("web.reports.export.download")}
      cancelText={t("web.common.cancel")}
      okButtonProps={{ loading: p.aExportar, disabled: x.vazio }}
      onOk={x.descarregar}
      destroyOnHidden
    >
      {e && (
        <Flex vertical gap={12}>
          <Space>
            <Typography.Text type="secondary">{t("web.reports.export.format")}</Typography.Text>
            <Radio.Group
              optionType="button"
              value={e.formato}
              onChange={(ev) => x.setE({ ...e, formato: ev.target.value })}
              options={(Object.keys(FORMATOS) as Formato[]).map((f) => ({ value: f, label: FORMATOS[f] }))}
            />
          </Space>
          {p.temResumo && (
            <Checkbox checked={e.resumo} onChange={(ev) => x.setE({ ...e, resumo: ev.target.checked })}>
              {t("web.reports.export.summary")}
            </Checkbox>
          )}
          {p.tabelas.map((tab) => {
            const et = e.tabelas[tab.titulo];
            const nSel = x.selecionadas(tab).length;
            return (
              <Card
                key={tab.titulo}
                size="small"
                title={
                  <Checkbox checked={et.incluir} onChange={(ev) => x.mudar(tab.titulo, { incluir: ev.target.checked })}>
                    {t(tab.titulo)}
                  </Checkbox>
                }
                extra={
                  et.incluir &&
                  !igual(et.colunas, tab.colunas) && (
                    <Button size="small" type="link" onClick={() => x.mudar(tab.titulo, { colunas: tab.colunas })}>
                      {t("web.reports.export.reset")}
                    </Button>
                  )
                }
                styles={{ body: et.incluir ? undefined : { display: "none" } }}
              >
                <Flex vertical gap={10}>
                  <div>
                    <Typography.Text type="secondary">{t("web.reports.export.columns")}</Typography.Text>
                    <Checkbox.Group
                      style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", rowGap: 4, marginTop: 4 }}
                      value={et.colunas}
                      onChange={(v) => x.mudar(tab.titulo, { colunas: v as string[] })}
                      options={tab.disponiveis.map((c) => ({ value: c, label: t(`web.reports.col.${c}`) }))}
                    />
                  </div>
                  <div>
                    <Typography.Text type="secondary">{t("web.reports.export.rows")}</Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      <Radio.Group
                        value={et.linhas}
                        onChange={(ev) => x.mudar(tab.titulo, { linhas: ev.target.value })}
                        options={[
                          { value: "todas", label: t("web.reports.export.rows_all", { n: tab.linhas.length }) },
                          ...(p.pesquisa.trim()
                            ? [{ value: "pesquisa", label: t("web.reports.export.rows_search", { n: p.filtrar(tab).length }) }]
                            : []),
                          { value: "selecionadas", label: t("web.reports.export.rows_selected", { n: nSel }), disabled: !nSel },
                        ]}
                      />
                    </div>
                    {!nSel && (
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {t("web.reports.export.select_hint")}
                      </Typography.Text>
                    )}
                  </div>
                </Flex>
              </Card>
            );
          })}
          {x.vazio && <Alert type="warning" showIcon title={t("web.reports.error.nothing_to_export")} />}
        </Flex>
      )}
    </Modal>
  );
}

function ExportarMobile(p: Props) {
  const t = useT();
  const x = useExportar(p);
  const e = x.e;
  const [escolher, setEscolher] = useState<Tabela | null>(null);
  const [q, setQ] = useState("");

  return (
    <>
      <Popup
        visible={p.aberto}
        onMaskClick={p.fechar}
        onClose={p.fechar}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16, maxHeight: "85dvh", overflowY: "auto" }}
      >
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>{t("web.reports.export.title")}</div>
        {e && (
          <>
            <Selector
              columns={3}
              value={[e.formato]}
              onChange={(v) => v[0] && x.setE({ ...e, formato: v[0] })}
              options={(Object.keys(FORMATOS) as Formato[]).map((f) => ({ value: f, label: FORMATOS[f] }))}
            />
            {p.temResumo && (
              <div style={{ marginTop: 12 }}>
                <MCheckbox checked={e.resumo} onChange={(v) => x.setE({ ...e, resumo: v })}>
                  {t("web.reports.export.summary")}
                </MCheckbox>
              </div>
            )}
            {p.tabelas.map((tab) => {
              const et = e.tabelas[tab.titulo];
              const nSel = x.selecionadas(tab).length;
              return (
                <div key={tab.titulo} style={{ marginTop: 12 }}>
                  <MCheckbox checked={et.incluir} onChange={(v) => x.mudar(tab.titulo, { incluir: v })}>
                    <b>{t(tab.titulo)}</b>
                  </MCheckbox>
                  {et.incluir && (
                    <>
                      <div style={{ color: "#999", margin: "8px 0 6px" }}>{t("web.reports.export.columns")}</div>
                      <Selector
                        multiple
                        columns={2}
                        value={et.colunas}
                        onChange={(v) => x.mudar(tab.titulo, { colunas: v })}
                        options={tab.disponiveis.map((c) => ({ value: c, label: t(`web.reports.col.${c}`) }))}
                      />
                      <div style={{ color: "#999", margin: "8px 0 6px" }}>{t("web.reports.export.rows")}</div>
                      <Selector
                        columns={1}
                        value={[et.linhas]}
                        onChange={(v) => v[0] && x.mudar(tab.titulo, { linhas: v[0] as Linhas })}
                        options={[
                          { value: "todas", label: t("web.reports.export.rows_all", { n: tab.linhas.length }) },
                          ...(p.pesquisa.trim()
                            ? [{ value: "pesquisa", label: t("web.reports.export.rows_search", { n: p.filtrar(tab).length }) }]
                            : []),
                          { value: "selecionadas", label: t("web.reports.export.rows_selected", { n: nSel }) },
                        ]}
                      />
                      <List style={{ "--border-top": "none", "--border-bottom": "none" } as React.CSSProperties}>
                        <List.Item
                          arrow
                          onClick={() => (setQ(""), setEscolher(tab), x.mudar(tab.titulo, { linhas: "selecionadas" }))}
                          extra={nSel ? t("web.reports.export.selected", { n: nSel }) : ""}
                        >
                          {t("web.reports.export.choose_rows")}
                        </List.Item>
                      </List>
                    </>
                  )}
                </div>
              );
            })}
            {x.vazio && <div style={{ color: "#c00", marginTop: 12 }}>{t("web.reports.error.nothing_to_export")}</div>}
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <MButton block onClick={p.fechar}>
                {t("web.common.cancel")}
              </MButton>
              <MButton
                block
                color="primary"
                loading={p.aExportar}
                disabled={
                  x.vazio ||
                  p.tabelas.some(
                    (tab) =>
                      e.tabelas[tab.titulo].incluir && e.tabelas[tab.titulo].linhas === "selecionadas" && !x.selecionadas(tab).length,
                  )
                }
                onClick={x.descarregar}
              >
                {t("web.reports.export.download")}
              </MButton>
            </div>
          </>
        )}
      </Popup>

      <Popup
        visible={escolher !== null}
        onMaskClick={() => setEscolher(null)}
        onClose={() => setEscolher(null)}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, height: "80dvh", display: "flex", flexDirection: "column" }}
      >
        {escolher && (
          <>
            <div style={{ padding: 12 }}>
              <SearchBar placeholder={t("web.reports.search")} value={q} onChange={setQ} />
            </div>
            <Cabecalho>
              {t(escolher.titulo)} · {t("web.reports.export.selected", { n: x.selecionadas(escolher).length })}
            </Cabecalho>
            <div style={{ flex: 1, overflowY: "auto" }}>
              <CheckList multiple value={p.selecao[escolher.titulo] ?? []} onChange={(v) => p.setSelecao(escolher.titulo, v as number[])}>
                {escolher.linhas
                  .filter((l) => !q.trim() || escolher.colunas.some((c) => p.celula(l[c]).toLowerCase().includes(q.trim().toLowerCase())))
                  .slice(0, 300)
                  .map((l) => (
                    <CheckList.Item
                      key={l._id as number}
                      value={l._id as number}
                      description={escolher.colunas
                        .slice(1)
                        .map((c) => `${t(`web.reports.col.${c}`)}: ${p.celula(l[c])}`)
                        .join(" · ")}
                    >
                      {p.celula(l[escolher.colunas[0]])}
                    </CheckList.Item>
                  ))}
              </CheckList>
            </div>
            <div style={{ padding: 12 }}>
              <MButton block color="primary" onClick={() => setEscolher(null)}>
                OK
              </MButton>
            </div>
          </>
        )}
      </Popup>
    </>
  );
}
