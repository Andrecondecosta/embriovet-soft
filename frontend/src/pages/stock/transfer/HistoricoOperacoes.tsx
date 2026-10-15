import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import dayjs, { type Dayjs } from "dayjs";
import { Alert, Button, Card, DatePicker, Flex, Modal, Space, Typography } from "antd";
import { LeftOutlined, RightOutlined } from "@ant-design/icons";

import { useT } from "../../../i18n/I18n";
import { useIsMobile } from "../../../components/responsive";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../../components/errors";
import { Lista } from "../../../components/Lista";
import { useAnular, useHistorico, type OpHistorico } from "./api";

const FMT = "YYYY-MM-DD";
export const hora = (iso: string | null) => (iso ? dayjs(iso).format("HH:mm") : "—");

/** Histórico de operações do dia (transferências e inseminações), com
 *  Editar (só transferências — as inseminações editam-se na sua página)
 *  e Anular. Igual a `_render_historico_operacoes` da app atual. */
/** Dia do histórico (no endereço, `?dia=AAAA-MM-DD`; hoje por omissão). */
export function useDiaHistorico() {
  const [params, setParams] = useSearchParams();
  const pedido = params.get("dia") ?? "";
  const dia: Dayjs = /^\d{4}-\d{2}-\d{2}$/.test(pedido) && dayjs(pedido).isValid() ? dayjs(pedido) : dayjs();
  const ehHoje = dia.isSame(dayjs(), "day");
  const historico = useHistorico(dia.format(FMT));
  const irPara = (d: Dayjs) =>
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        if (d.isSame(dayjs(), "day")) r.delete("dia");
        else r.set("dia", d.format(FMT));
        return r;
      },
      { replace: true },
    );
  return { dia, ehHoje, irPara, historico };
}

export function HistoricoOperacoes({
  onEditar,
  comUtilizador = false,
  titulo,
}: {
  onEditar: (op: OpHistorico) => void;
  /** Mostra quem fez cada operação (página Atividade). */
  comUtilizador?: boolean;
  titulo?: string;
}) {
  const t = useT();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const { dia, ehHoje, irPara, historico } = useDiaHistorico();
  const { data, isPending, isError, error } = historico;
  const [anular, setAnular] = useState<OpHistorico | null>(null);

  return (
    <Card size="small" title={titulo ?? t("web.transfer.history")}>
      <Flex gap={6} align="center" style={{ marginBottom: 12 }}>
        <Button icon={<LeftOutlined />} onClick={() => irPara(dia.subtract(1, "day"))} aria-label="◀" />
        <DatePicker
          value={dia}
          onChange={(d) => d && irPara(d)}
          allowClear={false}
          format="DD/MM/YYYY"
          style={{ flex: isMobile ? 1 : undefined }}
        />
        <Button icon={<RightOutlined />} onClick={() => irPara(dia.add(1, "day"))} aria-label="▶" />
        {!ehHoje && (
          <Button type="link" onClick={() => irPara(dayjs())}>
            {t("web.transfer.today")}
          </Button>
        )}
      </Flex>

      {isError ? (
        <Alert type="error" showIcon title={errorMessage(error)} />
      ) : (
        <Lista
          itens={data ?? []}
          chave={(op) => `${op.tipo}-${op.operation_id ?? op.action_id}`}
          carregando={isPending}
          vazio={t("web.transfer.history.empty")}
          semContorno
          alturaMax={460}
          render={(op) => ({
            corpo: (
              <Typography.Text>
                <b>{hora(op.ts)}</b> · {comUtilizador && <Typography.Text type="secondary">{op.usuario ?? "—"} · </Typography.Text>}
                <Typography.Text type="secondary">{op.acao}</Typography.Text> — {op.detalhe}
              </Typography.Text>
            ),
            acoes: (
              <>
                {op.tipo !== "insemination" && (
                  <Button size="small" type="link" onClick={() => onEditar(op)}>
                    {t("btn.edit")}
                  </Button>
                )}
                <Button size="small" onClick={() => setAnular(op)}>
                  {t("web.transfer.undo")}
                </Button>
              </>
            ),
          })}
        />
      )}

      <AnularModal op={anular} onClose={() => setAnular(null)} />
    </Card>
  );
}

export function AnularModal({ op, onClose }: { op: OpHistorico | null; onClose: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const anular = useAnular();

  const confirmar = async () => {
    if (!op) return;
    try {
      await anular.mutateAsync({ tipo: op.tipo, action_id: op.action_id, operation_id: op.operation_id });
      notifySuccess(t("web.transfer.undo.done"));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Modal
      open={op !== null}
      onCancel={onClose}
      title={t("web.transfer.undo.title")}
      okText={t("web.transfer.undo.confirm_btn")}
      cancelText={t("web.common.cancel")}
      okButtonProps={{ danger: true }}
      confirmLoading={anular.isPending}
      onOk={confirmar}
    >
      {op && (
        <Space orientation="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Text>
            {op.acao} — {op.detalhe}
          </Typography.Text>
          <Alert
            type="error"
            showIcon
            title={
              <>
                {t("web.transfer.undo.confirm", { qty: op.quantidade })}{" "}
                {op.num_lotes > 1 && t("web.transfer.undo.multi", { n: op.num_lotes })} <b>{t("web.transfer.undo.irreversible")}</b>
              </>
            }
          />
        </Space>
      )}
    </Modal>
  );
}
