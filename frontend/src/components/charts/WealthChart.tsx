"use client";

import dynamic from "next/dynamic";
import type { TimeSeriesPoint } from "@/lib/api";

const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[260px] text-text-muted text-xs">
      Loading chart...
    </div>
  ),
});

interface WealthChartProps {
  spt:    TimeSeriesPoint[];
  market: TimeSeriesPoint[];
  net:    TimeSeriesPoint[];
}

export default function WealthChart({ spt, market, net }: WealthChartProps) {
  const layout: Partial<Plotly.Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor:  "transparent",
    font: { family: "Inter, sans-serif", color: "#94a3b8", size: 11 },
    xaxis: {
      gridcolor:   "#1e3a5f",
      linecolor:   "#1e3a5f",
      tickfont:    { color: "#475569", size: 10 },
      showgrid:    true,
      zeroline:    false,
    },
    yaxis: {
      gridcolor:   "#1e3a5f",
      linecolor:   "#1e3a5f",
      tickfont:    { color: "#475569", size: 10 },
      showgrid:    true,
      zeroline:    false,
      tickprefix:  "₹",
    },
    legend: {
      bgcolor:     "rgba(13,27,46,0.8)",
      bordercolor: "#1e3a5f",
      borderwidth: 1,
      font:        { size: 11, color: "#94a3b8" },
      x: 0.01, y: 0.99,
    },
    margin: { l: 50, r: 20, t: 10, b: 40 },
    hovermode: "x unified",
    hoverlabel: {
      bgcolor:     "#112240",
      bordercolor: "#1e3a5f",
      font:        { color: "#f0f4ff", size: 12 },
    },
  };

  const traces: Plotly.Data[] = [
    {
      x:    spt.map((d) => d.date),
      y:    spt.map((d) => d.value),
      name: "SPT (Gross)",
      type: "scatter",
      mode: "lines",
      line: { color: "#00d4ff", width: 2.5 },
    },
    {
      x:    net.map((d) => d.date),
      y:    net.map((d) => d.value),
      name: "SPT (After Cost)",
      type: "scatter",
      mode: "lines",
      line: { color: "#7c3aed", width: 2, dash: "dash" },
    },
    {
      x:    market.map((d) => d.date),
      y:    market.map((d) => d.value),
      name: "Market",
      type: "scatter",
      mode: "lines",
      line: { color: "#475569", width: 1.5, dash: "dot" },
    },
  ];

  if (!spt.length) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted text-sm">
        No data — train the model first
      </div>
    );
  }

  return (
    <Plot
      data={traces}
      layout={layout as any}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%", height: "300px" }}
    />
  );
}
