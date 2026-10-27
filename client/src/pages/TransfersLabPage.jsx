import { useCallback, useEffect, useMemo, useState } from "react";
import { errorMessage } from "../api/client";
import { transfersLabApi } from "../api/endpoints";
import { ErrorBanner } from "../components/ui";
import { hasTranslation, t } from "../i18n";
import { fmtDate, fmtDateTime, fmtMoney, fmtQty, toNumber } from "../lib/format";

const exchangeName = (e) => (hasTranslation(`transfersLab.exchanges.${e}`) ? t(`transfersLab.exchanges.${e}`) : e);
const short = (text, n = 10) => (text && text.length > n + 6 ? `${text.slice(0, n)}…${text.slice(-4)}` : text);

function Section({ title, hint, children }) {
  return (
    <section className="tile p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{title}</h2>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
      <div className="mt-3 overflow-x-auto">{children}</div>
    </section>
  );
}

function Table({ columns, prefix, children, minWidth = 640 }) {
  return (
    <table className="w-full text-sm" style={{ minWidth }}>
      <thead className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
        <tr>{columns.map((k) => <th key={k} className="px-2 py-1 font-medium">{t(`${prefix}.${k}`)}</th>)}</tr>
      </thead>
      <tbody className="num whitespace-nowrap">{children}</tbody>
    </table>
  );
}

const Row = ({ children, tone = "" }) => <tr className={`border-t border-white/[0.04] ${tone}`}>{children}</tr>;
const Cell = ({ children, className = "" }) => <td className={`px-2 py-1.5 ${className}`}>{children}</td>;

function Balances({ rows }) {
  const groups = useMemo(() => {
    const map = new Map();
    for (const r of rows) map.set(r.exchange, [...(map.get(r.exchange) ?? []), r]);
    return [...map];
  }, [rows]);
  return (
    <Section title={t("transfersLab.balances.title")} hint={t("transfersLab.balances.hint")}>
      <div className="space-y-5">
        {groups.map(([exchange, items]) => (
          <div key={exchange} className="overflow-x-auto">
            <div className="mb-1 flex items-baseline gap-2">
              <span className="font-semibold text-zinc-100">{items[0].name}</span>
              {!items[0].has_transfer_files && <span className="text-xs text-amber-300">{t("transfersLab.balances.noFiles")}</span>}
            </div>
            <Table prefix="transfersLab.balances.columns" columns={["coin", "traded", "deposits", "withdrawals", "balance", "value"]} minWidth={520}>
              {items.filter((r) => toNumber(r.traded) || toNumber(r.deposits) || toNumber(r.withdrawals)).map((r) => {
                const balance = toNumber(r.balance);
                return (
                  <Row key={r.coin}>
                    <Cell className="font-semibold text-zinc-100">{r.coin}</Cell>
                    <Cell>{fmtQty(r.traded)}</Cell>
                    <Cell className="text-sky-300">{toNumber(r.deposits) ? `+${fmtQty(r.deposits)}` : "—"}</Cell>
                    <Cell className="text-amber-300">{toNumber(r.withdrawals) ? `−${fmtQty(r.withdrawals)}` : "—"}</Cell>
                    <Cell className={`font-semibold ${balance < -1e-9 ? "text-loss" : "text-zinc-100"}`}>{fmtQty(r.balance)}</Cell>
                    <Cell className="text-zinc-400">{r.value === null ? "—" : fmtMoney(r.value)}</Cell>
                  </Row>
                );
              })}
            </Table>
          </div>
        ))}
      </div>
    </Section>
  );
}

function AddressRow({ row, onSaved }) {
  const [label, setLabel] = useState(row.label ?? "");
  const save = (owner, text = label) => transfersLabApi.label({ address: row.address, owner: owner || null, label: text })
    .then(onSaved);
  return (
    <Row tone={row.owner === "own" ? "bg-neon-green/[0.03]" : row.owner === "foreign" ? "opacity-60" : ""}>
      <Cell>
        <div className="font-medium text-zinc-100" title={row.address}>{short(row.address, 12)}</div>
        <div className="text-[11px] text-zinc-500">{row.networks.join(", ")} · {row.exchanges.map(exchangeName).join(", ")}</div>
      </Cell>
      <Cell>{row.coins.map((c) => <div key={c.coin}>{fmtQty(c.sent)} {c.coin} <span className="text-zinc-500">({c.count}×)</span></div>)}</Cell>
      <Cell className="text-zinc-400">{row.coins.map((c) => <div key={c.coin}>{toNumber(c.returned) ? `${fmtQty(c.returned)} ${c.coin}` : "—"}</div>)}</Cell>
      <Cell className="text-zinc-400">{fmtDate(row.first)} – {fmtDate(row.last)}</Cell>
      <Cell>
        <select className="py-1 text-xs" value={row.owner ?? ""} onChange={(e) => save(e.target.value)}>
          {["", "own", "foreign"].map((o) => <option key={o} value={o}>{t(`transfersLab.addresses.owner.${o || "none"}`)}</option>)}
        </select>
      </Cell>
      <Cell>
        <input className="w-36 py-1 text-xs" value={label} placeholder={t("transfersLab.addresses.labelPlaceholder")}
          maxLength={100} onChange={(e) => setLabel(e.target.value)}
          onBlur={() => label !== (row.label ?? "") && save(row.owner, label)} />
      </Cell>
    </Row>
  );
}

