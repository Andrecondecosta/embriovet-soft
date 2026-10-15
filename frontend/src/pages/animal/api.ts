import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

export interface Animal {
  id: number;
  nome: string;
  tipo: "egua" | "garanhao" | "receptora";
  raca: string | null;
  data_nascimento: string | null;
  numero_registo: string | null;
  dono_id: number | null;
  pelagem: string | null;
  altura: number | null;
  peso: number | null;
  pai: string | null;
  mae: string | null;
  avo_paterno: string | null;
  avo_materno: string | null;
  chip: string | null;
  observacoes: string | null;
  is_receptora: boolean;
  ativo: boolean;
  proprietario: string | null;
  estadia_ativa: number | null;
  estadia_inseminacao: { id: number; garanhao: string | null; data_entrada: string | null } | null;
}
export type AnimalIn = Omit<Animal, "id" | "ativo" | "estadia_ativa" | "estadia_inseminacao" | "proprietario" | "is_receptora">;

export const COMPORTAMENTOS = ["cio_ativo", "sem_cio", "anestro", "pos_ovulacao"] as const;
export interface Registo {
  id: number;
  data_registo: string;
  foliculo_mm: number | null;
  edema_grau: number | null;
  fluido_uterino: boolean;
  comportamento: (typeof COMPORTAMENTOS)[number] | null;
  temperatura: number | null;
  tratamentos: string | null;
  proxima_observacao: string | null;
  observacoes: string | null;
}
export type RegistoIn = Omit<Registo, "id">;

export interface Inseminacao {
  data_inseminacao: string | null;
  garanhao?: string | null;
  egua?: string | null;
  proprietario: string | null;
  palhetas_gastas: number | null;
  num_lotes: number;
  resultado: "pendente" | "gestacao_confirmada" | "falhou" | string;
  observacoes?: string | null;
  op_key?: string;
  pode_resultado?: boolean;
  etapa?: string;
}
export interface Acompanhamento {
  estadia_id: number;
  garanhao: string | null;
  data_entrada: string | null;
  data_inseminacao: string | null;
  data_1o_diagnostico: string | null;
  data_confirmacao: string | null;
  data_2a_confirmacao: string | null;
  data_parto_previsto: string | null;
  resultado: string | null;
}
export interface EstadiaAnimal {
  tipo_registo: string;
  motivo: string | null;
  estado: string | null;
  data_entrada: string | null;
  data_saida: string | null;
  dias: number | null;
}

const base = (id: number) => `/animais/${id}`;

export const useAnimal = (id: number) => useQuery({ queryKey: ["animal", id], queryFn: () => api<Animal>(base(id)) });
export const useDiario = (id: number) =>
  useQuery({ queryKey: ["animal", id, "diario"], queryFn: () => api<Registo[]>(`${base(id)}/diario`) });
export const useReprodutivo = (id: number) =>
  useQuery({
    queryKey: ["animal", id, "reprodutivo"],
    queryFn: () => api<{ total: number; gestacoes: number; taxa: number | null; inseminacoes: Inseminacao[] }>(`${base(id)}/reprodutivo`),
  });
export const useEstadiasAnimal = (id: number) =>
  useQuery({
    queryKey: ["animal", id, "estadias"],
    queryFn: () => api<{ estadias: EstadiaAnimal[]; acompanhamento: Acompanhamento | null }>(`${base(id)}/estadias`),
  });
export const useProducao = (id: number) =>
  useQuery({
    queryKey: ["animal", id, "producao"],
    queryFn: () =>
      api<{
        kpis: { palhetas: number; lotes: number; motilidade: string; internas: number; externas: number };
        lotes: Record<string, string | number | null>[];
      }>(`${base(id)}/producao`),
  });
export const useFertilidade = (id: number) =>
  useQuery({
    queryKey: ["animal", id, "fertilidade"],
    queryFn: () => api<{ total: number; gestacoes: number; taxa: number | null; inseminacoes: Inseminacao[] }>(`${base(id)}/fertilidade`),
  });
export const useAlertas = (id: number) =>
  useQuery({
    queryKey: ["animal", id, "alertas"],
    queryFn: () =>
      api<{ nivel: "erro" | "aviso" | "info" | "ok"; chave: string; params: Record<string, string | number> }[]>(`${base(id)}/alertas`),
  });
export const useColheitas = (id: number) =>
  useQuery({
    queryKey: ["animal", id, "colheitas"],
    queryFn: () => api<{ id: number; data_tarefa: string; urgencia: string | null }[]>(`${base(id)}/colheitas`),
  });

/** Escritas na ficha: refrescam a ficha e as listas que mostram tarefas. */
function useFichaMutation<V, R>(id: number, fn: (v: V) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["animal", id] });
      queryClient.invalidateQueries({ queryKey: ["trabalho"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["estadias"] });
    },
  });
}

export const useEditarAnimal = (id: number) => useFichaMutation(id, (d: AnimalIn) => api<Animal>(base(id), "PUT", d));
export const useNovoRegisto = (id: number) =>
  useFichaMutation(id, (d: RegistoIn) => api<{ id: number; tarefas_concluidas: number }>(`${base(id)}/diario`, "POST", d));
export const useEditarRegisto = (id: number) =>
  useFichaMutation(id, ({ rid, ...d }: RegistoIn & { rid: number }) => api<{ ok: boolean }>(`${base(id)}/diario/${rid}`, "PUT", d));
export const useApagarRegisto = (id: number) =>
  useFichaMutation(id, (rid: number) => api<{ ok: boolean }>(`${base(id)}/diario/${rid}`, "DELETE"));
export const useResultado = (id: number) =>
  useFichaMutation(id, (d: { op_key: string; resultado: "positivo" | "negativo" }) =>
    api<{ resultado: string }>(`${base(id)}/resultado`, "POST", d),
  );
export const useGuardarAcompanhamento = (id: number) =>
  useFichaMutation(id, (d: Omit<Acompanhamento, "estadia_id" | "data_entrada" | "resultado">) =>
    api(`${base(id)}/acompanhamento`, "PUT", d),
  );
export const useAgendarColheita = (id: number) =>
  useFichaMutation(id, (data: string) => api<{ id: number }>(`${base(id)}/colheitas`, "POST", { data }));
export const useCancelarColheita = (id: number) =>
  useFichaMutation(id, (tid: number) => api<{ ok: boolean }>(`${base(id)}/colheitas/${tid}`, "DELETE"));
