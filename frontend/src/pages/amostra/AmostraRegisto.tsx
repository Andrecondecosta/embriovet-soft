import { useState, type ReactNode } from "react";
import dayjs from "dayjs";
import { Drawer } from "antd";
import { Button, Checkbox, DatePicker, Input, Popup, Selector, TextArea } from "antd-mobile";

import { useIsMobile } from "../../components/responsive";
import { useBrand } from "../../components/Brand";
import { useUser } from "../../components/User";

/* ───────────────────────────────────────────────────────────────────────────
 * AMOSTRA (só para ver e opinar) — novo "Registo de hoje" das éguas, a
 * partir das folhas desenhadas pelo utilizador. Dados fictícios, nada é
 * gravado. As fichas usam os mesmos componentes no telemóvel e no
 * computador (no computador abrem numa gaveta à direita).
 * ─────────────────────────────────────────────────────────────────────────── */

type Parte = "OE" | "OD" | "UT" | "CER";
type Ficha = Parte | "TX" | "DG";
interface Foliculo {
  tamanho: number; // mm; 9 = "<10", 61 = ">60"
  achados: string[];
}
interface Ovario {
  foliculos: Foliculo[];
  comentario: string;
}
interface Utero {
  edema: number; // índice em EDEMA
  liquido: number; // índice em LIQUIDO
  comentario: string;
}
interface Cervix {
  grau: number; // 1..3
  comentario: string;
}
interface Tratamento {
  ocitocina: { vezes: number; hora: string } | null;
  pg: number; // vezes
  p4: boolean;
  infusao: { ab: string[]; abOutro: string; mucolitico: boolean; outro: string } | null;
  zaragatoa: boolean;
  lavagem: number;
  inducao: { data: string; produto: string } | null;
  marcar: { dias: string } | null;
}
interface Registo {
  data: string;
  equipa: string;
  OE?: Ovario;
  OD?: Ovario;
  UT?: Utero;
  CER?: Cervix;
  TX?: Tratamento;
  DG?: string;
  prioritario?: boolean;
}

const NOMES: Record<Ficha, string> = {
  OE: "Ovário esquerdo",
  OD: "Ovário direito",
  UT: "Útero",
  CER: "Cérvix",
  TX: "Tratamento",
  DG: "Diagnóstico de gestação",
};
const ACHADOS = ["NS", "OV", "FH", "MF", "CL"];
const EDEMA = ["0", "+", "++", "+++"];
const LIQUIDO = ["0", "<2 cm", "+", "++", "+++"];
const HORAS = ["8h", "10h", "12h", "14h", "16h"];
const ANTIBIOTICOS = ["Genta", "Genta + Peni", "Ceftiofur", "Marbofloxacina"];
// Grau da cérvix (escala da clínica): 1 fechado, 2 intermédio, 3 aberto.
const CERVIX = ["1 · fechado", "2 · intermédio", "3 · aberto"];
// Siglas dos achados no ovário (NS e MF ainda por confirmar).
const LEGENDA_ACHADOS = "OV ovulação · CL corpo lúteo · FH folículo hemorrágico · MF a confirmar · NS a confirmar";
// Intervalo entre doses de ocitocina, conforme as vezes por dia (folha "Ocitocina").
const INTERVALO_OCITOCINA: Record<number, string> = {
  1: "1× na hora",
  2: "2×: na hora + 1, até 6 h depois",
  3: "3×: na hora + 2, de 4 em 4 h",
  4: "4×: na hora + 3, de 3 em 3 h",
};

const mm = (n: number) => (n <= 9 ? "<10" : n >= 61 ? ">60" : String(n));

/** Registos anteriores fictícios. */
const ANTERIORES: Registo[] = [
  {
    data: dayjs().subtract(1, "day").hour(9).minute(40).toISOString(),
    equipa: "Dr.ª Ana",
    OE: { foliculos: [{ tamanho: 32, achados: [] }], comentario: "" },
    OD: { foliculos: [{ tamanho: 18, achados: ["MF"] }], comentario: "" },
    UT: { edema: 2, liquido: 0, comentario: "" },
    CER: { grau: 2, comentario: "" },
  },
  {
    data: dayjs().subtract(3, "day").hour(10).minute(5).toISOString(),
    equipa: "Dr. João",
    OE: { foliculos: [{ tamanho: 25, achados: [] }], comentario: "" },
    OD: { foliculos: [{ tamanho: 9, achados: ["CL"] }], comentario: "" },
    UT: { edema: 1, liquido: 1, comentario: "" },
    TX: { ocitocina: null, pg: 1, p4: false, infusao: null, zaragatoa: false, lavagem: 0, inducao: null, marcar: null },
  },
];

