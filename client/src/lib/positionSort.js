import { toNumber } from "./format";

// Labels: portfolio.sort.<mode> in the locale files.
export const SORT_MODES = ["custom", "date_desc", "date_asc", "price_asc", "price_desc", "pnl_desc", "pnl_asc", "qty_desc"];

const byNumber = (get, direction) => (a, b) => {
  const x = get(a);
  const y = get(b);
  if (x === null && y === null) return 0;
  if (x === null) return 1; // missing values always last
  if (y === null) return -1;
  return direction * (x - y);
};

const COMPARATORS = {
  date_desc: byNumber((p) => new Date(p.bought_at).getTime(), -1),
  date_asc: byNumber((p) => new Date(p.bought_at).getTime(), 1),
  price_asc: byNumber((p) => toNumber(p.buy_price), 1),
  price_desc: byNumber((p) => toNumber(p.buy_price), -1),
  pnl_desc: byNumber((p) => toNumber(p.total_pnl_pct), -1),
  pnl_asc: byNumber((p) => toNumber(p.total_pnl_pct), 1),
  qty_desc: byNumber((p) => toNumber(p.open_quantity), -1),
};

/** "custom" = order stored in the database (set by drag & drop). */
export function sortPositions(positions, mode) {
  const compare = COMPARATORS[mode];
  return compare ? [...positions].sort((a, b) => compare(a, b) || a.sort_order - b.sort_order) : positions;
}
