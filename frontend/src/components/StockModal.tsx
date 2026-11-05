"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { Check, Plus, Search, X } from "lucide-react";
import { portfolioAPI } from "@/lib/api";
import { ALL_INDIAN_STOCKS, INDIAN_STOCK_SECTORS } from "@/lib/indianStocks";

interface StockModalProps {
  isOpen:      boolean;
  onClose:     () => void;
  portfolioId: string;
  existingStocks: string[];
  onSuccess:   () => void;
}

export default function StockModal({
  isOpen,
  onClose,
  portfolioId,
  existingStocks,
  onSuccess,
}: StockModalProps) {
  const [ticker,  setTicker]  = useState("");
  const [search,  setSearch]  = useState("");
  const [sector, setSector] = useState("Banking");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

  if (!isOpen) return null;

  const sectorNames = Object.keys(INDIAN_STOCK_SECTORS);
  const sourceStocks = search.trim()
    ? ALL_INDIAN_STOCKS
    : INDIAN_STOCK_SECTORS[sector] ?? [];
  const filtered = sourceStocks.filter((stock) => {
    const query = search.toLowerCase();
    return (
      !existingStocks.includes(stock.ticker) &&
      (!query ||
        stock.ticker.toLowerCase().includes(query) ||
        stock.name.toLowerCase().includes(query) ||
        stock.sector.toLowerCase().includes(query))
    );
  });

  function toggleSelected(tickerToToggle: string) {
    setSelected((current) =>
      current.includes(tickerToToggle)
        ? current.filter((ticker) => ticker !== tickerToToggle)
        : [...current, tickerToToggle]
    );
  }

  async function handleAdd(tickerToAdd: string) {
    const t = tickerToAdd.trim().toUpperCase();
    if (!t) { toast.error("Enter a ticker symbol"); return; }
    setLoading(true);
    try {
      await portfolioAPI.addStock(portfolioId, t);
      toast.success(`${t} added! Model retraining started.`);
      setTicker("");
      onSuccess();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to add stock");
    } finally {
      setLoading(false);
    }
  }

  async function handleAddSelected() {
    if (!selected.length) {
      toast.error("Select at least one stock");
      return;
    }
    setLoading(true);
    try {
      await portfolioAPI.addStocks(portfolioId, selected);
      toast.success(`${selected.length} stocks added. Model retraining started.`);
      setSelected([]);
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to add selected stocks");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-fade-in"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="card w-full max-w-3xl animate-slide-up p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-bold text-text-primary">Add Stock</h2>
              <p className="text-xs text-text-muted mt-0.5">
                Model will retrain with the new stock universe
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Custom ticker input */}
          <div className="mb-5">
            <label className="label">Enter Ticker Symbol</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === "Enter" && handleAdd(ticker)}
                placeholder="e.g. RELIANCE.NS"
                className="input flex-1"
                disabled={loading}
              />
              <button
                onClick={() => handleAdd(ticker)}
                disabled={loading || !ticker.trim()}
                className="btn-primary px-4"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-bg-primary border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          <div className="glow-line mb-4" />

          {/* Quick-add from Indian market universe */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="label mb-0">Indian Market Stocks</label>
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-text-muted" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter…"
                  className="input pl-6 py-1 text-xs w-32"
                />
              </div>
            </div>

            <div className="flex gap-2 overflow-x-auto pb-2 mb-3">
              {sectorNames.map((name) => (
                <button
                  key={name}
                  onClick={() => setSector(name)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all whitespace-nowrap ${
                    sector === name && !search.trim()
                      ? "bg-accent-cyan/10 border-accent-cyan text-accent-cyan"
                      : "bg-bg-tertiary border-border text-text-secondary hover:border-border-bright"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>

            <div className="grid sm:grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-1">
              {filtered.map((stock) => {
                const checked = selected.includes(stock.ticker);
                return (
                  <button
                    key={stock.ticker}
                    onClick={() => toggleSelected(stock.ticker)}
                    disabled={loading}
                    className={`flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-left border
                               transition-all duration-150 active:scale-95 ${
                                 checked
                                   ? "bg-accent-cyan/10 border-accent-cyan text-text-primary"
                                   : "bg-bg-tertiary border-border text-text-secondary hover:border-accent-cyan hover:bg-accent-cyan/5"
                               }`}
                  >
                    <span>
                      <span className="block text-sm font-semibold text-text-primary">
                        {stock.name}
                      </span>
                      <span className="block text-xs font-mono">{stock.ticker}</span>
                    </span>
                    <span className={`w-6 h-6 rounded-md border flex items-center justify-center flex-shrink-0 ${
                      checked
                        ? "bg-accent-cyan text-bg-primary border-accent-cyan"
                        : "border-border text-text-muted"
                    }`}>
                      {checked ? <Check className="w-4 h-4" /> : null}
                    </span>
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <p className="text-xs text-text-muted">No suggestions match your filter</p>
              )}
            </div>
          </div>

          <div className="mt-5 flex items-center justify-between gap-3 border-t border-border pt-4">
            <p className="text-xs text-text-muted">
              {selected.length} selected
            </p>
            <div className="flex items-center gap-2">
              <button onClick={onClose} className="btn-ghost" disabled={loading}>
                Cancel
              </button>
              <button
                onClick={handleAddSelected}
                disabled={loading || selected.length === 0}
                className="btn-primary flex items-center gap-2"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-bg-primary border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                Add Selected
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
