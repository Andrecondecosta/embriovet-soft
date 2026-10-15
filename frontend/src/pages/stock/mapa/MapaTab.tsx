import { useState } from "react";
import { Alert, Button, Empty, Flex, Form, Input, Modal, Popover, Segmented, Select, Space, Spin, Typography } from "antd";
import { AppstoreOutlined, DownloadOutlined, PlusOutlined } from "@ant-design/icons";

import { useT } from "../../../i18n/I18n";
import { useElementWidth, useIsMobile } from "../../../components/responsive";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../../components/errors";
import { MapaCanvas } from "./MapaCanvas";
import { ContentorModal } from "./ContentorModal";
import { ListaContentores } from "./ListaContentores";
import { useCriarContentor, useGravarPosicao, useMapa, useOrganizar, type Contentor } from "./api";

/** Abaixo desta escala as caixas do mapa (70 × escala px) ficam pequenas
 *  demais para ler — passa-se para a lista. */
const ESCALA_MIN_LEGIVEL = 0.75;

export function MapaTab() {
  // O elemento medido existe desde o primeiro desenho (também durante o
  // carregamento), senão a medição da largura nunca arranca.
  const { ref, width } = useElementWidth<HTMLDivElement>();
  return (
    <div ref={ref}>
      <MapaConteudo areaW={width} />
    </div>
  );
}

function MapaConteudo({ areaW }: { areaW: number }) {
  const t = useT();
  const errorMessage = useErrorMessage();
  const notifyError = useNotifyError();
  const isMobile = useIsMobile();
  const { data, isPending, isError, error } = useMapa();
  const gravar = useGravarPosicao();
  const [aberto, setAberto] = useState<Contentor | null>(null);
  const [novo, setNovo] = useState(false);
  // Muda depois de "Organizar", para o mapa esquecer posições locais antigas.
  const [versao, setVersao] = useState(0);
  // Lista ou mapa: o mapa só aparece quando cabe inteiro no espaço
  // disponível com as caixas legíveis; senão (telemóvel, tablet, monitor
  // pequeno) passa para a lista. Nesse caso há um botão para forçar o mapa.
  const [escolha, setEscolha] = useState<"mapa" | "lista">(() => {
    try {
      return localStorage.getItem("mapa_vista") === "mapa" ? "mapa" : "lista";
    } catch {
      return "lista";
    }
  });
  const mudarVista = (v: "mapa" | "lista") => {
    setEscolha(v);
    try {
      localStorage.setItem("mapa_vista", v);
    } catch {
      // sem armazenamento: fica só nesta visita
    }
  };

  if (isError) return <Alert type="error" showIcon title={errorMessage(error)} />;
  if (isPending) return <Spin style={{ display: "block", margin: 32 }} />;

  const contentores = data.contentores;
  const total = contentores.reduce((s, c) => s + c.palhetas, 0);
  const lado = data.virtual.lado;
  const extW = Math.max(lado, ...contentores.map((c) => c.x + lado));
  const extH = Math.max(lado, ...contentores.map((c) => c.y + lado));
  const escalaPossivel = Math.min(areaW / (extW + 12), (isMobile ? 420 : 520) / (extH + 12));
  const mapaCabe = escalaPossivel >= ESCALA_MIN_LEGIVEL;
  const vista = mapaCabe ? "mapa" : escolha;

  return (
    <>
      {contentores.length === 0 ? (
        <Empty description={<><b>{t("web.map.empty.title")}</b><br />{t("web.map.empty.text")}</>}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setNovo(true)}>
            {t("web.map.empty.add")}
          </Button>
        </Empty>
      ) : (
        <Space orientation="vertical" size={10} style={{ width: "100%" }}>
          <Flex justify="space-between" align="center" wrap gap={8}>
            <Space wrap>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setNovo(true)}>
                {t("map.add")}
              </Button>
              <Organizar onFeito={() => setVersao((v) => v + 1)} />
              <Exportar contentores={contentores} />
            </Space>
            <Typography.Text type="secondary">
              <b>{contentores.length}</b> {t("web.map.containers")} · <b>{total}</b> {t("label.straws")}
            </Typography.Text>
          </Flex>

          {areaW > 0 && !mapaCabe && (
            <Segmented
              block={isMobile}
              value={vista}
              onChange={(v) => mudarVista(v as "mapa" | "lista")}
              options={[
                { value: "lista", label: t("web.map.view_list") },
                { value: "mapa", label: t("web.map.view_map") },
              ]}
            />
          )}

          {/* Só se decide depois de medir a largura (evita mostrar uma e
              trocar logo para a outra). */}
          {areaW === 0 ? null : vista === "lista" ? (
            <>
              <ListaContentores contentores={contentores} onAbrir={setAberto} />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {t("web.map.hint_list")}
              </Typography.Text>
            </>
          ) : (
            <>
              <MapaCanvas
                key={versao}
                contentores={contentores}
                virtual={data.virtual}
                onAbrir={setAberto}
                onMover={async (c, x, y) => {
                  try {
                    await gravar.mutateAsync({ id: c.id, x, y });
                    notifySuccess(t("web.map.position_saved"));
                  } catch (err) {
                    notifyError(err);
                  }
                }}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {t("web.map.hint")}
              </Typography.Text>
            </>
          )}
        </Space>
      )}

      <NovoContentorModal opened={novo} onClose={() => setNovo(false)} />
      <ContentorModal contentor={aberto} todos={contentores} onClose={() => setAberto(null)} />
    </>
  );
}

