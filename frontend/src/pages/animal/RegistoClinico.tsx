import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { PlusOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Descriptions,
  Drawer,
  Flex,
  Input,
  InputNumber,
  Modal,
  Radio,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  Button as MButton,
  Checkbox as MCheckbox,
  DatePicker as MDatePicker,
  Dialog,
  DotLoading,
  Input as MInput,
  List,
  Popup,
  Selector,
  Stepper,
  TextArea,
} from "antd-mobile";

import { api } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { useBrand } from "../../components/Brand";
import { useUser } from "../../components/User";
import { confirmar, notifySuccess, useNotifyError } from "../../components/errors";
import { Cabecalho } from "../../components/mobile";
import type { Animal } from "./api";

/* Registo clínico das éguas — desenho com ovário esquerdo/direito, útero e
 * cérvix; DG (diagnóstico de gestação), TX (tratamento), ! (prioritário) e
 * INS (inseminação). Desenhado pelo utilizador em folhas (out. 2026).
 * Computador: antd; telemóvel: antd-mobile — como as outras abas da ficha. */

type Parte = "OE" | "OD" | "UT" | "CER";
type Ficha = Parte | "TX" | "DG";
interface Foliculo {
  tamanho: number; // 9 = "<10", 61 = ">60"
  achados: string[];
}
interface Ovario {
  foliculos: Foliculo[];
  comentario?: string;
}
interface Utero {
  edema: number;
  liquido: number;
  comentario?: string;
}
interface Cervix {
  grau: number;
  comentario?: string;
}
interface Tratamento {
  ocitocina?: { vezes: number; hora: string } | null;
  pg?: number;
  p4?: boolean;
  infusao?: { ab: string[]; abOutro?: string; mucolitico?: boolean; outro?: string } | null;
  zaragatoa?: boolean;
  lavagem?: number;
  inducao?: { data: string; produto?: string } | null;
  marcar?: { dias: string; data?: string | null } | null;
}
interface Dados {
  OE?: Ovario;
  OD?: Ovario;
  UT?: Utero;
  CER?: Cervix;
  TX?: Tratamento;
  DG?: string;
}
interface Historico {
  id: number;
  data_registo: string;
  utilizador: string | null;
  prioritario: boolean;
  antigo: boolean;
  texto?: string;
  dados: Dados;
}
interface Resposta {
  cliente: string | null;
  local: string | null;
  garanhao: string | null;
  estadia_ativa: boolean;
  historico: Historico[];
  tamanho_inicial: { OE: number; OD: number };
  tratamentos_anteriores: { data_registo: string; texto: string }[];
  antibioticos: string[];
  infusoes: string[];
}
interface Novo {
  id?: number; // a corrigir um registo existente
  data: string;
  dados: Dados;
  prioritario: boolean;
}

const ACHADOS = ["NS", "OV", "FH", "MF", "CL"];
const EDEMA = ["0", "+", "++", "+++"];
const LIQUIDO = ["0", "<2 cm", "+", "++", "+++"];
const HORAS = ["8h", "10h", "12h", "14h", "16h"];
const mm = (n: number) => (n <= 9 ? "<10" : n >= 61 ? ">60" : String(n));

/** Resumo curto de cada parte (tabela, desenho). */
function useResumo() {
  const t = useT();
  const cervix = (g: number) => t(`web.registo.cervix.${g}`);
  const tx = (x?: Tratamento) => {
    if (!x) return "";
    const inf = x.infusao;
    return [
      x.ocitocina && `${t("web.registo.tx.ocitocina")} ${x.ocitocina.vezes}× ${x.ocitocina.hora}`,
      x.pg && `PG ${x.pg}×`,
      x.p4 && "P4",
      inf &&
        `${t("web.registo.tx.infusao")} ${[...inf.ab, inf.abOutro, inf.mucolitico && t("web.registo.tx.mucolitico"), inf.outro].filter(Boolean).join(" + ")}`,
      x.zaragatoa && t("web.registo.tx.zaragatoa"),
      x.lavagem && `${t("web.registo.tx.lavagem")} ${x.lavagem}×`,
      x.inducao &&
        `${t("web.registo.tx.inducao")} ${x.inducao.produto ? `${x.inducao.produto} ` : ""}${dayjs(x.inducao.data).format("DD/MM HH:mm")}`,
    ]
      .filter(Boolean)
      .join(" · ");
  };
  return (d: Dados, f: Ficha): string => {
    if (f === "OE" || f === "OD") return d[f]?.foliculos.map((x) => [`${mm(x.tamanho)} mm`, ...x.achados].join(" ")).join(" · ") ?? "";
    if (f === "UT") return d.UT ? `Ed ${EDEMA[d.UT.edema]} · ${t("web.registo.liquid_short")} ${LIQUIDO[d.UT.liquido]}` : "";
    if (f === "CER") return d.CER ? cervix(d.CER.grau) : "";
    if (f === "DG") return d.DG ? t(`web.registo.dg.${d.DG}`) : "";
    return tx(d.TX);
  };
}

// ── Campos (antd no computador, antd-mobile no telemóvel) ───────────────────

interface Op {
  label: string;
  value: string;
}

/** Uma opção de várias (botões). */
function Escolha({ opcoes, valor, onChange }: { opcoes: Op[]; valor?: string; onChange: (v: string) => void }) {
  if (useIsMobile())
    return (
      <Selector
        columns={Math.min(opcoes.length, 5)}
        showCheckMark={false}
        value={valor != null ? [valor] : []}
        onChange={(v) => v[0] != null && onChange(v[0])}
        options={opcoes}
        style={{ "--padding": "6px 0" } as React.CSSProperties}
      />
    );
  return <Radio.Group optionType="button" buttonStyle="solid" options={opcoes} value={valor} onChange={(e) => onChange(e.target.value)} />;
}

