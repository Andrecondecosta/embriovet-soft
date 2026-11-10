export type Nivel = "Administrador" | "Gestor" | "Visualizador";

export interface User {
  id: number;
  username: string;
  nome: string;
  nivel: Nivel;
  must_change_password: boolean;
  /** Faturação, dada pessoa a pessoa (não pelo nível): sem acesso, só ver ou editar. */
  acesso_faturacao?: AcessoFaturacao;
}

export interface PublicSettings {
  company_name: string;
  logo_base64: string | null;
  primary_color: string;
  language: string;
}

export interface Owner {
  id: number;
  nome: string;
  ativo: boolean | null;
  email: string | null;
  telemovel: string | null;
  nome_completo: string | null;
  nif: string | null;
  morada: string | null;
  codigo_postal: string | null;
  cidade: string | null;
}

export type OwnerInput = Omit<Owner, "id" | "ativo">;

export interface Page<T> {
  items: T[];
  total: number;
  pagina: number;
  por_pagina: number;
}

export type AcessoFaturacao = "nenhum" | "ver" | "editar";
/** Vê o separador Faturação (só ver ou editar). */
export const veFaturacao = (u: { acesso_faturacao?: AcessoFaturacao }) => u.acesso_faturacao === "ver" || u.acesso_faturacao === "editar";
