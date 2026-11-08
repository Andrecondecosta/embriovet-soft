import dayjs from "dayjs";
import { Tag } from "antd";

import { useT } from "../i18n/I18n";
import { dataCurta } from "./csv";

/** Estado da última inseminação de uma égua (o que a receção diz ao dono). */
export interface Repro {
  data_inseminacao: string | null;
  resultado: string;
  ultimo_dg?: { etapa: string; resultado: string; data: string } | null;
}

/** "Gestante · D+28 ✓ 12/05", "Inseminada há 9 d · DG 22/11", "Vazia · D+14 12/05". */
export function useEstadoReprodutivo() {
  const t = useT();
  return (r: Repro | null | undefined): { texto: string; cor: string } | null => {
    if (!r || !r.data_inseminacao) return null;
    const dg = r.ultimo_dg;
    const dgTexto = dg ? `${dg.etapa} ${t(`web.animal.dg_result.${dg.resultado}`)} ${dataCurta(dg.data)}` : null;
    if (r.resultado === "gestacao_confirmada")
      return { texto: [t("web.repro.pregnant"), dgTexto].filter(Boolean).join(" · "), cor: "green" };
    if (r.resultado === "falhou") return { texto: [t("web.repro.empty"), dgTexto].filter(Boolean).join(" · "), cor: "default" };
    const dias = dayjs().startOf("day").diff(dayjs(r.data_inseminacao), "day");
    const proximo = dgTexto ?? t("web.repro.dg_on", { data: dataCurta(dayjs(r.data_inseminacao).add(14, "day").format("YYYY-MM-DD")) });
    return { texto: `${t("web.repro.inseminated", { n: dias })} · ${proximo}`, cor: "blue" };
  };
}

export function TagReprodutivo({ r }: { r: Repro | null | undefined }) {
  const estado = useEstadoReprodutivo()(r);
  return estado ? <Tag color={estado.cor}>{estado.texto}</Tag> : null;
}
