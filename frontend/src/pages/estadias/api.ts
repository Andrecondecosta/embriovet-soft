import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

export const TIPOS_REGISTO = ["estadia", "visita", "externo"] as const;
export const MOTIVOS = ["inseminacao", "colheita", "diagnostico", "tratamento", "embriao"] as const;
export const TIPOS_ANIMAL = ["egua", "garanhao", "receptora"] as const;
export const ESTADOS_SAIDA = ["gestante", "alta", "sem_resultado", "transferido"] as const;

export type TipoRegisto = (typeof TIPOS_REGISTO)[number];
export type Motivo = (typeof MOTIVOS)[number];
export type TipoAnimal = (typeof TIPOS_ANIMAL)[number];
export type EstadoSaida = (typeof ESTADOS_SAIDA)[number];

/** Motivos por tipo de animal (as mesmas regras do servidor): a égua não faz
 *  colheita; a receptora só recebe embriões e pode ter diagnóstico; o
 *  garanhão só faz colheita e tratamento. */
export const MOTIVOS_POR_TIPO: Record<TipoAnimal, readonly Motivo[]> = {
  egua: ["inseminacao", "diagnostico", "tratamento", "embriao"],
  receptora: ["embriao", "diagnostico"],
  garanhao: ["colheita", "tratamento"],
};

export interface Estadia {
  id: number;
  animal_id: number;
  animal: string | null;
  tipo: TipoRegisto;
  animal_tipo: TipoAnimal;
  proprietario: string | null;
  motivo: Motivo | null;
  estado: string | null;
  data_entrada: string | null;
  data_saida: string | null;
  alojamento_nome: string | null;
  dias_internado: number | null;
}

export interface AnimalPesquisa {
  id: number;
  nome: string;
  tipo: TipoAnimal;
  dono_id: number | null;
  proprietario: string | null;
  em_aberto: TipoRegisto | null;
}

export interface AnimalNovo {
  nome: string;
  tipo: TipoAnimal;
  raca?: string;
  pelagem?: string;
  data_nascimento?: string | null;
  numero_registo?: string;
  chip?: string;
  altura?: number | null;
  peso?: number | null;
  pai?: string;
  mae?: string;
  avo_paterno?: string;
  avo_materno?: string;
}

export interface EstadiaIn {
  animal_id?: number;
  animal?: AnimalNovo;
  tipo_registo: TipoRegisto;
  motivo: Motivo;
  dono_id: number | null;
  data_entrada: string;
  alojamento_id: number | null;
  observacoes?: string;
}

export const useInternadas = (tipo: TipoAnimal | null) =>
  useQuery({
    queryKey: ["estadias", "internadas", tipo],
    queryFn: () => api<{ total: number; itens: Estadia[] }>(`/estadias/internadas${tipo ? `?tipo_animal=${tipo}` : ""}`),
    placeholderData: keepPreviousData,
  });

export const useMovimentos = () =>
  useQuery({
    queryKey: ["estadias", "movimentos"],
    queryFn: () => api<{ inicio: string; fim: string; entram: Estadia[]; saem: Estadia[] }>("/estadias/movimentos"),
  });

export const useHistoricoEstadias = (ano: number, mes: number, tipo: TipoAnimal | null) =>
  useQuery({
    queryKey: ["estadias", "historico", ano, mes, tipo],
    queryFn: () =>
      api<{ total: number; itens: Estadia[] }>(`/estadias/historico?ano=${ano}&mes=${mes}${tipo ? `&tipo_animal=${tipo}` : ""}`),
    placeholderData: keepPreviousData,
  });

export const useOpcoesEstadia = () =>
  useQuery({
    queryKey: ["estadias", "opcoes"],
    queryFn: () =>
      api<{ donos: { id: number; nome: string }[]; alojamentos: { id: number; nome: string; tipo: string; capacidade: number }[] }>(
        "/estadias/opcoes",
      ),
  });

export const usePesquisaAnimais = (q: string, tipo?: TipoAnimal) =>
  useQuery({
    queryKey: ["animais", "pesquisa", q, tipo],
    queryFn: () => api<AnimalPesquisa[]>(`/animais/pesquisa?q=${encodeURIComponent(q)}${tipo ? `&tipo=${tipo}` : ""}`),
    placeholderData: keepPreviousData,
  });

function useEstadiaMutation<V, R>(fn: (v: V) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["estadias"] });
      queryClient.invalidateQueries({ queryKey: ["animais"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export const useCriarEstadia = () => useEstadiaMutation((d: EstadiaIn) => api<{ id: number; animal_id: number }>("/estadias", "POST", d));
export const useRegistarSaida = () =>
  useEstadiaMutation(({ id, ...d }: { id: number; data_saida: string; estado: EstadoSaida; observacoes?: string }) =>
    api<{ ok: boolean }>(`/estadias/${id}/saida`, "POST", d),
  );
