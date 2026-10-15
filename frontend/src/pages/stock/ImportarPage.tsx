import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Flex,
  Form,
  Input,
  Modal,
  Result,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Steps,
  Table,
  Tag,
  Typography,
} from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  Form as MForm,
  Input as MInput,
  List,
  Popup,
  Result as MResult,
  Steps as MSteps,
  Tag as MTag,
} from "antd-mobile";

import { api } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { baixarCsv } from "../../components/csv";
import { descarregar } from "../../components/download";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { Cabecalho } from "../../components/mobile";

type Linha = Record<string, string | number> & { __row: number };
interface Entidades {
  proprietarios: string[];
  contentores: string[];
  existentes: { id: number; nome: string }[];
}
interface Validacao {
  total: number;
  validas: number;
  erros: { linha: number; coluna: string; erro: string }[];
  com_data: number;
}
interface Relatorio {
  importados: number;
  relatorio: { linha: number; garanhao: string; proprietario: string; palhetas: number; stock_id: number; data_ajustada: string }[];
}

const COLUNAS = [
  "garanhao",
  "data_embriovet/ref",
  "existencia_atual",
  "dose",
  "motilidade",
  "qualidade",
  "concentracao",
  "cor",
  "proprietario_nome",
  "contentor_codigo",
  "canister",
  "andar",
  "observacoes",
  "certificado",
];
const COMPACTAS = [
  "garanhao",
  "data_embriovet/ref",
  "existencia_atual",
  "proprietario_nome",
  "contentor_codigo",
  "canister",
  "andar",
  "motilidade",
];
const CRIAR = "__criar__";
/** Nomes das colunas no ecrã (as que não estão nos Relatórios). */
const ROTULOS: Record<string, string> = {
  "data_embriovet/ref": "web.reports.col.data_embriovet",
  contentor_codigo: "label.container",
  dose: "stock.dose_label",
  motilidade: "stock.motility_label",
  concentracao: "stock.concentration_label",
  cor: "stock.color",
  certificado: "stock.certificate_label",
};

/** Ficheiro → base64 (sem o prefixo "data:…;base64,"). */
function base64(f: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onerror = () => rej(r.error);
    r.onload = () => res(String(r.result).split(",")[1] ?? "");
    r.readAsDataURL(f);
  });
}

