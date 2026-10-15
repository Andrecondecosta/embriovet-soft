import { useNavigate } from "react-router-dom";

import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { HistoricoOperacoes } from "./stock/transfer/HistoricoOperacoes";
import { HistoricoMobile } from "./stock/transfer/TransferenciasMobile";
import type { OpHistorico } from "./stock/transfer/api";

/** Atividade — histórico único de operações do dia (inseminações e
 *  transferências), com quem as fez, Editar e Anular. Igual a
 *  `atividade_page.py`. Editar abre a transferência no separador
 *  Transferências ou a inseminação no seu ecrã de registo. */
export function AtividadePage() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const editar = (op: OpHistorico) =>
    navigate(
      op.tipo === "insemination"
        ? `/trabalho-diario/inseminacao?editar=${op.operation_id ?? `id-${op.action_id}`}`
        : `/stock-semen/transferencias?editar=${op.tipo}-${op.action_id}`,
    );
  const titulo = t("web.activity.title");

  return isMobile ? (
    <HistoricoMobile onEditar={editar} comUtilizador editarInseminacoes titulo={titulo} />
  ) : (
    <HistoricoOperacoes onEditar={editar} comUtilizador editarInseminacoes titulo={titulo} />
  );
}
