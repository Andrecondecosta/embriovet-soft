import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { Drawer } from "antd";
import { Button, Checkbox, DatePicker, Dialog, DotLoading, Input, Popup, Selector, TextArea } from "antd-mobile";

import { api } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { useBrand } from "../../components/Brand";
import { useUser } from "../../components/User";
import { notifySuccess, useNotifyError } from "../../components/errors";
import type { Animal } from "./api";

/* Registo clínico das éguas — desenho com ovário esquerdo/direito, útero e
 * cérvix; DG (diagnóstico de gestação), TX (tratamento), ! (prioritário) e
 * INS (inseminação). Desenhado pelo utilizador em folhas (out. 2026). As
 * fichas usam os mesmos componentes no telemóvel e no computador. */

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

// ── Peças ───────────────────────────────────────────────────────────────────

const btn: React.CSSProperties = { width: 44, height: 40, border: "none", background: "#f5f5f5", fontSize: 20, cursor: "pointer" };
const caixa: React.CSSProperties = { background: "#f7f7f7", borderRadius: 8, padding: 8 };

/** "− valor +" como no desenho. */
function Escala({ valores, indice, onChange }: { valores: string[]; indice: number; onChange: (i: number) => void }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", border: "1px solid #d9d9d9", borderRadius: 8, overflow: "hidden" }}>
      <button type="button" onClick={() => onChange(Math.max(0, indice - 1))} style={btn} aria-label="−">
        −
      </button>
      <div style={{ minWidth: 56, padding: "0 6px", textAlign: "center", fontWeight: 700, fontSize: 16 }}>{valores[indice]}</div>
      <button type="button" onClick={() => onChange(Math.min(valores.length - 1, indice + 1))} style={btn} aria-label="+">
        +
      </button>
    </div>
  );
}

function Seccao({ titulo, children, direita }: { titulo: string; children: ReactNode; direita?: ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 12, color: "#999", textTransform: "uppercase", letterSpacing: ".04em" }}>{titulo}</span>
        {direita}
      </div>
      {children}
    </div>
  );
}

function Comentario({ value, onChange }: { value?: string; onChange: (v: string) => void }) {
  const t = useT();
  return (
    <TextArea placeholder={t("web.registo.comment")} value={value ?? ""} onChange={onChange} autoSize={{ minRows: 2 }} style={caixa} />
  );
}

function Guardar({ onClick, children, disabled }: { onClick: () => void; children?: ReactNode; disabled?: boolean }) {
  const t = useT();
  return (
    <Button block color="primary" style={{ marginTop: 12 }} onClick={onClick} disabled={disabled}>
      {children ?? t("btn.save")}
    </Button>
  );
}

// ── Fichas ──────────────────────────────────────────────────────────────────