/** O folículo começa no último registo se tiver menos de 5 dias; senão, 25 mm. */
function tamanhoInicial(p: "OE" | "OD") {
  const ultimo = ANTERIORES.find((r) => r[p]);
  if (ultimo && dayjs().diff(dayjs(ultimo.data), "day") < 5) return ultimo[p]!.foliculos[0]?.tamanho ?? 25;
  return 25;
}

function resumo(r: Registo, f: Ficha): string {
  if (f === "OE" || f === "OD") return r[f]?.foliculos.map((x) => [`${mm(x.tamanho)} mm`, ...x.achados].join(" ")).join(" · ") ?? "";
  if (f === "UT") return r.UT ? `Ed ${EDEMA[r.UT.edema]} · Líq ${LIQUIDO[r.UT.liquido]}` : "";
  if (f === "CER") return r.CER ? CERVIX[r.CER.grau - 1] : "";
  if (f === "DG") return r.DG ?? "";
  const t = r.TX;
  if (!t) return "";
  const inf = t.infusao;
  return [
    t.ocitocina && `Ocitocina ${t.ocitocina.vezes}× ${t.ocitocina.hora}`,
    t.pg > 0 && `PG ${t.pg}×`,
    t.p4 && "P4",
    inf && `Infusão ${[...inf.ab, inf.abOutro, inf.mucolitico && "Mucolítico", inf.outro].filter(Boolean).join(" + ")}`,
    t.zaragatoa && "Zaragatoa",
    t.lavagem > 0 && `Lavagem ${t.lavagem}×`,
    t.inducao && `Indução ${t.inducao.produto ? `${t.inducao.produto} ` : ""}${dayjs(t.inducao.data).format("DD/MM HH:mm")}`,
    t.marcar && (t.marcar.dias === "agenda" ? "agendado" : `repetir ${t.marcar.dias} dia(s)`),
  ]
    .filter(Boolean)
    .join(" · ");
}

// ── Peças ───────────────────────────────────────────────────────────────────

const btn: React.CSSProperties = { width: 44, height: 40, border: "none", background: "#f5f5f5", fontSize: 20, cursor: "pointer" };
const caixa: React.CSSProperties = { background: "#f7f7f7", borderRadius: 8, padding: 8 };

