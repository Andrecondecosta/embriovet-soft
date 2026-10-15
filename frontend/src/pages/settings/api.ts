import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { descarregar } from "../../components/download";
import type { PublicSettings } from "../../api/types";

// ── Marca e idioma ──────────────────────────────────────────────────────────

// Cada língua no seu próprio nome, para quem não percebe a atual a encontrar.
export const IDIOMAS = [
  { value: "pt-PT", label: "Português (Portugal)" },
  { value: "en", label: "English" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
] as const;

export type Marca = PublicSettings;

export const useMarca = () => useQuery({ queryKey: ["definicoes", "marca"], queryFn: () => api<Marca>("/definicoes/marca") });

/** Grava e atualiza logo a marca/idioma em toda a app (menu, título, traduções). */
function useMarcaMutation<V>(fn: (v: V) => Promise<Marca>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (m) => {
      queryClient.setQueryData(["definicoes", "marca"], m);
      queryClient.setQueryData(["settings", "public"], m);
    },
  });
}

export const useGravarMarca = () => useMarcaMutation((m: Marca) => api<Marca>("/definicoes/marca", "PUT", m));
export const useReporMarca = () => useMarcaMutation((_: void) => api<Marca>("/definicoes/marca/repor", "POST"));

// ── Alojamentos ─────────────────────────────────────────────────────────────

export const TIPOS_ALOJAMENTO = ["box", "paddock", "outro"] as const;
export type TipoAlojamento = (typeof TIPOS_ALOJAMENTO)[number];

export interface Alojamento {
  id: number;
  tipo: TipoAlojamento;
  nome: string;
  capacidade: number;
  ativo: boolean;
  observacoes: string | null;
}
export type AlojamentoIn = Pick<Alojamento, "nome" | "tipo" | "capacidade" | "observacoes">;

export const useAlojamentos = () =>
  useQuery({ queryKey: ["definicoes", "alojamentos"], queryFn: () => api<Alojamento[]>("/definicoes/alojamentos") });

function useAlojMutation<V>(fn: (v: V) => Promise<Alojamento>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["definicoes", "alojamentos"] }) });
}

export const useCriarAlojamento = () => useAlojMutation((d: AlojamentoIn) => api<Alojamento>("/definicoes/alojamentos", "POST", d));
export const useEditarAlojamento = () =>
  useAlojMutation(({ id, ...d }: AlojamentoIn & { id: number }) => api<Alojamento>(`/definicoes/alojamentos/${id}`, "PUT", d));
export const useAlternarAlojamento = () =>
  useAlojMutation((id: number) => api<Alojamento>(`/definicoes/alojamentos/${id}/alternar`, "POST"));

// ── Utilizadores ────────────────────────────────────────────────────────────

export const NIVEIS = [
  { value: "Administrador", label: "users.level.admin" },
  { value: "Gestor", label: "users.level.manager" },
  { value: "Visualizador", label: "users.level.viewer" },
] as const;
export type Nivel = (typeof NIVEIS)[number]["value"];

export interface Utilizador {
  id: number;
  username: string;
  nome_completo: string;
  nivel: string;
  ativo: boolean;
  created_at: string | null;
  last_login: string | null;
}
export interface UtilizadorIn {
  username: string;
  nome_completo: string;
  nivel: Nivel;
  password: string;
}

export const useUtilizadores = () =>
  useQuery({ queryKey: ["definicoes", "utilizadores"], queryFn: () => api<Utilizador[]>("/definicoes/utilizadores") });

function useUsrMutation<V, R>(fn: (v: V) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["definicoes", "utilizadores"] }) });
}

export const useCriarUtilizador = () => useUsrMutation((d: UtilizadorIn) => api<Utilizador>("/definicoes/utilizadores", "POST", d));
export const useAtivarUtilizador = () =>
  useUsrMutation(({ id, ativar }: { id: number; ativar: boolean }) =>
    api<Utilizador>(`/definicoes/utilizadores/${id}/${ativar ? "ativar" : "desativar"}`, "POST"),
  );
export const useMudarPassword = () =>
  useUsrMutation(({ id, password }: { id: number; password: string }) =>
    api<{ ok: boolean }>(`/definicoes/utilizadores/${id}/password`, "POST", { password }),
  );

// ── Cópia de segurança ──────────────────────────────────────────────────────

export interface ResumoBackup {
  lotes: number;
  proprietarios: number;
  animais: number;
  inseminacoes: number;
  estadias: number;
  tabelas: number;
}

export const useResumoBackup = () =>
  useQuery({ queryKey: ["definicoes", "backup"], queryFn: () => api<ResumoBackup>("/definicoes/backup") });

/** Descarrega o ZIP (pode demorar: é gerado na hora). */
export const baixarBackup = () => descarregar("/definicoes/backup/zip", "backup.zip");
