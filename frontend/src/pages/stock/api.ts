import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

export interface Lote {
  id: number;
  garanhao: string;
  garanhao_nome: string;
  animal_id: number | null;
  dono_id: number | null;
  proprietario_nome: string | null;
  data_embriovet: string | null;
  origem_externa: string | null;
  palhetas_produzidas: number | null;
  qualidade: string | null;
  concentracao: number | null;
  motilidade: number | null;
  local_armazenagem: string | null;
  certificado: string | null;
  dose: string | null;
  observacoes: string | null;
  quantidade_inicial: number | null;
  existencia_atual: number | null;
  data_criacao: string | null;
  criado_por: string | null;
  contentor_id: number | null;
  contentor_codigo: string | null;
  canister: number | null;
  andar: number | null;
  cor: string | null;
}

export interface GaranhaoStock {
  animal_id: number | null;
  garanhao: string;
  palhetas: number;
  lotes: number;
  donos: number;
  no_seletor: boolean;
}

export interface Ligacoes {
  inseminacoes?: number;
  transferencias?: number;
  transferencias_externas?: number;
}

export interface LotesResposta {
  items: Lote[];
  kpis: { lotes: number; palhetas: number; proprietarios: number; qualidade_media: number | null };
  por_proprietario: { dono_id: number | null; proprietario_nome: string | null; palhetas: number }[];
  ligacoes: Record<string, Ligacoes>;
  donos_disponiveis: { id: number | null; nome: string | null }[];
}

export interface TransfInterna {
  id: number;
  data: string | null;
  quantidade: number;
  origem_id: number | null;
  origem: string | null;
  destino_id: number | null;
  destino: string | null;
}

export interface TransfExterna {
  id: number;
  data: string | null;
  quantidade: number;
  origem_id: number | null;
  origem: string | null;
  destinatario: string;
  tipo: string | null;
  observacoes: string | null;
}

export interface Opcao {
  id: number;
  nome: string;
}

export interface LotesFiltro {
  garanhao: string;
  donos: number[];
  semDono: boolean;
  minPalhetas: number;
  incluirVazios: boolean;
}

export interface LoteCampos {
  data_embriovet: string;
  origem_externa: string;
  qualidade: string;
  concentracao: number;
  motilidade: number;
  certificado: "Sim" | "Não";
  dose: string;
  cor: string;
  contentor_id: number | null;
  canister: number;
  andar: 1 | 2;
  observacoes: string;
  garanhao: string;
  dono_id: number | null;
}

export type LoteNovo = LoteCampos & { palhetas: number };
export type LoteEdicao = LoteCampos & { palhetas_produzidas: number; existencia_atual: number };

export const useGaranhoesStock = () =>
  useQuery({ queryKey: ["stock", "garanhoes"], queryFn: () => api<GaranhaoStock[]>("/stock/garanhoes") });

export function useLotes(f: LotesFiltro | null) {
  return useQuery({
    queryKey: ["stock", "lotes", f],
    enabled: !!f?.garanhao,
    placeholderData: keepPreviousData,
    queryFn: () => {
      const p = new URLSearchParams({ garanhao: f!.garanhao });
      f!.donos.forEach((d) => p.append("donos", String(d)));
      if (f!.semDono) p.set("sem_dono", "true");
      if (f!.minPalhetas) p.set("min_palhetas", String(f!.minPalhetas));
      if (f!.incluirVazios) p.set("incluir_vazios", "true");
      return api<LotesResposta>(`/stock/lotes?${p}`);
    },
  });
}

export const useTransferencias = (garanhao: string | null) =>
  useQuery({
    queryKey: ["stock", "transferencias", garanhao],
    enabled: !!garanhao,
    queryFn: () =>
      api<{ internas: TransfInterna[]; externas: TransfExterna[] }>(
        `/stock/transferencias?garanhao=${encodeURIComponent(garanhao!)}`,
      ),
  });

export const useOpcoes = (tipo: "proprietarios" | "contentores" | "garanhoes", apenasAtivos = false) =>
  useQuery({
    queryKey: ["opcoes", tipo, apenasAtivos],
    queryFn: () => api<Opcao[]>(`/opcoes/${tipo}${apenasAtivos ? "?apenas_ativos=true" : ""}`),
    staleTime: 60_000,
  });

function useStockMutation<V, R>(fn: (v: V) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["opcoes"] });
    },
  });
}

export const useCriarLote = () => useStockMutation((d: LoteNovo) => api<Lote>("/stock/lotes", "POST", d));
export const useEditarLote = () =>
  useStockMutation(({ id, ...d }: LoteEdicao & { id: number }) => api<Lote>(`/stock/lotes/${id}`, "PUT", d));
export const useApagarLote = () =>
  useStockMutation((id: number) => api<{ ok: boolean }>(`/stock/lotes/${id}`, "DELETE"));

/** "CT1/C3/A2" — como na lista da app atual. */
export function localizacao(l: Pick<Lote, "contentor_codigo" | "canister" | "andar" | "local_armazenagem">): string | null {
  if (l.contentor_codigo) {
    return l.canister != null && l.andar != null ? `${l.contentor_codigo}/C${l.canister}/A${l.andar}` : l.contentor_codigo;
  }
  return l.local_armazenagem || null;
}

/** Referência do lote: origem externa, ou data de produção. */
export const referencia = (l: Pick<Lote, "origem_externa" | "data_embriovet">) => l.origem_externa || l.data_embriovet || null;
