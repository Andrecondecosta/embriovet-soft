import { useMemo, useState } from "react";
import { Alert, Button, Collapse, Flex, Form, Input, Modal, Segmented, Select, Table, Tag, Typography } from "antd";
import { KeyOutlined, PlusOutlined } from "@ant-design/icons";
import {
  Button as MButton,
  Dialog,
  DotLoading,
  ErrorBlock,
  FloatingBubble,
  Form as MForm,
  Input as MInput,
  List,
  Popup,
  Selector,
  Tabs,
  Tag as MTag,
} from "antd-mobile";
import { AddOutline } from "antd-mobile-icons";

import { useT } from "../../i18n/I18n";
import { useUser } from "../../components/User";
import { useIsMobile } from "../../components/responsive";
import { dataHora } from "../../components/csv";
import { notifySuccess, useErrorMessage, useNotifyError } from "../../components/errors";
import { Cabecalho, FolhaEcraInteiro, irParaErro } from "../../components/mobile";
import {
  NIVEIS,
  useAtivarUtilizador,
  useCriarUtilizador,
  useMudarPassword,
  useUtilizadores,
  type Utilizador,
  type UtilizadorIn,
} from "./api";

type Estado = "todos" | "ativos" | "inativos";
type NovoForm = UtilizadorIn & { confirmar: string };

const COR_NIVEL: Record<string, string> = { Administrador: "red", Gestor: "gold", Visualizador: "green" };

/** Lista filtrada + ações — comum ao computador e ao telemóvel. */
function useUtilizadoresTab() {
  const t = useT();
  const eu = useUser();
  const notifyError = useNotifyError();
  const lista = useUtilizadores();
  const criar = useCriarUtilizador();
  const ativar = useAtivarUtilizador();
  const mudarPw = useMudarPassword();
  const [nivel, setNivel] = useState<string | null>(null);
  const [estado, setEstado] = useState<Estado>("todos");

  const filtrados = useMemo(
    () =>
      (lista.data ?? []).filter((u) => (!nivel || u.nivel === nivel) && (estado === "todos" || (estado === "ativos" ? u.ativo : !u.ativo))),
    [lista.data, nivel, estado],
  );
  const nomeNivel = (n: string) => t(NIVEIS.find((x) => x.value === n)?.label ?? n);

  const criarUtilizador = async (d: NovoForm) => {
    try {
      const u = await criar.mutateAsync({ username: d.username, nome_completo: d.nome_completo, nivel: d.nivel, password: d.password });
      notifySuccess(t("web.users.created", { username: u.username }));
      return true;
    } catch (err) {
      notifyError(err);
      return false;
    }
  };
  const alternar = async (u: Utilizador) => {
    try {
      const r = await ativar.mutateAsync({ id: u.id, ativar: !u.ativo });
      notifySuccess(r.ativo ? t("web.users.activated") : t("web.users.deactivated"));
      return r;
    } catch (err) {
      notifyError(err);
      return null;
    }
  };
  const mudarPassword = async (u: Utilizador, password: string) => {
    try {
      await mudarPw.mutateAsync({ id: u.id, password });
      notifySuccess(t("web.users.password_changed", { name: u.nome_completo }));
      return true;
    } catch (err) {
      notifyError(err);
      return false;
    }
  };

  return {
    eu,
    lista,
    filtrados,
    nivel,
    setNivel,
    estado,
    setEstado,
    nomeNivel,
    criarUtilizador,
    aCriar: criar.isPending,
    alternar,
    mudarPassword,
    aMudarPw: mudarPw.isPending,
  };
}

/** Regras dos campos (as mesmas da app atual), para os dois formulários. */
function useRegras() {
  const t = useT();
  return {
    username: [
      { required: true, whitespace: true, message: t("users.fill_required") },
      { pattern: /^\S+$/, message: t("users.username_no_spaces") },
    ],
    nome: [{ required: true, whitespace: true, message: t("users.fill_required") }],
    password: [
      { required: true, message: t("users.password_required") },
      { min: 6, message: t("users.password_min_error") },
    ],
    confirmar: [
      { required: true, message: t("users.password_required") },
      ({ getFieldValue }: { getFieldValue: (n: string) => unknown }) => ({
        validator: (_: unknown, v: string) =>
          !v || v === getFieldValue("password") ? Promise.resolve() : Promise.reject(new Error(t("web.users.password_mismatch"))),
      }),
    ],
  };
}

