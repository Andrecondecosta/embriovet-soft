import { createTheme } from "@mantine/core";
import { generateColors } from "@mantine/colors-generator";

export function criarTema(primaria: string) {
  return createTheme({
    colors: { brand: generateColors(primaria) },
    primaryColor: "brand",
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    defaultRadius: "md",
    cursorType: "pointer",
  });
}
