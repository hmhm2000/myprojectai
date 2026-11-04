import { t } from "../../i18n";

// Harmonic patterns (see server indicators/custom/harmonics.py) as one primitive on the candle series:
// a canvas layer that draws only the newest patterns in view, so panning stays smooth however many
// patterns were found. Scrolling back shows the older ones - the limit counts what is on screen.

const STATUS_ICON = { target2: "✅✅", target1: "✅", target1_open: "✅⏳", failed: "❌", missed: "⛔", timeout: "🕝",
  waiting: "⏳", open: "⏳" };
const LIVE = new Set(["waiting", "open", "target1_open", "potential"]);
const FONT = "11px sans-serif";
const LEVEL_BARS = 30;                  // length of the entry / stop / target lines

/** Pattern not finished yet: drawn in full color with its levels, refreshed with the newest candles. */
export const isLive = (pattern) => LIVE.has(pattern.status);

const capitalized = (text) => text[0].toUpperCase() + text.slice(1);

function line(ctx, from, to, width, dash = []) {
  ctx.setLineDash(dash);
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(from.x, from.y);
  ctx.lineTo(to.x, to.y);
  ctx.stroke();
}

function fillTriangle(ctx, a, b, c) {
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.lineTo(c.x, c.y);
  ctx.closePath();
  ctx.fill();
}

function label(ctx, text, x, y, color, background) {
  const width = ctx.measureText(text).width + 8;
  ctx.fillStyle = background;
  ctx.fillRect(x - width / 2, y - 8, width, 16);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

class Renderer {
  constructor(owner) {
    this.owner = owner;
  }

  draw(target) {
    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => this.owner.drawAll(ctx, mediaSize.width));
  }
}

export class HarmonicPrimitive {
  patterns = [];
  host = null;
  view = { renderer: () => this.renderer, zOrder: () => "normal" };
  renderer = new Renderer(this);

  constructor(api, { bull, color, width, params }) {
    this.api = api;
    this.bull = bull;
    this.color = color;
    this.width = width;
    this.params = params;
  }

  attached(host) {
    this.host = host;
  }

  detached() {
    this.host = null;
  }

  paneViews() {
    return [this.view];
  }

  setPatterns(patterns) {
    this.patterns = patterns.filter((p) => p.bull === this.bull).sort((a, b) => a.points.at(-1)[0] - b.points.at(-1)[0]);
    this.host?.requestUpdate();
  }

  // Index of the candle containing `unix`; a pattern from another timeframe lands on the nearest candle.
  barIndex(unix) {
    const bars = this.api.getBars();
    let lo = 0;
    let hi = bars.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (bars[mid].unix <= unix) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  }

  point(scale, [unix, price]) {
    const x = scale.logicalToCoordinate(this.barIndex(unix));
    const y = this.host.series.priceToCoordinate(price);
    return x === null || y === null ? null : { x, y };
  }

  drawAll(ctx, width) {
    if (!this.host || !this.api.getBars().length) return;
    const { max_patterns: limit, only_active: onlyActive } = this.params;
    const scale = this.host.chart.timeScale();
    ctx.save();
    ctx.font = FONT;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    let shown = 0;
    for (let i = this.patterns.length - 1; i >= 0 && shown < limit; i--) {
      const pattern = this.patterns[i];
      if (onlyActive && !isLive(pattern)) continue;
      const points = pattern.points.map((p) => this.point(scale, p));
      if (points.includes(null)) continue;
      const xs = points.map((p) => p.x);
      if (Math.max(...xs) < 0 || Math.min(...xs) > width) continue;
      this.drawPattern(ctx, pattern, points, scale);
      shown += 1;
    }
    ctx.restore();
  }

  drawPattern(ctx, pattern, points, scale) {
    const { show_labels: showLabels, show_points: showPoints, show_ratios: showRatios, show_levels: showLevels } = this.params;
    const live = isLive(pattern);
    const [x, a, b, c, d] = points;
    ctx.globalAlpha = live ? 1 : 0.6;
    ctx.strokeStyle = this.color;
    ctx.fillStyle = this.color;

    ctx.save();
    ctx.globalAlpha *= 0.12;
    fillTriangle(ctx, x, a, b);
    if (d) fillTriangle(ctx, b, c, d);
    ctx.restore();
    points.slice(1).forEach((p, i) => line(ctx, points[i], p, this.width));

    if (showRatios && d) this.drawRatios(ctx, pattern, points);
    if (showPoints) {
      ["X", "A", "B", "C", "D"].slice(0, points.length).forEach((name, i) => {
        const up = (i % 2 === 1) === this.bull;      // highs get the letter above
        label(ctx, name, points[i].x, points[i].y + (up ? -12 : 12), "#ffffff", this.color);
      });
    }
    if (showLevels && live) this.drawLevels(ctx, pattern, points.at(-1), scale);
    if (showLabels) {
      const end = points.at(-1);
      const text = `${capitalized(pattern.kind)} ${Math.round(pattern.score)} ${STATUS_ICON[pattern.status] ?? ""}`.trim();
      label(ctx, text, end.x, end.y + (this.bull === Boolean(d) ? 30 : -30), "#ffffff", "rgba(24,24,27,0.85)");
    }
    ctx.setLineDash([]);
  }

  drawRatios(ctx, pattern, points) {
    const [x, a, b, c, d] = points;
    const prices = pattern.points.map((p) => p[1]);
    const ratio = (first, second) => Math.abs(first) / Math.abs(second);
    const [px, pa, pb, pc, pd] = prices;
    const parts = [[x, b, ratio(pa - pb, px - pa)], [a, c, ratio(pc - pb, pa - pb)], [b, d, ratio(pc - pd, pc - pb)],
      [x, d, ratio(pa - pd, px - pa)]];
    for (const [from, to, value] of parts) {
      line(ctx, from, to, 1, [3, 3]);
      label(ctx, value.toFixed(3), (from.x + to.x) / 2, (from.y + to.y) / 2, "#d4d4d8", "rgba(24,24,27,0.85)");
    }
  }

  drawLevels(ctx, pattern, from, scale) {
    const series = this.host.series;
    const start = this.barIndex(pattern.points.at(-1)[0]);
    const right = scale.logicalToCoordinate(start + LEVEL_BARS);
    if (right === null) return;
    const [low, high] = pattern.prz.map((price) => series.priceToCoordinate(price));
    if (low !== null && high !== null) {
      ctx.save();
      ctx.fillStyle = this.color;
      ctx.globalAlpha *= 0.15;
      ctx.fillRect(from.x, Math.min(low, high), right - from.x, Math.abs(high - low));
      ctx.restore();
    }
    const format = (price) => series.priceFormatter().format(price);
    const levels = [[t("chart.harmonicEntry"), pattern.entry, "#a1a1aa"], ["Stop", pattern.stop, "#f87171"],
      ["T1", pattern.t1, "#34d399"], ["T2", pattern.t2, "#34d399"]];
    ctx.textAlign = "left";
    for (const [name, price, color] of levels) {
      const y = price === null || price === undefined ? null : series.priceToCoordinate(price);
      if (y === null) continue;
      ctx.strokeStyle = color;
      line(ctx, { x: from.x, y }, { x: right, y }, 1, [4, 3]);
      ctx.fillStyle = color;
      ctx.fillText(`${name} ${format(price)}`, right + 4, y);
    }
    ctx.textAlign = "center";
    ctx.strokeStyle = this.color;
    ctx.fillStyle = this.color;
  }
}
