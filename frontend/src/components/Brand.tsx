import { createContext, useContext } from "react";
import { Box, Image, Text } from "@mantine/core";
import type { PublicSettings } from "../api/types";

export const BrandContext = createContext<PublicSettings>({
  company_name: "Sistema",
  logo_base64: null,
  primary_color: "#E85D4A",
  language: "pt-PT",
});

export const useBrand = () => useContext(BrandContext);

/** Nome do nosso programa — a marca acima (nome/logótipo) é a da clínica cliente. */
export const PRODUCT_NAME = "EquiCore";

/** Assinatura do programa, discreta, por baixo da marca da clínica. */
export function ProductSignature() {
  return (
    <Text size="xs" c="dimmed" ta="center">
      <Text span fw={700} c="gray.7" style={{ letterSpacing: "0.02em" }}>
        {PRODUCT_NAME}
      </Text>
      {" · Gestor v3.0"}
    </Text>
  );
}

/** Logótipo da empresa, ou as iniciais num quadrado da cor da marca
 *  (mesma regra do ecrã de login da app atual). */
export function BrandMark({ size = 40 }: { size?: number }) {
  const { company_name, logo_base64, primary_color } = useBrand();
  if (logo_base64) {
    const src = logo_base64.startsWith("data:") ? logo_base64 : `data:image/png;base64,${logo_base64}`;
    return <Image src={src} alt={company_name} w={size} h={size} fit="contain" radius="md" />;
  }
  const iniciais =
    company_name
      .split(/\s+/)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? "")
      .join("") || "S";
  return (
    <Box
      w={size}
      h={size}
      style={{
        background: primary_color,
        borderRadius: size * 0.24,
        color: "#fff",
        fontWeight: 700,
        fontSize: size * 0.4,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      {iniciais}
    </Box>
  );
}
