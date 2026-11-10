import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import dayjs, { type Dayjs } from "dayjs";
import { Alert, Button, Card, Checkbox, DatePicker, Flex, Input, Modal, Space, Spin, Table, Tag, Typography } from "antd";
import { FilePdfOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  Checkbox as MCheckbox,
  Dialog,
  Input as MInput,
  List,
  TextArea,
} from "antd-mobile";

import { ApiError } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { useBrand } from "../../components/Brand";
import { useIsMobile } from "../../components/responsive";
import { confirmar, notifySuccess, useNotifyError } from "../../components/errors";
import { DataCampo, FolhaEcraInteiro } from "../../components/mobile";
import { dataCurta } from "../../components/csv";
import { numerosUsados, useFaturar, useResumo, type DonoFat, type Movimento, type PorFaturar } from "./api";

const ISO = "YYYY-MM-DD";
const nDias = (l: { inicio: string; fim: string }) => dayjs(l.fim).diff(dayjs(l.inicio), "day") + 1;

interface Grupo {
  chave: string;
  dono_id: number | null;
  nome: string;
  linhas: PorFaturar[];
  movimentos: { lote: string; m: Movimento }[];
  dias: number;
  ds: number;
}

function useTextosResumo() {
  const t = useT();
  return {
    mov: (m: Movimento) =>
      `${dataCurta(m.data)}: ${t("web.billing.mov.out", { count: m.quantidade })} — ${t(`web.billing.mov.${m.tipo}`, { detalhe: m.detalhe ?? "—" })}`,
    dias: (l: { inicio: string; fim: string }) => t("web.billing.days", { count: nDias(l) }),
    palhetas: (l: PorFaturar) => (l.tipo === "armazenamento" && l.palhetas != null ? t("web.billing.straws", { count: l.palhetas }) : ""),
    tipo: (l: PorFaturar) => t(`web.billing.type.${l.tipo}`),
    morada: (d?: DonoFat) => (d ? [d.morada, [d.codigo_postal, d.cidade].filter(Boolean).join(" ")].filter(Boolean).join(", ") : ""),
  };
}

/** Antes de marcar como faturado: o que vai ser faturado, por proprietário
 *  (uma fatura cada), com o porquê de cada mudança de palhetas, em PDF se
 *  se quiser. Só depois se escreve o número de cada fatura. */