/** Test view of deposits / withdrawals across exchanges - read only, nothing changes in the portfolios. */
export default function TransfersLabPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => {
    transfersLabApi.overview().then(setData).catch((err) => setError(errorMessage(err)));
  }, []);
  useEffect(load, [load]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">{t("transfersLab.title")}</h1>
        <p className="max-w-3xl text-xs text-zinc-500">{t("transfersLab.intro")}</p>
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>
      {!data && !error && <p className="text-sm text-zinc-500">{t("transfersLab.loading")}</p>}
      {data && (
        <>
          <Section title={t("transfersLab.files.title", { count: data.files.length })}
            hint={t("transfersLab.files.summary", data.counts)}>
            <ul className="space-y-0.5 text-xs text-zinc-400">
              {data.files.map((f) => (
                <li key={f.file}>
                  <span className="chip mr-2">{exchangeName(f.exchange)}</span>{f.file} · {f.completed}
                  {f.other_status > 0 && <span className="text-amber-300"> · {t("transfersLab.files.otherStatus", { count: f.other_status })}</span>}
                </li>
              ))}
            </ul>
          </Section>

          <Balances rows={data.balances} />

          <Section title={t("transfersLab.private.title")}>
            {data.private.length === 0 ? <p className="text-sm text-zinc-500">{t("transfersLab.private.empty")}</p> : (
              <Table prefix="transfersLab.private.columns" columns={["coin", "sent", "returned", "balance", "value"]}>
                {data.private.map((r) => (
                  <Row key={r.coin}>
                    <Cell className="font-semibold text-zinc-100">{r.coin}</Cell>
                    <Cell>{fmtQty(r.sent)}</Cell>
                    <Cell className="text-zinc-400">{fmtQty(r.returned)}</Cell>
                    <Cell className="font-semibold text-zinc-100">{fmtQty(r.balance)}</Cell>
                    <Cell className="text-zinc-400">{r.value === null ? "—" : fmtMoney(r.value)}</Cell>
                  </Row>
                ))}
              </Table>
            )}
          </Section>

          <Section title={t("transfersLab.addresses.title", { count: data.addresses.length })} hint={t("transfersLab.addresses.hint")}>
            <Table prefix="transfersLab.addresses.columns" columns={["address", "coins", "returned", "dates", "owner", "label"]} minWidth={900}>
              {data.addresses.map((a) => <AddressRow key={a.address} row={a} onSaved={load} />)}
            </Table>
          </Section>

          <Section title={t("transfersLab.moves.title", { count: data.moves.length })} hint={t("transfersLab.moves.hint")}>
            <Table prefix="transfersLab.moves.columns" columns={["date", "coin", "route", "amount", "minutes", "txid"]}>
              {data.moves.map((m) => (
                <Row key={m.txid}>
                  <Cell className="text-zinc-400">{fmtDateTime(m.sent_at)}</Cell>
                  <Cell className="font-semibold text-zinc-100">{m.coin}</Cell>
                  <Cell>{exchangeName(m.from)} → {exchangeName(m.to)}</Cell>
                  <Cell>{fmtQty(m.arrived)}</Cell>
                  <Cell className="text-zinc-400">{t("transfersLab.moves.minutes", { n: m.minutes })}</Cell>
                  <Cell className="text-zinc-500" title={m.txid}>{short(m.txid)}</Cell>
                </Row>
              ))}
            </Table>
          </Section>

          <Section title={t("transfersLab.returns.title", { count: data.returns.length })} hint={t("transfersLab.returns.hint")}>
            <Table prefix="transfersLab.returns.columns" columns={["date", "coin", "to", "amount", "from"]} minWidth={760}>
              {data.returns.map((r, i) => (
                <Row key={i}>
                  <Cell className="text-zinc-400">{fmtDateTime(r.arrived_at)}</Cell>
                  <Cell className="font-semibold text-zinc-100">{r.coin}</Cell>
                  <Cell>{exchangeName(r.to)}</Cell>
                  <Cell>{fmtQty(r.amount)}</Cell>
                  <Cell className="text-xs text-zinc-400">
                    {r.from.map((f, j) => (
                      <div key={j}>{fmtQty(f.amount)} · {short(f.address, 8)} ({exchangeName(f.exchange)}, {fmtDate(f.sent_at)})</div>
                    ))}
                  </Cell>
                </Row>
              ))}
            </Table>
          </Section>

          <Section title={t("transfersLab.external.title", { count: data.external.length })} hint={t("transfersLab.external.hint")}>
            <Table prefix="transfersLab.external.columns" columns={["date", "exchange", "coin", "amount", "network"]}>
              {data.external.map((d) => (
                <Row key={d.txid || `${d.time}-${d.coin}`}>
                  <Cell className="text-zinc-400">{fmtDateTime(d.time)}</Cell>
                  <Cell>{exchangeName(d.exchange)}</Cell>
                  <Cell className="font-semibold text-zinc-100">{d.coin}</Cell>
                  <Cell>{fmtQty(d.amount)}</Cell>
                  <Cell className="text-zinc-400">{d.network}</Cell>
                </Row>
              ))}
            </Table>
          </Section>
        </>
      )}
    </div>
  );
}