function FichaOvario({ inicial, atual, onGuardar }: { inicial: number; atual?: Ovario; onGuardar: (v: Ovario) => void }) {
  const t = useT();
  const [ov, setOv] = useState<Ovario>(atual ?? { foliculos: [{ tamanho: inicial, achados: [] }] });
  const tamanhos = Array.from({ length: 53 }, (_, i) => mm(i + 9));
  const mudar = (i: number, f: Partial<Foliculo>) =>
    setOv((o) => ({ ...o, foliculos: o.foliculos.map((x, j) => (j === i ? { ...x, ...f } : x)) }));
  return (
    <>
      {ov.foliculos.map((f, i) => (
        <Seccao
          key={i}
          titulo={t("web.registo.follicle", { n: i + 1 })}
          direita={
            i > 0 && (
              <Button
                size="mini"
                color="danger"
                fill="none"
                onClick={() => setOv((o) => ({ ...o, foliculos: o.foliculos.filter((_, j) => j !== i) }))}
              >
                {t("btn.remove")}
              </Button>
            )
          }
        >
          <Escala valores={tamanhos} indice={f.tamanho - 9} onChange={(j) => mudar(i, { tamanho: j + 9 })} />
          <Selector
            multiple
            columns={5}
            showCheckMark={false}
            value={f.achados}
            onChange={(v) => mudar(i, { achados: v })}
            options={ACHADOS.map((a) => ({ label: a, value: a }))}
            style={{ marginTop: 10, "--padding": "8px 0" } as React.CSSProperties}
          />
        </Seccao>
      ))}
      <div style={{ fontSize: 11, color: "#999", margin: "-6px 0 10px" }}>{t("web.registo.findings_legend")}</div>
      <Button block size="small" onClick={() => setOv((o) => ({ ...o, foliculos: [...o.foliculos, { tamanho: 25, achados: [] }] }))}>
        + {t("web.registo.add_follicle")}
      </Button>
      <div style={{ fontSize: 11, color: "#999", margin: "6px 0 12px" }}>{t("web.registo.follicle_hint")}</div>
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
        <Escala valores={EDEMA} indice={u.edema} onChange={(i) => setU({ ...u, edema: i })} />
      </Seccao>
      <Seccao titulo={t("web.registo.liquid")}>
        <Escala valores={LIQUIDO} indice={u.liquido} onChange={(i) => setU({ ...u, liquido: i })} />
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
        <Escala
          valores={[1, 2, 3].map((g) => t(`web.registo.cervix.${g}`))}
          indice={c.grau - 1}
          onChange={(i) => setC({ ...c, grau: i + 1 })}
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
      <Selector
        columns={3}
        showCheckMark={false}
        value={v ? [v] : []}
        onChange={(x) => setV(x[0] ?? "")}
        options={["Positivo", "Negativo", "Inconclusivo"].map((d) => ({ label: t(`web.registo.dg.${d}`), value: d }))}
      />
      <div style={{ fontSize: 11, color: "#999", margin: "8px 0" }}>{t("web.registo.dg_help")}</div>
      <Guardar onClick={() => onGuardar(v || undefined)} />
    </>
  );
}