function Organizar({ onFeito }: { onFeito: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const organizar = useOrganizar();
  const [aberto, setAberto] = useState(false);
  return (
    <Popover
      open={aberto}
      onOpenChange={setAberto}
      trigger="click"
      placement="bottomLeft"
      title={t("map.organize")}
      content={
        <Space orientation="vertical" style={{ width: 280 }}>
          <Typography.Text>{t("map.organize_help")}</Typography.Text>
          <Button
            type="primary"
            block
            loading={organizar.isPending}
            onClick={async () => {
              try {
                const r = await organizar.mutateAsync(undefined);
                notifySuccess(t("map.organized", { count: r.count }));
                onFeito();
                setAberto(false);
              } catch (err) {
                notifyError(err);
              }
            }}
          >
            {t("map.organize_confirm")}
          </Button>
        </Space>
      }
    >
      <Button icon={<AppstoreOutlined />}>{t("map.organize")}</Button>
    </Popover>
  );
}

function Exportar({ contentores }: { contentores: Contentor[] }) {
  const t = useT();
  const notifyError = useNotifyError();
  const [ids, setIds] = useState<number[]>([]);
  const [aGerar, setAGerar] = useState<string | null>(null);

  const baixar = async (formato: "pdf" | "xlsx") => {
    setAGerar(formato);
    try {
      const p = new URLSearchParams({ formato });
      ids.forEach((i) => p.append("ids", String(i)));
      const res = await fetch(`/api/mapa/exportar?${p}`, { credentials: "same-origin" });
      if (!res.ok) throw new Error(String(res.status));
      const nome = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? `inventario.${formato}`;
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = nome;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      notifyError(err);
    } finally {
      setAGerar(null);
    }
  };

  return (
    <Popover
      trigger="click"
      placement="bottomLeft"
      title={t("map.export")}
      content={
        <Space orientation="vertical" style={{ width: 300 }}>
          <Typography.Text>{t("map.export_help")}</Typography.Text>
          <Typography.Text type="secondary">{t("map.export_containers")}</Typography.Text>
          <Select
            mode="multiple"
            allowClear
            style={{ width: "100%" }}
            placeholder={t("map.export_all")}
            value={ids}
            onChange={setIds}
            optionFilterProp="label"
            options={contentores.map((c) => ({ value: c.id, label: c.codigo }))}
          />
          <Flex gap={8}>
            <Button block onClick={() => baixar("pdf")} loading={aGerar === "pdf"}>
              PDF
            </Button>
            <Button block onClick={() => baixar("xlsx")} loading={aGerar === "xlsx"}>
              Excel
            </Button>
          </Flex>
        </Space>
      }
    >
      <Button icon={<DownloadOutlined />}>{t("map.export")}</Button>
    </Popover>
  );
}

function NovoContentorModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const criar = useCriarContentor();
  const [form] = Form.useForm<{ codigo: string; descricao: string }>();

  const guardar = async (v: { codigo: string; descricao?: string }) => {
    try {
      const c = await criar.mutateAsync({ codigo: v.codigo, descricao: v.descricao ?? "" });
      notifySuccess(t("web.map.created", { code: c.codigo }));
      onClose();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Modal
      open={opened}
      onCancel={onClose}
      title={t("map.add_container_title")}
      okText={t("btn.create_container")}
      cancelText={t("web.common.cancel")}
      onOk={() => form.submit()}
      confirmLoading={criar.isPending}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={guardar} preserve={false}>
        <Form.Item
          name="codigo"
          label={t("map.container_code_required").replace(" *", "")}
          extra={t("map.container_code_help")}
          rules={[{ required: true, whitespace: true, message: t("map.container_code_required_error") }]}
        >
          <Input placeholder={t("map.container_code_placeholder")} autoFocus />
        </Form.Item>
        <Form.Item name="descricao" label={t("map.container_description_optional")}>
          <Input placeholder={t("map.container_description_placeholder")} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