/** Estado do assistente — comum ao computador e ao telemóvel. */
function useImportar() {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notifyError = useNotifyError();
  const [passo, setPasso] = useState(0);
  const [nome, setNome] = useState<string | null>(null);
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [entidades, setEntidades] = useState<Entidades | null>(null);
  // Proprietários mapeados para um existente ({nome em minúsculas: id}).
  const [mapaDonos, setMapaDonos] = useState<Record<string, number>>({});
  const [resolvidos, setResolvidos] = useState<Record<string, string>>({});
  const [validacao, setValidacao] = useState<Validacao | null>(null);
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);

  const correr = async <R,>(fn: () => Promise<R>) => {
    setOcupado(true);
    try {
      return await fn();
    } catch (err) {
      notifyError(err);
      return undefined;
    } finally {
      setOcupado(false);
    }
  };

  const ler = async (f: File) => {
    const r = await correr(async () => api<{ linhas: Linha[] }>("/importar/ler", "POST", { nome: f.name, conteudo: await base64(f) }));
    if (!r) return;
    setNome(f.name);
    setLinhas(r.linhas);
    setEntidades(null);
    setMapaDonos({});
    setResolvidos({});
    setValidacao(null);
  };
  const verEntidades = async () => {
    const r = await correr(() => api<Entidades>("/importar/entidades", "POST", { linhas, mapa_donos: mapaDonos }));
    if (r) {
      setEntidades(r);
      setPasso(1);
    }
  };
  const resolverDono = async (dono: string, escolha: string) => {
    if (escolha === CRIAR) {
      const r = await correr(() => api<{ id: number }>("/importar/proprietario", "POST", { nome: dono }));
      if (r) setResolvidos((x) => ({ ...x, [`p:${dono}`]: t("import.entities.created_new", { name: dono }) }));
    } else {
      const e = entidades?.existentes.find((x) => String(x.id) === escolha);
      if (!e) return;
      setMapaDonos((m) => ({ ...m, [dono.toLowerCase()]: e.id }));
      setResolvidos((x) => ({ ...x, [`p:${dono}`]: t("import.entities.mapped_to", { name: e.nome }) }));
    }
  };
  const criarContentor = async (codigo: string, descricao: string) => {
    const r = await correr(() => api<{ id: number }>("/importar/contentor", "POST", { codigo, descricao }));
    if (r) setResolvidos((x) => ({ ...x, [`c:${codigo}`]: t("import.entities.cont_created") }));
  };
  const tudoResolvido =
    !!entidades && entidades.proprietarios.every((p) => resolvidos[`p:${p}`]) && entidades.contentores.every((c) => resolvidos[`c:${c}`]);

  const validar = async (ls = linhas) => {
    const r = await correr(() => api<Validacao>("/importar/validar", "POST", { linhas: ls, mapa_donos: mapaDonos }));
    if (r) {
      setValidacao(r);
      setPasso(2);
    }
  };
  const corrigir = (row: number, valores: Record<string, string>) => {
    const novas = linhas.map((l) => (l.__row === row ? { ...l, ...valores } : l));
    setLinhas(novas);
    validar(novas);
  };
  const importar = async () => {
    const r = await correr(() => api<Relatorio>("/importar/executar", "POST", { linhas, mapa_donos: mapaDonos }));
    if (r) {
      setRelatorio(r);
      setPasso(3);
      notifySuccess(t("import.completed", { count: r.importados }));
      for (const k of ["stock", "mapa", "dashboard", "inseminacoes", "relatorios"]) queryClient.invalidateQueries({ queryKey: [k] });
    }
  };
  const recomecar = () => {
    setPasso(0);
    setNome(null);
    setLinhas([]);
    setRelatorio(null);
    setValidacao(null);
  };
  const errosDaLinha = (row: number) => (validacao?.erros ?? []).filter((e) => e.linha === row);
  const modelo = (formato: "xlsx" | "csv") => correr(() => descarregar(`/importar/modelo?formato=${formato}`));
  const baixarRelatorio = () =>
    relatorio &&
    baixarCsv(
      "relatorio_importacao.csv",
      ["linha", "garanhao", "proprietario", "palhetas", "stock_id", "data_criacao_ajustada"],
      relatorio.relatorio.map((r) => [r.linha, r.garanhao, r.proprietario, r.palhetas, r.stock_id, r.data_ajustada]),
    );

  return {
    t,
    navigate,
    passo,
    setPasso,
    nome,
    linhas,
    ocupado,
    entidades,
    resolvidos,
    tudoResolvido,
    validacao,
    relatorio,
    ler,
    verEntidades,
    resolverDono,
    criarContentor,
    validar,
    corrigir,
    importar,
    recomecar,
    errosDaLinha,
    modelo,
    baixarRelatorio,
    col: (c: string) => t(ROTULOS[c] ?? `web.reports.col.${c}`),
  };
}
type X = ReturnType<typeof useImportar>;

export function ImportarPage() {
  const x = useImportar();
  return useIsMobile() ? <ImportarMobile x={x} /> : <ImportarDesktop x={x} />;
}

/** Botão para escolher o ficheiro (input escondido). */
function EscolherFicheiro({ x, children }: { x: X; children: (abrir: () => void) => React.ReactNode }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      {children(() => ref.current?.click())}
      <input
        ref={ref}
        type="file"
        accept=".csv,.xlsx,.xls"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) x.ler(f);
          e.target.value = "";
        }}
      />
    </>
  );
}

/** Formulário de correção de uma linha (todas as colunas, em texto). */
function useCorrecao(x: X) {
  const [linha, setLinha] = useState<Linha | null>(null);
  return {
    linha,
    abrir: setLinha,
    fechar: () => setLinha(null),
    guardar: (v: Record<string, string>) => {
      if (linha) x.corrigir(linha.__row, v);
      setLinha(null);
    },
  };
}

// ── Computador ──────────────────────────────────────────────────────────────

