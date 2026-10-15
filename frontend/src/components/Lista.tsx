import type { ReactNode } from "react";
import { Empty, Flex, Pagination, Spin, Typography, theme, type PaginationProps } from "antd";

/**
 * Lista simples com contorno (cabeçalho, linhas tocáveis, paginação) — usada
 * no telemóvel em vez das tabelas. Substitui o `List` do Ant Design, que
 * está marcado como obsoleto desde a versão 6.6.
 */
export function Lista<T>({
  itens,
  chave,
  render,
  onClick,
  cabecalho,
  carregando = false,
  vazio,
  paginacao,
  semContorno = false,
  alturaMax,
}: {
  itens: T[];
  chave: (item: T) => string | number;
  render: (item: T) => { titulo?: ReactNode; descricao?: ReactNode; extra?: ReactNode; acoes?: ReactNode; corpo?: ReactNode };
  onClick?: (item: T) => void;
  cabecalho?: ReactNode;
  carregando?: boolean;
  vazio?: ReactNode;
  paginacao?: PaginationProps | false;
  semContorno?: boolean;
  alturaMax?: number;
}) {
  const { token } = theme.useToken();
  const linha = `1px solid ${token.colorBorderSecondary}`;
  return (
    <Spin spinning={carregando}>
      <div
        style={{
          border: semContorno ? undefined : `1px solid ${token.colorBorder}`,
          borderRadius: token.borderRadiusLG,
          background: token.colorBgContainer,
          overflow: "hidden",
        }}
      >
        {cabecalho && <div style={{ padding: "8px 16px", borderBottom: linha }}>{cabecalho}</div>}
        <div style={alturaMax ? { maxHeight: alturaMax, overflowY: "auto" } : undefined}>
          {!itens.length && !carregando ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={vazio} style={{ margin: "16px 0" }} />
          ) : (
            itens.map((item, i) => {
              const r = render(item);
              return (
                <Flex
                  key={chave(item)}
                  align="center"
                  gap={12}
                  onClick={onClick ? () => onClick(item) : undefined}
                  style={{
                    padding: semContorno ? "8px 0" : "10px 16px",
                    borderTop: i ? linha : undefined,
                    cursor: onClick ? "pointer" : undefined,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {r.corpo ?? (
                      <>
                        {r.titulo && <div style={{ fontWeight: 600 }}>{r.titulo}</div>}
                        {r.descricao && (
                          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                            {r.descricao}
                          </Typography.Text>
                        )}
                      </>
                    )}
                  </div>
                  {r.acoes && <Flex gap={4}>{r.acoes}</Flex>}
                  {r.extra}
                </Flex>
              );
            })
          )}
        </div>
        {paginacao && (
          <Flex justify="center" style={{ padding: 8, borderTop: linha }}>
            <Pagination size="small" {...paginacao} />
          </Flex>
        )}
      </div>
    </Spin>
  );
}
