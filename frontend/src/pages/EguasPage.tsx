import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Input, Segmented, Space, Table, Tag, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { DotLoading, ErrorBlock, FloatingBubble, List, SearchBar, Selector } from "antd-mobile";
import { AddOutline } from "antd-mobile-icons";

import { api } from "../api/client";
import { useT } from "../i18n/I18n";
import { useIsMobile } from "../components/responsive";
import { useErrorMessage } from "../components/errors";
import { dataCurta } from "../components/csv";
import { TagReprodutivo, useEstadoReprodutivo, type Repro } from "../components/EstadoReprodutivo";
import type { TipoRegisto } from "./estadias/api";
import { NovaEstadia } from "./estadias/NovaEstadia";

// Todas as éguas e receptoras; tocar numa abre a ficha no Diário clínico.

interface Egua {
  id: number;
  nome: string;
  tipo: "egua" | "receptora";
  proprietario: string | null;
  em_aberto: TipoRegisto | null;
  ultimo_registo: string | null;
  repro: Repro | null;
}

function useEguas() {
  const t = useT();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["animais", "eguas"], queryFn: () => api<Egua[]>("/animais/eguas") });
  const [texto, setTexto] = useState("");
  // Tipo (éguas / receptoras) e situação (na clínica / externas).
  const [tipo, setTipo] = useState<"todos" | "egua" | "receptora">("todos");
  const [situacao, setSituacao] = useState<"todas" | "aqui" | "externas">("todas");
  const procura = texto.trim().toLowerCase();
  const lista = (q.data ?? []).filter(
    (e) =>
      (tipo === "todos" || e.tipo === tipo) &&
      (situacao === "todas" ||
        (situacao === "externas" ? e.em_aberto === "externo" : !!e.em_aberto && e.em_aberto !== "externo")) &&
      (!procura || e.nome.toLowerCase().includes(procura) || (e.proprietario ?? "").toLowerCase().includes(procura)),
  );
  return {
    t,
    q,
    lista,
    texto,
    setTexto,
    tipo,
    setTipo,
    situacao,
    setSituacao,
    abrir: (e: Egua) => navigate(`/animais/${e.id}?tab=diario`),
    tipos: [
      { value: "todos" as const, label: t("web.daily.mares.all") },
      { value: "egua" as const, label: t("web.stays.animals.egua") },
      { value: "receptora" as const, label: t("web.stays.animals.receptora") },
    ],
    situacoes: [
      { value: "todas" as const, label: t("web.daily.mares.all") },
      { value: "aqui" as const, label: t("web.daily.mares.here") },
      { value: "externas" as const, label: t("web.daily.mares.external") },
    ],
    naClinica: (e: Egua) => (e.em_aberto ? t(`web.stays.kind.${e.em_aberto}`) : null),
  };
}

export function EguasPage() {
  // "Nova égua": o formulário das Estadias, mas por defeito sem entrada na clínica.
  const [nova, setNova] = useState(false);
  return (
    <>
      {useIsMobile() ? <EguasMobile novaEgua={() => setNova(true)} /> : <EguasDesktop novaEgua={() => setNova(true)} />}
      <NovaEstadia egua aberto={nova} onClose={() => setNova(false)} />
    </>
  );
}

