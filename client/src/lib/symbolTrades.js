import { portfoliosApi } from "../api/endpoints";
import { collectSaleGroups } from "./saleGroups";

/**
 * All BUY / SELL events of one coin across the user's portfolios (from the existing portfolio API).
 * BUY = a position (purchase); SELL = a sale group (one sale can cover several positions).
 * Times are unix seconds; dates in the API are local time, so `new Date()` parses them correctly.
 */
export async function loadSymbolTrades(symbol) {
  const list = await portfoliosApi.list();
  const views = await Promise.all(list.map((p) => portfoliosApi.get(p.id)));
  const events = [];
  for (const view of views) {
    const coin = view.coins.find((c) => c.symbol === symbol);
    if (!coin) continue;
    for (const position of coin.positions) {
      events.push({
        id: `buy-${position.id}`,
        side: "BUY",
        time: Math.floor(new Date(position.bought_at).getTime() / 1000),
        portfolio: view.name,
        symbol,
        price: position.buy_price,
        quantity: position.quantity,
        position,
      });
    }
    for (const group of collectSaleGroups(coin).values()) {
      events.push({
        id: `sell-${group.group_id}`,
        side: "SELL",
        time: Math.floor(new Date(group.sold_at).getTime() / 1000),
        portfolio: view.name,
        symbol,
        price: group.price,
        quantity: group.quantity,
        group,
        positions: group.parts.map((part) => coin.positions.find((p) => p.id === part.position_id)).filter(Boolean),
      });
    }
  }
  return events.sort((a, b) => a.time - b.time);
}
