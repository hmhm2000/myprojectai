import { customSeriesDefaultOptions } from "lightweight-charts";

// Fill between two lines (Pine's fill()) as a Lightweight Charts custom series.
// Data: { time, upper, lower, fill? } - `fill` color per point (e.g. green / red by sign); without it the
// series option `color` is used. A point without upper/lower is a gap.

class BandRenderer {
  data = null;
  options = null;

  update(data, options) {
    this.data = data;
    this.options = options;
  }

  draw(target, priceToCoordinate) {
    const { data, options } = this;
    if (!data?.visibleRange || !data.bars.length) return;
    target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
      const from = Math.max(0, data.visibleRange.from - 1);
      const to = Math.min(data.bars.length, data.visibleRange.to + 1);
      const points = [];
      for (let i = from; i < to; i++) {
        const { x, originalData: d } = data.bars[i];
        const up = d.upper == null ? null : priceToCoordinate(d.upper);
        const low = d.lower == null ? null : priceToCoordinate(d.lower);
        points.push(up == null || low == null ? null : { x: x * hr, up: up * vr, low: low * vr, color: d.fill ?? options.color });
      }
      // Segment k (between points k-1 and k) takes the color of point k; equal neighbours form one polygon.
      let run = [];
      const flush = () => {
        if (run.length > 1) {
          ctx.beginPath();
          ctx.moveTo(run[0].x, run[0].up);
          for (const p of run) ctx.lineTo(p.x, p.up);
          for (let k = run.length - 1; k >= 0; k--) ctx.lineTo(run[k].x, run[k].low);
          ctx.closePath();
          ctx.fillStyle = run[run.length - 1].color;
          ctx.fill();
        }
        run = [];
      };
      for (let k = 1; k < points.length; k++) {
        const prev = points[k - 1];
        const point = points[k];
        if (!prev || !point) {
          flush();
          continue;
        }
        if (run.length && run[run.length - 1] === prev && run[run.length - 1].color === point.color) run.push(point);
        else {
          flush();
          run = [prev, point];
        }
      }
      flush();
    });
  }
}

export class BandSeries {
  constructor() {
    this._renderer = new BandRenderer();
  }

  priceValueBuilder(d) {
    return [d.lower, d.upper, d.upper];
  }

  isWhitespace(d) {
    return d.upper == null || d.lower == null;
  }

  renderer() {
    return this._renderer;
  }

  update(data, options) {
    this._renderer.update(data, options);
  }

  defaultOptions() {
    return { ...customSeriesDefaultOptions, color: "rgba(161,161,170,0.1)" };
  }
}
