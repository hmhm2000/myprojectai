import { hasTranslation, t } from "../i18n";

const SOURCE_DEFAULT = "close";

/** "RSI(14)", "BB(20, 2) lower", "Price", "30" (translated) - a readable label of one side of a condition. */
export function operandLabel(operand, definitions = []) {
  if (operand.type === "price") return t("alerts.operandTypes.price");
  if (operand.type === "value") return String(operand.value);
  const def = definitions.find((d) => d.id === operand.id);
  if (!def) return operand.id;
  const values = def.params
    .filter((p) => p.type !== "source" || (operand.params?.[p.name] ?? p.default) !== SOURCE_DEFAULT)
    .map((p) => operand.params?.[p.name] ?? p.default);
  const name = `${def.name}(${values.join(", ")})`;
  if (def.outputs.length === 1) return name;
  const output = hasTranslation(`alerts.outputs.${operand.output}`) ? t(`alerts.outputs.${operand.output}`) : operand.output;
  return `${name} ${output}`;
}

/** Whole condition, e.g. "RSI(14) < 30" in the UI language. */
export function conditionText(condition, definitions = []) {
  return [
    operandLabel(condition.left, definitions),
    t(`alerts.operators.${condition.op}`),
    operandLabel(condition.right, definitions),
  ].join(" ");
}
