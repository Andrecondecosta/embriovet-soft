import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

// Telemóvel < 768px · tablet 768–991px · computador ≥ 992px (os mesmos
// pontos de quebra do Ant Design: md = 768, lg = 992).

function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (cb: () => void) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", cb);
      return () => mq.removeEventListener("change", cb);
    },
    [query],
  );
  // Valor certo logo no primeiro desenho (sem "saltar" de computador para
  // telemóvel depois de abrir).
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false);
}

export const useIsMobile = () => useMediaQuery("(max-width: 767.98px)");
export const useIsTablet = () => useMediaQuery("(min-width: 768px) and (max-width: 991.98px)");

/** Largura de um elemento, atualizada quando muda (ResizeObserver).
 *  Devolve uma ref de callback, por isso funciona mesmo que o elemento só
 *  apareça depois do primeiro desenho. */
export function useElementWidth<T extends HTMLElement>() {
  const [width, setWidth] = useState(0);
  const obs = useRef<ResizeObserver | null>(null);
  const ref = useCallback((el: T | null) => {
    obs.current?.disconnect();
    if (!el) return;
    setWidth(el.getBoundingClientRect().width);
    obs.current = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    obs.current.observe(el);
  }, []);
  useEffect(() => () => obs.current?.disconnect(), []);
  return { ref, width };
}

/** Valor que só muda depois de `ms` sem alterações (pesquisas). */
export function useDebounced<T>(valor: T, ms: number): T {
  const [v, setV] = useState(valor);
  useEffect(() => {
    const id = setTimeout(() => setV(valor), ms);
    return () => clearTimeout(id);
  }, [valor, ms]);
  return v;
}
