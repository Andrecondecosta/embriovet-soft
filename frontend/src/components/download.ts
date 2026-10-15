import { ApiError } from "../api/client";

/** Descarrega um ficheiro gerado pela API, com o nome que o servidor dá
 *  (inclui nomes com acentos, enviados em `filename*=UTF-8''…`). */
export async function descarregar(caminho: string, nomePorOmissao = "ficheiro") {
  const res = await fetch(`/api${caminho}`, { credentials: "same-origin" });
  if (!res.ok) {
    let codigo = "web.error.generic";
    let params: Record<string, string | number> = {};
    try {
      const detalhe = (await res.json()).detail;
      if (typeof detalhe === "string") codigo = detalhe;
      else if (detalhe?.code) ({ code: codigo, params = {} } = detalhe);
    } catch {
      // resposta sem JSON
    }
    throw new ApiError(res.status, codigo, params);
  }
  const cd = res.headers.get("content-disposition") ?? "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(cd)?.[1];
  const nome = utf8 ? decodeURIComponent(utf8) : (/filename="([^"]+)"/.exec(cd)?.[1] ?? nomePorOmissao);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  a.click();
  URL.revokeObjectURL(url);
}
