import { theme, type ThemeConfig } from "antd";

/**
 * Tema Ant Design da app.
 * - Computador/tablet: modo compacto (letra 13 px, controlos baixos) — o
 *   aspeto de "software de gestão" escolhido.
 * - Telemóvel: modo normal, com controlos mais altos para o dedo (os
 *   campos ficam a 16 px por CSS, ver styles.css, para o iPhone não fazer
 *   zoom ao escrever).
 */
export function criarTema(primaria: string, telemovel: boolean): ThemeConfig {
  return {
    algorithm: telemovel ? theme.defaultAlgorithm : theme.compactAlgorithm,
    token: {
      colorPrimary: primaria,
      colorLink: primaria,
      borderRadius: 4,
      fontSize: telemovel ? 14 : 13,
      controlHeight: telemovel ? 40 : 32,
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    },
    components: {
      Layout: { headerHeight: 48, headerPadding: telemovel ? "0 8px" : "0 16px", siderBg: "#001529" },
      Table: { headerBg: "#fafafa" },
    },
  };
}