export function ResumoFaturar({
  aberto,
  linhas: selecionadas,
  onClose,
}: {
  aberto: boolean;
  linhas: PorFaturar[];
  onClose: (feito: boolean) => void;
}) {
  const t = useT();
  const isMobile = useIsMobile();
  const tx = useTextosResumo();
  const faturar = useFaturar();
  const notifyError = useNotifyError();
  const [numeros, setNumeros] = useState<Record<string, string>>({});
  const [data, setData] = useState<Dayjs>(dayjs());
  const [acerto, setAcerto] = useState(false);
  const [obs, setObs] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [imprimir, setImprimir] = useState(false);

  // Período a faturar: começa pelo das linhas escolhidas e pode encurtar-se
  // (ex.: faturar só até ao fim do mês passado). O resto fica por faturar.
  const limites = useMemo<[Dayjs, Dayjs] | null>(() => {
    if (!selecionadas.length) return null;
    const ini = selecionadas.reduce((m, l) => (l.inicio < m ? l.inicio : m), selecionadas[0].inicio);
    const fim = selecionadas.reduce((m, l) => (l.fim > m ? l.fim : m), selecionadas[0].fim);
    return [dayjs(ini), dayjs(fim)];
  }, [selecionadas]);
  const [periodo, setPeriodo] = useState<[Dayjs, Dayjs] | null>(null);
  const linhas = useMemo(() => {
    if (!periodo) return selecionadas;
    const [de, ate] = [periodo[0].format(ISO), periodo[1].format(ISO)];
    return selecionadas.flatMap((l) => {
      const inicio = l.inicio > de ? l.inicio : de;
      const fim = l.fim < ate ? l.fim : ate;
      if (inicio > fim) return [];
      const dias = nDias({ inicio, fim });
      return [{ ...l, inicio, fim, dias, quantidade: l.tipo === "estadia" ? dias : dias * (l.palhetas ?? 0) }];
    });
  }, [selecionadas, periodo]);

  useEffect(() => {
    if (!aberto) return;
    setPeriodo(limites);
    setNumeros({});
    setData(dayjs());
    setAcerto(false);
    setObs("");
    setErro(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aberto]);

  const atalhosAte = limites
    ? [
        { label: t("web.billing.until_last_month"), data: dayjs().subtract(1, "month").endOf("month") },
        { label: t("web.billing.until_end_of", { ano: dayjs().year() - 1 }), data: dayjs(`${dayjs().year() - 1}-12-31`) },
      ]
        .filter((x) => !x.data.isBefore(limites[0], "day") && x.data.isBefore(limites[1], "day"))
        .map((x) => ({ label: x.label, value: [limites[0], x.data] as [Dayjs, Dayjs] }))
    : [];
  const foraDosLimites = (d: Dayjs) => !!limites && (d.isBefore(limites[0], "day") || d.isAfter(limites[1], "day"));

  const refs = useMemo(() => linhas.map((l) => ({ tipo: l.tipo, ref_id: l.ref_id, inicio: l.inicio, fim: l.fim })), [linhas]);
  const donoIds = useMemo(() => [...new Set(linhas.map((l) => l.dono_id).filter((x): x is number => x != null))], [linhas]);
  const q = useResumo(refs, donoIds, aberto);
  const donos = new Map((q.data?.donos ?? []).map((d) => [d.id, d]));

  const grupos = useMemo<Grupo[]>(() => {
    const porDono = new Map<string, Grupo>();
    for (const l of linhas) {
      const chave = String(l.dono_id ?? "sem");
      const g =
        porDono.get(chave) ??
        porDono
          .set(chave, { chave, dono_id: l.dono_id, nome: l.dono_nome ?? t("web.billing.no_owner"), linhas: [], movimentos: [], dias: 0, ds: 0 })
          .get(chave)!;
      g.linhas.push(l);
      if (l.tipo === "estadia") g.dias += nDias(l);
      else g.ds += nDias(l);
    }
    // Cada saída uma vez (o mesmo lote pode ter vários troços pedidos).
    const vistos = new Set<string>();
    for (const m of q.data?.movimentos ?? []) {
      const k = `${m.ref_id}|${m.data}|${m.tipo}|${m.detalhe}|${m.quantidade}`;
      if (vistos.has(k)) continue;
      vistos.add(k);
      const l = linhas.find((x) => x.tipo === "armazenamento" && x.ref_id === m.ref_id);
      if (l) porDono.get(String(l.dono_id ?? "sem"))?.movimentos.push({ lote: l.descricao, m });
    }
    for (const g of porDono.values()) {
      g.linhas.sort((a, b) => a.descricao.localeCompare(b.descricao) || a.inicio.localeCompare(b.inicio));
      g.movimentos.sort((a, b) => a.lote.localeCompare(b.lote) || a.m.data.localeCompare(b.m.data));
    }
    return [...porDono.values()].sort((a, b) => a.nome.localeCompare(b.nome));
  }, [linhas, q.data, t]);

  /** Número repetido (já usado noutro proprietário, ou escrito para dois
   *  nesta janela): normalmente é engano de escrita. Avisa e pergunta. */
  const repetidos = async (): Promise<string[]> => {
    const escritos = grupos.map((g) => ({ g, n: (numeros[g.chave] ?? "").trim() })).filter((x) => x.n);
    if (!escritos.length) return [];
    const norm = (n: string) => n.toLowerCase();
    const avisos: string[] = [];
    const vezes = new Map<string, number>();
    for (const { n } of escritos) vezes.set(norm(n), (vezes.get(norm(n)) ?? 0) + 1);
    for (const [n, k] of vezes) if (k > 1) avisos.push(t("web.billing.dup_same", { numero: escritos.find((x) => norm(x.n) === n)!.n }));
    try {
      for (const u of await numerosUsados(escritos.map((x) => x.n))) {
        const meu = escritos.find((x) => norm(x.n) === norm(u.fatura_numero));
        if (meu && meu.g.dono_id !== u.dono_id)
          avisos.push(t("web.billing.dup_used", { numero: u.fatura_numero, dono: u.dono_nome ?? t("web.billing.no_owner") }));
      }
    } catch {
      // Sem a verificação não se impede a gravação: é só um aviso.
    }
    return avisos;
  };
  const perguntar = (avisos: string[]) =>
    new Promise<boolean>((resolve) => {
      const texto = (
        <>
          {avisos.map((a) => (
            <div key={a}>{a}</div>
          ))}
          <div style={{ marginTop: 8 }}>{t("web.billing.dup_question")}</div>
        </>
      );
      if (isMobile)
        void Dialog.confirm({
          title: t("web.billing.dup_title"),
          content: texto,
          confirmText: t("web.billing.dup_ok"),
          cancelText: t("web.common.cancel"),
          onConfirm: () => resolve(true),
          onCancel: () => resolve(false),
        });
      else
        confirmar({
          titulo: t("web.billing.dup_title"),
          texto,
          ok: t("web.billing.dup_ok"),
          cancelar: t("web.common.cancel"),
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
    });

  const guardar = async () => {
    setErro(null);
    if (!linhas.length) return setErro(t("web.billing.nothing_in_period"));
    if (!acerto && grupos.some((g) => !numeros[g.chave]?.trim())) return setErro(t("web.billing.invoice_each"));
    const avisos = await repetidos();
    if (avisos.length && !(await perguntar(avisos))) return;
    try {
      const r = await faturar.mutateAsync({
        faturas: grupos.map((g) => ({
          dono_id: g.dono_id,
          fatura_numero: acerto ? (numeros[g.chave] ?? "").trim() : numeros[g.chave].trim(),
          fatura_data: data.format(ISO),
          acerto_inicial: acerto,
          observacoes: obs.trim() || undefined,
          linhas: g.linhas.map((l) => ({ tipo: l.tipo, ref_id: l.ref_id, inicio: l.inicio, fim: l.fim })),
        })),
      });
      notifySuccess(t("web.billing.marked", { n: r.linhas }));
      onClose(true);
    } catch (err) {
      notifyError(err);
      // Já faturado entretanto: a lista atualiza e escolhe-se de novo.
      if (err instanceof ApiError && err.code === "web.billing.error.changed") onClose(true);
    }
  };

  const pdf = () => setImprimir(true);
  const impressao = imprimir && <FolhaImpressao grupos={grupos} donos={donos} onFim={() => setImprimir(false)} />;
  const totalTexto = (g: Grupo) => t("web.billing.total_owner", { dias: g.dias, ds: g.ds });
  const numero = (g: Grupo) => numeros[g.chave] ?? "";
  const mudarNumero = (g: Grupo, v: string) => setNumeros((n) => ({ ...n, [g.chave]: v }));

  if (isMobile)
    return (
      <>
        <FolhaEcraInteiro
          visible={aberto}
          titulo={t("web.billing.review_title")}
          onCancel={() => onClose(false)}
          onOk={guardar}
          okText={t("web.billing.mark")}
          loading={faturar.isPending}
        >
          <div style={{ padding: "8px 12px", color: "#999", fontSize: 13 }}>{t("web.billing.review_help")}</div>
          {periodo && limites && (
            <List header={t("web.billing.period_to_bill")}>
              <DataMobile
                titulo={t("web.billing.from")}
                data={periodo[0]}
                min={limites[0]}
                max={periodo[1]}
                onChange={(d) => setPeriodo([d, periodo[1]])}
              />
              <DataMobile
                titulo={t("web.billing.until")}
                data={periodo[1]}
                min={periodo[0]}
                max={limites[1]}
                onChange={(d) => setPeriodo([periodo[0], d])}
              />
            </List>
          )}
          {grupos.map((g) => (
            <List
              key={g.chave}
              header={
                <div>
                  <b>{g.nome}</b>
                  {donos.get(g.dono_id ?? -1)?.nif && <span> · {t("web.billing.nif", { nif: donos.get(g.dono_id!)!.nif! })}</span>}
                  <div style={{ fontSize: 12 }}>{totalTexto(g)}</div>
                </div>
              }
            >
              {g.linhas.map((l) => (
                <List.Item
                  key={`${l.tipo}-${l.ref_id}-${l.inicio}`}
                  description={`${dataCurta(l.inicio)} – ${dataCurta(l.fim)}`}
                  extra={[tx.palhetas(l), tx.dias(l)].filter(Boolean).join(" · ")}
                >
                  {l.descricao}
                </List.Item>
              ))}
              {g.movimentos.map(({ lote, m }, i) => (
                <List.Item key={`m${i}`} style={{ fontSize: 12, color: "#888" }}>
                  {lote} — {tx.mov(m)}
                </List.Item>
              ))}
              {!acerto && (
                <List.Item title={t("web.billing.invoice_number")}>
                  <MInput clearable value={numero(g)} onChange={(v) => mudarNumero(g, v)} />
                </List.Item>
              )}
            </List>
          ))}
          <List>
            <List.Item>
              <MCheckbox checked={acerto} onChange={setAcerto}>
                {t("web.billing.initial")}
              </MCheckbox>
            </List.Item>
            <DataMobile titulo={t("web.billing.invoice_date")} data={data} onChange={setData} />
            <List.Item title={t("web.billing.notes")}>
              <TextArea value={obs} onChange={setObs} autoSize={{ minRows: 1 }} />
            </List.Item>
          </List>
          {erro && <div style={{ color: "#ff3141", padding: "8px 12px" }}>{erro}</div>}
          <div style={{ padding: 12 }}>
            <MButton block onClick={pdf} disabled={q.isPending}>
              {t("web.billing.pdf")}
            </MButton>
          </div>
        </FolhaEcraInteiro>
        {impressao}
      </>
    );

  return (
    <>
      <Modal
        open={aberto}
        title={t("web.billing.review_title")}
        width={960}
        onCancel={() => onClose(false)}
        destroyOnHidden
        footer={
          <Flex justify="space-between" align="center" wrap gap={8}>
            <Space wrap>
              <Checkbox checked={acerto} onChange={(e) => setAcerto(e.target.checked)}>
                {t("web.billing.initial")}
              </Checkbox>
              <Typography.Text type="secondary">{t("web.billing.invoice_date")}</Typography.Text>
              <DatePicker format="DD/MM/YYYY" allowClear={false} value={data} onChange={(v) => v && setData(v)} />
            </Space>
            <Space>
              <Button onClick={() => onClose(false)}>{t("web.common.cancel")}</Button>
              <Button icon={<FilePdfOutlined />} onClick={pdf} disabled={q.isPending}>
                {t("web.billing.pdf")}
              </Button>
              <Button type="primary" loading={faturar.isPending} onClick={guardar}>
                {t("web.billing.mark")}
              </Button>
            </Space>
          </Flex>
        }
      >
        <Typography.Paragraph type="secondary">{t("web.billing.review_help")}</Typography.Paragraph>
        {periodo && (
          <Space wrap style={{ marginBottom: 12 }}>
            <Typography.Text strong>{t("web.billing.period_to_bill")}</Typography.Text>
            <DatePicker.RangePicker
              format="DD/MM/YYYY"
              allowClear={false}
              value={periodo}
              disabledDate={foraDosLimites}
              presets={atalhosAte}
              onChange={(v) => v?.[0] && v[1] && setPeriodo([v[0], v[1]])}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("web.billing.period_help")}
            </Typography.Text>
          </Space>
        )}
        {q.isPending && <Spin style={{ display: "block", margin: 12 }} />}
        <Flex vertical gap={12}>
          {grupos.map((g) => {
            const d = donos.get(g.dono_id ?? -1);
            return (
              <Card
                key={g.chave}
                size="small"
                title={
                  <>
                    {g.nome}
                    {d?.nif && <Typography.Text type="secondary"> · {t("web.billing.nif", { nif: d.nif })}</Typography.Text>}
                  </>
                }
                extra={
                  acerto ? (
                    <Tag>{t("web.billing.initial_tag")}</Tag>
                  ) : (
                    <Input
                      placeholder={t("web.billing.invoice_number")}
                      value={numero(g)}
                      onChange={(e) => mudarNumero(g, e.target.value)}
                      maxLength={60}
                      status={erro && !numero(g).trim() ? "error" : undefined}
                      style={{ width: 200 }}
                    />
                  )
                }
              >
                <Table<PorFaturar>
                  size="small"
                  pagination={false}
                  rowKey={(l) => `${l.tipo}-${l.ref_id}-${l.inicio}`}
                  dataSource={g.linhas}
                  columns={[
                    {
                      title: t("web.billing.col.what"),
                      render: (_, l) => (
                        <>
                          <Tag color={l.tipo === "estadia" ? "blue" : "purple"}>{tx.tipo(l)}</Tag>
                          {l.descricao}
                        </>
                      ),
                    },
                    { title: t("web.billing.col.period"), render: (_, l) => `${dataCurta(l.inicio)} – ${dataCurta(l.fim)}` },
                    { title: t("web.billing.col.straws"), align: "right", render: (_, l) => tx.palhetas(l) },
                    { title: t("web.billing.col.days"), align: "right", render: (_, l) => tx.dias(l) },
                  ]}
                />
                {g.movimentos.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Typography.Text strong style={{ fontSize: 12 }}>
                      {t("web.billing.changes")}
                    </Typography.Text>
                    {g.movimentos.map(({ lote, m }, i) => (
                      <div key={i} style={{ fontSize: 12 }}>
                        <Typography.Text type="secondary">
                          {lote} — {tx.mov(m)}
                        </Typography.Text>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ marginTop: 8, textAlign: "right" }}>
                  <Typography.Text strong>{totalTexto(g)}</Typography.Text>
                </div>
              </Card>
            );
          })}
        </Flex>
        <Input.TextArea
          placeholder={t("web.billing.notes")}
          value={obs}
          onChange={(e) => setObs(e.target.value)}
          autoSize={{ minRows: 1 }}
          style={{ marginTop: 12 }}
        />
        {erro && <Alert type="error" showIcon title={erro} style={{ marginTop: 12 }} />}
      </Modal>
      {impressao}
    </>
  );
}

function DataMobile({
  titulo,
  data,
  onChange,
  min,
  max,
}: {
  titulo: string;
  data: Dayjs;
  onChange: (d: Dayjs) => void;
  min?: Dayjs;
  max?: Dayjs;
}) {
  const ref = useRef<{ open: () => void }>(null);
  return (
    <List.Item title={titulo} arrow onClick={() => ref.current?.open()}>
      <DataCampo
        ref={ref}
        value={data.format(ISO)}
        min={min?.toDate()}
        max={max?.toDate()}
        onChange={(v) => v && onChange(dayjs(v))}
      />
    </List.Item>
  );
}

/** Folha para imprimir / guardar em PDF (o "Guardar como PDF" do browser):
 *  só ela aparece na impressão. Um proprietário por página. */
function FolhaImpressao({ grupos, donos, onFim }: { grupos: Grupo[]; donos: Map<number, DonoFat>; onFim: () => void }) {
  const t = useT();
  const tx = useTextosResumo();
  const { company_name, logo_base64 } = useBrand();
  const logo = logo_base64 && (logo_base64.startsWith("data:") ? logo_base64 : `data:image/png;base64,${logo_base64}`);

  const fimRef = useRef(onFim);
  fimRef.current = onFim;
  useEffect(() => {
    document.body.classList.add("a-imprimir");
    const fim = () => {
      document.body.classList.remove("a-imprimir");
      fimRef.current();
    };
    window.addEventListener("afterprint", fim, { once: true });
    // Dá tempo ao React de pôr a folha no ecrã antes de abrir a impressão.
    const id = window.setTimeout(() => window.print(), 50);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("afterprint", fim);
      document.body.classList.remove("a-imprimir");
    };
  }, []);

  const celula = { border: "1px solid #ccc", padding: "4px 6px", fontSize: 12 } as const;
  return createPortal(
    <div className="folha-impressao">
      {grupos.map((g, i) => {
        const d = donos.get(g.dono_id ?? -1);
        return (
          <section key={g.chave} style={{ pageBreakBefore: i ? "always" : undefined, fontFamily: "sans-serif", color: "#000" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              {logo && <img src={logo} alt="" style={{ height: 48, objectFit: "contain" }} />}
              <div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{company_name}</div>
                <div style={{ fontSize: 12 }}>{t("web.billing.print_title")}</div>
              </div>
              <div style={{ marginLeft: "auto", fontSize: 12 }}>{t("web.billing.print_date", { data: dayjs().format("DD/MM/YYYY") })}</div>
            </div>
            <div style={{ marginBottom: 12, fontSize: 13 }}>
              <div style={{ fontWeight: 700 }}>{d?.nome_completo || g.nome}</div>
              {d?.nif && <div>{t("web.billing.nif", { nif: d.nif })}</div>}
              {tx.morada(d) && <div>{tx.morada(d)}</div>}
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {[t("web.billing.col.what"), t("web.billing.col.period"), t("web.billing.col.straws"), t("web.billing.col.days")].map((h) => (
                    <th key={h} style={{ ...celula, textAlign: "left", background: "#f2f2f2" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {g.linhas.map((l) => (
                  <tr key={`${l.tipo}-${l.ref_id}-${l.inicio}`}>
                    <td style={celula}>
                      {tx.tipo(l)} — {l.descricao}
                    </td>
                    <td style={celula}>
                      {dataCurta(l.inicio)} – {dataCurta(l.fim)}
                    </td>
                    <td style={{ ...celula, textAlign: "right" }}>{tx.palhetas(l)}</td>
                    <td style={{ ...celula, textAlign: "right" }}>{tx.dias(l)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {g.movimentos.length > 0 && (
              <div style={{ marginTop: 12, fontSize: 12 }}>
                <div style={{ fontWeight: 700 }}>{t("web.billing.changes")}</div>
                {g.movimentos.map(({ lote, m }, j) => (
                  <div key={j}>
                    {lote} — {tx.mov(m)}
                  </div>
                ))}
              </div>
            )}
            <div style={{ marginTop: 12, textAlign: "right", fontWeight: 700, fontSize: 13 }}>
              {t("web.billing.total_owner", { dias: g.dias, ds: g.ds })}
            </div>
          </section>
        );
      })}
    </div>,
    document.body,
  );
}
