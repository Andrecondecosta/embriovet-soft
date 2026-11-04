import { Bar, Column } from "@ant-design/plots";
import { theme } from "antd";

export interface Grafico {
  titulo: string;
  tipo: "colunas" | "barras";
  dados: { x: string; y: number }[];
}

/** Gráfico simples de um relatório: colunas (por mês) ou barras (por nome).
 *  Fica num ficheiro à parte para a biblioteca só carregar nos Relatórios. */
export default function GraficoRelatorio({ g, compacto }: { g: Grafico; compacto?: boolean }) {
  const { token } = theme.useToken();
  const comum = {
    data: g.dados,
    xField: "x",
    yField: "y",
    style: { fill: token.colorPrimary, maxWidth: 28 },
    label: {
      text: (d: { y: number }) => (d.y ? String(d.y) : ""),
      position: g.tipo === "barras" ? ("right" as const) : ("top" as const),
      style: { fontSize: 10 },
    },
    tooltip: { items: [{ channel: "y" }] },
    axis: { x: { title: false, labelFontSize: 10 }, y: { title: false, labelFontSize: 10 } },
    autoFit: true,
  };
  if (g.tipo === "barras") return <Bar {...comum} height={Math.max(140, g.dados.length * 22 + 40)} />;
  return <Column {...comum} height={compacto ? 180 : 220} />;
}
