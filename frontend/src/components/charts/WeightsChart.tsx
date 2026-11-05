"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { StockAllocation } from "@/lib/api";
import { tickerColor } from "@/lib/utils";

const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[260px] text-text-muted text-xs">
      Loading chart...
    </div>
  ),
});

interface WeightsChartProps {
  allocations: StockAllocation[];
  isTraining?: boolean;
}

function initRandomWeights(n: number): number[] {
  if (n <= 0) return [];
  const raw = Array.from({ length: n }, () => Math.pow(Math.random(), 1.3) + 0.15);
  const sum = raw.reduce((acc, v) => acc + v, 0);
  return raw.map((v) => Number((v / sum).toFixed(4)));
}

function stepWeights(prev: number[]): number[] {
  const n = prev.length;
  if (n === 0) return [];
  const perturbed = prev.map((w) => {
    const delta = (Math.random() - 0.5) * 0.08;
    return Math.max(0.015, w + delta);
  });
  const sum = perturbed.reduce((acc, v) => acc + v, 0);
  return perturbed.map((v) => Number((v / sum).toFixed(4)));
}

export default function WeightsChart({ allocations, isTraining = false }: WeightsChartProps) {
  const [animatedWeights, setAnimatedWeights] = useState<number[]>([]);
  const [epoch, setEpoch] = useState(1);
  const [revision, setRevision] = useState(0);

  // When model is training, continuously shuffle & perturb weights to simulate optimization epochs
  useEffect(() => {
    if (!isTraining || allocations.length === 0) {
      setEpoch(1);
      return;
    }

    // Initialize with varied distribution
    setAnimatedWeights(initRandomWeights(allocations.length));
    setRevision((r) => r + 1);

    const interval = setInterval(() => {
      setAnimatedWeights((prev) => {
        const current = prev.length === allocations.length ? prev : initRandomWeights(allocations.length);
        return stepWeights(current);
      });
      setEpoch((ep) => ep + 1);
      setRevision((r) => r + 1);
    }, 260);

    return () => clearInterval(interval);
  }, [isTraining, allocations.length]);

  if (!allocations.length) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted text-sm">
        No holdings
      </div>
    );
  }

  const labels = allocations.map((a) => a.ticker.replace(".NS", ""));
  const colors = allocations.map((a) => tickerColor(a.ticker));

  // Use dynamic fluctuating weights when training, otherwise actual trained weights
  const values =
    isTraining && animatedWeights.length === allocations.length
      ? animatedWeights
      : allocations.map((a) => a.weight);

  return (
    <Plot
      data={[
        {
          type: "pie",
          labels,
          values,
          marker: { colors, line: { color: "#0d1b2e", width: 2 } },
          textinfo: "label+percent",
          textfont: { color: "#f0f4ff", size: 10 },
          hovertemplate: "<b>%{label}</b><br>Weight: %{percent}<extra></extra>",
          hole: 0.5,
          sort: false, // Keep slices in place so color arcs grow/shrink naturally
        } as any,
      ]}
      layout={{
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        showlegend: false,
        margin: { l: 10, r: 10, t: 10, b: 10 },
        transition: {
          duration: 220,
          easing: "cubic-in-out",
        },
        datarevision: revision,
        uirevision: "static",
        annotations: [
          {
            font: { size: 12, color: isTraining ? "#38bdf8" : "#94a3b8", family: "Inter" },
            showarrow: false,
            text: isTraining
              ? `<b>OPTIMIZING</b><br><span style="font-size:12px;color:#38bdf8;font-weight:700">Epoch #${epoch}</span><br><span style="font-size:10px;color:#64748b">${allocations.length} stocks</span>`
              : `${allocations.length} stocks`,
            x: 0.5,
            y: 0.5,
            xref: "paper",
            yref: "paper",
          },
        ],
      } as any}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%", height: "260px" }}
    />
  );
}
