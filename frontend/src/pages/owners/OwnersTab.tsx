import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Button, Flex, FloatButton, Input, Segmented, Select, Table, Typography } from "antd";
import { PlusOutlined, RightOutlined, SearchOutlined } from "@ant-design/icons";

import type { Owner } from "../../api/types";
import { useT } from "../../i18n/I18n";
import { useErrorMessage } from "../../components/errors";
import { useDebounced, useIsMobile } from "../../components/responsive";
import { StatusPill } from "../../components/ds";
import { Lista } from "../../components/Lista";
import { POR_PAGINA, useOwners, type Estado, type Ordem } from "./api";
import { OwnerDrawer } from "./OwnerDrawer";
import { OwnerFormModal } from "./OwnerFormModal";

const ESTADOS: Estado[] = ["todos", "ativos", "inativos"];
const ORDENS: Ordem[] = ["nome", "id", "status"];

export function OwnersTab() {
  const t = useT();
  const errorMessage = useErrorMessage();
  const isMobile = useIsMobile();

  // Filtros no endereço: um "Atualizar" ou o botão "Voltar" mantêm a
  // pesquisa e a página onde se estava.
  const [params, setParams] = useSearchParams();
  const estado = (ESTADOS.find((e) => e === params.get("estado")) ?? "todos") as Estado;
  const ordem = (ORDENS.find((o) => o === params.get("ordem")) ?? "nome") as Ordem;
  const pagina = Math.max(1, Number(params.get("pagina")) || 1);
  const [pesquisa, setPesquisa] = useState(params.get("q") ?? "");
  const q = useDebounced(pesquisa.trim(), 300);

  const atualizar = (novo: Record<string, string | number | null>) => {
    setParams(
      (p) => {
        const r = new URLSearchParams(p);
        for (const [k, v] of Object.entries(novo)) {
          if (v === null || v === "" || (k === "pagina" && v === 1)) r.delete(k);
          else r.set(k, String(v));
        }
        return r;
      },
      { replace: true },
    );
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) atualizar({ q, pagina: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { data, isPending, isError, error, isFetching } = useOwners({ q, estado, ordem, pagina });
  const [selecionado, setSelecionado] = useState<Owner | null>(null);
  const [form, setForm] = useState<{ aberto: boolean; owner: Owner | null }>({ aberto: false, owner: null });

  const totalPaginas = data ? Math.max(1, Math.ceil(data.total / POR_PAGINA)) : 1;
  // Se apagar o último da última página, recua uma página.
  useEffect(() => {
    if (data && pagina > totalPaginas) atualizar({ pagina: totalPaginas });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, pagina, totalPaginas]);

  const abrirNovo = () => setForm({ aberto: true, owner: null });
  const vazio = (v: string | null) => v || <Typography.Text type="secondary">—</Typography.Text>;
  const paginacao = {
    current: Math.min(pagina, totalPaginas),
    pageSize: POR_PAGINA,
    total: data?.total ?? 0,
    onChange: (p: number) => {
      atualizar({ pagina: p });
      window.scrollTo({ top: 0 });
    },
    showSizeChanger: false,
    hideOnSinglePage: true,
    size: "small" as const,
  };

  return (
    <>
      <Flex gap={8} wrap align="center" justify="space-between" style={{ marginBottom: 12 }}>
        <Flex gap={8} wrap align="center" style={{ flex: 1 }}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder={t("web.owners.search")}
            value={pesquisa}
            onChange={(e) => setPesquisa(e.target.value)}
            style={{ width: isMobile ? "100%" : 320 }}
          />
          <Segmented
            value={estado}
            onChange={(v) => atualizar({ estado: v === "todos" ? null : (v as string), pagina: 1 })}
            options={[
              { value: "todos", label: t("owners.filter.all") },
              { value: "ativos", label: t("owners.filter.active") },
              { value: "inativos", label: t("owners.filter.inactive") },
            ]}
            block={isMobile}
            style={isMobile ? { width: "100%" } : undefined}
          />
          <Select
            value={ordem}
            onChange={(v) => atualizar({ ordem: v === "nome" ? null : v, pagina: 1 })}
            style={{ width: isMobile ? "100%" : 180 }}
            options={[
              { value: "nome", label: `${t("owners.sort_by")} ${t("owners.sort.name")}` },
              { value: "id", label: `${t("owners.sort_by")} ${t("owners.sort.id")}` },
              { value: "status", label: `${t("owners.sort_by")} ${t("web.owners.status")}` },
            ]}
          />
        </Flex>
        {!isMobile && (
          <Button type="primary" icon={<PlusOutlined />} onClick={abrirNovo}>
            {t("web.owners.new")}
          </Button>
        )}
      </Flex>

      {isError ? (
        <Alert type="error" title={errorMessage(error)} showIcon />
      ) : isMobile ? (
        <Lista
          itens={data?.items ?? []}
          chave={(o) => o.id}
          carregando={isPending || isFetching}
          cabecalho={data && <Typography.Text type="secondary">{t("web.owners.count", { count: data.total })}</Typography.Text>}
          vazio={t("web.owners.empty")}
          paginacao={data && data.total > POR_PAGINA ? paginacao : false}
          onClick={setSelecionado}
          render={(o) => ({
            titulo: (
              <Flex gap={8} align="center">
                <Typography.Text strong ellipsis>
                  {o.nome}
                </Typography.Text>
                <StatusPill ativo={o.ativo} />
              </Flex>
            ),
            descricao: [o.cidade, o.telemovel, o.email].filter(Boolean).join(" · ") || `#${o.id}`,
            extra: <RightOutlined style={{ color: "#bfbfbf" }} />,
          })}
        />
      ) : (
        <Table<Owner>
          size="small"
          bordered
          rowKey="id"
          loading={isPending || isFetching}
          dataSource={data?.items ?? []}
          pagination={paginacao}
          locale={{ emptyText: t("web.owners.empty") }}
          title={() => data && <Typography.Text type="secondary">{t("web.owners.count", { count: data.total })}</Typography.Text>}
          onRow={(o) => ({ onClick: () => setSelecionado(o), style: { cursor: "pointer" } })}
          columns={[
            { title: t("label.id"), dataIndex: "id", width: 70, render: (v) => <Typography.Text type="secondary">{v}</Typography.Text> },
            {
              title: t("label.name"),
              dataIndex: "nome",
              render: (_, o) => (
                <>
                  <Typography.Text strong>{o.nome}</Typography.Text>
                  {o.nome_completo && o.nome_completo !== o.nome && (
                    <div>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {o.nome_completo}
                      </Typography.Text>
                    </div>
                  )}
                </>
              ),
            },
            { title: t("label.email"), dataIndex: "email", render: vazio, ellipsis: true },
            { title: t("label.phone"), dataIndex: "telemovel", render: vazio, responsive: ["lg"] },
            { title: t("label.city"), dataIndex: "cidade", render: vazio },
            { title: t("web.owners.status"), dataIndex: "ativo", width: 100, render: (v) => <StatusPill ativo={v} /> },
          ]}
        />
      )}

      {isMobile && <FloatButton type="primary" icon={<PlusOutlined />} onClick={abrirNovo} tooltip={t("web.owners.new")} />}

      <OwnerDrawer
        owner={selecionado}
        onClose={() => setSelecionado(null)}
        onEdit={(o) => setForm({ aberto: true, owner: o })}
        onChanged={setSelecionado}
      />
      <OwnerFormModal
        opened={form.aberto}
        owner={form.owner}
        onClose={() => setForm((f) => ({ ...f, aberto: false }))}
        onSaved={(o) => {
          if (selecionado) setSelecionado(o);
        }}
      />
    </>
  );
}
