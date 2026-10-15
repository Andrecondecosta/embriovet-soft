import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";

export interface Contentor {
  id: number;
  codigo: string;
  descricao: string | null;
  x: number;
  y: number;
  palhetas: number;
  lotes: number;
}

export interface MapaResposta {
  contentores: Contentor[];
  virtual: { w: number; h: number; lado: number };
}

export interface LoteContentor {
  id: number;
  garanhao: string;
  dono_id: number | null;
  proprietario_nome: string | null;
  canister: number | null;
  andar: number | null;
  existencia_atual: number;
  qualidade: string | null;
  data_embriovet: string | null;
  origem_externa: string | null;
  motilidade: number | null;
  concentracao: number | null;
}

export interface StockContentor {
  contentor: { id: number; codigo: string; descricao: string | null; x: number; y: number };
  lotes: LoteContentor[];
  palhetas: number;
}

export const useMapa = () =>
  useQuery({ queryKey: ["mapa", "contentores"], queryFn: () => api<MapaResposta>("/mapa/contentores") });

export const useStockContentor = (id: number | null) =>
  useQuery({
    queryKey: ["mapa", "stock", id],
    enabled: id !== null,
    queryFn: () => api<StockContentor>(`/mapa/contentores/${id}/stock`),
  });

function useMapaMutation<V, R>(fn: (v: V) => Promise<R>, tambemStock = false) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mapa"] });
      queryClient.invalidateQueries({ queryKey: ["opcoes", "contentores"] });
      // Mover/inverter mudam a localização dos lotes, que aparece nos Lotes.
      if (tambemStock) queryClient.invalidateQueries({ queryKey: ["stock"] });
    },
  });
}

export const useCriarContentor = () =>
  useMapaMutation((d: { codigo: string; descricao: string }) => api<Contentor>("/mapa/contentores", "POST", d));
export const useEditarContentor = () =>
  useMapaMutation(({ id, ...d }: { id: number; codigo: string; descricao: string }) =>
    api<Contentor>(`/mapa/contentores/${id}`, "PUT", d),
  );
export const useApagarContentor = () =>
  useMapaMutation((id: number) => api<{ ok: boolean }>(`/mapa/contentores/${id}`, "DELETE"), true);
export const useOrganizar = () => useMapaMutation(() => api<{ count: number }>("/mapa/organizar", "POST"));
export const useInverterAndares = () =>
  useMapaMutation((id: number) => api<{ count: number }>(`/mapa/contentores/${id}/inverter-andares`, "POST"), true);
export const useMoverPalhetas = () =>
  useMapaMutation(
    (d: { lote_id: number; quantidade: number; contentor_id: number; canister: number; andar: number }) =>
      api<{ ok: boolean }>("/mapa/mover", "POST", d),
    true,
  );

/** Grava a posição sem esperar pela lista (a caixa já está no sítio novo). */
export function useGravarPosicao() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, x, y }: { id: number; x: number; y: number }) =>
      api<{ id: number; x: number; y: number }>(`/mapa/contentores/${id}/posicao`, "PATCH", { x, y }),
    onSuccess: (r) =>
      queryClient.setQueryData<MapaResposta>(["mapa", "contentores"], (old) =>
        old ? { ...old, contentores: old.contentores.map((c) => (c.id === r.id ? { ...c, x: r.x, y: r.y } : c)) } : old,
      ),
  });
}

/** Troca dois contentores de lugar. A lista muda logo (sem esperar pela
 *  resposta); se a gravação falhar, volta ao que está na BD. */
export function useTrocarContentores() {
  const queryClient = useQueryClient();
  const chave = ["mapa", "contentores"];
  return useMutation({
    mutationFn: (d: { a: number; b: number }) => api<unknown>("/mapa/trocar", "POST", d),
    onMutate: ({ a, b }) => {
      queryClient.setQueryData<MapaResposta>(chave, (old) => {
        if (!old) return old;
        const ca = old.contentores.find((c) => c.id === a);
        const cb = old.contentores.find((c) => c.id === b);
        if (!ca || !cb) return old;
        return {
          ...old,
          contentores: old.contentores.map((c) =>
            c.id === a ? { ...c, x: cb.x, y: cb.y } : c.id === b ? { ...c, x: ca.x, y: ca.y } : c,
          ),
        };
      });
    },
    onError: () => queryClient.invalidateQueries({ queryKey: chave }),
  });
}

/** "Lote #12" / primeira palavra da referência — como a app atual mostra no tanque. */
export const refCurta = (l: LoteContentor) =>
  (l.origem_externa || l.data_embriovet || `#${l.id}`).trim().split(/\s+/)[0];
