// Pequeno wrapper de fetch para a API. Os erros da API trazem uma chave de
// tradução (`detail` = "login.invalid") ou { code, params } — o ecrã traduz.

export class ApiError extends Error {
  status: number;
  code: string;
  params: Record<string, string | number>;

  constructor(status: number, code: string, params: Record<string, string | number> = {}) {
    super(code);
    this.status = status;
    this.code = code;
    this.params = params;
  }
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

let onUnauthorized: (() => void) | null = null;

/** Chamado quando a API responde 401 (sessão expirada ou terminada). */
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export async function api<T>(path: string, method: Method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.ok) return (await res.json()) as T;

  let detail: unknown = null;
  try {
    detail = (await res.json()).detail;
  } catch {
    // resposta sem JSON
  }

  if (res.status === 401 && detail === "not_authenticated") onUnauthorized?.();

  if (typeof detail === "string") throw new ApiError(res.status, detail);
  if (detail && typeof detail === "object" && "code" in detail) {
    const d = detail as { code: string; params?: Record<string, string | number> };
    throw new ApiError(res.status, d.code, d.params ?? {});
  }
  throw new ApiError(res.status, "web.error.generic");
}

export const qs = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") s.set(k, String(v));
  return s.toString();
};
