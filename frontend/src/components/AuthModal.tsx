"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { X, Mail, Lock, Eye, EyeOff, Brain, TrendingUp, LogIn, UserPlus } from "lucide-react";
import { authAPI } from "@/lib/api";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (email: string) => void;
  initialMode?: "login" | "signup";
}

export default function AuthModal({
  isOpen,
  onClose,
  onSuccess,
  initialMode = "login",
}: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "signup">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !password) {
      toast.error("Please fill in email and password");
      return;
    }

    if (mode === "signup") {
      if (password !== confirmPassword) {
        toast.error("Passwords do not match");
        return;
      }
      if (password.length < 6) {
        toast.error("Password must be at least 6 characters");
        return;
      }
    }

    setLoading(true);
    try {
      let res;
      if (mode === "signup") {
        res = await authAPI.register(email, password);
        toast.success(`Account created for ${email}! Welcome 🎉`);
      } else {
        res = await authAPI.login(email, password);
        toast.success(`Welcome back, ${email}!`);
      }

      // Save token and user email in localStorage
      localStorage.setItem("token", res.data.access_token);
      localStorage.setItem("user_email", email);

      if (onSuccess) {
        onSuccess(email);
      } else {
        // Trigger a hard reload to refresh all SWR caches for the new user
        window.location.reload();
      }

      onClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === "Email already registered") {
        toast.error("Email already registered. Switching to Log In.");
        setMode("login");
      } else {
        toast.error(detail || (mode === "login" ? "Invalid email or password" : "Signup failed"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="card p-6 sm:p-8 max-w-md w-full relative border border-border shadow-2xl animate-scale-in">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors"
          title="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex flex-col items-center mb-6 text-center">
          <div className="w-12 h-12 rounded-2xl bg-gradient-accent flex items-center justify-center shadow-glow-cyan mb-3">
            <TrendingUp className="w-6 h-6 text-bg-primary" />
          </div>
          <h2 className="text-xl font-bold text-text-primary">
            {mode === "login" ? "Investor Log In" : "Create Investor Account"}
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Accounts and portfolios are isolated per user in PostgreSQL
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex rounded-xl bg-bg-tertiary p-1 mb-6 border border-border">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`flex-1 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
              mode === "login"
                ? "bg-accent-cyan text-bg-primary shadow"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            <LogIn className="w-3.5 h-3.5" />
            Log In
          </button>
          <button
            type="button"
            onClick={() => setMode("signup")}
            className={`flex-1 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
              mode === "signup"
                ? "bg-accent-cyan text-bg-primary shadow"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            <UserPlus className="w-3.5 h-3.5" />
            Sign Up
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Email */}
          <div>
            <label className="label text-xs">Email Address (Dummy or Real)</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input pl-10 text-sm"
                placeholder="e.g. abc@gmail.com"
                autoComplete="email"
                required
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label className="label text-xs">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input pl-10 pr-10 text-sm"
                placeholder={mode === "signup" ? "At least 6 characters" : "Enter password"}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Confirm Password (signup only) */}
          {mode === "signup" && (
            <div>
              <label className="label text-xs">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input pl-10 text-sm"
                  placeholder="Repeat your password"
                  autoComplete="new-password"
                  required
                />
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-2.5 text-sm font-semibold flex items-center justify-center gap-2 mt-2 shadow-glow-cyan"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 rounded-full border-2 border-bg-primary border-t-transparent animate-spin" />
                <span>{mode === "login" ? "Logging in…" : "Creating account…"}</span>
              </>
            ) : (
              <span>{mode === "login" ? "Log In" : "Create Account"}</span>
            )}
          </button>
        </form>

        {/* Footer info */}
        <div className="mt-5 pt-4 border-t border-border text-center">
          <p className="text-[11px] text-text-muted flex items-center justify-center gap-1.5">
            <Brain className="w-3 h-3 text-accent-purple" />
            Dummy emails supported · Stored in local PostgreSQL
          </p>
        </div>
      </div>
    </div>
  );
}
