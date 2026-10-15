import { useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  MouseSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { Typography } from "antd";

import { useT } from "../../../i18n/I18n";
import { useBrand } from "../../../components/Brand";
import { notifySuccess, useNotifyError } from "../../../components/errors";
import { useTrocarContentores, type Contentor } from "./api";

/**
 * Contentores numa grelha compacta — usada quando o mapa não cabe no ecrã.
 *
 * A ordem é a do mapa (fila a fila, da esquerda para a direita), por isso
 * arrastar um contentor para cima de outro troca-os de lugar no mapa e na
 * lista. Com o rato basta arrastar; com o dedo é preciso manter o dedo um
 * instante (senão deslizar a lista arrastava contentores sem querer).
 */
export function ListaContentores({ contentores, onAbrir }: { contentores: Contentor[]; onAbrir: (c: Contentor) => void }) {
  const t = useT();
  const notifyError = useNotifyError();
  const trocar = useTrocarContentores();
  const [ativo, setAtivo] = useState<Contentor | null>(null);
  // Depois de largar, o browser ainda dispara um "click" — não abrir o contentor.
  const largouEm = useRef(0);

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
  );

  const ordenados = [...contentores].sort((a, b) => a.y - b.y || a.x - b.x);

  const fim = async ({ active, over }: DragEndEvent) => {
    setAtivo(null);
    largouEm.current = Date.now();
    if (!over || active.id === over.id) return;
    const a = contentores.find((c) => c.id === active.id);
    const b = contentores.find((c) => c.id === over.id);
    if (!a || !b) return;
    try {
      await trocar.mutateAsync({ a: a.id, b: b.id });
      notifySuccess(t("web.map.swapped", { a: a.codigo, b: b.codigo }));
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <DndContext
      sensors={sensors}
      onDragStart={(e) => setAtivo(contentores.find((c) => c.id === e.active.id) ?? null)}
      onDragEnd={fim}
      onDragCancel={() => setAtivo(null)}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(104px, 1fr))", gap: 6 }}>
        {ordenados.map((c) => (
          <Cartao key={c.id} c={c} onAbrir={() => Date.now() - largouEm.current > 300 && onAbrir(c)} />
        ))}
      </div>
      <DragOverlay dropAnimation={null}>{ativo && <Caixa c={ativo} levantado />}</DragOverlay>
    </DndContext>
  );
}

function Cartao({ c, onAbrir }: { c: Contentor; onAbrir: () => void }) {
  const drag = useDraggable({ id: c.id });
  const drop = useDroppable({ id: c.id });
  const ref = (el: HTMLElement | null) => {
    drag.setNodeRef(el);
    drop.setNodeRef(el);
  };
  return (
    <button
      type="button"
      ref={ref}
      {...drag.attributes}
      {...drag.listeners}
      onClick={onAbrir}
      style={{
        all: "unset",
        display: "block",
        minWidth: 0,
        // Sem o menu de "copiar/selecionar" do iPhone ao manter o dedo.
        userSelect: "none",
        WebkitUserSelect: "none",
        WebkitTouchCallout: "none",
        touchAction: "manipulation",
        opacity: drag.isDragging ? 0.35 : 1,
      }}
    >
      <Caixa c={c} alvo={drop.isOver && !drag.isDragging} />
    </button>
  );
}

function Caixa({ c, alvo = false, levantado = false }: { c: Contentor; alvo?: boolean; levantado?: boolean }) {
  const t = useT();
  const { primary_color } = useBrand();
  return (
    <div
      title={c.lotes ? `${c.codigo} · ${t("web.map.lots_count", { count: c.lotes })}` : c.codigo}
      style={{
        border: `${alvo ? 2 : 1}px ${alvo ? "dashed" : "solid"} ${c.palhetas || alvo ? primary_color : "#d9d9d9"}`,
        borderRadius: 6,
        background: alvo ? `${primary_color}14` : "#fff",
        padding: alvo ? "5px 7px" : "6px 8px",
        boxShadow: levantado ? "0 10px 24px rgba(0,0,0,.2)" : undefined,
        transform: levantado ? "scale(1.05)" : undefined,
        cursor: levantado ? "grabbing" : "pointer",
      }}
    >
      <Typography.Text strong ellipsis style={{ display: "block", fontSize: 11, color: primary_color, textTransform: "uppercase" }}>
        {c.codigo}
      </Typography.Text>
      <Typography.Text strong type={c.palhetas ? undefined : "secondary"} style={{ display: "block" }}>
        {t("web.stock.straws_count", { count: c.palhetas })}
      </Typography.Text>
    </div>
  );
}
