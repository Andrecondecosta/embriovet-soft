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
  // Lote: as palhetas deste troço (a linha divide-se quando mudam).
  local?: string | null;
  palhetas: number | null;
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
  palhetas: number | null;
  fatura_numero: string;
  fatura_data: string;
  /** Primeiro fecho, de antes da app (pode não ter número). */
  acerto_inicial: boolean;
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

export type LinhaRef = { tipo: TipoFat; ref_id: number; inicio: string; fim: string };

/** Uma fatura por proprietário, todas numa só gravação. */
export const useFaturar = () =>
  useFatMutation(
    (d: {
      faturas: {
        dono_id: number | null;
        fatura_numero: string;
        fatura_data: string;
        acerto_inicial: boolean;
        observacoes?: string;
        linhas: LinhaRef[];
      }[];
    }) => api<{ linhas: number }>("/faturacao/faturar", "POST", d),
  );

export interface Movimento {
  ref_id: number;
  data: string;
  quantidade: number;
  tipo: "inseminacao" | "transferencia" | "externa";
  detalhe: string | null;
}
export interface DonoFat {
  id: number;
  nome: string;
  nome_completo: string | null;
  nif: string | null;
  morada: string | null;
  codigo_postal: string | null;
  cidade: string | null;
  email: string | null;
  telemovel: string | null;
}

/** Resumo antes de faturar: porquê de cada mudança de palhetas e dados dos donos. */
export const useResumo = (linhas: LinhaRef[], donoIds: number[], ativo: boolean) =>
  useQuery({
    queryKey: ["faturacao", "resumo", linhas, donoIds],
    enabled: ativo && linhas.length > 0,
    queryFn: () => api<{ movimentos: Movimento[]; donos: DonoFat[] }>("/faturacao/resumo", "POST", { linhas, dono_ids: donoIds }),
  });

export const useAnularFaturada = () =>
  useFatMutation(({ id, motivo }: { id: number; motivo: string }) => api<{ ok: boolean }>(`/faturacao/linhas/${id}/anular`, "POST", { motivo }));

export interface CelulaAno {
  atividade: boolean;
  dias: number;
  /** Dias do calendário com sémen por faturar, e em quantos lotes. */
  dias_semen: number;
  lotes: number;
  pd: number;
}
export interface LinhaAno {
  dono_id: number | null;
  dono_nome: string | null;
  /** Última data já faturada deste proprietário. */
  faturado_ate: string | null;
  celulas: Record<string, CelulaAno>;
}

/** Proprietário × ano ("antes" = anos anteriores a `desde`). */
export const useAnos = (desde: number) =>
  useQuery({
    queryKey: ["faturacao", "anos", desde],
    placeholderData: keepPreviousData,
    queryFn: () => api<{ anos: string[]; linhas: LinhaAno[] }>(`/faturacao/anos?desde=${desde}`),
  });
