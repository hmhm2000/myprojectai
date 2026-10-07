import { useCallback, useRef, useState } from "react";

function move(list, from, to) {
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

/**
 * Drag & drop of list items by a handle (mouse and touch - Pointer Events).
 * While dragging, the list shows the new order live; on drop it calls onReorder(ids).
 */
export function useDragSort(ids, onReorder) {
  const [drag, setDrag] = useState(null); // { id, from, to, mids }
  const elements = useRef(new Map());

  const register = useCallback(
    (id) => (el) => {
      if (el) elements.current.set(id, el);
      else elements.current.delete(id);
    },
    [],
  );

  const handleProps = (id) => ({
    onPointerDown: (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      // Item midpoints captured at the start - stable even though the list reorders while dragging.
      const mids = ids.map((itemId) => {
        const rect = elements.current.get(itemId)?.getBoundingClientRect();
        return rect ? rect.top + rect.height / 2 : 0;
      });
      const from = ids.indexOf(id);
      setDrag({ id, from, to: from, mids });
    },
    onPointerMove: (e) => {
      if (!drag) return;
      const to = drag.mids.reduce((count, mid, index) => (index !== drag.from && mid < e.clientY ? count + 1 : count), 0);
      if (to !== drag.to) setDrag({ ...drag, to });
    },
    onPointerUp: () => {
      if (!drag) return;
      const { from, to } = drag;
      setDrag(null);
      if (from !== to) onReorder(move(ids, from, to));
    },
    onPointerCancel: () => setDrag(null),
    style: { touchAction: "none" },
  });

  return {
    orderedIds: drag ? move(ids, drag.from, drag.to) : ids,
    draggingId: drag?.id ?? null,
    register,
    handleProps,
  };
}