/** Várias opções ao mesmo tempo. */
function Multiplas({ opcoes, valor, onChange }: { opcoes: string[]; valor: string[]; onChange: (v: string[]) => void }) {
  if (useIsMobile())
    return (
      <Selector
        multiple
        columns={Math.min(opcoes.length, 5)}
        showCheckMark={false}
        value={valor}
        onChange={onChange}
        options={opcoes.map((a) => ({ label: a, value: a }))}
        style={{ "--padding": "6px 0" } as React.CSSProperties}
      />
    );
  return <Checkbox.Group options={opcoes} value={valor} onChange={(v) => onChange(v as string[])} />;
}

/** Tamanho do folículo em mm (9 = "<10", 61 = ">60"). */
function Tamanho({ valor, onChange }: { valor: number; onChange: (v: number) => void }) {
  const parser = (s?: string) => (!s ? 25 : s.startsWith("<") ? 9 : s.startsWith(">") ? 61 : Number(s.replace(/\D/g, "")) || 25);
  if (useIsMobile())
    return <Stepper min={9} max={61} digits={0} value={valor} formatter={(v) => mm(v ?? 25)} parser={parser} onChange={onChange} />;
  return (
    <InputNumber
      min={9}
      max={61}
      value={valor}
      formatter={(v) => mm(Number(v))}
      parser={parser}
      onChange={(v) => v != null && onChange(v)}
      suffix="mm"
      style={{ width: 110 }}
    />
  );
}

