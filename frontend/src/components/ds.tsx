import type { ReactNode } from "react";
import { Card, Col, Divider, Flex, Row, Statistic, Tag, Typography } from "antd";
import { useT } from "../i18n/I18n";

// Peças visuais partilhadas pelas páginas (Ant Design), para todas terem o
// mesmo aspeto.

/** Título de uma secção dentro da página. Fora a primeira, leva uma linha
 *  por cima a separar da secção anterior. */
export function ZoneTitle({ children, primeiro = false }: { children: ReactNode; primeiro?: boolean }) {
  return (
    <>
      {!primeiro && <Divider style={{ margin: "12px 0" }} />}
      <Typography.Text
        type="secondary"
        strong
        style={{ display: "block", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}
      >
        {children}
      </Typography.Text>
    </>
  );
}

/** Indicadores em pequenos cartões. */
export function KpiRow({ items, loading = false }: { items: [ReactNode, ReactNode][]; loading?: boolean }) {
  return (
    <Row gutter={[8, 8]}>
      {items.map(([label, valor], i) => (
        <Col key={i} xs={12} md={6}>
          <Card size="small">
            <Statistic title={label} value={valor as string | number} loading={loading} />
          </Card>
        </Col>
      ))}
    </Row>
  );
}

/** Etiqueta: ok = cinzenta, aviso = tom da marca, critico = cheia. */
export function Pill({ nivel = "ok", children }: { nivel?: "ok" | "aviso" | "critico"; children: ReactNode }) {
  const cor = nivel === "ok" ? "default" : nivel === "aviso" ? "red" : "error";
  return (
    <Tag color={cor} style={{ marginInlineEnd: 0, flexShrink: 0 }}>
      {children}
    </Tag>
  );
}

/** Cabeçalho da página: título e, à direita, as ações. */
export function PageHeader({ titulo, acoes }: { titulo: string; acoes?: ReactNode }) {
  return (
    <Flex justify="space-between" align="center" gap={8} wrap style={{ marginBottom: 12 }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        {titulo}
      </Typography.Title>
      {acoes}
    </Flex>
  );
}

/** Estado ativo/inativo (proprietários). */
export function StatusPill({ ativo }: { ativo: boolean | null }) {
  const t = useT();
  // `ativo` NULL conta como ativo, como na app atual (`prop.get('ativo', True)`).
  const on = ativo !== false;
  return (
    <Tag color={on ? "green" : "default"} style={{ marginInlineEnd: 0, flexShrink: 0 }}>
      {on ? t("web.owners.active") : t("web.owners.inactive")}
    </Tag>
  );
}