function EguasDesktop({ novaEgua }: { novaEgua: () => void }) {
  const x = useEguas();
  const { t } = x;
  const errorMessage = useErrorMessage();
  if (x.q.isError) return <Alert type="error" showIcon title={errorMessage(x.q.error)} />;
  return (
    <Card
      size="small"
      title={`${t("web.daily.mares.title")} (${x.lista.length})`}
      extra={
        <Space>
          <Input.Search
            allowClear
            placeholder={t("web.daily.mares.filter")}
            style={{ width: 260 }}
            value={x.texto}
            onChange={(e) => x.setTexto(e.target.value)}
          />
          <Segmented options={x.tipos} value={x.tipo} onChange={x.setTipo} />
          <Segmented options={x.situacoes} value={x.situacao} onChange={x.setSituacao} />
          <Button type="primary" icon={<PlusOutlined />} onClick={novaEgua}>
            {t("web.daily.mares.new")}
          </Button>
        </Space>
      }
    >
      <Table<Egua>
        size="small"
        rowKey="id"
        loading={x.q.isFetching}
        dataSource={x.lista}
        pagination={{ defaultPageSize: 50, showSizeChanger: true, hideOnSinglePage: true }}
        onRow={(e) => ({ onClick: () => x.abrir(e), style: { cursor: "pointer" } })}
        locale={{ emptyText: t("web.daily.mares.none") }}
        columns={[
          {
            title: t("web.dashboard.mare"),
            dataIndex: "nome",
            sorter: (a, b) => a.nome.localeCompare(b.nome),
            render: (v: string) => <Typography.Text strong>{v}</Typography.Text>,
          },
          {
            title: t("web.dashboard.owner"),
            dataIndex: "proprietario",
            sorter: (a, b) => (a.proprietario ?? "").localeCompare(b.proprietario ?? ""),
            render: (v: string | null) => v ?? "—",
          },
          { title: t("web.daily.mares.col.type"), dataIndex: "tipo", width: 110, render: (v: string) => t(`web.stays.animal.${v}`) },
          {
            title: t("web.daily.mares.col.where"),
            key: "aqui",
            width: 120,
            render: (_, e) => (x.naClinica(e) ? <Tag color={e.em_aberto === "externo" ? "default" : "green"}>{x.naClinica(e)}</Tag> : null),
          },
          { title: t("web.daily.mares.col.state"), key: "repro", render: (_, e) => <TagReprodutivo r={e.repro} /> },
          {
            title: t("web.daily.mares.col.last"),
            dataIndex: "ultimo_registo",
            width: 130,
            sorter: (a, b) => (a.ultimo_registo ?? "").localeCompare(b.ultimo_registo ?? ""),
            render: (v: string | null) => (v ? dataCurta(v) : "—"),
          },
        ]}
      />
    </Card>
  );
}

function EguasMobile({ novaEgua }: { novaEgua: () => void }) {
  const x = useEguas();
  const { t } = x;
  const estadoRepro = useEstadoReprodutivo();
  const errorMessage = useErrorMessage();
  if (x.q.isError) return <ErrorBlock status="default" title={errorMessage(x.q.error)} description="" />;
  return (
    <>
      <div style={{ padding: "8px 12px", background: "#fff" }}>
        <SearchBar value={x.texto} onChange={x.setTexto} placeholder={t("web.daily.mares.filter")} />
        <Selector
          style={{ marginTop: 8 }}
          columns={3}
          showCheckMark={false}
          options={x.tipos}
          value={[x.tipo]}
          onChange={(v) => v.length && x.setTipo(v[0])}
        />
        <Selector
          style={{ marginTop: 8 }}
          columns={3}
          showCheckMark={false}
          options={x.situacoes}
          value={[x.situacao]}
          onChange={(v) => v.length && x.setSituacao(v[0])}
        />
      </div>
      {!x.q.data ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <DotLoading color="primary" />
        </div>
      ) : (
        <List header={`${t("web.daily.mares.title")} (${x.lista.length})`}>
          {x.lista.map((e) => (
            <List.Item
              key={e.id}
              arrow
              description={[e.proprietario ?? "—", x.naClinica(e), estadoRepro(e.repro)?.texto].filter(Boolean).join(" · ")}
              onClick={() => x.abrir(e)}
            >
              {e.nome}
            </List.Item>
          ))}
          {!x.lista.length && (
            <List.Item>
              <span style={{ color: "#999" }}>{t("web.daily.mares.none")}</span>
            </List.Item>
          )}
        </List>
      )}
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
        onClick={novaEgua}
      >
        <AddOutline fontSize={26} />
      </FloatingBubble>
    </>
  );
}
