import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { t } from "../i18n";

// Quick colors (like TradingView's palette): greys, main colors, light and dark shades.
const PRESETS = [
  ["#ffffff", "#d1d4dc", "#b2b5be", "#9598a1", "#787b86", "#5d606b", "#434651", "#2a2e39", "#131722", "#000000"],
  ["#f23645", "#ff9800", "#ffeb3b", "#4caf50", "#089981", "#00bcd4", "#2962ff", "#673ab7", "#9c27b0", "#e91e63"],
  ["#faa1a4", "#ffcc80", "#fff59d", "#a5d6a7", "#70ccbd", "#80deea", "#90bff9", "#b39ddb", "#ce93d8", "#f48fb1"],
  ["#b22833", "#f57c00", "#fbc02d", "#388e3c", "#056656", "#0097a7", "#1848cc", "#512da8", "#7b1fa2", "#c2185b"],
];
const CHECKER = "repeating-conic-gradient(#3f3f46 0% 25%, #18181b 0% 50%) 50% / 8px 8px";
const WIDTH = 248;
const PICKING = "color-picking";   // on <html> while the eyedropper is open: dialogs are hidden (see index.css)

function rgba(hex, opacity) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${opacity / 100})`;
}

/**
 * Color + opacity: a swatch that opens a small panel with quick colors, an opacity slider, the full
 * color picker ("More...") and - where the browser has it - an eyedropper that hides the dialogs while
 * picking, so a color can be taken from the chart. `color` = "#rrggbb" or null (colors set elsewhere -
 * only the opacity), `opacity` = 0-100; onChange(color, opacity).
 */
export default function ColorPicker({ color, opacity, onChange, title }) {
  const [open, setOpen] = useState(false);
  const [place, setPlace] = useState(null);
  const button = useRef(null);
  const panel = useRef(null);
  const eyedropper = typeof window !== "undefined" && "EyeDropper" in window;

  // below the swatch (above it when there is no room), kept inside the window; follows scrolling
  useLayoutEffect(() => {
    if (!open) return undefined;
    const position = () => {
      const rect = button.current?.getBoundingClientRect();
      if (!rect) return;
      const height = panel.current?.offsetHeight ?? 220;
      const below = rect.bottom + 6 + height <= window.innerHeight;
      setPlace({
        left: Math.min(Math.max(8, rect.left), window.innerWidth - WIDTH - 8),
        top: below ? rect.bottom + 6 : Math.max(8, rect.top - 6 - height),
      });
    };
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [open]);

  // closes on a click outside or Esc (Esc closes only this panel, not the dialog under it)
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (!panel.current?.contains(e.target) && !button.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      e.stopImmediatePropagation();
      setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey, true);
    };
  }, [open]);

  const pick = async () => {
    document.documentElement.classList.add(PICKING);
    try {
      const { sRGBHex } = await new window.EyeDropper().open();
      if (/^#[0-9a-f]{6}$/i.test(sRGBHex)) onChange(sRGBHex.toLowerCase(), opacity);
    } catch {
      // cancelled (Esc)
    } finally {
      document.documentElement.classList.remove(PICKING);
    }
  };

  const shown = color ? rgba(color, opacity) : null;
  return (
    <>
      <button ref={button} type="button" title={title} aria-expanded={open} onClick={() => setOpen((v) => !v)}
        className="h-7 w-9 shrink-0 rounded-md border border-white/15 p-0.5 transition hover:border-white/40"
        style={{ background: CHECKER }}>
        <span className="block h-full w-full rounded-[4px] text-[10px] leading-[22px] text-zinc-300"
          style={{ background: shown ?? "linear-gradient(135deg,#34d399,#60a5fa,#f87171)" }}>
          {!color && t("chart.style.palette")}
        </span>
      </button>
      {open && createPortal(
        <div ref={panel} className="color-panel fixed z-[60] space-y-3 rounded-xl border border-white/10 bg-ink-900 p-3 shadow-2xl"
          style={{ width: WIDTH, left: place?.left ?? -9999, top: place?.top ?? -9999 }}>
          {color ? (
            <>
              <div className="grid grid-cols-10 gap-1">
                {PRESETS.flat().map((c) => (
                  <button key={c} type="button" title={c} onClick={() => onChange(c, opacity)}
                    className={`h-5 w-5 rounded border transition hover:scale-110 ${
                      c === color.toLowerCase() ? "border-white ring-1 ring-white" : "border-white/10"}`}
                    style={{ background: c }} />
                ))}
              </div>
              <div className="flex items-center gap-2">
                <label className="btn-ghost relative cursor-pointer px-2 py-1 text-xs">
                  {t("chart.colors.more")}
                  <input type="color" value={color} onChange={(e) => onChange(e.target.value, opacity)}
                    className="absolute inset-0 h-full w-full cursor-pointer opacity-0" />
                </label>
                {eyedropper && (
                  <button type="button" className="btn-ghost px-2 py-1 text-xs" title={t("chart.colors.eyedropperHint")} onClick={pick}>
                    {t("chart.colors.eyedropper")}
                  </button>
                )}
                <span className="num ml-auto text-[11px] text-zinc-500">{color}</span>
              </div>
            </>
          ) : (
            <p className="text-[11px] text-zinc-500">{t("chart.style.paletteHint")}</p>
          )}
          <label className="block space-y-1">
            <span className="flex justify-between text-[11px] text-zinc-400">
              {t("chart.colors.opacity")} <span className="num text-zinc-200">{opacity}%</span>
            </span>
            <input type="range" min={0} max={100} step={1} value={opacity} className="color-slider w-full"
              style={{ background: `linear-gradient(to right, transparent, ${color ?? "#a1a1aa"}), ${CHECKER}` }}
              onChange={(e) => onChange(color, Number(e.target.value))} />
          </label>
        </div>,
        document.body,
      )}
    </>
  );
}
