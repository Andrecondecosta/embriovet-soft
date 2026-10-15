import { useNavigate } from "react-router-dom";

import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { HistoricoOperacoes } from "./stock/transfer/HistoricoOperacoes";
import { HistoricoMobile } from "./stock/transfer/TransferenciasMobile";
import type { OpHistorico } from "./stock/transfer/api";

/** Atividade — histórico único de operações do dia (inseminações e
 *  transferências), com quem as fez, Editar e Anular. Igual a
 *  `atividade_page.py`. Editar uma transferência abre-a no separador
 *  Transferências; as inseminações editam-se no Trabalho diário. */
export function AtividadePage() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const editar = (op: OpHistorico) => navigate(`/stock-semen/transferencias?editar=${op.tipo}-${op.action_id}`);
  const titulo = t("web.activity.title");

  return isMobile ? (
    <HistoricoMobile onEditar={editar} comUtilizador titulo={titulo} />
  ) : (
    <HistoricoOperacoes onEditar={editar} comUtilizador titulo={titulo} />
  );
}
