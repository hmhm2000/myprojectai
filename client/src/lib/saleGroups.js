import { sum } from "./decimal";

/**
 * In the API a sale is a group of rows (one per position) sharing a group_id.
 * Here they are put back together into one transaction: price, date, total fee and split per position.
 */
export function collectSaleGroups(coin) {
  const groups = new Map();
  for (const position of coin.positions) {
    for (const sale of position.sales) {
      if (!groups.has(sale.group_id)) {
        groups.set(sale.group_id, {
          group_id: sale.group_id,
          price: sale.price,
          sold_at: sale.sold_at,
          exit_reason: sale.exit_reason,
          parts: [],
        });
      }
      groups.get(sale.group_id).parts.push({ position_id: position.id, quantity: sale.quantity, fee_quote: sale.fee_quote });
    }
  }
  for (const group of groups.values()) {
    group.quantity = sum(group.parts.map((p) => p.quantity));
    group.fee_quote = sum(group.parts.map((p) => p.fee_quote));
  }
  return groups;
}
