"use client";

import useSWR from "swr";
import { BarChart3 } from "lucide-react";

import Sidebar from "@/components/Sidebar";
import MetricCard from "@/components/MetricCard";
import WealthChart from "@/components/charts/WealthChart";
import TurnoverChart from "@/components/charts/TurnoverChart";
import { portfolioAPI, modelAPI } from "@/lib/api";
import { formatINR } from "@/lib/utils";

export default function AnalyticsPage() {
  const { data: portfolios } = useSWR(
    "portfolios",
    () => portfolioAPI.list().then((r) => r.data)
  );
  const { data: modelStatus } = useSWR(
    "model-status",
    () => modelAPI.status().then((r) => r.data),
    { refreshInterval: 10_000 }
  );

  const portfolio = portfolios?.[0];

  const { data: perfData } = useSWR(
    portfolio ? `perf-${portfolio.id}` : null,
    () => portfolioAPI.getPerformance(portfolio!.id).then((r) => r.data),
    { refreshInterval: 120_000 }
  );

  const metrics = perfData?.metrics;

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden">
      <Sidebar modelStatus={modelStatus?.status} />

      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-bg-primary/80 backdrop-blur-md border-b border-border px-8 py-4 flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-accent-cyan" />
          <h1 className="text-xl font-bold text-text-primary">Analytics</h1>
        </div>

        <div className="p-8 space-y-8 animate-fade-in">
          {/* Full metrics grid */}
          <section>
            <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-4">
              Complete Performance Summary
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard label="Sharpe Ratio"       value={metrics?.sharpe ?? 0}            format="ratio"   trend={metrics && metrics.sharpe > 1 ? "up" : "neutral"} highlight />
              <MetricCard label="Arithmetic Return"  value={metrics?.arithmetic_return ?? 0}  format="percent" trend={metrics && metrics.arithmetic_return > 0 ? "up" : "down"} />
              <MetricCard label="Geometric Return"   value={metrics?.geometric_return ?? 0}   format="percent" trend={metrics && metrics.geometric_return > 0 ? "up" : "down"} />
              <MetricCard label="Volatility"         value={metrics?.volatility ?? 0}          format="percent" trend="neutral" />
              <MetricCard label="Max Drawdown"       value={metrics?.max_drawdown ?? 0}        format="percent" trend="down" />
              <MetricCard label="Avg Turnover"       value={metrics?.avg_turnover ?? 0}        format="percent" trend="neutral" subtitle="Per rebalance" />
              <MetricCard label="Cost Drag"          value={metrics?.cost_drag ?? 0}           format="ratio"  trend="down" subtitle="₹1 initial investment" />
              <MetricCard
                label="Capital"
                value={formatINR(portfolio?.capital ?? 0)}
                subtitle="Under management"
              />
            </div>
          </section>

          {/* Cumulative wealth — full */}
          <section className="card p-6">
            <h3 className="text-sm font-semibold text-text-secondary mb-5">
              Cumulative Wealth — Gross vs After Cost vs Market
            </h3>
            <WealthChart
              spt={perfData?.wealth_spt ?? []}
              market={perfData?.wealth_market ?? []}
              net={perfData?.wealth_net ?? []}
            />
          </section>

          {/* Relative wealth + turnover */}
          <section className="card p-6">
            <h3 className="text-sm font-semibold text-text-secondary mb-5">
              Relative Wealth & Turnover
            </h3>
            <TurnoverChart
              turnover={perfData?.turnover ?? []}
              relativeWealth={perfData?.relative_wealth ?? []}
            />
          </section>

          {perfData?.weights_history?.length ? (
            <section className="card p-6">
              <h3 className="text-sm font-semibold text-text-secondary mb-4">
                21-Day Rebalance Weights
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-text-muted border-b border-border">
                      <th className="py-2 pr-4">Date</th>
                      {portfolio?.stocks.map((ticker) => (
                        <th key={ticker} className="py-2 pr-4 font-mono">{ticker}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {perfData.weights_history.slice(-20).reverse().map((row) => (
                      <tr key={String(row.date)} className="border-b border-border/50">
                        <td className="py-2 pr-4 text-text-secondary">{String(row.date)}</td>
                        {portfolio?.stocks.map((ticker) => (
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

          {/* Model metrics */}
          {modelStatus?.last_metrics && (
            <section className="card p-6">
              <h3 className="text-sm font-semibold text-text-secondary mb-4">Last Training Run</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {Object.entries(modelStatus.last_metrics).map(([key, val]) => (
                  <div key={key} className="bg-bg-tertiary rounded-xl p-4">
                    <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
                      {key.replace(/_/g, " ")}
                    </p>
                    <p className="text-lg font-bold font-mono text-text-primary">
                      {typeof val === "number" ? val.toFixed(4) : String(val)}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