function Niveis() {
  const t = useT();
  return (
    <>
      {NIVEIS.map((n) => (
        <div key={n.value} style={{ marginBottom: 6 }}>
          <b>{t(n.label)}</b> — {t(n.value === "Administrador" ? "web.users.level_desc.admin" : "web.users.level_desc.other")}
        </div>
      ))}
    </>
  );
}

export function UtilizadoresTab() {
  return useIsMobile() ? <UtilizadoresMobile /> : <UtilizadoresDesktop />;
}

function UtilizadoresDesktop() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const x = useUtilizadoresTab();
  const regras = useRegras();
  const [novo, setNovo] = useState(false);
  const [pw, setPw] = useState<Utilizador | null>(null);
  const [formNovo] = Form.useForm<NovoForm>();
  const [formPw] = Form.useForm<{ password: string; confirmar: string }>();

  if (x.lista.isError) return <Alert type="error" showIcon title={errorMessage(x.lista.error)} />;

  return (
    <>
      <Flex gap={8} wrap align="center" justify="space-between" style={{ marginBottom: 12 }}>
        <Flex gap={8} wrap>
          <Select
            allowClear
            placeholder={t("web.users.all_levels")}
            value={x.nivel}
            onChange={(v) => x.setNivel(v ?? null)}
            style={{ width: 180 }}
            options={NIVEIS.map((n) => ({ value: n.value, label: t(n.label) }))}
          />
          <Segmented
            value={x.estado}
            onChange={(v) => x.setEstado(v as Estado)}
            options={[
              { value: "todos", label: t("owners.filter.all") },
              { value: "ativos", label: t("owners.filter.active") },
              { value: "inativos", label: t("owners.filter.inactive") },
            ]}
          />
        </Flex>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setNovo(true)}>
          {t("web.users.new")}
        </Button>
      </Flex>

      <Table<Utilizador>
        size="small"
        bordered
        rowKey="id"
        loading={x.lista.isPending}
        dataSource={x.filtrados}
        pagination={false}
        title={() => <Typography.Text type="secondary">{t("web.users.count", { count: x.filtrados.length })}</Typography.Text>}
        columns={[
          {
            title: t("web.users.full_name"),
            dataIndex: "nome_completo",
            render: (v, u) => (
              <>
                <Typography.Text strong>{v}</Typography.Text>
                {u.id === x.eu.id && <Typography.Text type="secondary"> ({t("web.users.you")})</Typography.Text>}
                <div>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    @{u.username}
                  </Typography.Text>
                </div>
              </>
            ),
          },
          { title: t("web.users.level"), dataIndex: "nivel", width: 150, render: (v) => <Tag color={COR_NIVEL[v]}>{x.nomeNivel(v)}</Tag> },
          {
            title: t("web.common.status"),
            dataIndex: "ativo",
            width: 100,
            render: (v) => <Tag color={v ? "success" : "default"}>{v ? t("web.common.active") : t("web.common.inactive")}</Tag>,
          },
          { title: t("label.last_login"), dataIndex: "last_login", width: 150, render: (v) => (v ? dataHora(v) : t("web.users.never")) },
          { title: t("label.created_at"), dataIndex: "created_at", width: 150, responsive: ["lg"], render: (v) => (v ? dataHora(v) : "—") },
          {
            key: "acoes",
            width: 240,
            align: "right",
            render: (_, u) => (
              <Flex gap={4} justify="flex-end">
                <Button size="small" type="link" icon={<KeyOutlined />} onClick={() => setPw(u)}>
                  {t("web.users.change_password")}
                </Button>
                {u.id !== x.eu.id && (
                  <Button size="small" onClick={() => x.alternar(u)}>
                    {u.ativo ? t("web.common.deactivate") : t("web.common.activate")}
                  </Button>
                )}
              </Flex>
            ),
          },
        ]}
      />

      <Collapse size="small" style={{ marginTop: 12 }} items={[{ key: "n", label: t("web.users.levels_title"), children: <Niveis /> }]} />

      <Modal
        open={novo}
        onCancel={() => setNovo(false)}
        title={t("web.users.new")}
        okText={t("btn.add")}
        cancelText={t("web.common.cancel")}
        onOk={() => formNovo.submit()}
        confirmLoading={x.aCriar}
        destroyOnHidden
      >
        <Form
          form={formNovo}
          layout="vertical"
          preserve={false}
          initialValues={{ nivel: "Gestor" }}
          onFinish={async (d) => (await x.criarUtilizador(d)) && setNovo(false)}
        >
          <Form.Item name="username" label={t("web.users.username")} extra={t("web.users.username_help")} rules={regras.username}>
            <Input autoFocus autoComplete="off" autoCapitalize="none" />
          </Form.Item>
          <Form.Item name="nome_completo" label={t("web.users.full_name")} rules={regras.nome}>
            <Input />
          </Form.Item>
          <Form.Item name="nivel" label={t("web.users.level")}>
            <Segmented block options={NIVEIS.map((n) => ({ value: n.value, label: t(n.label) }))} />
          </Form.Item>
          <Form.Item name="password" label={t("web.users.password")} extra={t("users.password_min")} rules={regras.password}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="confirmar" label={t("web.users.password_confirm")} dependencies={["password"]} rules={regras.confirmar}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={pw !== null}
        onCancel={() => setPw(null)}
        title={pw ? `${t("web.users.change_password")} — ${pw.nome_completo}` : ""}
        okText={t("btn.save")}
        cancelText={t("web.common.cancel")}
        onOk={() => formPw.submit()}
        confirmLoading={x.aMudarPw}
        destroyOnHidden
      >
        <Form
          form={formPw}
          layout="vertical"
          preserve={false}
          onFinish={async (d) => pw && (await x.mudarPassword(pw, d.password)) && setPw(null)}
        >
          <Form.Item name="password" label={t("web.users.password")} extra={t("users.password_min")} rules={regras.password}>
            <Input.Password autoFocus autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="confirmar" label={t("web.users.password_confirm")} dependencies={["password"]} rules={regras.confirmar}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function UtilizadoresMobile() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const x = useUtilizadoresTab();
  const regras = useRegras();
  const [aberto, setAberto] = useState<Utilizador | null>(null);
  const [novo, setNovo] = useState(false);
  const [pw, setPw] = useState<Utilizador | null>(null);
  const [formNovo] = MForm.useForm<NovoForm>();
  const [formPw] = MForm.useForm<{ password: string; confirmar: string }>();
  const umSo = { getValueProps: (v: unknown) => ({ value: v == null ? [] : [v] }), normalize: (v: unknown[]) => v[0] };
  const largura = { "--prefix-width": "7.5em" } as React.CSSProperties;

  if (x.lista.isError) return <ErrorBlock status="default" title={errorMessage(x.lista.error)} description="" />;

  return (
    <>
      <Tabs
        activeKey={x.estado}
        onChange={(v) => x.setEstado(v as Estado)}
        style={{ background: "#fff", "--title-font-size": "13px" } as React.CSSProperties}
      >
        <Tabs.Tab key="todos" title={t("owners.filter.all")} />
        <Tabs.Tab key="ativos" title={t("owners.filter.active")} />
        <Tabs.Tab key="inativos" title={t("owners.filter.inactive")} />
      </Tabs>
      <List header={t("web.users.count", { count: x.filtrados.length })}>
        {x.lista.isPending ? (
          <List.Item>
            <DotLoading />
          </List.Item>
        ) : (
          x.filtrados.map((u) => (
            <List.Item
              key={u.id}
              arrow
              onClick={() => setAberto(u)}
              description={`@${u.username} · ${x.nomeNivel(u.nivel)}`}
              extra={!u.ativo && <MTag fill="outline">{t("web.common.inactive")}</MTag>}
            >
              {u.nome_completo}
              {u.id === x.eu.id && <span style={{ color: "#999" }}> ({t("web.users.you")})</span>}
            </List.Item>
          ))
        )}
      </List>
      <Cabecalho>{t("web.users.levels_title")}</Cabecalho>
      <div style={{ padding: "8px 12px 16px", fontSize: 12, color: "#666", background: "#fff" }}>
        <Niveis />
      </div>
      <div style={{ height: 72 }} />
      <FloatingBubble
        style={
          {
            "--initial-position-bottom": "calc(72px + env(safe-area-inset-bottom))",
            "--initial-position-right": "16px",
            "--edge-distance": "16px",
            "--size": "52px",
          } as React.CSSProperties
        }
        onClick={() => setNovo(true)}
      >
        <AddOutline fontSize={26} />
      </FloatingBubble>

      {/* Ficha do utilizador. */}
      <Popup
        visible={aberto !== null}
        onMaskClick={() => setAberto(null)}
        onClose={() => setAberto(null)}
        showCloseButton
        bodyStyle={{ borderTopLeftRadius: 12, borderTopRightRadius: 12, paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        {aberto && (
          <>
            <div style={{ padding: "16px 16px 4px" }}>
              <div style={{ fontSize: 11, color: "#999" }}>@{aberto.username}</div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>{aberto.nome_completo}</div>
            </div>
            <List>
              <List.Item extra={x.nomeNivel(aberto.nivel)}>{t("web.users.level")}</List.Item>
              <List.Item extra={aberto.ativo ? t("web.common.active") : t("web.common.inactive")}>{t("web.common.status")}</List.Item>
              <List.Item extra={aberto.last_login ? dataHora(aberto.last_login) : t("web.users.never")}>{t("label.last_login")}</List.Item>
              <List.Item extra={aberto.created_at ? dataHora(aberto.created_at) : "—"}>{t("label.created_at")}</List.Item>
            </List>
            <div style={{ display: "flex", gap: 8, padding: 16 }}>
              <MButton block color="primary" onClick={() => setPw(aberto)}>
                {t("web.users.change_password")}
              </MButton>
              {aberto.id !== x.eu.id && (
                <MButton
                  block
                  color={aberto.ativo ? "danger" : "success"}
                  fill="outline"
                  onClick={() =>
                    void (aberto.ativo
                      ? Dialog.confirm({
                          title: t("web.common.deactivate"),
                          content: aberto.nome_completo,
                          confirmText: t("web.common.deactivate"),
                          cancelText: t("web.common.cancel"),
                          onConfirm: async () => {
                            const r = await x.alternar(aberto);
                            if (r) setAberto(r);
                          },
                        })
                      : x.alternar(aberto).then((r) => r && setAberto(r)))
                  }
                >
                  {aberto.ativo ? t("web.common.deactivate") : t("web.common.activate")}
                </MButton>
              )}
            </div>
          </>
        )}
      </Popup>

      <FolhaEcraInteiro
        visible={novo}
        titulo={t("web.users.new")}
        onCancel={() => setNovo(false)}
        onOk={() => formNovo.submit()}
        okText={t("btn.add")}
        loading={x.aCriar}
      >
        <MForm
          form={formNovo}
          layout="horizontal"
          style={largura}
          initialValues={{ nivel: "Gestor" }}
          onFinish={async (d) => (await x.criarUtilizador(d)) && setNovo(false)}
          onFinishFailed={irParaErro}
        >
          <MForm.Item name="username" label={t("web.users.username")} description={t("web.users.username_help")} rules={regras.username}>
            <MInput clearable autoComplete="off" autoCapitalize="none" />
          </MForm.Item>
          <MForm.Item name="nome_completo" label={t("web.users.full_name")} rules={regras.nome}>
            <MInput clearable />
          </MForm.Item>
          <MForm.Item name="nivel" label={t("web.users.level")} {...umSo}>
            <Selector showCheckMark={false} columns={3} options={NIVEIS.map((n) => ({ value: n.value, label: t(n.label) }))} />
          </MForm.Item>
          <MForm.Item name="password" label={t("web.users.password")} description={t("users.password_min")} rules={regras.password}>
            <MInput type="password" autoComplete="new-password" />
          </MForm.Item>
          <MForm.Item name="confirmar" label={t("web.users.password_confirm")} dependencies={["password"]} rules={regras.confirmar}>
            <MInput type="password" autoComplete="new-password" />
          </MForm.Item>
        </MForm>
      </FolhaEcraInteiro>

      <FolhaEcraInteiro
        visible={pw !== null}
        titulo={t("web.users.change_password")}
        onCancel={() => setPw(null)}
        onOk={() => formPw.submit()}
        okText={t("btn.save")}
        loading={x.aMudarPw}
      >
        <div style={{ padding: "10px 12px", color: "#999" }}>{pw?.nome_completo}</div>
        <MForm
          form={formPw}
          layout="horizontal"
          style={largura}
          onFinish={async (d) => pw && (await x.mudarPassword(pw, d.password)) && setPw(null)}
          onFinishFailed={irParaErro}
        >
          <MForm.Item name="password" label={t("web.users.password")} description={t("users.password_min")} rules={regras.password}>
            <MInput type="password" autoComplete="new-password" />
          </MForm.Item>
          <MForm.Item name="confirmar" label={t("web.users.password_confirm")} dependencies={["password"]} rules={regras.confirmar}>
            <MInput type="password" autoComplete="new-password" />
          </MForm.Item>
        </MForm>
      </FolhaEcraInteiro>
    </>
  );
}
