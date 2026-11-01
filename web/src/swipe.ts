import { useRef } from "react";

// Swipe left/right between looks. A horizontal drag of 50px or more (and clearly more sideways than up
// or down, so the page still scrolls) counts; the click it would otherwise end in is swallowed, so a
// swipe that starts on a garment doesn't also open it.

export function useSwipe(onNext: () => void, onPrev: () => void) {
  const start = useRef<{ x: number; y: number } | null>(null);
  const swiped = useRef(false);
  return {
    onPointerDown: (e: React.PointerEvent) => {
      start.current = { x: e.clientX, y: e.clientY };
      swiped.current = false;
    },
    onPointerUp: (e: React.PointerEvent) => {
      const s = start.current;
      start.current = null;
      if (!s) return;
      const dx = e.clientX - s.x;
      const dy = e.clientY - s.y;
      if (Math.abs(dx) > 50 && Math.abs(dx) > 1.5 * Math.abs(dy)) {
        swiped.current = true;
        if (dx < 0) onNext();
        else onPrev();
      }
    },
    onPointerCancel: () => {
      start.current = null;
    },
    onClickCapture: (e: React.MouseEvent) => {
      if (swiped.current) {
        e.stopPropagation();
        e.preventDefault();
        swiped.current = false;
      }
    },
    style: { touchAction: "pan-y" } as React.CSSProperties,
  };
}
