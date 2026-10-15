import { createContext, useContext } from "react";
import { Typography } from "antd";
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
export function ProductSignature({ escuro = false }: { escuro?: boolean }) {
  return (
    <Typography.Text style={{ fontSize: 11, color: escuro ? "rgba(255,255,255,.45)" : "rgba(0,0,0,.45)" }}>
      <b style={{ color: escuro ? "rgba(255,255,255,.75)" : "rgba(0,0,0,.65)", letterSpacing: "0.02em" }}>
        {PRODUCT_NAME}
      </b>
      {" · Gestor v3.0"}
    </Typography.Text>
  );
}

/** Logótipo da empresa, ou as iniciais num quadrado da cor da marca
 *  (mesma regra do ecrã de login da app atual). */
export function BrandMark({ size = 40 }: { size?: number }) {
  const { company_name, logo_base64, primary_color } = useBrand();
  if (logo_base64) {
    const src = logo_base64.startsWith("data:") ? logo_base64 : `data:image/png;base64,${logo_base64}`;
    return (
      <img
        src={src}
        alt={company_name}
        width={size}
        height={size}
        style={{ objectFit: "contain", borderRadius: 6, flexShrink: 0 }}
      />
    );
  }
  const iniciais =
    company_name
      .split(/\s+/)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? "")
      .join("") || "S";
  return (
    <div
      style={{
        width: size,
        height: size,
        background: primary_color,
        borderRadius: size * 0.2,
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
    </div>
  );
}