/** "− valor +" como no desenho: percorre uma lista de valores. */
function Escala({ valores, indice, onChange }: { valores: string[]; indice: number; onChange: (i: number) => void }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", border: "1px solid #d9d9d9", borderRadius: 8, overflow: "hidden" }}>
      <button type="button" onClick={() => onChange(Math.max(0, indice - 1))} style={btn} aria-label="menos">
        −
      </button>
      <div style={{ minWidth: 56, textAlign: "center", fontWeight: 700, fontSize: 16 }}>{valores[indice]}</div>
      <button type="button" onClick={() => onChange(Math.min(valores.length - 1, indice + 1))} style={btn} aria-label="mais">
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

// ── Fichas ──────────────────────────────────────────────────────────────────

function FichaOvario({ parte, atual, onGuardar }: { parte: "OE" | "OD"; atual?: Ovario; onGuardar: (v: Ovario) => void }) {
  const [ov, setOv] = useState<Ovario>(atual ?? { foliculos: [{ tamanho: tamanhoInicial(parte), achados: [] }], comentario: "" });
  const tamanhos = Array.from({ length: 53 }, (_, i) => mm(i + 9));
  const mudar = (i: number, f: Partial<Foliculo>) =>
    setOv((o) => ({ ...o, foliculos: o.foliculos.map((x, j) => (j === i ? { ...x, ...f } : x)) }));
  return (
    <>
      {ov.foliculos.map((f, i) => (
        <Seccao
          key={i}
          titulo={`Folículo ${i + 1} (mm)`}
          direita={
            i > 0 && (
              <Button
                size="mini"
                color="danger"
                fill="none"
                onClick={() => setOv((o) => ({ ...o, foliculos: o.foliculos.filter((_, j) => j !== i) }))}
              >
                Retirar
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
      <div style={{ fontSize: 11, color: "#999", margin: "-6px 0 10px" }}>{LEGENDA_ACHADOS}</div>
      <Button block size="small" onClick={() => setOv((o) => ({ ...o, foliculos: [...o.foliculos, { tamanho: 25, achados: [] }] }))}>
        + Adicionar folículo
      </Button>
      <div style={{ fontSize: 11, color: "#999", margin: "6px 0 12px" }}>
        O tamanho começa no último registo (se tiver menos de 5 dias); senão, em 25 mm.
      </div>
      <TextArea
        placeholder="Comentário"
        value={ov.comentario}
        onChange={(v) => setOv({ ...ov, comentario: v })}
        autoSize={{ minRows: 2 }}
        style={caixa}
      />
      <Button block color="primary" style={{ marginTop: 12 }} onClick={() => onGuardar(ov)}>
        Guardar
      </Button>
    </>
  );
}

function FichaUtero({ atual, onGuardar }: { atual?: Utero; onGuardar: (v: Utero) => void }) {
  const [u, setU] = useState<Utero>(atual ?? { edema: 0, liquido: 0, comentario: "" });
  return (
    <>
      <Seccao titulo="Edema">
        <Escala valores={EDEMA} indice={u.edema} onChange={(i) => setU({ ...u, edema: i })} />
      </Seccao>
      <Seccao titulo="Líquido">
        <Escala valores={LIQUIDO} indice={u.liquido} onChange={(i) => setU({ ...u, liquido: i })} />
      </Seccao>
      <TextArea
        placeholder="Comentário"
        value={u.comentario}
        onChange={(v) => setU({ ...u, comentario: v })}
        autoSize={{ minRows: 2 }}
        style={caixa}
      />
      <Button block color="primary" style={{ marginTop: 12 }} onClick={() => onGuardar(u)}>
        Guardar
      </Button>
    </>
  );
}

function FichaCervix({ atual, onGuardar }: { atual?: Cervix; onGuardar: (v: Cervix) => void }) {
  const [c, setC] = useState<Cervix>(atual ?? { grau: 1, comentario: "" });
  return (
    <>
      <Seccao titulo="Grau (1 a 3)">
        <Escala valores={CERVIX} indice={c.grau - 1} onChange={(i) => setC({ ...c, grau: i + 1 })} />
      </Seccao>
      <TextArea
        placeholder="Comentário"
        value={c.comentario}
        onChange={(v) => setC({ ...c, comentario: v })}
        autoSize={{ minRows: 2 }}
        style={caixa}
      />
      <Button block color="primary" style={{ marginTop: 12 }} onClick={() => onGuardar(c)}>
        Guardar
      </Button>
    </>
  );
}

function FichaDG({ atual, onGuardar }: { atual?: string; onGuardar: (v: string) => void }) {
  const [v, setV] = useState(atual ?? "");
  return (
    <>
      <Selector
        columns={3}
        showCheckMark={false}
        value={v ? [v] : []}
        onChange={(x) => setV(x[0] ?? "")}
        options={[
          { label: "+ Positivo", value: "Positivo" },
          { label: "− Negativo", value: "Negativo" },
          { label: "Inconclusivo", value: "Inconclusivo" },
        ]}
      />
      <div style={{ fontSize: 11, color: "#999", margin: "8px 0" }}>
        No registo verdadeiro, isto regista o resultado da inseminação: positivo agenda D+28/D+45, negativo fecha o ciclo.
      </div>
      <Button block color="primary" disabled={!v} onClick={() => onGuardar(v)}>
        Guardar
      </Button>
    </>
  );
}

const TX_VAZIO: Tratamento = {
  ocitocina: null,
  pg: 0,
  p4: false,
  infusao: null,
  zaragatoa: false,
  lavagem: 0,
  inducao: null,
  marcar: null,
};

function FichaTX({ atual, onGuardar }: { atual?: Tratamento; onGuardar: (v: Tratamento) => void }) {
  const [t, setT] = useState<Tratamento>(atual ?? TX_VAZIO);
  const [calendario, setCalendario] = useState(false);
  const inf = t.infusao ?? { ab: [], abOutro: "", mucolitico: false, outro: "" };
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
      <span style={{ color: "#999" }}>Vezes</span>
      <Escala valores={["1×", "2×", "3×", "4×"]} indice={n - 1} onChange={(i) => mudar(i + 1)} />
    </div>
  );

  const anteriores = ANTERIORES.filter((r) => r.TX);
  return (
    <>
      <div style={{ ...caixa, marginBottom: 6 }}>
        <div style={{ fontSize: 12, color: "#999", marginBottom: 4 }}>Tratamentos anteriores</div>
        {!anteriores.length ? (
          <div style={{ fontSize: 12, color: "#999" }}>—</div>
        ) : (
          anteriores.map((r) => (
            <div key={r.data} style={{ fontSize: 12 }}>
              <b>{dayjs(r.data).format("DD/MM")}</b> · {resumo(r, "TX")}
            </div>
          ))
        )}
      </div>
      {linha(
        "Ocitocina",
        !!t.ocitocina,
        () => setT({ ...t, ocitocina: t.ocitocina ? null : { vezes: 1, hora: "8h" } }),
        t.ocitocina && (
          <>
            {vezes(t.ocitocina.vezes, (n) => setT({ ...t, ocitocina: { ...t.ocitocina!, vezes: n } }))}
            <Selector
              columns={5}
              showCheckMark={false}
              value={[t.ocitocina.hora]}
              onChange={(v) => v[0] && setT({ ...t, ocitocina: { ...t.ocitocina!, hora: v[0] } })}
              options={HORAS.map((h) => ({ label: h, value: h }))}
              style={{ marginTop: 8, "--padding": "6px 0" } as React.CSSProperties}
            />
            <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>{INTERVALO_OCITOCINA[t.ocitocina.vezes]}</div>
          </>
        ),
      )}
      {linha(
        "PG",
        t.pg > 0,
        () => setT({ ...t, pg: t.pg ? 0 : 1 }),
        vezes(t.pg || 1, (n) => setT({ ...t, pg: n })),
      )}
      {linha("P4", t.p4, () => setT({ ...t, p4: !t.p4 }))}
      {linha(
        "Infusão",
        !!t.infusao,
        () => setT({ ...t, infusao: t.infusao ? null : inf }),
        <>
          <div style={{ color: "#999", fontSize: 12, marginBottom: 4 }}>Antibiótico (AB)</div>
          <Selector
            multiple
            columns={2}
            showCheckMark={false}
            value={inf.ab}
            onChange={(v) => setT({ ...t, infusao: { ...inf, ab: v } })}
            options={ANTIBIOTICOS.map((a) => ({ label: a, value: a }))}
          />
          <Input
            placeholder="Outro antibiótico (fica gravado na lista)"
            value={inf.abOutro}
            onChange={(v) => setT({ ...t, infusao: { ...inf, abOutro: v } })}
            style={{ ...caixa, marginTop: 6 }}
          />
          <Checkbox
            checked={inf.mucolitico}
            onChange={(on) => setT({ ...t, infusao: { ...inf, mucolitico: on } })}
            style={{ marginTop: 8 }}
          >
            Mucolítico
          </Checkbox>
          <Input
            placeholder="Outros (fica gravado na lista)"
            value={inf.outro}
            onChange={(v) => setT({ ...t, infusao: { ...inf, outro: v } })}
            style={{ ...caixa, marginTop: 6 }}
          />
        </>,
      )}
      {linha("Zaragatoa", t.zaragatoa, () => setT({ ...t, zaragatoa: !t.zaragatoa }))}
      {linha(
        "Lavagem",
        t.lavagem > 0,
        () => setT({ ...t, lavagem: t.lavagem ? 0 : 1 }),
        vezes(t.lavagem || 1, (n) => setT({ ...t, lavagem: n })),
      )}
      {linha(
        "Indução",
        !!t.inducao,
        () => setT({ ...t, inducao: t.inducao ? null : { data: dayjs().add(1, "day").hour(20).minute(0).toISOString(), produto: "" } }),
        t.inducao && (
          <>
            <Input
              placeholder="Produto (opcional)"
              value={t.inducao.produto}
              onChange={(v) => setT({ ...t, inducao: { ...t.inducao!, produto: v } })}
              style={{ ...caixa, marginBottom: 6 }}
            />
            <Button size="small" onClick={() => setCalendario(true)}>
              {dayjs(t.inducao.data).format("DD/MM/YYYY HH:mm")}
            </Button>
          </>
        ),
      )}

      <div style={{ margin: "14px 0" }}>
        <Checkbox checked={!!t.marcar} onChange={(on) => setT({ ...t, marcar: on ? { dias: "1" } : null })} style={{ fontWeight: 600 }}>
          Marcar TX — repetir no Trabalho diário
        </Checkbox>
        {t.marcar && (
          <div style={{ marginTop: 8, paddingLeft: 28 }}>
            <Selector
              columns={4}
              showCheckMark={false}
              value={[t.marcar.dias]}
              onChange={(v) => v[0] && setT({ ...t, marcar: { dias: v[0] } })}
              options={[
                { label: "1 dia", value: "1" },
                { label: "2 dias", value: "2" },
                { label: "3 dias", value: "3" },
                { label: "Agenda", value: "agenda" },
              ]}
              style={{ "--padding": "6px 0" } as React.CSSProperties}
            />
            <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>
              Cria as tarefas no Trabalho diário. Repete as mesmas vezes por dia (na ocitocina, também as mesmas horas). A zaragatoa vai
              para a próxima vez; a indução fica no dia/hora escolhido.
            </div>
          </div>
        )}
      </div>
      <Button block color="primary" onClick={() => onGuardar(t)}>
        Guardar tratamento
      </Button>
      <DatePicker
        visible={calendario}
        precision="minute"
        onClose={() => setCalendario(false)}
        value={t.inducao ? new Date(t.inducao.data) : new Date()}
        onConfirm={(d) => t.inducao && setT({ ...t, inducao: { ...t.inducao, data: d.toISOString() } })}
      />
    </>
  );
}

// ── Desenho com os 4 pontos ─────────────────────────────────────────────────

function Desenho({ registo, onTocar }: { registo: Registo; onTocar: (p: Parte) => void }) {
  const { primary_color } = useBrand();
  const ponto = (p: Parte, cx: number, cy: number, r: number) => {
    const feito = !!registo[p];
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
            {resumo(registo, p).slice(0, 24)}
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

// ── Página ──────────────────────────────────────────────────────────────────

const td: React.CSSProperties = { padding: "6px 8px", borderBottom: "1px solid #f5f5f5", verticalAlign: "top" };

export default function AmostraRegisto() {
  const isMobile = useIsMobile();
  const user = useUser();
  const { primary_color } = useBrand();
  const [anteriores, setAnteriores] = useState(ANTERIORES);
  const vazio = (): Registo => ({ data: dayjs().toISOString(), equipa: user.nome || user.username });
  const [novo, setNovo] = useState<Registo>(vazio);
  const [aberto, setAberto] = useState<Ficha | null>(null);
  const [calendario, setCalendario] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const guardar = (f: Ficha, v: unknown) => {
    setNovo((r) => ({ ...r, [f]: v }));
    setAberto(null);
  };
  const temAlgo = !!(novo.OE || novo.OD || novo.UT || novo.CER || novo.TX || novo.DG);

  const ficha =
    aberto === "OE" || aberto === "OD" ? (
      <FichaOvario parte={aberto} atual={novo[aberto]} onGuardar={(v) => guardar(aberto, v)} />
    ) : aberto === "UT" ? (
      <FichaUtero atual={novo.UT} onGuardar={(v) => guardar("UT", v)} />
    ) : aberto === "CER" ? (
      <FichaCervix atual={novo.CER} onGuardar={(v) => guardar("CER", v)} />
    ) : aberto === "TX" ? (
      <FichaTX atual={novo.TX} onGuardar={(v) => guardar("TX", v)} />
    ) : aberto === "DG" ? (
      <FichaDG atual={novo.DG} onGuardar={(v) => guardar("DG", v)} />
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

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", paddingBottom: 24 }}>
      {/* Cabeçalho: Equipa · Animal · Cliente · Data/Hora */}
      <div style={{ background: "#fff", padding: "10px 12px", borderRadius: isMobile ? 0 : 8 }}>
        <div style={{ fontSize: 11, color: "#999" }}>Amostra — nada é gravado</div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 18, fontWeight: 700 }}>Estrela</span>
          <span style={{ color: "#666" }}>Coudelaria Vale · Box 4</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 12, color: "#666" }}>
            Registado por <b>{novo.equipa}</b>
          </span>
          <Button size="small" onClick={() => setCalendario(true)}>
            {dayjs(novo.data).format("DD/MM HH:mm")}
          </Button>
        </div>
        <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>A data e a hora entram sozinhas e podem ser alteradas.</div>
      </div>

      {/* Desenho + DG · TX · ! · INS */}
      <div style={{ background: "#fff", marginTop: 8, padding: "8px 0", borderRadius: isMobile ? 0 : 8 }}>
        <div style={{ padding: "0 12px 4px", fontSize: 12, color: "#999" }}>Toque numa parte para registar</div>
        <Desenho registo={novo} onTocar={setAberto} />
        <div style={{ display: "flex", gap: 8, padding: "8px 12px" }}>
          {acao("DG", () => setAberto("DG"), !!novo.DG)}
          {acao("TX", () => setAberto("TX"), !!novo.TX)}
          {acao("!", () => setNovo({ ...novo, prioritario: !novo.prioritario }), !!novo.prioritario)}
          {acao("INS", () => setAviso("No registo verdadeiro, abre o Registar inseminação desta égua."), false)}
        </div>
        <div style={{ padding: "0 12px", fontSize: 11, color: "#999" }}>
          DG: diagnóstico de gestação · TX: tratamento · !: tarefa prioritária · INS: registar inseminação
        </div>
        {aviso && <div style={{ padding: "6px 12px", fontSize: 12, color: "#d46b08" }}>{aviso}</div>}
        {(novo.TX || novo.DG || novo.prioritario) && (
          <div style={{ padding: "8px 12px", fontSize: 12 }}>
            {novo.prioritario && (
              <div style={{ color: primary_color, fontWeight: 700 }}>
                ! Prioritária — a próxima tarefa desta égua fica urgente no Trabalho diário
              </div>
            )}
            {novo.DG && <div>DG: {novo.DG}</div>}
            {novo.TX && <div>TX: {resumo(novo, "TX") || "—"}</div>}
          </div>
        )}
        <div style={{ padding: "8px 12px" }}>
          <Button
            block
            color="primary"
            disabled={!temAlgo}
            onClick={() => {
              setAnteriores((a) => [novo, ...a].slice(0, 10));
              setNovo(vazio());
              setAviso(null);
            }}
          >
            Guardar registo
          </Button>
        </div>
      </div>

      {/* Últimos registos */}
      <div style={{ padding: "12px 12px 4px", fontSize: 12, color: "#999" }}>Últimos registos</div>
      <div style={{ background: "#fff", borderRadius: isMobile ? 0 : 8, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ color: "#999", textAlign: "left" }}>
              {["Data/Hora", "OE", "OD", "UT", "CER", "TX"].map((h) => (
                <th key={h} style={{ padding: "6px 8px", borderBottom: "1px solid #f0f0f0", whiteSpace: "nowrap" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {anteriores.map((r) => (
              <tr key={r.data}>
                <td style={td}>
                  <b>{dayjs(r.data).format("DD/MM HH:mm")}</b>
                  <div style={{ color: "#999" }}>{r.equipa}</div>
                </td>
                {(["OE", "OD", "UT", "CER", "TX"] as Ficha[]).map((f) => (
                  <td key={f} style={td}>
                    {resumo(r, f) || "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Fichas: folha de baixo no telemóvel, gaveta à direita no computador */}
      {isMobile ? (
        <Popup
          visible={aberto !== null}
          onMaskClick={() => setAberto(null)}
          destroyOnClose
          bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 16, maxHeight: "88dvh", overflowY: "auto" }}
        >
          {aberto && <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>{NOMES[aberto]}</div>}
          {ficha}
        </Popup>
      ) : (
        <Drawer open={aberto !== null} onClose={() => setAberto(null)} title={aberto ? NOMES[aberto] : ""} size={440} destroyOnHidden>
          {ficha}
        </Drawer>
      )}
      <DatePicker
        visible={calendario}
        precision="minute"
        onClose={() => setCalendario(false)}
        value={new Date(novo.data)}
        onConfirm={(d) => setNovo({ ...novo, data: d.toISOString() })}
      />
    </div>
  );
}
