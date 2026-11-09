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

export type Marca = PublicSettings & { fuso_horario?: string };

/** Fusos horários mais prováveis (IANA). "Hoje" na app segue o escolhido. */
export const FUSOS = [
  "Europe/Lisbon",
  "Atlantic/Madeira",
  "Atlantic/Azores",
  "Europe/London",
  "Europe/Madrid",
  "Europe/Paris",
  "Europe/Brussels",
  "Europe/Berlin",
  "Europe/Rome",
  "Europe/Zurich",
  "America/Sao_Paulo",
  "America/New_York",
  "Africa/Luanda",
  "Africa/Maputo",
  "UTC",
];

const CIDADES: Record<string, string> = {
  "Europe/Lisbon": "Lisboa",
  "Atlantic/Madeira": "Madeira",
  "Atlantic/Azores": "Açores",
  "Europe/London": "Londres",
  "Europe/Madrid": "Madrid",
  "Europe/Paris": "Paris",
  "Europe/Brussels": "Bruxelas",
  "Europe/Berlin": "Berlim",
  "Europe/Rome": "Roma",
  "Europe/Zurich": "Zurique",
  "America/Sao_Paulo": "São Paulo",
  "America/New_York": "Nova Iorque",
  "Africa/Luanda": "Luanda",
  "Africa/Maputo": "Maputo",
};

/** "Lisboa (UTC+0)" em vez de "Europe/Lisbon" — com a diferença de hoje. */
export function rotuloFuso(fuso: string): string {
  let desvio = "";
  try {
    desvio =
      new Intl.DateTimeFormat("en", { timeZone: fuso, timeZoneName: "shortOffset" })
        .formatToParts(new Date())
        .find((p) => p.type === "timeZoneName")
        ?.value.replace("GMT", "UTC") ?? "";
  } catch {
    /* fuso desconhecido do browser: só o nome */
  }
  if (desvio === "UTC") desvio = "UTC+0";
  const nome = CIDADES[fuso] ?? fuso.replace("_", " ");
  return fuso === "UTC" ? "UTC" : desvio ? `${nome} (${desvio})` : nome;
}

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

/** A clínica usa boxes/paddocks nas estadias? (desligado: a entrada não pede alojamento) */
export const useUsoAlojamentos = () =>
  useQuery({ queryKey: ["definicoes", "alojamentos", "uso"], queryFn: () => api<{ usar: boolean }>("/definicoes/alojamentos/uso") });

export function useMudarUsoAlojamentos() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (usar: boolean) => api<{ usar: boolean }>("/definicoes/alojamentos/uso", "PUT", { usar }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["definicoes", "alojamentos"] });
      queryClient.invalidateQueries({ queryKey: ["estadias"] });
    },
  });
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
  acesso_faturacao: boolean;
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
/** Acesso ao separador Faturação. Se for o próprio, o menu atualiza logo. */
export function useAcessoFaturacao() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ativo }: { id: number; ativo: boolean }) => api<Utilizador>(`/definicoes/utilizadores/${id}/faturacao`, "PUT", { ativo }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["definicoes", "utilizadores"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}
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