function FichaTX({ r, atual, onGuardar }: { r: Resposta; atual?: Tratamento; onGuardar: (v: Tratamento | undefined) => void }) {
  const t = useT();
  const [x, setX] = useState<Tratamento>(atual ?? {});
  const [calendario, setCalendario] = useState<"inducao" | "agenda" | null>(null);
  const resumo = useResumo();
  const inf = x.infusao ?? { ab: [] };
  const linha = (rotulo: string, ativo: boolean, alternar: () => void, conteudo?: ReactNode) => (
    <div style={{ borderBottom: "1px solid #f0f0f0", padding: "10px 0" }}>
      <Checkbox checked={ativo} onChange={alternar} style={{ fontWeight: 600 }}>
        {rotulo}
      </Checkbox>
      {ativo && conteudo && <div style={{ marginTop: 8, paddingLeft: 28 }}>{conteudo}</div>}
    </div>
  );
  const vezes = (n: number, mudar: (n: number) => void) => (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ color: "#999" }}>{t("web.registo.times")}</span>
      <Escala valores={["1×", "2×", "3×", "4×"]} indice={n - 1} onChange={(i) => mudar(i + 1)} />
    </div>
  );
  const vazio = !x.ocitocina && !x.pg && !x.p4 && !x.infusao && !x.zaragatoa && !x.lavagem && !x.inducao;

  return (
    <>
      <div style={{ ...caixa, marginBottom: 6 }}>
        <div style={{ fontSize: 12, color: "#999", marginBottom: 4 }}>{t("web.registo.previous_tx")}</div>
        {!r.tratamentos_anteriores.length ? (
          <div style={{ fontSize: 12, color: "#999" }}>—</div>
        ) : (
          r.tratamentos_anteriores.map((a) => (
            <div key={a.data_registo} style={{ fontSize: 12 }}>
              <b>{dayjs(a.data_registo).format("DD/MM")}</b> · {a.texto}
            </div>
          ))
        )}
      </div>
      {linha(
        t("web.registo.tx.ocitocina"),
        !!x.ocitocina,
        () => setX({ ...x, ocitocina: x.ocitocina ? null : { vezes: 1, hora: "8h" } }),
        x.ocitocina && (
          <>
            {vezes(x.ocitocina.vezes, (n) => setX({ ...x, ocitocina: { ...x.ocitocina!, vezes: n } }))}
            <Selector
              columns={5}
              showCheckMark={false}
              value={[x.ocitocina.hora]}
              onChange={(v) => v[0] && setX({ ...x, ocitocina: { ...x.ocitocina!, hora: v[0] } })}
              options={HORAS.map((h) => ({ label: h, value: h }))}
              style={{ marginTop: 8, "--padding": "6px 0" } as React.CSSProperties}
            />
            <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>{t(`web.registo.ocitocina.${x.ocitocina.vezes}`)}</div>
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
          <div style={{ color: "#999", fontSize: 12, marginBottom: 4 }}>{t("web.registo.antibiotic")}</div>
          <Selector
            multiple
            columns={2}
            showCheckMark={false}
            value={inf.ab}
            onChange={(v) => setX({ ...x, infusao: { ...inf, ab: v } })}
            options={r.antibioticos.map((a) => ({ label: a, value: a }))}
          />
          <Input
            placeholder={t("web.registo.other_antibiotic")}
            value={inf.abOutro ?? ""}
            onChange={(v) => setX({ ...x, infusao: { ...inf, abOutro: v } })}
            style={{ ...caixa, marginTop: 6 }}
          />
          <Checkbox
            checked={!!inf.mucolitico}
            onChange={(on) => setX({ ...x, infusao: { ...inf, mucolitico: on } })}
            style={{ marginTop: 8 }}
          >
            {t("web.registo.tx.mucolitico")}
          </Checkbox>
          {r.infusoes.length > 0 && (
            <Selector
              columns={2}
              showCheckMark={false}
              value={inf.outro ? [inf.outro] : []}
              onChange={(v) => setX({ ...x, infusao: { ...inf, outro: v[0] ?? "" } })}
              options={r.infusoes.map((a) => ({ label: a, value: a }))}
              style={{ marginTop: 8 }}
            />
          )}
          <Input
            placeholder={t("web.registo.other_infusion")}
            value={inf.outro ?? ""}
            onChange={(v) => setX({ ...x, infusao: { ...inf, outro: v } })}
            style={{ ...caixa, marginTop: 6 }}
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
            <Input
              placeholder={t("web.registo.product_optional")}
              value={x.inducao.produto ?? ""}
              onChange={(v) => setX({ ...x, inducao: { ...x.inducao!, produto: v } })}
              style={{ ...caixa, marginBottom: 6 }}
            />
            <Button size="small" onClick={() => setCalendario("inducao")}>
              {dayjs(x.inducao.data).format("DD/MM/YYYY HH:mm")}
            </Button>
          </>
        ),
      )}

      <div style={{ margin: "14px 0" }}>
        <Checkbox checked={!!x.marcar} onChange={(on) => setX({ ...x, marcar: on ? { dias: "1" } : null })} style={{ fontWeight: 600 }}>
          {t("web.registo.mark_tx")}
        </Checkbox>
        {x.marcar && (
          <div style={{ marginTop: 8, paddingLeft: 28 }}>
            <Selector
              columns={4}
              showCheckMark={false}
              value={[x.marcar.dias]}
              onChange={(v) => {
                if (!v[0]) return;
                setX({
                  ...x,
                  marcar: { dias: v[0], data: v[0] === "agenda" ? (x.marcar?.data ?? dayjs().add(1, "day").format("YYYY-MM-DD")) : null },
                });
              }}
              options={[
                { label: t("web.registo.days", { n: 1 }), value: "1" },
                { label: t("web.registo.days", { n: 2 }), value: "2" },
                { label: t("web.registo.days", { n: 3 }), value: "3" },
                { label: t("web.registo.agenda"), value: "agenda" },
              ]}
              style={{ "--padding": "6px 0" } as React.CSSProperties}
            />
            {x.marcar.dias === "agenda" && (
              <Button size="small" style={{ marginTop: 6 }} onClick={() => setCalendario("agenda")}>
                {dayjs(x.marcar.data).format("DD/MM/YYYY")}
              </Button>
            )}
            <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>{t("web.registo.mark_tx_help")}</div>
          </div>
        )}
      </div>

      {!vazio && <div style={{ fontSize: 12, marginBottom: 8 }}>{resumo({ TX: x }, "TX")}</div>}
      <Guardar onClick={() => onGuardar(vazio ? undefined : x)}>{t("web.registo.save_tx")}</Guardar>
      <DatePicker
        visible={calendario !== null}
        precision={calendario === "inducao" ? "minute" : "day"}
        onClose={() => setCalendario(null)}
        value={
          calendario === "inducao" && x.inducao
            ? new Date(x.inducao.data)
            : x.marcar?.data
              ? new Date(`${x.marcar.data}T12:00:00`)
              : new Date()
        }
        min={new Date()}
        onConfirm={(d) => {
          if (calendario === "inducao" && x.inducao)
            setX({ ...x, inducao: { ...x.inducao, data: dayjs(d).format("YYYY-MM-DDTHH:mm:ss") } });
          if (calendario === "agenda" && x.marcar) setX({ ...x, marcar: { ...x.marcar, data: dayjs(d).format("YYYY-MM-DD") } });
        }}
      />
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
          fill={feito ? `${primary_color}33` : "#fff"}
          stroke={feito ? primary_color : "#8c8c8c"}
          strokeWidth={feito ? 3 : 2}
        />
        <text x={cx} y={cy + 5} textAnchor="middle" fontSize={15} fontWeight={700} fill={feito ? primary_color : "#595959"}>
          {p}
        </text>
        {feito && (
          <text x={cx} y={cy + r + 17} textAnchor="middle" fontSize={11} fill="#595959">
            {resumo(dados, p).slice(0, 24)}
          </text>
        )}
      </g>
    );
  };
  return (
    <svg viewBox="0 0 360 330" style={{ width: "100%", maxWidth: 380, display: "block", margin: "0 auto", touchAction: "manipulation" }}>
      <path
        d="M70 70 C 95 120, 140 150, 170 175 L 190 175 C 220 150, 265 120, 290 70"
        fill="none"
        stroke="#d9a6a6"
        strokeWidth={22}
        strokeLinecap="round"
      />
      <path d="M180 175 L 180 255" stroke="#d9a6a6" strokeWidth={34} strokeLinecap="round" />
      {ponto("OE", 60, 58, 30)}
      {ponto("OD", 300, 58, 30)}
      {ponto("UT", 180, 185, 34)}
      {ponto("CER", 180, 282, 26)}
    </svg>
  );
}

