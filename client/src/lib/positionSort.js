import { toNumber } from "./format";

export const SORT_OPTIONS = [
  { value: "custom", label: "Własna kolejność" },
  { value: "date_desc", label: "Data zakupu: najnowsze" },
  { value: "date_asc", label: "Data zakupu: najstarsze" },
  { value: "price_asc", label: "Cena zakupu: najniższa" },
  { value: "price_desc", label: "Cena zakupu: najwyższa" },
  { value: "pnl_desc", label: "Zysk %: najwyższy" },
  { value: "pnl_asc", label: "Zysk %: najniższy" },
  { value: "qty_desc", label: "Ilość: największa" },
];

const byNumber = (get, direction) => (a, b) => {
  const x = get(a);
  const y = get(b);
  if (x === null && y === null) return 0;
  if (x === null) return 1; // brak wartości zawsze na końcu
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

/** "custom" = kolejność zapisana w bazie (ustawiana przeciąganiem). */
export function sortPositions(positions, mode) {
  const compare = COMPARATORS[mode];
  return compare ? [...positions].sort((a, b) => compare(a, b) || a.sort_order - b.sort_order) : positions;
}
