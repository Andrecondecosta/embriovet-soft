import dayjs from "dayjs";

import type { PorFaturar } from "./api";

const ISO = "YYYY-MM-DD";

/** Um período em que o total de palhetas do garanhão não mudou. */
export interface Troco {
  inicio: string;
  fim: string;
  dias: number;
  palhetas: number;
  /** Mudança em relação ao período anterior (null no primeiro, ou depois de um intervalo). */
  diferenca: number | null;
  /** Palhetas × dias. */
  quantidade: number;
}

/** O sémen de um proprietário, por garanhão: os lotes juntos, com os totais. */
export interface GrupoGaranhao {
  chave: string;
  dono_id: number | null;
  dono_nome: string | null;
  garanhao: string;
  lotes: PorFaturar[];
  trocos: Troco[];
  /** Palhetas × dias do período todo. */
  quantidade: number;
  /** Palhetas no fim do período (o último troço). */
  palhetas: number;
}

/** O garanhão do lote ("Rubi · lote 812" → "Rubi"). */
export const garanhaoDe = (l: PorFaturar & { garanhao?: string | null }) => l.garanhao ?? l.descricao.split(" · lote ")[0];

/**
 * Junta as linhas dos lotes por proprietário e garanhão. Cada linha de lote
 * já tem as palhetas fixas no seu período; o total do garanhão em cada dia é
 * a soma dos lotes nesse dia, e parte-se num troço novo sempre que muda — as
 * mesmas contas (palhetas × dias), só mostradas por garanhão.
 */
export function agruparPorGaranhao(linhas: PorFaturar[]): GrupoGaranhao[] {
  const grupos = new Map<string, PorFaturar[]>();
  for (const l of linhas) {
    const k = `${l.dono_id ?? "sem"}|${garanhaoDe(l)}`;
    (grupos.get(k) ?? grupos.set(k, []).get(k)!).push(l);
  }
  return [...grupos.entries()].map(([chave, lotes]) => {
    // Dias em que algum lote começa ou acaba: entre dois deles o total não muda.
    const cortes = [...new Set(lotes.flatMap((l) => [l.inicio, dayjs(l.fim).add(1, "day").format(ISO)]))].sort();
    const trocos: Troco[] = [];
    for (let i = 0; i < cortes.length - 1; i++) {
      const inicio = cortes[i];
      const fim = dayjs(cortes[i + 1]).subtract(1, "day").format(ISO);
      const palhetas = lotes.filter((l) => l.inicio <= inicio && l.fim >= inicio).reduce((s, l) => s + (l.palhetas ?? 0), 0);
      if (!palhetas) continue;
      const anterior = trocos[trocos.length - 1];
      const seguido = anterior && dayjs(anterior.fim).add(1, "day").format(ISO) === inicio;
      if (seguido && anterior.palhetas === palhetas) {
        anterior.fim = fim;
        continue;
      }
      trocos.push({ inicio, fim, dias: 0, palhetas, diferenca: seguido ? palhetas - anterior.palhetas : null, quantidade: 0 });
    }
    for (const tr of trocos) {
      tr.dias = dayjs(tr.fim).diff(dayjs(tr.inicio), "day") + 1;
      tr.quantidade = tr.dias * tr.palhetas;
    }
    const l0 = lotes[0];
    return {
      chave,
      dono_id: l0.dono_id,
      dono_nome: l0.dono_nome,
      garanhao: garanhaoDe(l0),
      lotes: [...lotes].sort((a, b) => a.descricao.localeCompare(b.descricao) || a.inicio.localeCompare(b.inicio)),
      trocos,
      quantidade: lotes.reduce((s, l) => s + l.quantidade, 0),
      palhetas: trocos[trocos.length - 1]?.palhetas ?? 0,
    };
  });
}
