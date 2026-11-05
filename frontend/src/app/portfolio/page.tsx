"use client";

import { useState } from "react";
import useSWR from "swr";
import toast from "react-hot-toast";
import { Plus, RefreshCw, Briefcase, Calendar, TrendingUp } from "lucide-react";

import Sidebar from "@/components/Sidebar";
import AllocationTable from "@/components/AllocationTable";
import StockModal from "@/components/StockModal";
import { portfolioAPI, modelAPI } from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { useAuth } from "@/lib/useAuth";

export default function PortfolioPage() {
  const { ready } = useAuth();
  const [addModal, setAddModal] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [liquidating, setLiquidating] = useState(false);

  const { data: portfolios, mutate: mutatePortfolios } = useSWR(
    "portfolios",
    () => portfolioAPI.list().then((r) => r.data),
    { refreshInterval: 30_000 }
  );

  const { data: modelStatus } = useSWR(
    "model-status",
    () => modelAPI.status().then((r) => r.data),
    { refreshInterval: 10_000 }
  );

  const portfolio = portfolios?.[0];

  const { data: weightsData, mutate: mutateWeights } = useSWR(
    portfolio ? `weights-${portfolio.id}` : null,
    () => portfolioAPI.getWeights(portfolio!.id).then((r) => r.data),
    { refreshInterval: 60_000 }
  );

  const allocations = weightsData?.allocations ?? [];
  const capital = portfolio?.capital ?? 0;

  async function handleRemoveStock(ticker: string) {
    if (!portfolio) return;
    setRemoving(ticker);
    try {
      await portfolioAPI.removeStock(portfolio.id, ticker);
      toast.success(`${ticker} removed. Weights recalculated.`);
      mutatePortfolios();
      mutateWeights();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to remove stock");
    } finally {
      setRemoving(null);
    }
  }

  async function handleLiquidateAll() {
    if (!portfolio || !allocations.length) return;
    setLiquidating(true);
    try {
      for (const alloc of allocations) {
        await portfolioAPI.exitStock(portfolio.id, alloc.ticker, alloc.allocation_inr);
      }
      toast.success(`All ${allocations.length} holdings liquidated. Capital moved to pocket.`);
      mutatePortfolios();
      mutateWeights();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to liquidate all holdings");
    } finally {
      setLiquidating(false);
    }
  }

  async function handleRetrain() {
    if (!portfolio) return;
    try {
      toast.loading("Training model...", { id: "manual-train" });
      await modelAPI.retrain(portfolio.id);
      toast.success("Training complete", { id: "manual-train" });
      mutatePortfolios();
      mutateWeights();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Training failed", { id: "manual-train" });
    }
  }

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-primary">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-2 border-accent-cyan border-t-transparent animate-spin" />
          <p className="text-text-secondary text-sm">Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden">
      <Sidebar modelStatus={modelStatus?.status} />

      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-bg-primary/80 backdrop-blur-md border-b border-border px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Briefcase className="w-5 h-5 text-accent-cyan" />
            <h1 className="text-xl font-bold text-text-primary">Portfolio Management</h1>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleRetrain} className="btn-ghost flex items-center gap-2">
              <RefreshCw className="w-4 h-4" />
              Retrain Model
            </button>
            <button onClick={() => setAddModal(true)} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Add Stock
            </button>
          </div>
        </div>

        <div className="p-8 space-y-8 animate-fade-in">
          {portfolio ? (
            <div className="card p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-text-primary">{portfolio.name}</h2>
                <div className="flex items-center gap-4 mt-1 text-xs text-text-muted">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    Created: {new Date(portfolio.created_at).toLocaleDateString()}
                  </span>
                  {portfolio.last_rebalanced && (
                    <span className="flex items-center gap-1">
                      <RefreshCw className="w-3.5 h-3.5" />
                      Last rebalanced: {new Date(portfolio.last_rebalanced).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-6">
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Total Invested</p>
                  <p className="text-xl font-bold text-accent-cyan">{formatINR(capital)}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Holdings</p>
                  <p className="text-xl font-bold text-text-primary">{allocations.length}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Status</p>
                  <span className={portfolio.model_trained ? "badge-success" : "badge-warning"}>
                    {portfolio.model_trained ? "Active" : "Training"}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="card p-8 text-center">
              <p className="text-text-muted text-sm">No portfolio found. Create one from the Dashboard.</p>
            </div>
          )}

          <section className="card">
            <div className="p-6 border-b border-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">Current Positions</h3>
                <p className="text-xs text-text-muted mt-0.5">
                  Proportionally allocated based on trained model weights
                </p>
              </div>
              <span className="badge-info">{allocations.length} positions</span>
            </div>

            <AllocationTable
              allocations={allocations}
              capital={capital}
              onRemove={handleRemoveStock}
              onRemoveAll={handleLiquidateAll}
              loading={liquidating || Boolean(removing)}
              stockCount={portfolio?.stocks?.length ?? 0}
            />
          </section>
        </div>
      </main>

      {portfolio && (
        <StockModal
          isOpen={addModal}
          onClose={() => setAddModal(false)}
          portfolioId={portfolio.id}
          existingStocks={portfolio.stocks ?? []}
          onSuccess={() => {
            mutatePortfolios();
            mutateWeights();
          }}
        />
      )}
    </div>
  );
}