function ImportarDesktop({ x }: { x: X }) {
  const { t } = x;
  const corr = useCorrecao(x);
  const [form] = Form.useForm();
  const [escolhas, setEscolhas] = useState<Record<string, string>>({});
  const [descricoes, setDescricoes] = useState<Record<string, string>>({});
  useEffect(() => {
    if (corr.linha) form.setFieldsValue(Object.fromEntries(COLUNAS.map((c) => [c, String(corr.linha![c] ?? "")])));
  }, [corr.linha, form]);

  const passos = [t("import.wizard.step1"), t("import.wizard.step2"), t("import.wizard.step3"), t("import.wizard.step4")];

  return (
    <Card size="small">
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {t("import.title")}
      </Typography.Title>
      <Steps size="small" current={x.passo} items={passos.map((title) => ({ title }))} style={{ marginBottom: 20 }} />
      <Spin spinning={x.ocupado}>
        {x.passo === 0 && (
          <Space orientation="vertical" size={16} style={{ width: "100%" }}>
            <Flex justify="space-between" gap={16} wrap>
              <Typography.Text type="secondary" style={{ maxWidth: 640 }}>
                {t("import.hint")}
              </Typography.Text>
              <Space>
                <Button icon={<DownloadOutlined />} onClick={() => x.modelo("xlsx")}>
                  {t("import.download_xlsx")}
                </Button>
                <Button icon={<DownloadOutlined />} onClick={() => x.modelo("csv")}>
                  {t("import.download_csv")}
                </Button>
              </Space>
            </Flex>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("import.rules_hint")}
            </Typography.Text>
            <EscolherFicheiro x={x}>
              {(abrir) => (
                <Button type="primary" icon={<UploadOutlined />} onClick={abrir}>
                  {t("import.upload_label")}
                </Button>
              )}
            </EscolherFicheiro>
            {x.linhas.length > 0 && (
              <>
                <Alert type="success" showIcon title={`${x.nome} — ${t("import.file_loaded", { count: x.linhas.length })}`} />
                <Typography.Text strong>{t("import.preview_title")}</Typography.Text>
                <Table
                  size="small"
                  bordered
                  rowKey="__row"
                  pagination={false}
                  scroll={{ x: true }}
                  dataSource={x.linhas.slice(0, 5)}
                  columns={COMPACTAS.slice(0, 5).map((c) => ({ title: x.col(c), dataIndex: c, render: (v) => v || "—" }))}
                />
                <div>
                  <Button type="primary" onClick={x.verEntidades}>
                    {t("import.btn.next_entities")}
                  </Button>
                </div>
              </>
            )}
          </Space>
        )}

        {x.passo === 1 && x.entidades && (
          <Space orientation="vertical" size={16} style={{ width: "100%" }}>
            {!x.entidades.proprietarios.length && !x.entidades.contentores.length ? (
              <Alert type="success" showIcon title={t("import.entities.all_ok")} />
            ) : (
              <Alert type="info" showIcon title={t("import.entities.intro")} />
            )}
            {x.entidades.proprietarios.length > 0 && (
              <Card size="small" title={t("import.entities.owners_title", { count: x.entidades.proprietarios.length })}>
                {x.entidades.proprietarios.map((p) => (
                  <Flex key={p} gap={8} align="center" style={{ marginBottom: 8 }} wrap>
                    <Typography.Text strong style={{ width: 220 }}>
                      {p}
                    </Typography.Text>
                    {x.resolvidos[`p:${p}`] ? (
                      <Tag color="success">{x.resolvidos[`p:${p}`]}</Tag>
                    ) : (
                      <>
                        <Select
                          showSearch
                          optionFilterProp="label"
                          style={{ width: 280 }}
                          value={escolhas[p] ?? CRIAR}
                          onChange={(v) => setEscolhas((e) => ({ ...e, [p]: v }))}
                          options={[
                            { value: CRIAR, label: t("web.import.create_new") },
                            ...x.entidades!.existentes.map((e) => ({ value: String(e.id), label: `${t("web.import.map_to")}: ${e.nome}` })),
                          ]}
                        />
                        <Button type="primary" onClick={() => x.resolverDono(p, escolhas[p] ?? CRIAR)}>
                          {t("import.entities.confirm_btn")}
                        </Button>
                      </>
                    )}
                  </Flex>
                ))}
              </Card>
            )}
            {x.entidades.contentores.length > 0 && (
              <Card size="small" title={t("import.entities.conts_title", { count: x.entidades.contentores.length })}>
                {x.entidades.contentores.map((c) => (
                  <Flex key={c} gap={8} align="center" style={{ marginBottom: 8 }} wrap>
                    <Typography.Text strong style={{ width: 220 }}>
                      {c}
                    </Typography.Text>
                    {x.resolvidos[`c:${c}`] ? (
                      <Tag color="success">{x.resolvidos[`c:${c}`]}</Tag>
                    ) : (
                      <>
                        <Input
                          style={{ width: 280 }}
                          placeholder={t("import.entities.cont_desc_placeholder")}
                          value={descricoes[c] ?? ""}
                          onChange={(e) => setDescricoes((d) => ({ ...d, [c]: e.target.value }))}
                        />
                        <Button type="primary" onClick={() => x.criarContentor(c, descricoes[c] ?? "")}>
                          {t("import.entities.create_cont_btn")}
                        </Button>
                      </>
                    )}
                  </Flex>
                ))}
              </Card>
            )}
            <Flex gap={8} align="center">
              <Button onClick={() => x.setPasso(0)}>{t("import.btn.previous")}</Button>
              <Button type="primary" disabled={!x.tudoResolvido} onClick={() => x.validar()}>
                {t("import.btn.next_validate")}
              </Button>
              {!x.tudoResolvido && <Typography.Text type="secondary">{t("import.entities.resolve_all_hint")}</Typography.Text>}
            </Flex>
          </Space>
        )}

        {x.passo === 2 && x.validacao && (
          <Space orientation="vertical" size={16} style={{ width: "100%" }}>
            <Flex gap={40}>
              <Statistic title={t("import.kpi.lines")} value={x.validacao.total} />
              <Statistic title={t("import.kpi.valid")} value={x.validacao.validas} />
              <Statistic
                title={t("import.kpi.errors")}
                value={x.validacao.total - x.validacao.validas}
                styles={{ content: x.validacao.erros.length ? { color: "#dc2626" } : undefined }}
              />
            </Flex>
            {x.validacao.erros.length ? (
              <Alert type="warning" showIcon title={t("import.validation_errors")} />
            ) : (
              <Alert
                type="success"
                showIcon
                title={t("import.validation_ok")}
                description={x.validacao.com_data ? t("import.date_adjustment_info", { count: x.validacao.com_data }) : undefined}
              />
            )}
            <Table<Linha>
              size="small"
              bordered
              rowKey="__row"
              dataSource={x.linhas}
              pagination={{ pageSize: 25, hideOnSinglePage: true, size: "small" }}
              scroll={{ x: true }}
              onRow={(l) => ({ onClick: () => corr.abrir(l), style: { cursor: "pointer" } })}
              columns={[
                { title: "#", dataIndex: "__row", width: 50 },
                ...COMPACTAS.map((c) => ({
                  title: x.col(c),
                  dataIndex: c,
                  render: (v: string, l: Linha) => {
                    const e = x.errosDaLinha(l.__row).find((y) => y.coluna === c);
                    return e ? (
                      <Typography.Text type="danger" title={t(e.erro)}>
                        {v || "—"} ⚠
                      </Typography.Text>
                    ) : (
                      v || "—"
                    );
                  },
                })),
                {
                  title: t("web.import.errors_title"),
                  key: "erros",
                  render: (_: unknown, l: Linha) =>
                    x.errosDaLinha(l.__row).map((e) => (
                      <Tag key={e.coluna} color="red">
                        {t(e.erro)}
                      </Tag>
                    )),
                },
              ]}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("import.edit_caption")}
            </Typography.Text>
            <Flex gap={8}>
              <Button onClick={() => x.setPasso(1)}>{t("import.btn.previous")}</Button>
              <Button type="primary" disabled={!!x.validacao.erros.length || !x.validacao.validas} loading={x.ocupado} onClick={x.importar}>
                {t("btn.import")}
              </Button>
            </Flex>
          </Space>
        )}

        {x.passo === 3 && x.relatorio && (
          <Result
            status="success"
            title={t("import.completed", { count: x.relatorio.importados })}
            extra={[
              <Button key="r" icon={<DownloadOutlined />} onClick={x.baixarRelatorio}>
                {t("import.download_report")}
              </Button>,
              <Button key="n" onClick={x.recomecar}>
                {t("import.btn.new_import")}
              </Button>,
              <Button key="s" type="primary" onClick={() => x.navigate("/stock-semen/lotes")}>
                {t("import.btn.view_stock")}
              </Button>,
            ]}
          >
            <Table
              size="small"
              bordered
              rowKey="stock_id"
              pagination={false}
              dataSource={x.relatorio.relatorio}
              columns={[
                { title: "#", dataIndex: "linha", width: 50 },
                { title: x.col("garanhao"), dataIndex: "garanhao" },
                { title: x.col("proprietario_nome"), dataIndex: "proprietario", render: (v) => v || "—" },
                { title: x.col("existencia_atual"), dataIndex: "palhetas", align: "right" },
                { title: t("web.import.adjusted"), dataIndex: "data_ajustada", render: (v) => v || "—" },
              ]}
            />
          </Result>
        )}
      </Spin>

      <Modal
        open={corr.linha !== null}
        onCancel={corr.fechar}
        title={corr.linha ? t("web.import.edit_row", { n: corr.linha.__row }) : ""}
        okText={t("web.import.revalidate")}
        cancelText={t("web.common.cancel")}
        onOk={() => form.submit()}
        width={760}
      >
        <Form form={form} layout="vertical" onFinish={corr.guardar}>
          <Row gutter={12}>
            {COLUNAS.map((c) => {
              const e = corr.linha && x.errosDaLinha(corr.linha.__row).find((y) => y.coluna === c);
              return (
                <Col key={c} xs={12} sm={8}>
                  <Form.Item name={c} label={x.col(c)} validateStatus={e ? "error" : undefined} help={e ? t(e.erro) : undefined}>
                    <Input />
                  </Form.Item>
                </Col>
              );
            })}
          </Row>
        </Form>
      </Modal>
    </Card>
  );
}

