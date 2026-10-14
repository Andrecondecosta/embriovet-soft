import { useMediaQuery } from "@mantine/hooks";

// Pontos de quebra do Mantine: sm = 48em (768px), md = 62em (992px).
// Telemóvel < 768px · tablet 768–991px · computador ≥ 992px.
// Para mostrar/esconder blocos inteiros preferir `hiddenFrom`/`visibleFrom`
// (CSS, sem "salto" no primeiro desenho); estes hooks são para props que
// não têm versão CSS (ex.: fullScreen de um modal).
export const useIsMobile = () => useMediaQuery("(max-width: 47.99em)") ?? false;
export const useIsTablet = () => useMediaQuery("(min-width: 48em) and (max-width: 61.99em)") ?? false;
