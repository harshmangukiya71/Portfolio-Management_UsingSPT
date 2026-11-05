"use client";

import { useState, useEffect } from "react";
import { formatINR, tickerColor } from "@/lib/utils";
import { X, TrendingUp, Wallet, ArrowRight, RefreshCw, AlertCircle } from "lucide-react";

interface ExitStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticker: string;
  allocationINR: number;
  remainingCount: number;
  onConfirm: (withdrawAmount: number) => Promise<void>;
  loading?: boolean;
}

export default function ExitStockModal({
  isOpen,
  onClose,
  ticker,
  allocationINR,
  remainingCount,
  onConfirm,
  loading = false,
}: ExitStockModalProps) {
  // Amount to withdraw to pocket balance (default 0 => 100% reinvested)
  const [withdrawAmount, setWithdrawAmount] = useState<number>(0);

  useEffect(() => {
    // Reset withdraw amount to 0 (default: 100% reinvest) whenever modal opens
    setWithdrawAmount(0);
  }, [isOpen, ticker]);

  if (!isOpen) return null;

  const totalValue = allocationINR;
  const safeWithdraw = Math.min(Math.max(0, Number(withdrawAmount) || 0), totalValue);
  const reinvestAmount = Math.max(0, totalValue - safeWithdraw);
  const reinvestPct = totalValue > 0 ? (reinvestAmount / totalValue) * 100 : 0;
  const withdrawPct = totalValue > 0 ? (safeWithdraw / totalValue) * 100 : 0;

  const setPercentWithdraw = (pct: number) => {
    const amt = Math.round((totalValue * pct) / 100);
    setWithdrawAmount(amt);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onConfirm(safeWithdraw);
    onClose();
  };

  const color = tickerColor(ticker);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="card p-6 sm:p-7 max-w-lg w-full relative border border-border shadow-2xl animate-scale-in">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors"
          title="Cancel"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center text-sm font-bold text-bg-primary shadow"
            style={{ background: color }}
          >
            {ticker.replace(".NS", "").slice(0, 3)}
          </div>
          <div>
            <h2 className="text-base font-bold text-text-primary">
              Exit {ticker.replace(".NS", "")}
            </h2>
            <p className="text-xs text-text-muted">
              Choose how much to withdraw to pocket vs. reinvest in remaining stocks
            </p>
          </div>
        </div>

        {/* Current Total Value Card */}
        <div className="p-4 rounded-xl bg-bg-tertiary border border-border mb-5 flex items-center justify-between">
          <div>
            <p className="text-xs text-text-muted uppercase tracking-wider">Current Holding Value</p>
            <p className="text-xl font-bold font-mono text-accent-cyan mt-0.5">
              {formatINR(totalValue)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">Remaining Universe</p>
            <p className="text-sm font-semibold text-text-primary mt-0.5">
              {remainingCount} stocks
            </p>
          </div>
        </div>

        <form onSubmit={handleFormSubmit} className="space-y-5">
          {/* Quick Percentage Presets */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-text-secondary">
                Reinvestment Distribution
              </label>
              <span className="text-[11px] text-text-muted">Quick presets:</span>
            </div>

            <div className="grid grid-cols-4 gap-2">
              <button
                type="button"
                onClick={() => setPercentWithdraw(0)}
                className={`py-1.5 px-2 rounded-lg text-xs font-medium border transition-all ${
                  safeWithdraw === 0
                    ? "bg-accent-cyan/15 border-accent-cyan text-accent-cyan font-bold"
                    : "bg-bg-tertiary border-border text-text-secondary hover:text-text-primary"
                }`}
              >
                100% Reinvest
              </button>
              <button
                type="button"
                onClick={() => setPercentWithdraw(25)}
                className={`py-1.5 px-2 rounded-lg text-xs font-medium border transition-all ${
                  Math.abs(withdrawPct - 25) < 1
                    ? "bg-accent-cyan/15 border-accent-cyan text-accent-cyan font-bold"
                    : "bg-bg-tertiary border-border text-text-secondary hover:text-text-primary"
                }`}
              >
                75% Reinvest
              </button>
              <button
                type="button"
                onClick={() => setPercentWithdraw(50)}
                className={`py-1.5 px-2 rounded-lg text-xs font-medium border transition-all ${
                  Math.abs(withdrawPct - 50) < 1
                    ? "bg-accent-cyan/15 border-accent-cyan text-accent-cyan font-bold"
                    : "bg-bg-tertiary border-border text-text-secondary hover:text-text-primary"
                }`}
              >
                50% / 50%
              </button>
              <button
                type="button"
                onClick={() => setPercentWithdraw(100)}
                className={`py-1.5 px-2 rounded-lg text-xs font-medium border transition-all ${
                  safeWithdraw === totalValue
                    ? "bg-danger/15 border-danger text-danger font-bold"
                    : "bg-bg-tertiary border-border text-text-secondary hover:text-text-primary"
                }`}
              >
                100% Pocket
              </button>
            </div>
          </div>

          {/* Amount to Withdraw Input */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-text-muted flex items-center gap-1.5">
                <Wallet className="w-3.5 h-3.5 text-warning" />
                Withdraw to Pocket Balance (Cash)
              </label>
              <span className="text-xs font-mono text-warning font-semibold">
                {formatINR(safeWithdraw)} ({withdrawPct.toFixed(0)}%)
              </span>
            </div>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">₹</span>
              <input
                type="number"
                min="0"
                max={totalValue}
                step="any"
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(Math.max(0, Number(e.target.value) || 0))}
                className="input pl-8 text-sm font-mono"
                placeholder="0"
              />
            </div>
          </div>

          {/* Reinvestment Preview Box */}
          <div className="p-3.5 rounded-xl bg-accent-cyan/5 border border-accent-cyan/20 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-text-secondary flex items-center gap-1.5">
                <RefreshCw className="w-3.5 h-3.5 text-accent-cyan" />
                Amount to Reinvest:
              </span>
              <span className="font-mono font-bold text-accent-cyan text-sm">
                {formatINR(reinvestAmount)} ({reinvestPct.toFixed(0)}%)
              </span>
            </div>
            <p className="text-[11px] text-text-muted leading-relaxed">
              💡 Reinvestment is distributed across the remaining{" "}
              <strong className="text-text-primary">{remainingCount} stocks</strong> in proportion
              to their current normalized model weights without retraining.
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="btn-ghost flex-1 py-2.5 text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary flex-1 py-2.5 text-sm font-semibold flex items-center justify-center gap-2 shadow-glow-cyan"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-bg-primary border-t-transparent animate-spin" />
                  <span>Processing…</span>
                </>
              ) : (
                <>
                  <span>Confirm Exit</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}