// ── Telemóvel ───────────────────────────────────────────────────────────────

function ImportarMobile({ x }: { x: X }) {
  const { t } = x;
  const corr = useCorrecao(x);
  const [mform] = MForm.useForm();
  useEffect(() => {
    if (corr.linha) mform.setFieldsValue(Object.fromEntries(COLUNAS.map((c) => [c, String(corr.linha![c] ?? "")])));
  }, [corr.linha, mform]);
  const passos = [t("import.wizard.step1"), t("import.wizard.step2"), t("import.wizard.step3"), t("import.wizard.step4")];

  return (
    <>
      <div style={{ background: "#fff", padding: "8px 0" }}>
        <MSteps current={x.passo}>
          {passos.map((p) => (
            <MSteps.Step key={p} title={p.replace(/^\d+\.\s*/, "")} />
          ))}
        </MSteps>
      </div>

      {x.passo === 0 && (
        <>
          <div style={{ padding: 12, color: "#666", fontSize: 13 }}>{t("import.hint")}</div>
          <div style={{ display: "flex", gap: 8, padding: "0 12px 12px" }}>
            <MButton size="small" onClick={() => x.modelo("xlsx")}>
              XLSX
            </MButton>
            <MButton size="small" onClick={() => x.modelo("csv")}>
              CSV
            </MButton>
          </div>
          <div style={{ padding: "0 12px" }}>
            <EscolherFicheiro x={x}>
              {(abrir) => (
                <MButton block color="primary" loading={x.ocupado} onClick={abrir}>
                  {t("web.import.choose_file")}
                </MButton>
              )}
            </EscolherFicheiro>
          </div>
          {x.linhas.length > 0 && (
            <>
              <List header={`${x.nome} — ${t("import.file_loaded", { count: x.linhas.length })}`} style={{ marginTop: 12 }}>
                {x.linhas.slice(0, 5).map((l) => (
                  <List.Item
                    key={l.__row}
                    description={`${l["data_embriovet/ref"] || "—"} · ${l.proprietario_nome || "—"} · ${l.contentor_codigo || "—"}`}
                    extra={l.existencia_atual}
                  >
                    {l.garanhao || "—"}
                  </List.Item>
                ))}
              </List>
              <div style={{ padding: 12 }}>
                <MButton block color="primary" loading={x.ocupado} onClick={x.verEntidades}>
                  {t("import.btn.next_entities")}
                </MButton>
              </div>
            </>
          )}
        </>
      )}

      {x.passo === 1 && x.entidades && (
        <>
          {!x.entidades.proprietarios.length && !x.entidades.contentores.length && (
            <div style={{ padding: 12, color: "var(--adm-color-success)" }}>{t("import.entities.all_ok")}</div>
          )}
          {x.entidades.proprietarios.length > 0 && (
            <List header={t("import.entities.owners_title", { count: x.entidades.proprietarios.length })}>
              {x.entidades.proprietarios.map((p) => (
                <List.Item
                  key={p}
                  description={x.resolvidos[`p:${p}`]}
                  extra={
                    !x.resolvidos[`p:${p}`] && (
                      <MButton size="mini" color="primary" onClick={() => x.resolverDono(p, CRIAR)}>
                        {t("web.import.create_new")}
                      </MButton>
                    )
                  }
                >
                  {p}
                </List.Item>
              ))}
            </List>
          )}
          {x.entidades.contentores.length > 0 && (
            <List header={t("import.entities.conts_title", { count: x.entidades.contentores.length })}>
              {x.entidades.contentores.map((c) => (
                <List.Item
                  key={c}
                  description={x.resolvidos[`c:${c}`]}
                  extra={
                    !x.resolvidos[`c:${c}`] && (
                      <MButton size="mini" color="primary" onClick={() => x.criarContentor(c, "")}>
                        {t("import.entities.create_cont_btn")}
                      </MButton>
                    )
                  }
                >
                  {c}
                </List.Item>
              ))}
            </List>
          )}
          <div style={{ display: "flex", gap: 8, padding: 12 }}>
            <MButton block onClick={() => x.setPasso(0)}>
              {t("import.btn.previous")}
            </MButton>
            <MButton block color="primary" disabled={!x.tudoResolvido} loading={x.ocupado} onClick={() => x.validar()}>
              {t("import.btn.next_validate")}
            </MButton>
          </div>
        </>
      )}

      {x.passo === 2 && x.validacao && (
        <>
          <div style={{ padding: 12, color: x.validacao.erros.length ? "var(--adm-color-warning)" : "var(--adm-color-success)" }}>
            {x.validacao.erros.length ? t("import.validation_errors") : t("import.validation_ok")} ({x.validacao.validas}/
            {x.validacao.total})
          </div>
          <List>
            {x.linhas.map((l) => {
              const erros = x.errosDaLinha(l.__row);
              return (
                <List.Item
                  key={l.__row}
                  arrow
                  onClick={() => corr.abrir(l)}
                  description={
                    erros.length ? (
                      <span style={{ color: "var(--adm-color-danger)" }}>{erros.map((e) => t(e.erro)).join(" · ")}</span>
                    ) : (
                      `${l["data_embriovet/ref"] || "—"} · ${l.proprietario_nome || "—"} · ${l.contentor_codigo || "—"}`
                    )
                  }
                  extra={erros.length ? <MTag color="danger">!</MTag> : l.existencia_atual}
                >
                  {t("web.import.row", { n: l.__row })} · {l.garanhao || "—"}
                </List.Item>
              );
            })}
          </List>
          <div style={{ display: "flex", gap: 8, padding: 12 }}>
            <MButton block onClick={() => x.setPasso(1)}>
              {t("import.btn.previous")}
            </MButton>
            <MButton
              block
              color="primary"
              disabled={!!x.validacao.erros.length || !x.validacao.validas}
              loading={x.ocupado}
              onClick={x.importar}
            >
              {t("btn.import")}
            </MButton>
          </div>
        </>
      )}

      {x.passo === 3 && x.relatorio && (
        <>
          <MResult status="success" title={t("import.completed", { count: x.relatorio.importados })} />
          <List>
            {x.relatorio.relatorio.map((r) => (
              <List.Item key={r.stock_id} description={r.proprietario || "—"} extra={r.palhetas}>
                {r.garanhao}
              </List.Item>
            ))}
          </List>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 12 }}>
            <MButton block color="primary" onClick={() => x.navigate("/stock-semen/lotes")}>
              {t("import.btn.view_stock")}
            </MButton>
            <MButton block onClick={x.recomecar}>
              {t("import.btn.new_import")}
            </MButton>
          </div>
        </>
      )}

      <Popup
        visible={corr.linha !== null}
        onMaskClick={corr.fechar}
        onClose={corr.fechar}
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, maxHeight: "88dvh", overflowY: "auto" }}
      >
        {corr.linha && (
          <>
            <Cabecalho>{t("web.import.edit_row", { n: corr.linha.__row })}</Cabecalho>
            <MForm form={mform} layout="horizontal" style={{ "--prefix-width": "8em" } as React.CSSProperties} onFinish={corr.guardar}>
              {COLUNAS.map((c) => {
                const e = x.errosDaLinha(corr.linha!.__row).find((y) => y.coluna === c);
                return (
                  <MForm.Item
                    key={c}
                    name={c}
                    label={x.col(c)}
                    description={e && <span style={{ color: "var(--adm-color-danger)" }}>{t(e.erro)}</span>}
                  >
                    <MInput clearable />
                  </MForm.Item>
                );
              })}
            </MForm>
            <div style={{ padding: 12, paddingBottom: "calc(12px + env(safe-area-inset-bottom))" }}>
              <MButton block color="primary" onClick={() => mform.submit()}>
                {t("web.import.revalidate")}
              </MButton>
            </div>
          </>
        )}
      </Popup>
    </>
  );
}
