import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs, { type Dayjs } from "dayjs";
import { Alert, Button, DatePicker, Flex, Input, Modal, Segmented, Typography } from "antd";
import { Button as MButton, Input as MInput, List, Popup, Selector } from "antd-mobile";

import { api } from "../../api/client";
import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { DataCampo } from "../../components/mobile";
import { FORMATO_DATA } from "../../components/datas";

export interface EstadoConsulta {
  falta: boolean;
  terminadas: boolean;
  marcada: { id: number; data: string; observacoes: string } | null;
  outras: { tipo: string; data: string; motivo: string | null }[];
  pode_terminar: boolean;
}

export const useEstadoConsulta = (animalId: number, ativo = true) =>
  useQuery({
    queryKey: ["animal", animalId, "proxima-consulta"],
    queryFn: () => api<EstadoConsulta>(`/animais/${animalId}/proxima-consulta`),
    enabled: ativo,
  });

const PALAVRA = "TERMINAR";
const DIAS = [1, 2, 3, 4, 5, 6, 7];
const FMT = "YYYY-MM-DD";

/**
 * Próxima consulta, obrigatória depois de gravar uma consulta: sem X nem
 * "Cancelar" — só se sai marcando o dia (1 a 7 dias ou outra data) ou
 * terminando as consultas da égua (escrevendo TERMINAR).
 */