// ── Diário clínico ──────────────────────────────────────────────────────────

const td: React.CSSProperties = { padding: "6px 8px", borderBottom: "1px solid #f5f5f5", verticalAlign: "top" };

export function RegistoClinico({ animal }: { animal: Animal }) {
  const t = useT();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const user = useUser();
  const queryClient = useQueryClient();
  const notifyError = useNotifyError();
  const { primary_color } = useBrand();
  const resumo = useResumo();
  const q = useQuery({ queryKey: ["animal", animal.id, "registos"], queryFn: () => api<Resposta>(`/animais/${animal.id}/registos`) });
  const vazio = (): Novo => ({ data: dayjs().format("YYYY-MM-DDTHH:mm:ss"), dados: {}, prioritario: false });
  const [novo, setNovo] = useState<Novo>(vazio);
  const [aberto, setAberto] = useState<Ficha | null>(null);
  const [calendario, setCalendario] = useState(false);

  const invalidar = () => {
    for (const k of [["animal", animal.id], ["trabalho"], ["dashboard"]]) queryClient.invalidateQueries({ queryKey: k });
  };
  const gravar = useMutation({
    mutationFn: () => {
      const corpo = { data_registo: novo.data, dados: novo.dados, prioritario: novo.prioritario };
      return novo.id
        ? api(`/animais/${animal.id}/registos/${novo.id}`, "PUT", corpo)
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
    return (
      <div style={{ textAlign: "center", padding: 32 }}>
        <DotLoading color="primary" />
      </div>
    );
  const r = q.data;
  const dados = novo.dados;
  const temAlgo = !!(dados.OE || dados.OD || dados.UT || dados.CER || dados.TX || dados.DG);
  const guardarParte = (f: Ficha, v: unknown) => {
    setNovo((n) => ({ ...n, dados: { ...n.dados, [f]: v } }));
    setAberto(null);
  };

  const submeter = async () => {
    try {
      const res = await gravar.mutateAsync();
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
      setNovo(vazio());
    } catch (err) {
      notifyError(err);
    }
  };
  const editar = (h: Historico) => {
    if (h.antigo) return;
    setNovo({ id: h.id, data: h.data_registo, dados: h.dados, prioritario: h.prioritario });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const perguntarApagar = () =>
    void Dialog.confirm({
      content: t("web.animal.delete_record", { data: dayjs(novo.data).format("DD/MM/YYYY") }),
      confirmText: <span style={{ color: "var(--adm-color-danger)" }}>{t("btn.delete")}</span>,
      cancelText: t("web.common.cancel"),
      onConfirm: async () => {
        try {
          await apagar.mutateAsync(novo.id!);
          notifySuccess(t("web.animal.record_deleted"));
          setNovo(vazio());
        } catch (err) {
          notifyError(err);
        }
      },
    });

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

  const acao = (rotulo: string, onClick: () => void, ativo: boolean) => (
    <button
      type="button"
      onClick={onClick}
      style={{
        flex: 1,
        height: 48,
        borderRadius: 10,
        border: `2px solid ${ativo ? primary_color : "#d9d9d9"}`,
        background: ativo ? `${primary_color}1a` : "#fff",
        fontWeight: 800,
        fontSize: 16,
        color: ativo ? primary_color : "#434343",
        cursor: "pointer",
      }}
    >
      {rotulo}
    </button>
  );
  const nLinhas = isMobile ? 5 : 10;
  const bloco: React.CSSProperties = {
    background: "#fff",
    borderRadius: isMobile ? 0 : 8,
    border: isMobile ? undefined : "1px solid #f0f0f0",
  };

  return (
    <div style={{ maxWidth: 960 }}>
      {/* Identificação */}
      <div style={{ ...bloco, padding: "10px 12px" }}>
        <div style={{ color: "#666" }}>
          {[r.cliente, r.local, r.garanhao && `${t("web.animal.col.stallion")} ${r.garanhao}`].filter(Boolean).join(" · ") || "—"}
        </div>
      </div>

      {/* Últimos registos */}
      <div style={{ padding: "12px 12px 4px", fontSize: 12, color: "#999" }}>{t("web.registo.last_n", { n: nLinhas })}</div>
      <div style={{ ...bloco, overflowX: "auto" }}>
        {!r.historico.length ? (
          <div style={{ padding: 12, color: "#999" }}>{t("web.animal.no_records")}</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ color: "#999", textAlign: "left" }}>
                {[t("web.registo.col.datetime"), "OE", "OD", "UT", "CER", "TX"].map((h) => (
                  <th key={h} style={{ padding: "6px 8px", borderBottom: "1px solid #f0f0f0", whiteSpace: "nowrap" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.historico.slice(0, nLinhas).map((h) => (
                <tr
                  key={`${h.antigo ? "a" : "n"}${h.id}`}
                  onClick={() => editar(h)}
                  style={{
                    cursor: h.antigo ? "default" : "pointer",
                    background: novo.id === h.id && !h.antigo ? `${primary_color}12` : undefined,
                  }}
                >
                  <td style={td}>
                    <b>{dayjs(h.data_registo).format("DD/MM HH:mm")}</b>
                    {h.prioritario && <span style={{ color: primary_color, fontWeight: 800 }}> !</span>}
                    <div style={{ color: "#999" }}>{h.utilizador ?? "—"}</div>
                  </td>
                  {h.antigo ? (
                    <td style={{ ...td, color: "#666" }} colSpan={5}>
                      <span style={{ fontSize: 10, color: "#999" }}>{t("web.registo.old")} · </span>
                      {h.texto || "—"}
                    </td>
                  ) : (
                    (["OE", "OD", "UT", "CER", "TX"] as Ficha[]).map((f) => (
                      <td key={f} style={td}>
                        {resumo(h.dados, f) || "—"}
                        {f === "TX" && h.dados.DG && <div style={{ color: "#999" }}>DG {resumo(h.dados, "DG")}</div>}
                      </td>
                    ))
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {r.historico.some((h) => !h.antigo) && (
        <div style={{ padding: "4px 12px", fontSize: 11, color: "#999" }}>{t("web.registo.tap_to_edit")}</div>
      )}

      {/* Novo registo (ou correção) */}
      {!r.estadia_ativa && !novo.id ? (
        <div style={{ ...bloco, marginTop: 8, padding: 12, color: "var(--adm-color-warning)" }}>{t("web.animal.error.no_active_stay")}</div>
      ) : (
        <div style={{ ...bloco, marginTop: 8, padding: "8px 0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 12px 4px", gap: 8 }}>
            <span style={{ fontSize: 12, color: novo.id ? primary_color : "#999", fontWeight: novo.id ? 700 : 400 }}>
              {novo.id ? t("web.registo.editing") : t("web.registo.new_hint")}
            </span>
            <Button size="mini" onClick={() => setCalendario(true)}>
              {dayjs(novo.data).format("DD/MM HH:mm")}
            </Button>
          </div>
          <div style={{ padding: "0 12px", fontSize: 11, color: "#999" }}>{t("web.registo.by", { name: user.nome || user.username })}</div>
          <Desenho dados={dados} onTocar={setAberto} />
          <div style={{ display: "flex", gap: 8, padding: "8px 12px" }}>
            {acao("DG", () => setAberto("DG"), !!dados.DG)}
            {acao("TX", () => setAberto("TX"), !!dados.TX)}
            {acao("!", () => setNovo({ ...novo, prioritario: !novo.prioritario }), novo.prioritario)}
            {animal.tipo === "egua" && acao("INS", () => navigate(`/trabalho-diario/inseminacao?egua=${animal.id}`), false)}
          </div>
          <div style={{ padding: "0 12px", fontSize: 11, color: "#999" }}>
            {t(animal.tipo === "egua" ? "web.registo.buttons_help" : "web.registo.buttons_help_recipient")}
          </div>
          {(dados.TX || dados.DG || novo.prioritario) && (
            <div style={{ padding: "8px 12px", fontSize: 12 }}>
              {novo.prioritario && <div style={{ color: primary_color, fontWeight: 700 }}>! {t("web.registo.priority_help")}</div>}
              {dados.DG && <div>DG: {resumo(dados, "DG")}</div>}
              {dados.TX && <div>TX: {resumo(dados, "TX") || "—"}</div>}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, padding: "8px 12px" }}>
            {novo.id && (
              <>
                <Button onClick={() => setNovo(vazio())}>{t("web.common.cancel")}</Button>
                <Button color="danger" fill="outline" onClick={perguntarApagar}>
                  {t("btn.delete")}
                </Button>
              </>
            )}
            <Button block color="primary" disabled={!temAlgo} loading={gravar.isPending} onClick={submeter}>
              {novo.id ? t("btn.save_changes") : t("web.registo.save")}
            </Button>
          </div>
        </div>
      )}

      {/* Fichas: folha de baixo no telemóvel, gaveta à direita no computador */}
      {isMobile ? (
        <Popup
          visible={aberto !== null}
          onMaskClick={() => setAberto(null)}
          destroyOnClose
          bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16, maxHeight: "88dvh", overflowY: "auto" }}
        >
          {aberto && <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>{t(`web.registo.part.${aberto}`)}</div>}
          {ficha}
        </Popup>
      ) : (
        <Drawer
          open={aberto !== null}
          onClose={() => setAberto(null)}
          title={aberto ? t(`web.registo.part.${aberto}`) : ""}
          size={440}
          destroyOnHidden
        >
          {ficha}
        </Drawer>
      )}
      <DatePicker
        visible={calendario}
        precision="minute"
        onClose={() => setCalendario(false)}
        value={new Date(novo.data)}
        max={new Date()}
        onConfirm={(d) => setNovo({ ...novo, data: dayjs(d).format("YYYY-MM-DDTHH:mm:ss") })}
      />
    </div>
  );
}
