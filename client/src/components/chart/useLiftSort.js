import { useCallback, useRef, useState } from "react";

const THRESHOLD = 5;   // px - a smaller move is a click, not a drag
const DROP_MS = 180;   // the lifted tile glides into its new place before the list is reordered
const SLIDE = "translate 200ms cubic-bezier(0.2, 0, 0, 1)";

function move(list, from, to) {
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

/**
 * Drag & drop of whole tiles with smooth movement (mouse and touch - Pointer Events).
 * The grabbed tile is lifted and follows the pointer, the others slide out of its way; on drop it glides
 * into the new place and `onReorder(ids)` is called. Buttons inside a tile keep working (no drag there).
 * - `items`: [{ id }] in the saved order; until a new `items` list arrives, the new order is shown at once,
 * - returns `order` (ids to render), `itemProps(id)` (spread on every tile) and `moveTo(id, index)` (arrows).
 */
export function useLiftSort(items, onReorder) {
  const [local, setLocal] = useState(null);   // { source: items, order } - order shown before the server answers
  const [drag, setDrag] = useState(null);     // { id, from, to, dy, tops, heights, gap, dropping }
  const pending = useRef(null);               // { id, pointerId, startY } - pressed, not moved enough yet
  const elements = useRef(new Map());
  const order = local?.source === items ? local.order : items.map((i) => i.id);

  const commit = useCallback((next) => {
    setLocal({ source: items, order: next });
    onReorder(next);
  }, [items, onReorder]);

  const moveTo = (id, index) => {
    const from = order.indexOf(id);
    if (from !== index && index >= 0 && index < order.length) commit(move(order, from, index));
  };

  const lift = (id, dy) => {
    const rects = order.map((itemId) => elements.current.get(itemId)?.getBoundingClientRect());
    if (rects.some((r) => !r)) return null;
    const tops = rects.map((r) => r.top);
    const heights = rects.map((r) => r.height);
    const gap = rects.length > 1 ? Math.max(0, tops[1] - tops[0] - heights[0]) : 0;
    const from = order.indexOf(id);
    return { id, from, to: from, dy, tops, heights, gap, dropping: false };
  };

  // where the lifted tile would land: the number of other tiles whose middle is above its middle
  const target = (d, dy) => {
    const middle = d.tops[d.from] + d.heights[d.from] / 2 + dy;
    return d.tops.reduce((n, top, i) => (i !== d.from && top + d.heights[i] / 2 < middle ? n + 1 : n), 0);
  };

  // vertical offset (px) of a tile while dragging
  const offsetOf = (index) => {
    const { from, to, heights, gap } = drag;
    const step = heights[from] + gap;
    if (index === from) {
      if (!drag.dropping) return drag.dy;
      let sum = 0;
      if (to > from) for (let i = from + 1; i <= to; i++) sum += heights[i] + gap;
      else for (let i = to; i < from; i++) sum -= heights[i] + gap;
      return sum;
    }
    if (from < to && index > from && index <= to) return -step;
    if (to < from && index >= to && index < from) return step;
    return 0;
  };

  const finish = () => {
    if (!drag || drag.dropping) return;
    setDrag({ ...drag, dropping: true });
    const { from, to } = drag;
    setTimeout(() => {
      setDrag(null);
      if (from !== to) commit(move(order, from, to));
    }, DROP_MS);
  };

  const itemProps = (id) => {
    const index = order.indexOf(id);
    const lifted = drag?.id === id;
    let style = { touchAction: "pan-y", cursor: drag ? "grabbing" : "grab" };
    if (drag) {
      style = lifted
        ? { ...style, position: "relative", zIndex: 20, translate: `0 ${offsetOf(index)}px`,
          scale: drag.dropping ? "1" : "1.03", rotate: drag.dropping ? "0deg" : "-0.6deg",
          boxShadow: drag.dropping ? "none" : "0 18px 40px -12px rgba(0,0,0,0.75), 0 0 0 1px rgba(167,139,250,0.55)",
          transition: drag.dropping
            ? `translate ${DROP_MS}ms ease-out, scale ${DROP_MS}ms ease-out, rotate ${DROP_MS}ms ease-out, box-shadow ${DROP_MS}ms`
            : "scale 150ms ease-out, rotate 150ms ease-out, box-shadow 150ms" }
        : { ...style, translate: `0 ${offsetOf(index)}px`, transition: SLIDE };
    }
    return {
      ref: (el) => {
        if (el) elements.current.set(id, el);
        else elements.current.delete(id);
      },
      style,
      onPointerDown: (e) => {
        if (e.button !== 0 || drag || e.target.closest("button, a, input, select")) return;
        pending.current = { id, pointerId: e.pointerId, startY: e.clientY };
      },
      onPointerMove: (e) => {
        const p = pending.current;
        if (drag && !drag.dropping && drag.id === id) {
          const first = drag.tops[0] - drag.tops[drag.from] - 12;
          const last = drag.tops.length - 1;
          const end = drag.tops[last] + drag.heights[last] - drag.tops[drag.from] - drag.heights[drag.from] + 12;
          const dy = Math.min(end, Math.max(first, e.clientY - drag.startY));
          setDrag({ ...drag, dy, to: target(drag, dy) });
        } else if (p && p.id === id && Math.abs(e.clientY - p.startY) > THRESHOLD) {
          const lifted = lift(id, e.clientY - p.startY);
          if (!lifted) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          window.getSelection()?.removeAllRanges();
          setDrag({ ...lifted, startY: p.startY });
          pending.current = null;
        }
      },
      onPointerUp: () => {
        pending.current = null;
        finish();
      },
      onPointerCancel: () => {
        pending.current = null;
        finish();
      },
    };
  };

  return { order, itemProps, moveTo, dragging: drag !== null };
}
