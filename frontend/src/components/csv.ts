/** Descarrega linhas como CSV (UTF-8 com BOM, para o Excel abrir os acentos). */
export function baixarCsv(nome: string, cabecalho: string[], linhas: (string | number | null | undefined)[][]) {
  const esc = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const texto = [cabecalho, ...linhas].map((l) => l.map(esc).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + texto], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  a.click();
  URL.revokeObjectURL(url);
}

export const dataCurta = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("pt-PT", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—";

export const dataHora = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString("pt-PT", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";
