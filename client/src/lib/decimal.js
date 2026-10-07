// Dokładne działania na kwotach zapisanych jako tekst ("0.1" + "0.2" = "0.3").
// Używane tam, gdzie front musi coś policzyć zanim wyśle dane (np. podział ilości przy sprzedaży).

const SCALE = 18;
const FACTOR = 10n ** BigInt(SCALE);

function toBig(value) {
  const text = String(value ?? "0").trim() || "0";
  const negative = text.startsWith("-");
  const [int, frac = ""] = text.replace(/^[-+]/, "").split(".");
  const big = BigInt(int || "0") * FACTOR + BigInt((frac + "0".repeat(SCALE)).slice(0, SCALE) || "0");
  return negative ? -big : big;
}

function fromBig(big) {
  const negative = big < 0n;
  const digits = (negative ? -big : big).toString().padStart(SCALE + 1, "0");
  let text = `${digits.slice(0, -SCALE)}.${digits.slice(-SCALE)}`.replace(/0+$/, "").replace(/\.$/, "");
  if (text === "") text = "0";
  return negative && text !== "0" ? `-${text}` : text;
}

export const add = (a, b) => fromBig(toBig(a) + toBig(b));
export const sub = (a, b) => fromBig(toBig(a) - toBig(b));
export const cmp = (a, b) => {
  const diff = toBig(a) - toBig(b);
  return diff === 0n ? 0 : diff > 0n ? 1 : -1;
};
export const min = (a, b) => (cmp(a, b) <= 0 ? fromBig(toBig(a)) : fromBig(toBig(b)));
export const isPositive = (a) => toBig(a) > 0n;
export const sum = (values) => values.reduce((acc, v) => add(acc, v), "0");
