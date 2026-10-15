import { useRef, useState, type PointerEvent as RPointerEvent } from "react";

import { useBrand } from "../../../components/Brand";
import { useElementWidth, useIsMobile } from "../../../components/responsive";
import { useT } from "../../../i18n/I18n";
import type { Contentor } from "./api";

/**
 * Mapa dos contentores, nas mesmas unidades "virtuais" da app atual
 * (900 × 550, caixas de 70 — `modules/mapa_layout.py`), com a mesma escala:
 * ajusta à largura e altura disponíveis, entre 0,5 (0,75 no telemóvel) e
 * 1,4; se não couber, o mapa desliza.
 *
 * Um toque/clique abre o contentor; arrastar mais de 6 px (10 px com o
 * dedo) muda-o de sítio e grava logo a posição.
 */
export function MapaCanvas({
  contentores,
  virtual,
  onAbrir,
  onMover,
}: {
  contentores: Contentor[];
  virtual: { w: number; h: number; lado: number };
  onAbrir: (c: Contentor) => void;
  onMover: (c: Contentor, x: number, y: number) => void;
}) {
  const t = useT();
  const isMobile = useIsMobile();
  const { primary_color } = useBrand();
  const { ref, width } = useElementWidth<HTMLDivElement>();
  const BOX = virtual.lado;

  // Posições locais enquanto se arrasta / até a gravação voltar — evita a
  // caixa "saltar" para o sítio antigo.
  const [local, setLocal] = useState<Record<number, { x: number; y: number }>>({});
  const pos = (c: Contentor) => local[c.id] ?? { x: c.x, y: c.y };

  const areaW = Math.max(width, 1);
  const areaMaxH = isMobile ? 420 : 520;
  const extW = Math.max(BOX, ...contentores.map((c) => pos(c).x + BOX));
  const extH = Math.max(BOX, ...contentores.map((c) => pos(c).y + BOX));
  const fit = Math.min(areaW / (extW + 12), areaMaxH / (extH + 12));
  const scale = Math.min(1.4, Math.max(isMobile ? 0.75 : 0.5, fit));
  const canvasW = Math.min(virtual.w, Math.max(extW, areaW / scale));
  // A altura acompanha os contentores (mais uma fila livre para onde os
  // arrastar), em vez de deixar um bloco vazio por baixo.
  const canvasH = Math.min(virtual.h, extH + BOX + 20);
  const areaH = Math.min(areaMaxH, Math.ceil(canvasH * scale) + 2);
  const lado = Math.round(BOX * scale);

  const arrasto = useRef<{
    id: number;
    inicioX: number;
    inicioY: number;
    origem: { x: number; y: number };
    ativo: boolean;
    limiar: number;
  } | null>(null);

  const down = (e: RPointerEvent, c: Contentor) => {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    arrasto.current = {
      id: c.id,
      inicioX: e.clientX,
      inicioY: e.clientY,
      origem: pos(c),
      ativo: false,
      limiar: e.pointerType === "touch" ? 10 : 6,
    };
  };

  const move = (e: RPointerEvent) => {
    const a = arrasto.current;
    if (!a) return;
    const dx = e.clientX - a.inicioX;
    const dy = e.clientY - a.inicioY;
    if (!a.ativo && Math.hypot(dx, dy) < a.limiar) return;
    a.ativo = true;
    const x = Math.max(0, Math.min(canvasW - BOX, a.origem.x + dx / scale));
    const y = Math.max(0, Math.min(canvasH - BOX, a.origem.y + dy / scale));
    setLocal((l) => ({ ...l, [a.id]: { x, y } }));
  };

  const up = (c: Contentor) => {
    const a = arrasto.current;
    arrasto.current = null;
    if (!a) return;
    if (!a.ativo) return onAbrir(c);
    const p = local[c.id];
    if (p) onMover(c, Math.round(p.x), Math.round(p.y));
  };

  return (
    <div>
      <div
        ref={ref}
        style={{
          height: areaH,
          overflow: "auto",
          border: "1px solid #d9d9d9",
          borderRadius: 8,
          background: "#fff",
        }}
      >
        <div
          style={{
            position: "relative",
            width: Math.floor(canvasW * scale),
            height: Math.floor(canvasH * scale),
            backgroundImage:
              "linear-gradient(#f0f0f0 1px, transparent 1px), linear-gradient(90deg, #f0f0f0 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        >
          {contentores.map((c) => {
            const p = pos(c);
            const aArrastar = arrasto.current?.id === c.id && arrasto.current.ativo;
            return (
              <div
                key={c.id}
                role="button"
                tabIndex={0}
                aria-label={`${c.codigo}: ${c.palhetas} ${t("label.straws")}`}
                title={c.descricao || c.codigo}
                onPointerDown={(e) => down(e, c)}
                onPointerMove={move}
                onPointerUp={() => up(c)}
                onPointerCancel={() => (arrasto.current = null)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onAbrir(c)}
                style={{
                  position: "absolute",
                  left: p.x * scale,
                  top: p.y * scale,
                  width: lado,
                  height: lado,
                  padding: Math.round(lado * 0.09),
                  boxSizing: "border-box",
                  borderRadius: 6,
                  border: `1.5px solid ${primary_color}`,
                  background: "linear-gradient(#fff, #f8fafc)",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: aArrastar ? "grabbing" : "pointer",
                  userSelect: "none",
                  // Deixa arrastar com o dedo sem a página deslizar.
                  touchAction: "none",
                  zIndex: aArrastar ? 10 : 1,
                  opacity: aArrastar ? 0.88 : 1,
                  transform: aArrastar ? "scale(1.06) rotate(1.5deg)" : undefined,
                  boxShadow: aArrastar ? "0 10px 24px rgba(15,23,42,.18)" : "0 1px 3px rgba(15,23,42,.06)",
                  transition: aArrastar ? "none" : "box-shadow .15s, transform .15s",
                }}
              >
                <span
                  style={{
                    fontSize: Math.max(8, Math.round(lado * 0.145)),
                    fontWeight: 700,
                    color: primary_color,
                    textTransform: "uppercase",
                    maxWidth: "100%",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {c.codigo}
                </span>
                <span style={{ fontSize: Math.max(11, Math.round(lado * 0.3)), fontWeight: 800, color: "#0f172a", lineHeight: 1.1 }}>
                  {c.palhetas}
                </span>
                <span
                  style={{
                    fontSize: Math.max(7, Math.round(lado * 0.115)),
                    color: "#64748b",
                    textTransform: "uppercase",
                  }}
                >
                  {t("label.straws")}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
