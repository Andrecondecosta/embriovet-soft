import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";

export type TipoOp = "transfer_internal" | "transfer_external" | "insemination";
export type Motivo = "Venda" | "Doação" | "Exportação" | "Outro";
export const MOTIVOS: { value: Motivo; label: string }[] = [
  { value: "Venda", label: "stock.type.sale" },
  { value: "Doação", label: "stock.type.donation" },
  { value: "Exportação", label: "stock.type.export" },
  { value: "Outro", label: "stock.type.other" },
];

export interface OperacaoIn {
  tipo: "interna" | "externa";
  linhas: { stock_id: number; quantidade: number }[];
  destino_id?: number | null;
  nova_localizacao?: { contentor_id: number; canister: number; andar: number } | null;
  destinatario?: string;
  motivo?: Motivo;
  observacoes?: string;
}

export interface LinhaOperacao {
  stock_id: number;
  garanhao: string;
  dono_id: number | null;
  proprietario_nome: string | null;
  existencia_atual: number;
  quantidade: number;
  origem_externa: string | null;
  data_embriovet: string | null;
  contentor_codigo: string | null;
  local_armazenagem: string | null;
  canister: number | null;
  andar: number | null;
  qualidade: string | null;
  concentracao: number | null;
  motilidade: number | null;
}

export interface Operacao {
  tipo: "transfer_internal" | "transfer_external";
  action_id: number;
  operation_id: string | null;
  linhas: LinhaOperacao[];
  destino_id: number | null;
  destinatario: string | null;
  motivo: Motivo | null;
  observacoes: string | null;
}

export interface OpHistorico {
  ts: string | null;
  usuario: string | null;
  acao: string | null;
  detalhe: string | null;
  tipo: TipoOp;
  action_id: number;
  operation_id: string | null;
  num_lotes: number;
  quantidade: number;
}

export const useOperacao = (ref: { tipo: string; id: number } | null) =>
  useQuery({
    queryKey: ["transferencias", "operacao", ref],
    enabled: !!ref,
    queryFn: () => api<Operacao>(`/transferencias/operacao/${ref!.tipo}/${ref!.id}`),
    staleTime: 0,
  });

export const useHistorico = (dia: string) =>
  useQuery({
    queryKey: ["transferencias", "historico", dia],
    queryFn: () => api<OpHistorico[]>(`/transferencias/historico?dia=${dia}`),
  });

function useTransfMutation<V>(fn: (v: V) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      // Mexe no stock e nos donos (um dono sem stock passa a inativo).
      queryClient.invalidateQueries({ queryKey: ["transferencias"] });
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["opcoes"] });
      queryClient.invalidateQueries({ queryKey: ["owners"] });
    },
  });
}

export const useCriarOperacao = () =>
  useTransfMutation((d: OperacaoIn) => api<{ operation_id: string }>("/transferencias", "POST", d));

export const useEditarOperacao = () =>
  useTransfMutation(({ tipoOp, id, ...d }: OperacaoIn & { tipoOp: string; id: number }) =>
    api<{ operation_id: string }>(`/transferencias/operacao/${tipoOp}/${id}`, "PUT", d),
  );

export const useAnular = () =>
  useTransfMutation((d: { tipo: TipoOp; action_id: number; operation_id: string | null }) =>
    api<{ ok: boolean }>("/transferencias/anular", "POST", d),
  );
