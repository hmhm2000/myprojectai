import { sum } from "./decimal";

/**
 * Sprzedaż w API to grupa wierszy (po jednym na pozycję) z tym samym group_id.
 * Tu składamy je z powrotem w jedną transakcję: cena, data, łączna opłata i podział na pozycje.
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
          note: sale.note,
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
