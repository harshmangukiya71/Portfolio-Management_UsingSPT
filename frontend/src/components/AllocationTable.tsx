"use client";

import { useState } from "react";
import { formatINR, formatPercent, tickerColor } from "@/lib/utils";
import type { StockAllocation } from "@/lib/api";
import { AlertTriangle, Trash2, TrendingUp, X } from "lucide-react";

interface AllocationTableProps {
  allocations:   StockAllocation[];
  capital:       number;
  onRemove?:     (ticker: string) => void;
  onRemoveAll?:  () => void;
  loading?:      boolean;
  stockCount?:   number;
}

export default function AllocationTable({
  allocations,
  capital,
  onRemove,
  onRemoveAll,
  loading,
  stockCount = 0,
}: AllocationTableProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  if (!allocations.length) {
    const hasStocks = stockCount > 0;
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <TrendingUp className="w-10 h-10 text-text-muted mb-3" />
        <p className="text-text-secondary font-medium">
          {hasStocks ? "No weights available yet" : "No stocks in portfolio"}
        </p>
        <p className="text-text-muted text-sm mt-1">
          {hasStocks ? "Train the model to calculate allocations" : "Add stocks to get started"}
        </p>
      </div>
    );
  }

  return (
    <>
      {/* ── Confirm modal ──────────────────────────────────────────────── */}
      {confirmOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-fade-in"
            onClick={() => setConfirmOpen(false)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="card w-full max-w-md animate-slide-up p-6">
              {/* header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-danger/10 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-5 h-5 text-danger" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-text-primary">Liquidate All Holdings</h2>
                    <p className="text-xs text-text-muted mt-0.5">This action cannot be undone</p>
                  </div>
                </div>
                <button
                  onClick={() => setConfirmOpen(false)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-all"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* body */}
              <div className="bg-danger/5 border border-danger/20 rounded-xl p-4 mb-5">
                <p className="text-sm text-text-secondary leading-relaxed">
                  You are about to <span className="text-danger font-semibold">exit all {allocations.length} positions</span> from your
                  portfolio. The full capital value of{" "}
                  <span className="text-text-primary font-semibold font-mono">{formatINR(capital)}</span> will be
                  moved to your pocket balance and the portfolio will be reset.
                </p>
              </div>

              {/* holdings preview */}
              <div className="max-h-36 overflow-y-auto mb-5 space-y-1.5 pr-1">
                {allocations.map((a) => {
                  const color = tickerColor(a.ticker);
                  return (
                    <div key={a.ticker} className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-bg-tertiary">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold text-bg-primary flex-shrink-0"
                          style={{ background: color }}
                        >
                          {a.ticker.slice(0, 2)}
                        </div>
                        <span className="text-xs font-mono text-text-primary">{a.ticker.replace(".NS", "")}</span>
                      </div>
                      <span className="text-xs font-mono text-accent-cyan">{formatINR(a.allocation_inr)}</span>
                    </div>
                  );
                })}
              </div>

              {/* actions */}
              <div className="flex gap-2">
                <button
                  onClick={() => setConfirmOpen(false)}
                  className="btn-ghost flex-1"
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    setConfirmOpen(false);
                    onRemoveAll?.();
                  }}
                  disabled={loading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-danger/10 border border-danger/30 text-danger text-sm font-semibold hover:bg-danger/20 hover:border-danger/60 transition-all duration-150 active:scale-95"
                >
                  <Trash2 className="w-4 h-4" />
                  Yes, Liquidate All
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Table ─────────────────────────────────────────────────────── */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Stock</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Weight</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Allocation (₹)</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">Distribution</th>
              {onRemove && (
                <th className="py-3 px-4 text-right">
                  {onRemoveAll && allocations.length > 1 && (
                    <button
                      onClick={() => setConfirmOpen(true)}
                      disabled={loading}
                      title="Liquidate all holdings"
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-danger/10 border border-danger/25 text-danger text-[11px] font-semibold hover:bg-danger/20 hover:border-danger/50 transition-all duration-150 active:scale-95 disabled:opacity-40"
                    >
                      <Trash2 className="w-3 h-3" />
                      Liquidate All
                    </button>
                  )}
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {allocations.map((a) => {
              const color = tickerColor(a.ticker);
              const pct   = a.weight * 100;
              return (
                <tr
                  key={a.ticker}
                  className="group hover:bg-bg-tertiary/50 transition-colors duration-150"
                >
                  {/* Ticker */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-bg-primary flex-shrink-0"
                        style={{ background: color }}
                      >
                        {a.ticker.slice(0, 2)}
                      </div>
                      <div>
                        <p className="font-semibold text-text-primary font-mono">
                          {a.ticker.replace(".NS", "")}
                        </p>
                        <p className="text-xs text-text-muted">{a.ticker}</p>
                      </div>
                    </div>
                  </td>

                  {/* Weight */}
                  <td className="py-3 px-4 text-right">
                    <span className="font-mono font-semibold text-text-primary">
                      {formatPercent(a.weight)}
                    </span>
                  </td>

                  {/* Allocation */}
                  <td className="py-3 px-4 text-right">
                    <span className="font-mono text-accent-cyan font-semibold">
                      {formatINR(a.allocation_inr)}
                    </span>
                  </td>

                  {/* Bar */}
                  <td className="py-3 px-4 min-w-[120px]">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-bg-tertiary rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${pct}%`, background: color }}
                        />
                      </div>
                      <span className="text-xs text-text-muted w-10 text-right">
                        {pct.toFixed(1)}%
                      </span>
                    </div>
                  </td>

                  {/* Remove */}
                  {onRemove && (
                    <td className="py-3 px-4">
                      <button
                        onClick={() => onRemove(a.ticker)}
                        disabled={loading}
                        className="btn-danger opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                        title={`Exit ${a.ticker}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>

          {/* Footer */}
          <tfoot>
            <tr className="border-t border-border">
              <td className="py-3 px-4 text-sm font-semibold text-text-secondary">Total</td>
              <td className="py-3 px-4 text-right font-mono font-bold text-text-primary">
                {formatPercent(allocations.reduce((s, a) => s + a.weight, 0))}
              </td>
              <td className="py-3 px-4 text-right font-mono font-bold text-accent-cyan">
                {formatINR(capital)}
              </td>
              <td colSpan={onRemove ? 2 : 1} />
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
