import { useState } from "react";
import { t } from "../../i18n";
import { EditIcon, EyeIcon, PlusIcon, TrashIcon } from "../icons";
import IndicatorModal from "./IndicatorModal";

/** "SMA 100", "BB 20, 2", "RSI 14 (hl2)" - the most important settings of an indicator. */
function summary(def, params) {
  const values = def.params.filter((p) => p.type !== "source").map((p) => params[p.name]);
  const source = def.params.some((p) => p.type === "source") && params.source && params.source !== "close" ? ` (${params.source})` : "";
  return `${def.name} ${values.join(", ")}${source}`;
}

/**
 * Left-hand panel of the chart: one tile per saved indicator (settings, timeframe, edit / hide / delete)
 * and "add indicator". All changes are saved per user on the server (`api` = chartIndicatorsApi).
 */
export default function IndicatorSidebar({ definitions, items, chartInterval, api, onChanged }) {
  const [modal, setModal] = useState(null); // { item } for edit, {} for add

  const save = async ({ indicator_id, params, interval }) => {
    if (modal.item) {
      await api.update(modal.item.id, { params, interval, follow_chart: !interval });
    } else {
      await api.add({ indicator_id, params, interval });
    }
    onChanged();
  };

  return (
    <aside className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">{t("chart.indicators.title")}</h2>
        <button type="button" className="btn-ghost px-2 py-1 text-xs" disabled={!definitions.length} onClick={() => setModal({})}>
          <PlusIcon size={12} /> {t("chart.indicators.add")}
        </button>
      </div>

      {items.length === 0 && <p className="text-xs text-zinc-500">{t("chart.indicators.empty")}</p>}

      {items.map((item) => {
        const def = definitions.find((d) => d.id === item.indicator_id);
        if (!def) return null;
        return (
          <div key={item.id} className={`tile px-3 py-2.5 ${item.visible ? "" : "opacity-50"}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-zinc-100">{summary(def, item.params)}</div>
                <div className="text-[11px] text-zinc-500">
                  {item.interval
                    ? t("chart.indicators.ownInterval", { interval: t(`chart.intervals.${item.interval}`) })
                    : t("chart.indicators.chartInterval", { interval: t(`chart.intervals.${chartInterval}`) })}
                </div>
              </div>
              <div className="flex shrink-0 gap-0.5">
                <button type="button" className="btn-icon h-7 w-7" title={t("chart.indicators.edit")} onClick={() => setModal({ item })}>
                  <EditIcon size={14} />
                </button>
                <button type="button" className={`btn-icon h-7 w-7 ${item.visible ? "text-neon-green" : ""}`}
                  title={item.visible ? t("chart.indicators.hide") : t("chart.indicators.show")}
                  onClick={() => api.update(item.id, { visible: !item.visible }).then(onChanged)}>
                  <EyeIcon size={14} />
                </button>
                <button type="button" className="btn-icon h-7 w-7 hover:text-loss" title={t("chart.indicators.remove")}
                  onClick={() => api.remove(item.id).then(onChanged)}>
                  <TrashIcon size={14} />
                </button>
              </div>
            </div>
          </div>
        );
      })}

      {modal && (
        <IndicatorModal
          definitions={definitions}
          item={modal.item ?? null}
          onSave={save}
          onReset={modal.item ? () => api.reset(modal.item.id).then(onChanged) : null}
          onClose={() => setModal(null)}
        />
      )}
    </aside>
  );
}
