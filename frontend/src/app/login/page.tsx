"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { TrendingUp, Mail, Lock, Eye, EyeOff, Brain } from "lucide-react";
import { authAPI } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !password) {
      toast.error("Please fill in all fields");
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
        toast.success("Account created! Welcome aboard 🎉");
      } else {
        res = await authAPI.login(email, password);
        toast.success("Logged in successfully");
      }
      localStorage.setItem("token", res.data.access_token);
      localStorage.setItem("user_email", email);
      router.replace("/dashboard");
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail === "Email already registered") {
        toast.error("Email already registered. Please log in.");
        setMode("login");
      } else {
        toast.error(detail || (mode === "login" ? "Invalid email or password" : "Signup failed"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-accent-cyan/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 left-1/3 w-72 h-72 bg-accent-purple/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-accent flex items-center justify-center shadow-glow-cyan mb-4">
            <TrendingUp className="w-7 h-7 text-bg-primary" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary">AI Portfolio Manager</h1>
          <p className="text-text-muted text-sm mt-1 flex items-center gap-1.5">
            <Brain className="w-3.5 h-3.5 text-accent-purple" />
            Functional SPT · GARCH · Deep Learning
          </p>
        </div>

        {/* Card */}
        <div className="card p-8">
          {/* Tab toggle */}
          <div className="flex rounded-xl bg-bg-tertiary p-1 mb-6">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === "login"
                  ? "bg-accent-cyan text-bg-primary shadow"
                  : "text-text-muted hover:text-text-primary"
              }`}
            >
              Log In
            </button>
            <button
              type="button"
              onClick={() => setMode("signup")}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === "signup"
                  ? "bg-accent-cyan text-bg-primary shadow"
                  : "text-text-muted hover:text-text-primary"
              }`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="label">Email address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input pl-10"
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="label">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input pl-10 pr-10"
                  placeholder={mode === "signup" ? "Min. 6 characters" : "Your password"}
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

            {/* Confirm password (signup only) */}
            {mode === "signup" && (
              <div>
                <label className="label">Confirm Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="input pl-10"
                    placeholder="Repeat your password"
                    autoComplete="new-password"
                    required
                  />
                </div>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 text-sm font-semibold flex items-center justify-center gap-2 mt-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-bg-primary border-t-transparent animate-spin" />
                  {mode === "login" ? "Logging in…" : "Creating account…"}
                </>
              ) : (
                mode === "login" ? "Log In" : "Create Account"
              )}
            </button>
          </form>

          {/* Footer hint */}
          <p className="text-center text-text-muted text-xs mt-6">
            {mode === "login" ? (
              <>No account?{" "}
                <button type="button" onClick={() => setMode("signup")} className="text-accent-cyan hover:underline">
                  Sign up
                </button>
              </>
            ) : (
              <>Already have an account?{" "}
                <button type="button" onClick={() => setMode("login")} className="text-accent-cyan hover:underline">
                  Log in
                </button>
              </>
            )}
          </p>
        </div>

        <p className="text-center text-text-muted text-xs mt-6">
          Any email format works · Passwords are stored securely (bcrypt)
        </p>
      </div>
    </div>
  );
}
