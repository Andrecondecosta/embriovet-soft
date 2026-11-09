import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Flex, Form, Input, Modal, Table, Tag, Typography } from "antd";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  DotLoading,
  ErrorBlock,
  Form as MForm,
  Input as MInput,
  List,
  SearchBar,
  Tag as MTag,
} from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../components/errors";
import { useIsMobile } from "../../components/responsive";
import { FolhaEcraInteiro, irParaErro } from "../../components/mobile";
import { useCriarGaranhao, useGaranhoesStock, type GaranhaoStock } from "./api";

/** "Novo garanhão": cria só o animal — sem lote nem entrada na clínica. */
function NovoGaranhao({ aberto, onClose }: { aberto: boolean; onClose: () => void }) {
  const t = useT();
  const isMobile = useIsMobile();
  const criar = useCriarGaranhao();
  const notifyError = useNotifyError();
  const [form] = Form.useForm<{ nome: string }>();
  const [mform] = MForm.useForm<{ nome: string }>();
  const guardar = ({ nome }: { nome: string }) =>
    criar.mutate(nome, {
      onSuccess: (g) => {
        notifySuccess(t("web.stock.new_stallion.created", { name: g.garanhao }));
        onClose();
      },
      onError: notifyError,
    });
  const regra = [{ required: true, whitespace: true, message: t("error.stallion_required") }];

  if (isMobile)
    return (
      <FolhaEcraInteiro
        visible={aberto}
        titulo={t("web.stock.new_stallion")}
        onCancel={onClose}
        onOk={() => mform.submit()}
        okText={t("btn.add")}
        loading={criar.isPending}
      >
        <MForm form={mform} onFinish={guardar} onFinishFailed={irParaErro} footer={null}>
          <MForm.Item name="nome" label={t("label.garanhao")} description={t("web.stock.new_stallion.help")} rules={regra}>
            <MInput clearable />
          </MForm.Item>
        </MForm>
      </FolhaEcraInteiro>
    );

  return (
    <Modal
      open={aberto}
      title={t("web.stock.new_stallion")}
      okText={t("btn.add")}
      cancelText={t("btn.cancel")}
      onOk={() => form.submit()}
      onCancel={onClose}
      confirmLoading={criar.isPending}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={guardar} preserve={false}>
        <Form.Item name="nome" label={t("label.garanhao")} extra={t("web.stock.new_stallion.help")} rules={regra}>
          <Input autoFocus />
        </Form.Item>
      </Form>
    </Modal>
  );
}

/** Separador Garanhões: garanhões e o stock de cada um. A ficha do
 *  animal ainda não foi migrada — por isso o clique abre os lotes. */
export function GaranhoesTab() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  // Também os que já estão a zero (é deles que se tem de encomendar).
  const { data, isPending, isError, error } = useGaranhoesStock(true);
  const [pesquisa, setPesquisa] = useState("");
  const [novo, setNovo] = useState(false);

  const lista = useMemo(() => {
    const q = pesquisa.trim().toLowerCase();
    // Os com menos palhetas primeiro; os ainda sem lotes no fim.
    return (data ?? [])
      .filter((g) => !q || g.garanhao.toLowerCase().includes(q))
      .sort((a, b) => Number(!a.lotes) - Number(!b.lotes) || a.palhetas - b.palhetas);
  }, [data, pesquisa]);

  // Sem lotes ainda: vai direto a "Adicionar lote" com o garanhão escolhido.
  const abrir = (g: GaranhaoStock) =>
    navigate(`/stock-semen/${g.lotes ? "lotes" : "novo"}?garanhao=${encodeURIComponent(g.garanhao)}`);
  const janela = <NovoGaranhao aberto={novo} onClose={() => setNovo(false)} />;
  const vazio = data && !data.length ? t("web.stock.garanhoes.empty") : t("web.common.no_results");

  if (isError) return <Alert type="error" title={errorMessage(error)} showIcon />;

  if (isMobile)
    // Telemóvel: pesquisa e lista de app (Ant Design Mobile).
    return (
      <>
        <div style={{ padding: 8, background: "#fff" }}>
          <SearchBar placeholder={t("web.stock.garanhoes.search")} value={pesquisa} onChange={setPesquisa} />
          <MButton block color="primary" fill="outline" style={{ marginTop: 8 }} onClick={() => setNovo(true)}>
            {t("web.stock.new_stallion")}
          </MButton>
        </div>
        <List header={t("web.stock.garanhoes.hint")}>
          {isPending ? (
            <List.Item>
              <DotLoading />
            </List.Item>
          ) : !lista.length ? (
            <ErrorBlock status="empty" title={vazio} description="" />
          ) : (
            lista.map((g) => (
              <List.Item
                key={`${g.animal_id}-${g.garanhao}`}
                arrow
                onClick={() => abrir(g)}
                description={
                  g.lotes
                    ? `${t("web.stock.n_lots", { count: g.lotes })} · ${t("web.stock.n_owners", { count: g.donos })}`
                    : t("web.stock.no_lots")
                }
                extra={`${g.palhetas} ${t("label.straws")}`}
              >
                {g.garanhao}
                {g.pouco && (
                  <MTag color="danger" fill="outline" style={{ marginLeft: 6 }}>
                    {t("web.stock.low")}
                  </MTag>
                )}
              </List.Item>
            ))
          )}
        </List>
        {janela}
      </>
    );

  return (
    <>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
        {t("web.stock.garanhoes.hint")}
      </Typography.Paragraph>
      <Flex justify="space-between" gap={8} wrap style={{ marginBottom: 12 }}>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder={t("web.stock.garanhoes.search")}
          value={pesquisa}
          onChange={(e) => setPesquisa(e.target.value)}
          style={{ width: 320 }}
        />
        <Button icon={<PlusOutlined />} onClick={() => setNovo(true)}>
          {t("web.stock.new_stallion")}
        </Button>
      </Flex>
      <Table<GaranhaoStock>
        size="small"
        bordered
        loading={isPending}
        rowKey={(g) => `${g.animal_id}-${g.garanhao}`}
        dataSource={lista}
        locale={{ emptyText: vazio }}
        pagination={{ pageSize: 50, hideOnSinglePage: true, size: "small" }}
        onRow={(g) => ({
          onClick: () => abrir(g),
          style: { cursor: "pointer" },
        })}
        columns={[
          {
            title: t("label.garanhao"),
            dataIndex: "garanhao",
            render: (v, g) => (
              <>
                <Typography.Text strong>{v}</Typography.Text>
                {g.pouco && (
                  <Tag color="red" style={{ marginLeft: 8 }}>
                    {t("web.stock.low")}
                  </Tag>
                )}
                {!g.lotes && <Tag style={{ marginLeft: 8 }}>{t("web.stock.no_lots")}</Tag>}
              </>
            ),
            sorter: (a, b) => a.garanhao.localeCompare(b.garanhao),
          },
          {
            title: t("web.stock.kpi.palhetas"),
            dataIndex: "palhetas",
            align: "right",
            defaultSortOrder: "ascend",
            sorter: (a, b) => a.palhetas - b.palhetas,
          },
          {
            title: t("web.stock.kpi.lotes"),
            dataIndex: "lotes",
            align: "right",
            sorter: (a, b) => a.lotes - b.lotes,
          },
          {
            title: t("web.stock.col.donos"),
            dataIndex: "donos",
            align: "right",
            sorter: (a, b) => a.donos - b.donos,
          },
        ]}
      />
      {janela}
    </>
  );
}