export function ProximaConsulta({ animalId, nome, aberto, onClose }: { animalId: number; nome: string; aberto: boolean; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const queryClient = useQueryClient();
  const q = useEstadoConsulta(animalId, aberto);
  const [data, setData] = useState<string | null>(null);
  const [obs, setObs] = useState("");
  const [terminar, setTerminar] = useState(false);
  const [palavra, setPalavra] = useState("");

  // Ao abrir: se já há uma consulta marcada, começa nela (muda-se em vez de criar outra).
  const marcada = q.data?.marcada;
  useEffect(() => {
    if (!aberto) return;
    setData(marcada?.data ?? null);
    setObs(marcada?.observacoes ?? "");
    setTerminar(false);
    setPalavra("");
  }, [aberto, marcada?.data, marcada?.observacoes]);

  const atualizar = () => {
    for (const k of [["animal", animalId], ["trabalho"], ["dashboard"]]) queryClient.invalidateQueries({ queryKey: k });
  };
  const marcar = useMutation({
    mutationFn: () => api(`/animais/${animalId}/proxima-consulta`, "PUT", { data, observacoes: obs }),
    onSuccess: () => {
      atualizar();
      notifySuccess(t("web.next_visit.saved", { data: dayjs(data).format("DD/MM/YYYY") }));
      onClose();
    },
    onError: notifyError,
  });
  const fim = useMutation({
    mutationFn: () => api(`/animais/${animalId}/terminar-consultas`, "POST", { confirmacao: palavra }),
    onSuccess: () => {
      atualizar();
      notifySuccess(t("web.next_visit.ended"));
      onClose();
    },
    onError: notifyError,
  });

  const amanha = dayjs().add(1, "day").startOf("day");
  const diasEscolhidos = data ? dayjs(data).startOf("day").diff(dayjs().startOf("day"), "day") : null;
  const palavraCerta = palavra.trim().toUpperCase() === PALAVRA;
  const titulo = t("web.next_visit.title", { name: nome });
  const fmt = (d: string) => dayjs(d).format("DD/MM");

  const jaMarcado = !!q.data?.outras.length && (
    <div>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {t("web.next_visit.already")}:
      </Typography.Text>{" "}
      {q.data.outras.map((o) => `${t(`web.task.${o.tipo}`)} ${fmt(o.data)}`).join(" · ")}
    </div>
  );
  const textoMarcada = marcada && t("web.next_visit.current", { data: dayjs(marcada.data).format("DD/MM/YYYY") });

  if (isMobile)
    return (
      <Popup visible={aberto} bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: "14px 16px", paddingBottom: "calc(14px + env(safe-area-inset-bottom))" }}>
        <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 10 }}>{terminar ? t("web.next_visit.end_title") : titulo}</div>
        {terminar ? (
          <>
            <div style={{ fontSize: 13, color: "#666", marginBottom: 10 }}>{t("web.next_visit.end_text")}</div>
            <MInput value={palavra} onChange={setPalavra} placeholder={PALAVRA} style={{ border: "1px solid #ddd", borderRadius: 6, padding: "6px 10px" }} />
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <MButton block onClick={() => setTerminar(false)}>
                {t("web.next_visit.end_back")}
              </MButton>
              <MButton block color="danger" disabled={!palavraCerta} loading={fim.isPending} onClick={() => fim.mutate()}>
                {t("web.next_visit.end_ok")}
              </MButton>
            </div>
          </>
        ) : (
          <>
            {jaMarcado && <div style={{ fontSize: 13, marginBottom: 8 }}>{jaMarcado}</div>}
            {textoMarcada && <div style={{ fontSize: 13, color: "var(--adm-color-primary)", marginBottom: 8 }}>{textoMarcada}</div>}
            <div style={{ fontSize: 13, color: "#999", marginBottom: 6 }}>{t("web.next_visit.in")}</div>
            <Selector
              columns={7}
              options={DIAS.map((n) => ({ label: String(n), value: n }))}
              value={diasEscolhidos !== null && DIAS.includes(diasEscolhidos) ? [diasEscolhidos] : []}
              onChange={(v) => v[0] && setData(dayjs().add(v[0], "day").format(FMT))}
              style={{ "--padding": "8px 0" } as React.CSSProperties}
            />
            <List style={{ margin: "10px -16px 0", "--border-top": "none" } as React.CSSProperties}>
              <List.Item prefix={<span style={{ width: 90, display: "inline-block" }}>{t("web.next_visit.date")}</span>}>
                <DataCampo value={data} onChange={setData} min={amanha.toDate()} placeholder={t("web.next_visit.date_required")} />
              </List.Item>
              <List.Item prefix={<span style={{ width: 90, display: "inline-block" }}>{t("web.next_visit.notes")}</span>}>
                <MInput value={obs} onChange={setObs} maxLength={300} placeholder={t("web.next_visit.notes_placeholder")} clearable />
              </List.Item>
            </List>
            <MButton block color="primary" disabled={!data} loading={marcar.isPending} onClick={() => marcar.mutate()} style={{ marginTop: 12 }}>
              {t("web.next_visit.save")}
            </MButton>
            {q.data?.pode_terminar && (
              <div style={{ textAlign: "center", marginTop: 14 }}>
                <a style={{ color: "var(--adm-color-danger)", fontSize: 13 }} onClick={() => setTerminar(true)}>
                  {t("web.next_visit.end_link")}
                </a>
              </div>
            )}
          </>
        )}
      </Popup>
    );

  return (
    <Modal
      open={aberto}
      title={terminar ? t("web.next_visit.end_title") : titulo}
      closable={false}
      mask={{ closable: false }}
      keyboard={false}
      width={480}
      footer={
        terminar ? (
          <Flex justify="end" gap={8}>
            <Button onClick={() => setTerminar(false)}>{t("web.next_visit.end_back")}</Button>
            <Button danger type="primary" disabled={!palavraCerta} loading={fim.isPending} onClick={() => fim.mutate()}>
              {t("web.next_visit.end_ok")}
            </Button>
          </Flex>
        ) : (
          <Flex justify="space-between" align="center">
            {q.data?.pode_terminar ? (
              <Button type="link" danger style={{ paddingInline: 0 }} onClick={() => setTerminar(true)}>
                {t("web.next_visit.end_link")}
              </Button>
            ) : (
              <span />
            )}
            <Button type="primary" disabled={!data} loading={marcar.isPending} onClick={() => marcar.mutate()}>
              {t("web.next_visit.save")}
            </Button>
          </Flex>
        )
      }
    >
      {terminar ? (
        <Flex vertical gap={12}>
          <Typography.Paragraph style={{ margin: 0 }}>{t("web.next_visit.end_text")}</Typography.Paragraph>
          <Input value={palavra} onChange={(e) => setPalavra(e.target.value)} placeholder={PALAVRA} autoFocus />
        </Flex>
      ) : (
        <Flex vertical gap={12}>
          {jaMarcado}
          {textoMarcada && <Alert type="info" showIcon title={textoMarcada} />}
          <div>
            <Typography.Text type="secondary">{t("web.next_visit.in")}</Typography.Text>
            <Segmented
              block
              style={{ marginTop: 4 }}
              options={DIAS.map((n) => ({ label: t("web.next_visit.days", { n }), value: n }))}
              value={diasEscolhidos !== null && DIAS.includes(diasEscolhidos) ? diasEscolhidos : (null as unknown as number)}
              onChange={(n) => setData(dayjs().add(n, "day").format(FMT))}
            />
          </div>
          <div>
            <Typography.Text type="secondary">{t("web.next_visit.date")}</Typography.Text>
            <DatePicker
              format={FORMATO_DATA}
              allowClear={false}
              style={{ width: "100%", marginTop: 4 }}
              value={data ? dayjs(data) : null}
              placeholder={t("web.next_visit.date_required")}
              disabledDate={(d: Dayjs) => d.isBefore(amanha, "day")}
              onChange={(d) => setData(d ? d.format(FMT) : null)}
            />
          </div>
          <div>
            <Typography.Text type="secondary">{t("web.next_visit.notes")}</Typography.Text>
            <Input
              style={{ marginTop: 4 }}
              value={obs}
              maxLength={300}
              onChange={(e) => setObs(e.target.value)}
              placeholder={t("web.next_visit.notes_placeholder")}
            />
          </div>
        </Flex>
      )}
    </Modal>
  );
}
