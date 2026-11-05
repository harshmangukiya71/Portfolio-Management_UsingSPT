"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Briefcase,
  BarChart3,
  RefreshCw,
  Brain,
  TrendingUp,
  ChevronRight,
  Cpu,
  LogOut,
  LogIn,
  User,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import AuthModal from "./AuthModal";

const navItems = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/portfolio", icon: Briefcase,        label: "Portfolio" },
  { href: "/analytics", icon: BarChart3,        label: "Analytics" },
];

interface SidebarProps {
  modelStatus?: string;   // "idle" | "training" | "done" | "error"
  nextRebalance?: string;
}

export default function Sidebar({ modelStatus = "idle", nextRebalance }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();

  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [userEmail, setUserEmail] = useState<string>("");
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    const email = localStorage.getItem("user_email") || "";
    setUserEmail(email);
    setIsLoggedIn(Boolean(token));
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user_email");
    setUserEmail("");
    setIsLoggedIn(false);
    window.location.reload();
  };

  const statusColor: Record<string, string> = {
    idle:     "bg-text-muted",
    training: "bg-warning animate-pulse",
    done:     "bg-success",
    error:    "bg-danger",
  };

  const statusLabel: Record<string, string> = {
    idle:     "Ready",
    training: "Training…",
    done:     "Trained",
    error:    "Error",
  };

  return (
    <>
      <aside className="w-64 flex-shrink-0 bg-bg-secondary border-r border-border flex flex-col h-screen sticky top-0">
        {/* Logo */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-accent flex items-center justify-center shadow-glow-cyan flex-shrink-0">
              <TrendingUp className="w-5 h-5 text-bg-primary" />
            </div>
            <div>
              <p className="text-sm font-bold text-text-primary leading-tight">AI Portfolio</p>
              <p className="text-xs text-text-muted leading-tight">Manager</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map(({ href, icon: Icon, label }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group",
                  active
                    ? "bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
                )}
              >
                <Icon className={cn("w-4 h-4 flex-shrink-0", active ? "text-accent-cyan" : "text-text-muted group-hover:text-text-secondary")} />
                <span className="flex-1">{label}</span>
                {active && <ChevronRight className="w-3 h-3 text-accent-cyan" />}
              </Link>
            );
          })}

          {/* Divider */}
          <div className="glow-line my-3" />

          {/* Model status */}
          <div className="px-3 py-3 rounded-xl bg-bg-tertiary border border-border">
            <div className="flex items-center gap-2 mb-1">
              <Cpu className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs text-text-muted font-medium uppercase tracking-wide">Model Status</span>
            </div>
            <div className="flex items-center gap-2 mt-1.5">
              <div className={cn("w-2 h-2 rounded-full flex-shrink-0", statusColor[modelStatus] || "bg-text-muted")} />
              <span className="text-sm font-medium text-text-primary">{statusLabel[modelStatus] || "Unknown"}</span>
            </div>
            {nextRebalance && (
              <div className="flex items-center gap-1.5 mt-2">
                <RefreshCw className="w-3 h-3 text-text-muted" />
                <span className="text-xs text-text-muted">Next: {nextRebalance}</span>
              </div>
            )}
          </div>

          {/* Brain indicator */}
          <div className="px-3 py-2.5 rounded-xl flex items-center gap-2 text-xs text-text-muted">
            <Brain className="w-3.5 h-3.5 text-accent-purple" />
            <span>Functional SPT · GARCH</span>
          </div>
        </nav>

        {/* User / Auth Section at Bottom */}
        <div className="p-3 border-t border-border">
          {isLoggedIn ? (
            <div className="p-2.5 rounded-xl bg-bg-tertiary border border-border space-y-2">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-accent-cyan/20 border border-accent-cyan/40 flex items-center justify-center text-accent-cyan font-bold text-xs flex-shrink-0">
                  {userEmail ? userEmail[0].toUpperCase() : "U"}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-text-primary truncate" title={userEmail}>
                    {userEmail || "Logged In"}
                  </p>
                  <p className="text-[10px] text-text-muted">PostgreSQL User</p>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  title="Sign Out"
                  className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors flex-shrink-0"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>

              <button
                type="button"
                onClick={() => setAuthModalOpen(true)}
                className="w-full py-1.5 px-2 rounded-lg bg-bg-secondary hover:bg-bg-primary text-[11px] text-accent-cyan font-medium flex items-center justify-center gap-1.5 border border-border transition-colors"
              >
                <Users className="w-3 h-3" />
                Switch / New User
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAuthModalOpen(true)}
              className="w-full py-2.5 px-3 rounded-xl bg-accent-cyan text-bg-primary font-semibold text-xs flex items-center justify-center gap-2 shadow-glow-cyan hover:opacity-90 transition-all"
            >
              <LogIn className="w-4 h-4" />
              Log In / Sign Up
            </button>
          )}
        </div>
      </aside>

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={(email) => {
          setUserEmail(email);
          setIsLoggedIn(true);
          window.location.reload();
        }}
      />
    </>
  );
}
