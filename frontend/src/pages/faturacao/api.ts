import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

export type TipoFat = "estadia" | "armazenamento";

/** Uma linha por faturar: uma estadia (dias) ou um lote (palhetas × dias). */
export interface PorFaturar {
  tipo: TipoFat;
  ref_id: number;
  dono_id: number | null;
  dono_nome: string | null;
  descricao: string;
  inicio: string;
  fim: string;
  dias: number;
  quantidade: number;
  // Estadia
  entrada?: string;
  saida?: string | null;
  // Lote
  local?: string | null;
  palhetas_inicio?: number;
  palhetas_fim?: number;
}

export interface Faturada {
  id: number;
  tipo: TipoFat;
  ref_id: number;
  dono_id: number | null;
  dono_nome: string | null;
  descricao: string;
  inicio: string;
  fim: string;
  quantidade: number;
  fatura_numero: string;
  fatura_data: string;
  observacoes: string | null;
  criado_por: string | null;
  created_at: string;
  anulada: boolean;
  anulada_por: string | null;
  motivo_anulacao: string | null;
}

export interface FiltroFat {
  inicio: string;
  fim: string;
  dono_id: number | null;
}

const params = (o: object) =>
  new URLSearchParams(Object.entries(o as Record<string, unknown>).filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));

export const usePorFaturar = (f: FiltroFat & { tipo: TipoFat | null }) =>
  useQuery({
    queryKey: ["faturacao", "por-faturar", f],
    placeholderData: keepPreviousData,
    queryFn: () => api<PorFaturar[]>(`/faturacao/por-faturar?${params(f)}`),
  });

export const useFaturado = (f: FiltroFat & { fatura: string; anuladas: boolean }) =>
  useQuery({
    queryKey: ["faturacao", "faturado", f],
    placeholderData: keepPreviousData,
    queryFn: () => api<Faturada[]>(`/faturacao/faturado?${params(f)}`),
  });

function useFatMutation<V, R>(fn: (v: V) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: fn, onSettled: () => queryClient.invalidateQueries({ queryKey: ["faturacao"] }) });
}

export const useFaturar = () =>
  useFatMutation(
    (d: {
      fatura_numero: string;
      fatura_data: string;
      observacoes?: string;
      linhas: { tipo: TipoFat; ref_id: number; inicio: string; fim: string }[];
    }) => api<{ linhas: number }>("/faturacao/faturar", "POST", d),
  );

export const useAnularFaturada = () =>
  useFatMutation(({ id, motivo }: { id: number; motivo: string }) => api<{ ok: boolean }>(`/faturacao/linhas/${id}/anular`, "POST", { motivo }));
