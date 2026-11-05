"use client";

import { useEffect, useState, useCallback } from "react";
import useSWR from "swr";
import toast from "react-hot-toast";
import {
  RefreshCw, Plus, TrendingUp, Activity,
  DollarSign, BarChart2, AlertTriangle, Brain, X,
} from "lucide-react";

import Sidebar from "@/components/Sidebar";
import MetricCard from "@/components/MetricCard";
import AllocationTable from "@/components/AllocationTable";
import WeightsChart from "@/components/charts/WeightsChart";
import WealthChart from "@/components/charts/WealthChart";
import StockModal from "@/components/StockModal";
import { portfolioAPI, modelAPI, type Portfolio } from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { INDIAN_STOCK_SECTORS } from "@/lib/indianStocks";

export default function DashboardPage() {
  // ── State ───────────────────────────────────────────────────────────────
  const [portfolioId,  setPortfolioId]  = useState<string | null>(null);
  const [addModal,     setAddModal]     = useState(false);
  const [rebalancing,  setRebalancing]  = useState(false);
  const [capitalInput, setCapitalInput] = useState("");
  const [savingCapital, setSavingCapital] = useState(false);
  const [creatingPortfolio, setCreatingPortfolio] = useState(false);
  const [selectedStocks, setSelectedStocks] = useState<string[]>([]);
  const [dismissSetup, setDismissSetup] = useState(false);

  // ── SWR data fetching ───────────────────────────────────────────────────
  const { data: portfolios, mutate: mutatePortfolios } = useSWR(
    "portfolios",
    () => portfolioAPI.list().then((r) => r.data),
    { refreshInterval: 30_000 }
  );

  const activePortfolio: Portfolio | undefined = portfolios?.[0];

  useEffect(() => {
    if (activePortfolio) {
      setPortfolioId(activePortfolio.id);
      if (!capitalInput) setCapitalInput(String(activePortfolio.capital));
    }
  }, [activePortfolio]);

  const { data: weightsData, mutate: mutateWeights } = useSWR(
    portfolioId ? `weights-${portfolioId}` : null,
    () => portfolioAPI.getWeights(portfolioId!).then((r) => r.data),
    { refreshInterval: 60_000 }
  );

  const { data: perfData, mutate: mutatePerf } = useSWR(
    portfolioId ? `perf-${portfolioId}` : null,
    () => portfolioAPI.getPerformance(portfolioId!).then((r) => r.data),
    { refreshInterval: 120_000 }
  );

  const { data: modelStatus } = useSWR(
    "model-status",
    () => modelAPI.status().then((r) => r.data),
    { refreshInterval: 10_000 }
  );

  // ── Handlers ────────────────────────────────────────────────────────────
  const handleRebalance = useCallback(async () => {
    if (!portfolioId) return;
    setRebalancing(true);
    try {
      const res = await portfolioAPI.rebalance(portfolioId);
      toast.success(`Rebalanced! Turnover: ${(res.data.turnover * 100).toFixed(2)}%`);
      mutateWeights();
      mutatePerf();
    } catch {
      toast.error("Rebalance failed");
    } finally {
      setRebalancing(false);
    }
  }, [portfolioId, mutateWeights, mutatePerf]);

  const handleLiquidateAll = useCallback(async () => {
    if (!portfolioId) return;
    const currentAllocations = weightsData?.allocations ?? [];
    if (!currentAllocations.length) return;
    setRebalancing(true);
    try {
      // Exit each stock sequentially, moving full allocation to pocket
      for (const alloc of currentAllocations) {
        await portfolioAPI.exitStock(portfolioId, alloc.ticker, alloc.allocation_inr);
      }
      toast.success(`All ${currentAllocations.length} holdings liquidated. Capital moved to pocket.`);
      await mutatePortfolios();
      await mutateWeights();
      await mutatePerf();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to liquidate all holdings");
    } finally {
      setRebalancing(false);
    }
  }, [portfolioId, weightsData, mutatePortfolios, mutateWeights, mutatePerf]);

  const handleRemoveStock = useCallback(async (ticker: string) => {
    if (!portfolioId) return;
    const allocation = weightsData?.allocations.find((item) => item.ticker === ticker);
    const maxWithdraw = allocation?.allocation_inr ?? 0;
    const input = prompt(
      `Exit ${ticker}\n\nCurrent allocation: ${formatINR(maxWithdraw)}\nAmount to withdraw to pocket (0 keeps all value reinvested):`,
      "0"
    );
    if (input === null) return;
    const withdrawAmount = Math.max(0, Number(input) || 0);
    try {
      await portfolioAPI.exitStock(portfolioId, ticker, withdrawAmount);
      toast.success(`${ticker} exited. Reinvested proportionally across remaining stocks.`);
      mutatePortfolios();
      mutateWeights();
      mutatePerf();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to exit stock");
    }
  }, [portfolioId, weightsData?.allocations, mutatePortfolios, mutateWeights, mutatePerf]);

  const handleSaveCapital = useCallback(async () => {
    if (!portfolioId || !capitalInput) return;
    setSavingCapital(true);
    try {
      await portfolioAPI.updateCapital(portfolioId, Number(capitalInput));
      toast.success("Capital updated");
      mutatePortfolios();
      mutateWeights();
    } catch {
      toast.error("Failed to update capital");
    } finally {
      setSavingCapital(false);
    }
  }, [portfolioId, capitalInput, mutatePortfolios, mutateWeights]);

  const handleOpenAddStock = useCallback(async () => {
    if (portfolioId) {
      setAddModal(true);
      return;
    }

    const capital = Number(capitalInput) > 0 ? Number(capitalInput) : 100000;
    setCreatingPortfolio(true);
    try {
      const res = await portfolioAPI.create("My Portfolio", selectedStocks, capital);
      setPortfolioId(res.data.id);
      setCapitalInput(String(res.data.capital));
      await mutatePortfolios();
      toast.success("Portfolio ready. Select a stock to add.");
      setAddModal(true);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Could not prepare portfolio");
    } finally {
      setCreatingPortfolio(false);
    }
  }, [portfolioId, capitalInput, selectedStocks, mutatePortfolios]);

  const handleManualTrain = useCallback(async () => {
    if (!portfolioId) return;
    setRebalancing(true);
    try {
      await modelAPI.retrain(portfolioId);
      toast.success("Training complete. Refreshing weights and backtest.");
      await mutatePortfolios();
      await mutateWeights();
      await mutatePerf();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Training failed");
    } finally {
      setRebalancing(false);
    }
  }, [portfolioId, mutatePortfolios, mutateWeights, mutatePerf]);

  const toggleSetupStock = useCallback((ticker: string) => {
    setSelectedStocks((current) =>
      current.includes(ticker)
        ? current.filter((item) => item !== ticker)
        : [...current, ticker]
    );
  }, []);

  // ── No portfolio — create one ───────────────────────────────────────────
  if (portfolios && portfolios.length === 0 && !dismissSetup) {
    return (
      <div className="flex h-screen bg-bg-primary">
        <Sidebar modelStatus={modelStatus?.status} />
        <main className="flex-1 flex items-center justify-center p-8 overflow-y-auto">
          <div className="card p-8 max-w-5xl w-full animate-slide-up relative">
            <button
              type="button"
              onClick={() => setDismissSetup(true)}
              className="absolute top-6 right-6 p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors"
              title="Cancel / Close"
            >
              <X className="w-5 h-5" />
            </button>
            <Brain className="w-12 h-12 text-accent-cyan mx-auto mb-4" />
            <h2 className="text-xl font-bold text-text-primary mb-6 text-center">Create Your Portfolio</h2>
            <div className="max-w-sm mx-auto mb-6">
              <label className="label">Budget</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">₹</span>
                <input
                  type="number"
                  value={capitalInput}
                  onChange={(e) => setCapitalInput(e.target.value)}
                  className="input pl-7"
                  placeholder="100000"
                />
              </div>
            </div>
            <div className="space-y-5 max-h-[50vh] overflow-y-auto pr-2">
              {Object.entries(INDIAN_STOCK_SECTORS).map(([sector, stocks]) => (
                <section key={sector}>
                  <h3 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-2">
                    {sector}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                    {stocks.map((stock) => {
                      const active = selectedStocks.includes(stock.ticker);
                      return (
                        <button
                          key={stock.ticker}
                          onClick={() => toggleSetupStock(stock.ticker)}
                          className={`text-left rounded-lg border p-3 transition-all ${
                            active
                              ? "bg-accent-cyan/10 border-accent-cyan text-text-primary"
                              : "bg-bg-tertiary border-border text-text-secondary hover:border-border-bright"
                          }`}
                        >
                          <span className="block text-sm font-semibold">{stock.name}</span>
                          <span className="block text-xs font-mono text-text-muted mt-1">
                            {stock.ticker}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
            <div className="flex items-center gap-4 mt-6">
              <button
                type="button"
                className="btn-ghost flex-1 py-3 border border-border hover:bg-bg-tertiary text-text-secondary rounded-lg font-medium transition-colors"
                onClick={() => {
                  setSelectedStocks([]);
                  setDismissSetup(true);
                }}
              >
                Cancel
              </button>
              <button
                className="btn-primary flex-1 py-3"
                disabled={creatingPortfolio || selectedStocks.length < 2}
                onClick={async () => {
                  const capital = Number(capitalInput) > 0 ? Number(capitalInput) : 100000;
                  try {
                    setCreatingPortfolio(true);
                    await portfolioAPI.create("My Portfolio", selectedStocks, capital);
                    toast.success("Portfolio created. Model training started.");
                    mutatePortfolios();
                  } catch (err: any) {
                    toast.error(err?.response?.data?.detail || "Failed to create portfolio");
                  } finally {
                    setCreatingPortfolio(false);
                  }
                }}
              >
                {creatingPortfolio ? "Creating..." : `Create With ${selectedStocks.length} Stocks`}
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ── Dismissed setup empty state ──────────────────────────────────────────
  if (portfolios && portfolios.length === 0 && dismissSetup) {
    return (
      <div className="flex h-screen bg-bg-primary overflow-hidden">
        <Sidebar modelStatus={modelStatus?.status} />
        <main className="flex-1 flex items-center justify-center p-8">
          <div className="card p-10 max-w-lg w-full text-center animate-slide-up">
            <Brain className="w-14 h-14 text-text-muted mx-auto mb-4 opacity-40" />
            <h2 className="text-xl font-bold text-text-primary mb-2">No Active Portfolio</h2>
            <p className="text-sm text-text-muted mb-6">
              Setup was cancelled. Whenever you are ready to train a model or manage a portfolio, click below to start.
            </p>
            <button
              onClick={() => setDismissSetup(false)}
              className="btn-primary px-6 py-3 text-sm font-semibold inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Create Portfolio
            </button>
          </div>
        </main>
      </div>
    );
  }

  const metrics    = perfData?.metrics;
  const allocations = weightsData?.allocations ?? [];
  const capital    = weightsData?.capital ?? activePortfolio?.capital ?? 0;
  const isTraining = Boolean(
    rebalancing ||
    modelStatus?.status === "training" ||
    weightsData?.model_trained === false
  );

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden">
      <Sidebar modelStatus={modelStatus?.status} />

      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-bg-primary/80 backdrop-blur-md border-b border-border px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-text-primary">
              {activePortfolio?.name ?? "Dashboard"}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              {weightsData?.model_trained ? (
                <span className="badge-success">Model Trained</span>
              ) : (
                <span className="badge-warning">Training…</span>
              )}
              {activePortfolio?.last_rebalanced && (
                <span className="text-xs text-text-muted">
                  Last rebalanced:{" "}
                  {new Date(activePortfolio.last_rebalanced).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Capital input */}
            <div className="flex items-center gap-2">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">₹</span>
                <input
                  type="number"
                  value={capitalInput}
                  onChange={(e) => setCapitalInput(e.target.value)}
                  className="input pl-7 w-36 text-sm"
                  placeholder="Capital"
                />
              </div>
              <button
                onClick={handleSaveCapital}
                disabled={savingCapital}
                className="btn-ghost text-xs py-2"
              >
                {savingCapital ? "Saving…" : "Update"}
              </button>
            </div>

            <button
              onClick={handleOpenAddStock}
              disabled={creatingPortfolio}
              className="btn-ghost flex items-center gap-2"
            >
              <Plus className={`w-4 h-4 ${creatingPortfolio ? "animate-spin" : ""}`} />
              {creatingPortfolio ? "Preparing..." : "Add Stock"}
            </button>

            <button
              onClick={handleManualTrain}
              disabled={rebalancing}
              className="btn-primary flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${rebalancing ? "animate-spin" : ""}`} />
              {rebalancing ? "Training..." : "Train Model"}
            </button>
          </div>
        </div>

        <div className="p-8 space-y-8 animate-fade-in">
          {/* Model training banner */}
          {modelStatus?.status === "training" && (
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-warning/10 border border-warning/20 text-warning text-sm">
              <Activity className="w-4 h-4 animate-pulse flex-shrink-0" />
              <span>Model is retraining — weights will update automatically when complete.</span>
            </div>
          )}
          {modelStatus?.status === "error" && (
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-sm">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>Training error: {modelStatus.error}</span>
            </div>
          )}

          {/* KPI Metrics */}
          <section>
            <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">Performance Metrics</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                label="Sharpe Ratio"
                value={metrics?.sharpe ?? 0}
                format="ratio"
                trend={metrics && metrics.sharpe > 1 ? "up" : metrics && metrics.sharpe > 0 ? "neutral" : "down"}
                highlight={!!(metrics && metrics.sharpe > 1)}
                icon={<TrendingUp className="w-4 h-4" />}
                subtitle="Risk-adjusted return"
              />
              <MetricCard
                label="Annual Return"
                value={metrics?.arithmetic_return ?? 0}
                format="percent"
                trend={metrics && metrics.arithmetic_return > 0 ? "up" : "down"}
                icon={<BarChart2 className="w-4 h-4" />}
                subtitle="Arithmetic (annualized)"
              />
              <MetricCard
                label="Volatility"
                value={metrics?.volatility ?? 0}
                format="percent"
                trend="neutral"
                icon={<Activity className="w-4 h-4" />}
                subtitle="Annualized std dev"
              />
              <MetricCard
                label="Max Drawdown"
                value={metrics?.max_drawdown ?? 0}
                format="percent"
                trend="down"
                icon={<AlertTriangle className="w-4 h-4" />}
                subtitle="Peak-to-trough loss"
              />
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
              <MetricCard
                label="Total Capital"
                value={formatINR(capital)}
                subtitle="Invested"
                icon={<DollarSign className="w-4 h-4" />}
              />
              <MetricCard
                label="Pocket Balance"
                value={formatINR(activePortfolio?.cash_balance ?? 0)}
                subtitle="Withdrawn cash"
              />
              <MetricCard
                label="Avg Turnover"
                value={metrics?.avg_turnover ?? 0}
                format="percent"
                trend="neutral"
                subtitle="Per rebalance day"
              />
              <MetricCard
                label="Cost Drag"
                value={metrics?.cost_drag ?? 0}
                format="ratio"
                trend="down"
                subtitle="Transaction cost impact"
              />
            </div>
          </section>

          {/* Charts row */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Cumulative wealth */}
            <div className="card p-6 lg:col-span-2">
              <h3 className="text-sm font-semibold text-text-secondary mb-4">Cumulative Wealth</h3>
              <WealthChart
                spt={perfData?.wealth_spt ?? []}
                market={perfData?.wealth_market ?? []}
                net={perfData?.wealth_net ?? []}
              />
            </div>

            {/* Weights donut */}
            <div className="card p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-text-secondary">Weight Distribution</h3>
                {isTraining && (
                  <span className="flex items-center gap-1.5 text-xs text-accent-cyan font-medium animate-pulse">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-ping" />
                    Optimizing
                  </span>
                )}
              </div>
              <WeightsChart allocations={allocations} isTraining={isTraining} />
            </div>
          </section>

          {/* Allocation table */}
          <section className="card">
            <div className="p-6 border-b border-border flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-secondary">Current Allocations</h3>
              <span className="badge-info">{allocations.length} positions</span>
            </div>
            <AllocationTable
              allocations={allocations}
              capital={capital}
              onRemove={handleRemoveStock}
              onRemoveAll={handleLiquidateAll}
              loading={rebalancing}
              stockCount={activePortfolio?.stocks.length ?? 0}
            />
          </section>

          {perfData?.weights_history?.length ? (
            <section className="card p-6">
              <h3 className="text-sm font-semibold text-text-secondary mb-4">
                21-Day Rebalance Weight History
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-text-muted border-b border-border">
                      <th className="py-2 pr-4">Date</th>
                      {activePortfolio?.stocks.map((ticker) => (
                        <th key={ticker} className="py-2 pr-4 font-mono">{ticker}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {perfData.weights_history.slice(-12).reverse().map((row) => (
                      <tr key={String(row.date)} className="border-b border-border/50">
                        <td className="py-2 pr-4 text-text-secondary">{String(row.date)}</td>
                        {activePortfolio?.stocks.map((ticker) => (
                          <td key={ticker} className="py-2 pr-4 font-mono text-text-primary">
                            {(((row[ticker] as number) ?? 0) * 100).toFixed(2)}%
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </div>
      </main>

      {/* Add Stock Modal */}
      {portfolioId && (
        <StockModal
          isOpen={addModal}
          onClose={() => setAddModal(false)}
          portfolioId={portfolioId}
          existingStocks={activePortfolio?.stocks ?? []}
          onSuccess={() => { mutatePortfolios(); mutateWeights(); mutatePerf(); }}
        />
      )}
    </div>
  );
}
