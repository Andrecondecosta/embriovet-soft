import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, qs } from "../../api/client";
import type { Owner, OwnerInput, Page } from "../../api/types";

export type Estado = "todos" | "ativos" | "inativos";
export type Ordem = "nome" | "id" | "status";

export interface OwnersFiltro {
  q: string;
  estado: Estado;
  ordem: Ordem;
  pagina: number;
}

export const POR_PAGINA = 25;

export function useOwners(f: OwnersFiltro) {
  return useQuery({
    queryKey: ["owners", f],
    queryFn: () => api<Page<Owner>>(`/owners?${qs({ ...f, por_pagina: POR_PAGINA })}`),
    // Mantém a página anterior visível enquanto a seguinte carrega —
    // sem tabela a piscar ou a desaparecer.
    placeholderData: keepPreviousData,
  });
}

function useOwnerMutation<V>(fn: (v: V) => Promise<Owner | { ok: boolean }>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["owners"] }),
  });
}

export const useCreateOwner = () => useOwnerMutation((d: OwnerInput) => api<Owner>("/owners", "POST", d));

export const useUpdateOwner = () =>
  useOwnerMutation(({ id, ...d }: OwnerInput & { id: number }) => api<Owner>(`/owners/${id}`, "PUT", d));

export const useToggleOwner = () =>
  useOwnerMutation((id: number) => api<Owner>(`/owners/${id}/alternar-estado`, "POST"));

export const useDeleteOwner = () =>
  useOwnerMutation((id: number) => api<{ ok: boolean }>(`/owners/${id}`, "DELETE"));
