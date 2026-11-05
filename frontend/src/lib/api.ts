/**
 * Typed API client for the FastAPI backend.
 */

import axios, { AxiosInstance } from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Axios instance ──────────────────────────────────────────────────────────
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token on every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Auto-logout on 401 Unauthorized (expired / invalid token)
    if (err?.response?.status === 401 && typeof window !== "undefined") {
      const isAuthRoute = window.location.pathname === "/login";
      if (!isAuthRoute) {
        localStorage.removeItem("token");
        localStorage.removeItem("user_email");
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

// ── Types ───────────────────────────────────────────────────────────────────

export interface StockAllocation {
  ticker: string;
  weight: number;
  allocation_inr: number;
}

export interface WeightsResponse {
  portfolio_id: string;
  date: string;
  capital: number;
  allocations: StockAllocation[];
  model_trained: boolean;
  status: string;
}

export interface PerformanceMetrics {
  sharpe: number;
  arithmetic_return: number;
  geometric_return: number;
  volatility: number;
  max_drawdown: number;
  avg_turnover: number;
  cost_drag: number;
}

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface PerformanceResponse {
  portfolio_id: string;
  metrics: PerformanceMetrics;
  wealth_spt: TimeSeriesPoint[];
  wealth_market: TimeSeriesPoint[];
  wealth_net: TimeSeriesPoint[];
  relative_wealth: TimeSeriesPoint[];
  turnover: TimeSeriesPoint[];
  weights_history: Record<string, number | string>[];
}

export interface Portfolio {
  id: string;
  name: string;
  stocks: string[];
  capital: number;
  cash_balance: number;
  status: string;
  model_trained: boolean;
  created_at: string;
  last_rebalanced: string | null;
}

export interface ModelStatus {
  status: string;
  last_trained: string | null;
  last_metrics: Record<string, number> | null;
  error: string | null;
}

export interface RebalanceResponse {
  message: string;
  date: string;
  allocations: StockAllocation[];
  turnover: number;
  transaction_cost_inr: number;
  metrics?: PerformanceMetrics;
}

// ── Auth ────────────────────────────────────────────────────────────────────

export const authAPI = {
  register: (email: string, password: string) =>
    api.post<{ access_token: string }>("/auth/register", { email, password }),
  login: (email: string, password: string) =>
    api.post<{ access_token: string }>(
      "/auth/login",
      new URLSearchParams({ username: email, password }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    ),
  me: () => api.get("/auth/me"),
};

// ── Portfolio ───────────────────────────────────────────────────────────────

export const portfolioAPI = {
  create: (name: string, stocks: string[], capital: number) =>
    api.post<Portfolio>("/portfolio/create", { name, stocks, capital }),

  list: () => api.get<Portfolio[]>("/portfolio/list"),

  get: (id: string) => api.get<Portfolio>(`/portfolio/${id}`),

  addStock: (portfolio_id: string, ticker: string) =>
    api.post("/portfolio/add-stock", { portfolio_id, ticker }),

  addStocks: (portfolio_id: string, tickers: string[]) =>
    api.post("/portfolio/add-stocks", { portfolio_id, tickers }),

  removeStock: (portfolio_id: string, ticker: string) =>
    api.post("/portfolio/remove-stock", { portfolio_id, ticker }),

  reinvestFromPocket: (portfolio_id: string, amount: number) =>
    api.post("/portfolio/reinvest-from-pocket", { portfolio_id, amount }),

  exitStock: (portfolio_id: string, ticker: string, withdraw_amount: number) =>
    api.post("/portfolio/exit-stock", { portfolio_id, ticker, withdraw_amount }),

  getWeights: (portfolio_id: string) =>
    api.get<WeightsResponse>("/portfolio/weights", { params: { portfolio_id } }),

  getPerformance: (portfolio_id: string) =>
    api.get<PerformanceResponse>("/portfolio/performance", { params: { portfolio_id } }),

  rebalance: (portfolio_id: string) =>
    api.post<RebalanceResponse>("/portfolio/rebalance", null, {
      params: { portfolio_id },
    }),

  updateCapital: (portfolio_id: string, capital: number) =>
    api.patch(`/portfolio/${portfolio_id}/capital`, null, { params: { capital } }),
};

// ── Model ───────────────────────────────────────────────────────────────────

export const modelAPI = {
  retrain: (portfolio_id: string) =>
    api.post("/model/retrain", null, { params: { portfolio_id } }),

  status: () => api.get<ModelStatus>("/model/status"),

  metrics: (portfolio_id: string, limit = 10) =>
    api.get("/model/metrics", { params: { portfolio_id, limit } }),
};

export default api;