function Marca({ ativo, onChange, children }: { ativo: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  if (useIsMobile())
    return (
      <MCheckbox checked={ativo} onChange={onChange} style={{ "--icon-size": "18px", "--font-size": "15px" } as React.CSSProperties}>
        {children}
      </MCheckbox>
    );
  return (
    <Checkbox checked={ativo} onChange={(e) => onChange(e.target.checked)}>
      {children}
    </Checkbox>
  );
}

const caixaM: React.CSSProperties = { background: "#f5f5f5", borderRadius: 6, padding: "6px 8px" };

function Texto({ valor, onChange, placeholder }: { valor?: string; onChange: (v: string) => void; placeholder: string }) {
  if (useIsMobile()) return <MInput placeholder={placeholder} value={valor ?? ""} onChange={onChange} style={caixaM} />;
  return <Input placeholder={placeholder} value={valor ?? ""} onChange={(e) => onChange(e.target.value)} />;
}

function Comentario({ value, onChange }: { value?: string; onChange: (v: string) => void }) {
  const t = useT();
  if (useIsMobile())
    return (
      <TextArea placeholder={t("web.registo.comment")} value={value ?? ""} onChange={onChange} autoSize={{ minRows: 2 }} style={caixaM} />
    );
  return (
    <Input.TextArea
      placeholder={t("web.registo.comment")}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      autoSize={{ minRows: 2 }}
    />
  );
}

/** Data (e hora). Computador: DatePicker do antd; telemóvel: botão + roda. */
function DataHora({
  valor,
  onChange,
  hora = true,
  futuro,
}: {
  valor: string;
  onChange: (v: string) => void;
  hora?: boolean;
  futuro?: boolean; // true = só futuro; false = só passado
}) {
  const [aberto, setAberto] = useState(false);
  const fmt = hora ? "DD/MM/YYYY HH:mm" : "DD/MM/YYYY";
  const iso = (d: dayjs.Dayjs) => (hora ? d.format("YYYY-MM-DDTHH:mm:ss") : d.format("YYYY-MM-DD"));
  if (useIsMobile())
    return (
      <>
        <MButton size="small" onClick={() => setAberto(true)}>
          {dayjs(valor).format(fmt)}
        </MButton>
        <MDatePicker
          visible={aberto}
          precision={hora ? "minute" : "day"}
          onClose={() => setAberto(false)}
          value={new Date(hora ? valor : `${valor}T12:00:00`)}
          min={futuro === true ? new Date() : undefined}
          max={futuro === false ? new Date() : undefined}
          onConfirm={(d) => onChange(iso(dayjs(d)))}
        />
      </>
    );
  return (
    <DatePicker
      allowClear={false}
      showTime={hora ? { format: "HH:mm" } : false}
      format={fmt}
      value={dayjs(valor)}
      disabledDate={(d) => (futuro === true ? d.isBefore(dayjs(), "day") : futuro === false ? d.isAfter(dayjs(), "day") : false)}
      onChange={(d) => d && onChange(iso(d))}
    />
  );
}

function Seccao({ titulo, children, direita }: { titulo: string; children: ReactNode; direita?: ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <Flex justify="space-between" align="center" style={{ marginBottom: 4 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {titulo}
        </Typography.Text>
        {direita}
      </Flex>
      {children}
    </div>
  );
}

function Ajuda({ children }: { children: ReactNode }) {
  return (
    <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 4 }}>
      {children}
    </Typography.Text>
  );
}

function Guardar({ onClick, children }: { onClick: () => void; children?: ReactNode }) {
  const t = useT();
  if (useIsMobile())
    return (
      <MButton block color="primary" style={{ marginTop: 12 }} onClick={onClick}>
        {children ?? t("btn.save")}
      </MButton>
    );
  return (
    <Button block type="primary" style={{ marginTop: 12 }} onClick={onClick}>
      {children ?? t("btn.save")}
    </Button>
  );
}

const indices = (valores: string[]): Op[] => valores.map((label, i) => ({ label, value: String(i) }));

// ── Fichas ──────────────────────────────────────────────────────────────────

function FichaOvario({ inicial, atual, onGuardar }: { inicial: number; atual?: Ovario; onGuardar: (v: Ovario) => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const [ov, setOv] = useState<Ovario>(atual ?? { foliculos: [{ tamanho: inicial, achados: [] }] });
  const mudar = (i: number, f: Partial<Foliculo>) =>
    setOv((o) => ({ ...o, foliculos: o.foliculos.map((x, j) => (j === i ? { ...x, ...f } : x)) }));
  const remover = (i: number) => setOv((o) => ({ ...o, foliculos: o.foliculos.filter((_, j) => j !== i) }));
  return (
    <>
      {ov.foliculos.map((f, i) => (
        <Seccao
          key={i}
          titulo={t("web.registo.follicle", { n: i + 1 })}
          direita={
            i > 0 &&
            (isMobile ? (
              <MButton size="mini" color="danger" fill="none" onClick={() => remover(i)}>
                {t("btn.remove")}
              </MButton>
            ) : (
              <Button size="small" type="link" danger onClick={() => remover(i)}>
                {t("btn.remove")}
              </Button>
            ))
          }
        >
          <Flex vertical gap={6}>
            <Tamanho valor={f.tamanho} onChange={(v) => mudar(i, { tamanho: v })} />
            <Multiplas opcoes={ACHADOS} valor={f.achados} onChange={(v) => mudar(i, { achados: v })} />
          </Flex>
        </Seccao>
      ))}
      <Ajuda>{t("web.registo.findings_legend")}</Ajuda>
      <div style={{ margin: "10px 0" }}>
        {isMobile ? (
          <MButton block size="small" onClick={() => setOv((o) => ({ ...o, foliculos: [...o.foliculos, { tamanho: 25, achados: [] }] }))}>
            + {t("web.registo.add_follicle")}
          </MButton>
        ) : (
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setOv((o) => ({ ...o, foliculos: [...o.foliculos, { tamanho: 25, achados: [] }] }))}
          >
            {t("web.registo.add_follicle")}
          </Button>
        )}
        <Ajuda>{t("web.registo.follicle_hint")}</Ajuda>
      </div>
      <Comentario value={ov.comentario} onChange={(v) => setOv({ ...ov, comentario: v })} />
      <Guardar onClick={() => onGuardar(ov)} />
    </>
  );
}

function FichaUtero({ atual, onGuardar }: { atual?: Utero; onGuardar: (v: Utero) => void }) {
  const t = useT();
  const [u, setU] = useState<Utero>(atual ?? { edema: 0, liquido: 0 });
  return (
    <>
      <Seccao titulo={t("web.registo.edema")}>
        <Escolha opcoes={indices(EDEMA)} valor={String(u.edema)} onChange={(v) => setU({ ...u, edema: Number(v) })} />
      </Seccao>
      <Seccao titulo={t("web.registo.liquid")}>
        <Escolha opcoes={indices(LIQUIDO)} valor={String(u.liquido)} onChange={(v) => setU({ ...u, liquido: Number(v) })} />
      </Seccao>
      <Comentario value={u.comentario} onChange={(v) => setU({ ...u, comentario: v })} />
      <Guardar onClick={() => onGuardar(u)} />
    </>
  );
}

function FichaCervix({ atual, onGuardar }: { atual?: Cervix; onGuardar: (v: Cervix) => void }) {
  const t = useT();
  const [c, setC] = useState<Cervix>(atual ?? { grau: 1 });
  return (
    <>
      <Seccao titulo={t("web.registo.grade")}>
        <Escolha
          opcoes={[1, 2, 3].map((g) => ({ label: t(`web.registo.cervix.${g}`), value: String(g) }))}
          valor={String(c.grau)}
          onChange={(v) => setC({ ...c, grau: Number(v) })}
        />
      </Seccao>
      <Comentario value={c.comentario} onChange={(v) => setC({ ...c, comentario: v })} />
      <Guardar onClick={() => onGuardar(c)} />
    </>
  );
}

function FichaDG({ atual, onGuardar }: { atual?: string; onGuardar: (v: string | undefined) => void }) {
  const t = useT();
  const [v, setV] = useState(atual ?? "");
  return (
    <>
      <Escolha
        opcoes={[
          ...["Positivo", "Negativo", "Inconclusivo"].map((d) => ({ label: t(`web.registo.dg.${d}`), value: d })),
          { label: "—", value: "" },
        ]}
        valor={v}
        onChange={setV}
      />
      <Ajuda>{t("web.registo.dg_help")}</Ajuda>
      <Guardar onClick={() => onGuardar(v || undefined)} />
    </>
  );
}

function FichaTX({ r, atual, onGuardar }: { r: Resposta; atual?: Tratamento; onGuardar: (v: Tratamento | undefined) => void }) {
  const t = useT();
  const resumo = useResumo();
  const [x, setX] = useState<Tratamento>(atual ?? {});
  const inf = x.infusao ?? { ab: [] };
  const vezes = (n: number, mudar: (n: number) => void) => (
    <Escolha
      opcoes={["1×", "2×", "3×", "4×"].map((label, i) => ({ label, value: String(i + 1) }))}
      valor={String(n)}
      onChange={(v) => mudar(Number(v))}
    />
  );
  const linha = (rotulo: string, ativo: boolean, alternar: () => void, conteudo?: ReactNode) => (
    <div style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 0" }}>
      <Marca ativo={ativo} onChange={alternar}>
        {rotulo}
      </Marca>
      {ativo && conteudo && (
        <Flex vertical gap={6} style={{ marginTop: 6, paddingLeft: 24 }}>
          {conteudo}
        </Flex>
      )}
    </div>
  );
  const vazio = !x.ocitocina && !x.pg && !x.p4 && !x.infusao && !x.zaragatoa && !x.lavagem && !x.inducao;

  return (
    <>
      <Seccao titulo={t("web.registo.previous_tx")}>
        {!r.tratamentos_anteriores.length ? (
          <Typography.Text type="secondary">—</Typography.Text>
        ) : (
          r.tratamentos_anteriores.map((a) => (
            <div key={a.data_registo} style={{ fontSize: 12 }}>
              <b>{dayjs(a.data_registo).format("DD/MM")}</b> · {a.texto}
            </div>
          ))
        )}
      </Seccao>
      {linha(
        t("web.registo.tx.ocitocina"),
        !!x.ocitocina,
        () => setX({ ...x, ocitocina: x.ocitocina ? null : { vezes: 1, hora: "8h" } }),
        x.ocitocina && (
          <>
            {vezes(x.ocitocina.vezes, (n) => setX({ ...x, ocitocina: { ...x.ocitocina!, vezes: n } }))}
            <Escolha
              opcoes={HORAS.map((h) => ({ label: h, value: h }))}
              valor={x.ocitocina.hora}
              onChange={(h) => setX({ ...x, ocitocina: { ...x.ocitocina!, hora: h } })}
            />
            <Ajuda>{t(`web.registo.ocitocina.${x.ocitocina.vezes}`)}</Ajuda>
          </>
        ),
      )}
      {linha(
        "PG",
        !!x.pg,
        () => setX({ ...x, pg: x.pg ? 0 : 1 }),
        vezes(x.pg || 1, (n) => setX({ ...x, pg: n })),
      )}
      {linha("P4", !!x.p4, () => setX({ ...x, p4: !x.p4 }))}
      {linha(
        t("web.registo.tx.infusao"),
        !!x.infusao,
        () => setX({ ...x, infusao: x.infusao ? null : inf }),
        <>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {t("web.registo.antibiotic")}
          </Typography.Text>
          <Multiplas opcoes={r.antibioticos} valor={inf.ab} onChange={(v) => setX({ ...x, infusao: { ...inf, ab: v } })} />
          <Texto
            placeholder={t("web.registo.other_antibiotic")}
            valor={inf.abOutro}
            onChange={(v) => setX({ ...x, infusao: { ...inf, abOutro: v } })}
          />
          <Marca ativo={!!inf.mucolitico} onChange={(on) => setX({ ...x, infusao: { ...inf, mucolitico: on } })}>
            {t("web.registo.tx.mucolitico")}
          </Marca>
          {r.infusoes.length > 0 && (
            <Escolha
              opcoes={r.infusoes.map((a) => ({ label: a, value: a }))}
              valor={inf.outro}
              onChange={(v) => setX({ ...x, infusao: { ...inf, outro: v } })}
            />
          )}
          <Texto
            placeholder={t("web.registo.other_infusion")}
            valor={inf.outro}
            onChange={(v) => setX({ ...x, infusao: { ...inf, outro: v } })}
          />
        </>,
      )}
      {linha(t("web.registo.tx.zaragatoa"), !!x.zaragatoa, () => setX({ ...x, zaragatoa: !x.zaragatoa }))}
      {linha(
        t("web.registo.tx.lavagem"),
        !!x.lavagem,
        () => setX({ ...x, lavagem: x.lavagem ? 0 : 1 }),
        vezes(x.lavagem || 1, (n) => setX({ ...x, lavagem: n })),
      )}
      {linha(
        t("web.registo.tx.inducao"),
        !!x.inducao,
        () =>
          setX({
            ...x,
            inducao: x.inducao ? null : { data: dayjs().add(1, "day").hour(20).minute(0).second(0).format("YYYY-MM-DDTHH:mm:ss") },
          }),
        x.inducao && (
          <>
            <Texto
              placeholder={t("web.registo.product_optional")}
              valor={x.inducao.produto}
              onChange={(v) => setX({ ...x, inducao: { ...x.inducao!, produto: v } })}
            />
            <div>
              <DataHora futuro valor={x.inducao.data} onChange={(d) => setX({ ...x, inducao: { ...x.inducao!, data: d } })} />
            </div>
          </>
        ),
      )}

      <div style={{ padding: "12px 0 4px" }}>
        <Marca ativo={!!x.marcar} onChange={(on) => setX({ ...x, marcar: on ? { dias: "1" } : null })}>
          <b>{t("web.registo.mark_tx")}</b>
        </Marca>
        {x.marcar && (
          <Flex vertical gap={6} style={{ marginTop: 6, paddingLeft: 24 }}>
            <Escolha
              opcoes={[
                { label: t("web.registo.days", { n: 1 }), value: "1" },
                { label: t("web.registo.days", { n: 2 }), value: "2" },
                { label: t("web.registo.days", { n: 3 }), value: "3" },
                { label: t("web.registo.agenda"), value: "agenda" },
              ]}
              valor={x.marcar.dias}
              onChange={(v) =>
                setX({
                  ...x,
                  marcar: { dias: v, data: v === "agenda" ? (x.marcar?.data ?? dayjs().add(1, "day").format("YYYY-MM-DD")) : null },
                })
              }
            />
            {x.marcar.dias === "agenda" && x.marcar.data && (
              <div>
                <DataHora hora={false} futuro valor={x.marcar.data} onChange={(d) => setX({ ...x, marcar: { ...x.marcar!, data: d } })} />
              </div>
            )}
            <Ajuda>{t("web.registo.mark_tx_help")}</Ajuda>
          </Flex>
        )}
      </div>

      {!vazio && <Ajuda>{resumo({ TX: x }, "TX")}</Ajuda>}
      <Guardar onClick={() => onGuardar(vazio ? undefined : x)}>{t("web.registo.save_tx")}</Guardar>
    </>
  );
}

// ── Desenho com os 4 pontos ─────────────────────────────────────────────────

function Desenho({ dados, onTocar }: { dados: Dados; onTocar: (p: Parte) => void }) {
  const { primary_color } = useBrand();
  const resumo = useResumo();
  const ponto = (p: Parte, cx: number, cy: number, r: number) => {
    const feito = !!dados[p];
    return (
      <g onClick={() => onTocar(p)} style={{ cursor: "pointer" }}>
        <circle cx={cx} cy={cy} r={r + 12} fill="transparent" />
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill={feito ? `${primary_color}22` : "#fff"}
          stroke={feito ? primary_color : "#bfbfbf"}
          strokeWidth={1.5}
        />
        <text x={cx} y={cy + 5} textAnchor="middle" fontSize={14} fontWeight={600} fill={feito ? primary_color : "#595959"}>
          {p}
        </text>
        {feito && (
          <text x={cx} y={cy + r + 15} textAnchor="middle" fontSize={11} fill="#8c8c8c">
            {resumo(dados, p).slice(0, 24)}
          </text>
        )}
      </g>
    );
  };
  return (
    <svg viewBox="0 0 360 320" style={{ width: "100%", maxWidth: 300, display: "block", margin: "0 auto", touchAction: "manipulation" }}>
      <path
        d="M70 70 C 95 120, 140 150, 170 175 L 190 175 C 220 150, 265 120, 290 70"
        fill="none"
        stroke="#ecd3d3"
        strokeWidth={18}
        strokeLinecap="round"
      />
      <path d="M180 175 L 180 255" stroke="#ecd3d3" strokeWidth={28} strokeLinecap="round" />
      {ponto("OE", 60, 58, 26)}
      {ponto("OD", 300, 58, 26)}
      {ponto("UT", 180, 182, 30)}
      {ponto("CER", 180, 278, 24)}
    </svg>
  );
}

// ── Detalhe de um registo (tudo, com comentários) ───────────────────────────

/** Linhas [título, conteúdo] do registo inteiro — Descriptions no computador, List no telemóvel. */
function useLinhasDetalhe() {
  const t = useT();
  const resumo = useResumo();
  return (h: Historico): [string, ReactNode][] => {
    if (h.antigo) return [[t("web.registo.old"), h.texto || "—"]];
    const d = h.dados;
    const com = (corpo: ReactNode, comentario?: string) => (
      <>
        {corpo}
        {comentario && (
          <Typography.Text type="secondary" italic style={{ display: "block" }}>
            “{comentario}”
          </Typography.Text>
        )}
      </>
    );
    const linhas: [string, ReactNode][] = [];
    for (const p of ["OE", "OD"] as const)
      if (d[p])
        linhas.push([
          t(`web.registo.part.${p}`),
          com(
            d[p]!.foliculos.map((f, i) => (
              <div key={i}>
                {t("web.registo.follicle", { n: i + 1 })}: <b>{mm(f.tamanho)}</b>
                {f.achados.length > 0 && ` · ${f.achados.join(", ")}`}
              </div>
            )),
            d[p]!.comentario,
          ),
        ]);
    if (d.UT) linhas.push([t("web.registo.part.UT"), com(resumo(d, "UT"), d.UT.comentario)]);
    if (d.CER) linhas.push([t("web.registo.part.CER"), com(resumo(d, "CER"), d.CER.comentario)]);
    if (d.DG) linhas.push([t("web.registo.part.DG"), resumo(d, "DG")]);
    if (d.TX)
      linhas.push([
        t("web.registo.part.TX"),
        <>
          {resumo(d, "TX") || "—"}
          {d.TX.marcar && (
            <Typography.Text type="secondary" style={{ display: "block" }}>
              {t("web.registo.mark_tx")}:{" "}
              {d.TX.marcar.dias === "agenda"
                ? dayjs(d.TX.marcar.data).format("DD/MM/YYYY")
                : t("web.registo.days", { n: d.TX.marcar.dias })}
            </Typography.Text>
          )}
        </>,
      ]);
    return linhas.length ? linhas : [["", "—"]];
  };
}

function Detalhe({ h }: { h: Historico }) {
  const t = useT();
  const linhas = useLinhasDetalhe()(h);
  const cabeca = (
    <>
      {dayjs(h.data_registo).format("DD/MM/YYYY HH:mm")} · {h.utilizador ?? "—"}
      {h.prioritario && (
        <Tag color="red" style={{ marginLeft: 8 }}>
          ! {t("web.registo.priority")}
        </Tag>
      )}
    </>
  );
  if (useIsMobile())
    return (
      <List header={cabeca} style={{ "--padding-left": "0", "--padding-right": "0" } as React.CSSProperties}>
        {linhas.map(([titulo, corpo], i) => (
          <List.Item key={i} description={titulo}>
            {corpo}
          </List.Item>
        ))}
      </List>
    );
  return (
    <Descriptions size="small" bordered column={1} title={<span style={{ fontWeight: 400, fontSize: 13 }}>{cabeca}</span>}>
      {linhas.map(([titulo, corpo], i) => (
        <Descriptions.Item key={i} label={titulo}>
          {corpo}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );
}

/** Resumo numa linha (lista do telemóvel e "último registo"). */
function useResumoLinha() {
  const t = useT();
  const resumo = useResumo();
  return (h: Historico) =>
    h.antigo
      ? h.texto || "—"
      : (["OE", "OD", "UT", "CER", "TX", "DG"] as Ficha[])
          .map((f) => resumo(h.dados, f) && `${f}: ${resumo(h.dados, f)}`)
          .filter(Boolean)
          .join(" · ") || t("web.common.none");
}

// ── Diário clínico ──────────────────────────────────────────────────────────

export function RegistoClinico({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const user = useUser();
  const queryClient = useQueryClient();
  const notifyError = useNotifyError();
  const resumo = useResumo();
  const resumoLinha = useResumoLinha();
  const q = useQuery({ queryKey: ["animal", animal.id, "registos"], queryFn: () => api<Resposta>(`/animais/${animal.id}/registos`) });
  // null = lista do diário; Novo = ecrã do registo (novo ou a corrigir).
  const [novo, setNovo] = useState<Novo | null>(null);
  const [aberto, setAberto] = useState<Ficha | null>(null);
  const [detalhe, setDetalhe] = useState<Historico | null>(null);
  const [ultimoAberto, setUltimoAberto] = useState(false);

  const invalidar = () => {
    for (const k of [["animal", animal.id], ["trabalho"], ["dashboard"]]) queryClient.invalidateQueries({ queryKey: k });
  };
  const gravar = useMutation({
    mutationFn: (n: Novo) => {
      const corpo = { data_registo: n.data, dados: n.dados, prioritario: n.prioritario };
      return n.id
        ? api(`/animais/${animal.id}/registos/${n.id}`, "PUT", corpo)
        : api<{ tarefas_concluidas: number; tarefas_criadas: number; resultado: string | null }>(
            `/animais/${animal.id}/registos`,
            "POST",
            corpo,
          );
    },
    onSuccess: invalidar,
  });
  const apagar = useMutation({ mutationFn: (id: number) => api(`/animais/${animal.id}/registos/${id}`, "DELETE"), onSuccess: invalidar });

  if (!q.data)
    return isMobile ? (
      <div style={{ textAlign: "center", padding: 32 }}>
        <DotLoading color="primary" />
      </div>
    ) : (
      <Spin style={{ display: "block", padding: 32 }} />
    );
  const r = q.data;
  const identificacao =
    [r.cliente, r.local, r.garanhao && `${t("web.animal.col.stallion")} ${r.garanhao}`].filter(Boolean).join(" · ") || "—";
  const abrirNovo = () => {
    setUltimoAberto(false);
    setNovo({ data: dayjs().format("YYYY-MM-DDTHH:mm:ss"), dados: {}, prioritario: false });
  };
  const corrigir = (h: Historico) => {
    setUltimoAberto(false);
    setNovo({ id: h.id, data: h.data_registo, dados: h.dados, prioritario: h.prioritario });
    setDetalhe(null);
  };
  const perguntarApagar = (h: Historico) => {
    const fazer = async () => {
      try {
        await apagar.mutateAsync(h.id);
        notifySuccess(t("web.animal.record_deleted"));
        setDetalhe(null);
      } catch (err) {
        notifyError(err);
      }
    };
    const texto = t("web.animal.delete_record", { data: dayjs(h.data_registo).format("DD/MM/YYYY") });
    if (isMobile)
      void Dialog.confirm({
        content: texto,
        confirmText: <span style={{ color: "var(--adm-color-danger)" }}>{t("btn.delete")}</span>,
        cancelText: t("web.common.cancel"),
        onConfirm: fazer,
      });
    else confirmar({ titulo: t("btn.delete"), texto, ok: t("btn.delete"), cancelar: t("web.common.cancel"), perigo: true, onOk: fazer });
  };

  // ── 1) Diário clínico: últimos 5 em resumo + "Novo registo" ──
  if (!novo) {
    const ultimos = r.historico.slice(0, 5);
    const semEstadia = <Alert type="warning" showIcon title={t("web.animal.error.no_active_stay")} />;

    if (isMobile)
      return (
        <>
          <List>
            <List.Item>
              <span style={{ fontSize: 13, color: "#666" }}>{identificacao}</span>
            </List.Item>
          </List>
          <Cabecalho>{t("web.registo.last_n", { n: 5 })}</Cabecalho>
          <List>
            {!ultimos.length ? (
              <List.Item>
                <span style={{ color: "#999" }}>{t("web.animal.no_records")}</span>
              </List.Item>
            ) : (
              ultimos.map((h) => (
                <List.Item
                  key={`${h.antigo ? "a" : "n"}${h.id}`}
                  onClick={() => setDetalhe(h)}
                  description={resumoLinha(h)}
                  extra={<span style={{ fontSize: 12 }}>{h.utilizador ?? "—"}</span>}
                >
                  {dayjs(h.data_registo).format("DD/MM HH:mm")}
                  {h.prioritario && <span style={{ color: "var(--adm-color-danger)" }}> !</span>}
                </List.Item>
              ))
            )}
          </List>
          <div style={{ padding: 12 }}>
            {r.estadia_ativa ? (
              <MButton block color="primary" onClick={abrirNovo}>
                + {t("web.registo.new_button")}
              </MButton>
            ) : (
              <div style={{ color: "var(--adm-color-warning)", fontSize: 13 }}>{t("web.animal.error.no_active_stay")}</div>
            )}
          </div>
          <Popup
            visible={detalhe !== null}
            onMaskClick={() => setDetalhe(null)}
            onClose={() => setDetalhe(null)}
            showCloseButton
            bodyStyle={{ borderTopLeftRadius: 8, borderTopRightRadius: 8, padding: "12px 16px", maxHeight: "85dvh", overflowY: "auto" }}
          >
            {detalhe && (
              <>
                <Detalhe h={detalhe} />
                {!detalhe.antigo && (
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <MButton style={{ flex: 1 }} color="danger" fill="outline" onClick={() => perguntarApagar(detalhe)}>
                      {t("btn.delete")}
                    </MButton>
                    <MButton style={{ flex: 1 }} color="primary" onClick={() => corrigir(detalhe)}>
                      {t("web.registo.correct")}
                    </MButton>
                  </div>
                )}
              </>
            )}
          </Popup>
        </>
      );

    const coluna = (f: Ficha) => ({
      title: f,
      key: f,
      onCell: (h: Historico) => (h.antigo ? { colSpan: f === "OE" ? 6 : 0 } : {}),
      render: (_: unknown, h: Historico) =>
        h.antigo ? (
          <>
            <Tag>{t("web.registo.old")}</Tag>
            {h.texto || "—"}
          </>
        ) : (
          resumo(h.dados, f) || "—"
        ),
    });
    return (
      <Flex vertical gap={12}>
        <Flex justify="space-between" align="center" gap={12} wrap>
          <Typography.Text type="secondary">{identificacao}</Typography.Text>
          {r.estadia_ativa ? (
            <Button type="primary" icon={<PlusOutlined />} onClick={abrirNovo}>
              {t("web.registo.new_button")}
            </Button>
          ) : (
            semEstadia
          )}
        </Flex>
        <Table<Historico>
          size="small"
          bordered
          title={() => t("web.registo.last_n", { n: 5 })}
          rowKey={(h) => `${h.antigo ? "a" : "n"}${h.id}`}
          dataSource={ultimos}
          pagination={false}
          locale={{ emptyText: t("web.animal.no_records") }}
          onRow={(h) => ({ onClick: () => setDetalhe(h), style: { cursor: "pointer" } })}
          columns={[
            {
              title: t("web.animal.col.date"),
              key: "data",
              width: 110,
              render: (_, h) => (
                <>
                  {dayjs(h.data_registo).format("DD/MM HH:mm")}
                  {h.prioritario && <Typography.Text type="danger"> !</Typography.Text>}
                </>
              ),
            },
            coluna("OE"),
            coluna("OD"),
            coluna("UT"),
            coluna("CER"),
            coluna("DG"),
            coluna("TX"),
            { title: t("web.registo.user"), dataIndex: "utilizador", width: 110, render: (v) => v ?? "—" },
          ]}
        />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t("web.registo.tap_to_see")}
        </Typography.Text>
        <Modal
          open={detalhe !== null}
          onCancel={() => setDetalhe(null)}
          title={t("web.registo.detail")}
          width={560}
          footer={
            detalhe && !detalhe.antigo ? (
              <Space>
                <Button danger onClick={() => perguntarApagar(detalhe)}>
                  {t("btn.delete")}
                </Button>
                <Button type="primary" onClick={() => corrigir(detalhe)}>
                  {t("web.registo.correct")}
                </Button>
              </Space>
            ) : null
          }
        >
          {detalhe && <Detalhe h={detalhe} />}
        </Modal>
      </Flex>
    );
  }

  // ── 2) Novo registo (ou correção): último registo em cima + desenho ──
  const dados = novo.dados;
  const temAlgo = !!(dados.OE || dados.OD || dados.UT || dados.CER || dados.TX || dados.DG);
  const guardarParte = (f: Ficha, v: unknown) => {
    setNovo((n) => n && { ...n, dados: { ...n.dados, [f]: v } });
    setAberto(null);
  };
  const submeter = async () => {
    try {
      const res = await gravar.mutateAsync(novo);
      if (novo.id) notifySuccess(t("web.animal.record_updated"));
      else {
        const x = res as { tarefas_concluidas: number; tarefas_criadas: number; resultado: string | null };
        notifySuccess(
          [
            t("web.animal.record_saved"),
            x.tarefas_concluidas > 0 && t("web.registo.tasks_done", { n: x.tarefas_concluidas }),
            x.tarefas_criadas > 0 && t("web.registo.tasks_created", { n: x.tarefas_criadas }),
            x.resultado === "registado" && t("web.registo.dg_saved"),
            x.resultado === "sem_inseminacao" && t("web.registo.dg_no_insemination"),
          ]
            .filter(Boolean)
            .join(" "),
        );
      }
      setNovo(null);
    } catch (err) {
      notifyError(err);
    }
  };
  const ficha =
    aberto === "OE" || aberto === "OD" ? (
      <FichaOvario inicial={r.tamanho_inicial[aberto]} atual={dados[aberto]} onGuardar={(v) => guardarParte(aberto, v)} />
    ) : aberto === "UT" ? (
      <FichaUtero atual={dados.UT} onGuardar={(v) => guardarParte("UT", v)} />
    ) : aberto === "CER" ? (
      <FichaCervix atual={dados.CER} onGuardar={(v) => guardarParte("CER", v)} />
    ) : aberto === "TX" ? (
      <FichaTX r={r} atual={dados.TX} onGuardar={(v) => guardarParte("TX", v)} />
    ) : aberto === "DG" ? (
      <FichaDG atual={dados.DG} onGuardar={(v) => guardarParte("DG", v)} />
    ) : null;
  // Ao corrigir, o "último registo" de referência é o anterior a este.
  const referencia = novo.id ? r.historico.find((h) => h.antigo || h.id !== novo.id) : r.historico[0];
  const titulo = novo.id ? t("web.registo.editing") : t("web.registo.new_button");
  const acoes: [string, () => void, boolean][] = [
    ["DG", () => setAberto("DG"), !!dados.DG],
    ["TX", () => setAberto("TX"), !!dados.TX],
    ["!", () => setNovo({ ...novo, prioritario: !novo.prioritario }), novo.prioritario],
    ...(animal.tipo === "egua"
      ? [["INS", () => navigate(`/trabalho-diario/inseminacao?egua=${animal.id}`), false] as [string, () => void, boolean]]
      : []),
  ];
  const ajudaBotoes = t(animal.tipo === "egua" ? "web.registo.buttons_help" : "web.registo.buttons_help_recipient");
  const extras = (
    <>
      {novo.prioritario && <Typography.Text type="danger">! {t("web.registo.priority_help")}</Typography.Text>}
      {dados.DG && <div>DG: {resumo(dados, "DG")}</div>}
      {dados.TX && <div>TX: {resumo(dados, "TX") || "—"}</div>}
    </>
  );

  if (isMobile)
    return (
      <>
        <List>
          <List.Item
            onClick={() => setNovo(null)}
            arrowIcon={false}
            prefix={<span style={{ color: "var(--adm-color-primary)" }}>‹</span>}
            extra={<b>{titulo}</b>}
          >
            <span style={{ color: "var(--adm-color-primary)", fontSize: 14 }}>{t("web.registo.back")}</span>
          </List.Item>
        </List>
        {referencia && (
          <>
            <Cabecalho>{t("web.registo.last_record")}</Cabecalho>
            {ultimoAberto ? (
              <div style={{ background: "#fff", padding: "0 12px 8px" }}>
                <Detalhe h={referencia} />
                <MButton size="mini" fill="none" color="primary" onClick={() => setUltimoAberto(false)}>
                  {t("web.registo.show_less")}
                </MButton>
              </div>
            ) : (
              <List>
                <List.Item
                  onClick={() => setUltimoAberto(true)}
                  description={resumoLinha(referencia)}
                  extra={<span style={{ fontSize: 12 }}>{t("web.registo.show_all")}</span>}
                >
                  {dayjs(referencia.data_registo).format("DD/MM HH:mm")} · {referencia.utilizador ?? "—"}
                </List.Item>
              </List>
            )}
          </>
        )}
        <Cabecalho>{t("web.registo.new_hint")}</Cabecalho>
        <div style={{ background: "#fff", padding: "8px 12px 12px" }}>
          <Flex justify="space-between" align="center" style={{ fontSize: 12, color: "#999" }}>
            <span>{t("web.registo.by", { name: user.nome || user.username })}</span>
            <DataHora futuro={false} valor={novo.data} onChange={(d) => setNovo({ ...novo, data: d })} />
          </Flex>
          <Desenho dados={dados} onTocar={setAberto} />
          <div style={{ display: "flex", gap: 8 }}>
            {acoes.map(([rotulo, onClick, ativo]) => (
              <MButton key={rotulo} style={{ flex: 1 }} size="small" color="primary" fill={ativo ? "solid" : "outline"} onClick={onClick}>
                {rotulo}
              </MButton>
            ))}
          </div>
          <div style={{ fontSize: 11, color: "#999", marginTop: 6 }}>{ajudaBotoes}</div>
          <div style={{ fontSize: 12, marginTop: 6 }}>{extras}</div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <MButton onClick={() => setNovo(null)}>{t("web.common.cancel")}</MButton>
            <MButton style={{ flex: 1 }} color="primary" disabled={!temAlgo} loading={gravar.isPending} onClick={submeter}>
              {novo.id ? t("btn.save_changes") : t("web.registo.save")}
            </MButton>
          </div>
        </div>
        <Popup
          visible={aberto !== null}
          onMaskClick={() => setAberto(null)}
          destroyOnClose
          showCloseButton
          onClose={() => setAberto(null)}
          bodyStyle={{ borderTopLeftRadius: 8, borderTopRightRadius: 8, padding: "12px 16px", maxHeight: "88dvh", overflowY: "auto" }}
        >
          {aberto && <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 10 }}>{t(`web.registo.part.${aberto}`)}</div>}
          {ficha}
        </Popup>
      </>
    );

  return (
    <Flex vertical gap={12}>
      <Flex justify="space-between" align="center" gap={12} wrap>
        <Space>
          <Button size="small" onClick={() => setNovo(null)}>
            ‹ {t("web.registo.back")}
          </Button>
          <Typography.Text type="secondary">{identificacao}</Typography.Text>
        </Space>
      </Flex>

      {referencia && (
        <Card
          size="small"
          title={t("web.registo.last_record")}
          extra={
            <Button type="link" size="small" onClick={() => setUltimoAberto((v) => !v)}>
              {ultimoAberto ? t("web.registo.show_less") : t("web.registo.show_all")}
            </Button>
          }
        >
          {ultimoAberto ? (
            <Detalhe h={referencia} />
          ) : (
            <Typography.Text>
              <b>{dayjs(referencia.data_registo).format("DD/MM HH:mm")}</b> · {resumoLinha(referencia)}{" "}
              <Typography.Text type="secondary">· {referencia.utilizador ?? "—"}</Typography.Text>
            </Typography.Text>
          )}
        </Card>
      )}

      <Card
        size="small"
        title={titulo}
        extra={<DataHora futuro={false} valor={novo.data} onChange={(d) => setNovo({ ...novo, data: d })} />}
      >
        <Row gutter={24}>
          <Col xs={24} md={12}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("web.registo.new_hint")}
            </Typography.Text>
            <Desenho dados={dados} onTocar={setAberto} />
          </Col>
          <Col xs={24} md={12}>
            <Flex vertical gap={8}>
              <Space wrap>
                {acoes.map(([rotulo, onClick, ativo]) => (
                  <Button key={rotulo} type={ativo ? "primary" : "default"} onClick={onClick} style={{ minWidth: 56 }}>
                    {rotulo}
                  </Button>
                ))}
              </Space>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {ajudaBotoes}
              </Typography.Text>
              <div>{extras}</div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {t("web.registo.by", { name: user.nome || user.username })}
              </Typography.Text>
              <Space>
                <Button onClick={() => setNovo(null)}>{t("web.common.cancel")}</Button>
                <Button type="primary" disabled={!temAlgo} loading={gravar.isPending} onClick={submeter}>
                  {novo.id ? t("btn.save_changes") : t("web.registo.save")}
                </Button>
              </Space>
            </Flex>
          </Col>
        </Row>
      </Card>

      <Drawer
        open={aberto !== null}
        onClose={() => setAberto(null)}
        title={aberto ? t(`web.registo.part.${aberto}`) : ""}
        size={420}
        destroyOnHidden
      >
        {ficha}
      </Drawer>
    </Flex>
  );
}
