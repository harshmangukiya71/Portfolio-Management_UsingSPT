import sys

path = r'c:\Users\os\Desktop\portfolio-mlops\frontend\src\app\dashboard\page.tsx'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update lucide-react imports and add AuthModal import
old_import = """import {
  RefreshCw, Plus, TrendingUp, Activity,
  DollarSign, BarChart2, AlertTriangle, Brain, X,
} from "lucide-react";"""

new_import = """import {
  RefreshCw, Plus, TrendingUp, Activity,
  DollarSign, BarChart2, AlertTriangle, Brain, X,
  LogIn, LogOut, User as UserIcon,
} from "lucide-react";
import AuthModal from "@/components/AuthModal";"""

if old_import not in text:
    print("Error: old_import not found")
    sys.exit(1)
text = text.replace(old_import, new_import, 1)

# 2. Add state
old_state = '  const [dismissSetup, setDismissSetup] = useState(false);'
new_state = """  const [dismissSetup, setDismissSetup] = useState(false);
  const [authModal, setAuthModal] = useState(false);
  const [currentUserEmail, setCurrentUserEmail] = useState<string>("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setCurrentUserEmail(localStorage.getItem("user_email") || "");
    }
  }, []);"""

if old_state not in text:
    print("Error: old_state not found")
    sys.exit(1)
text = text.replace(old_state, new_state, 1)

# 3. Add Log In / Sign Up / User badge in header
old_train = """            <button
              onClick={handleManualTrain}
              disabled={rebalancing}
              className="btn-primary flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${rebalancing ? "animate-spin" : ""}`} />
              {rebalancing ? "Training..." : "Train Model"}
            </button>
          </div>"""

new_train = """            <button
              onClick={handleManualTrain}
              disabled={rebalancing}
              className="btn-primary flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${rebalancing ? "animate-spin" : ""}`} />
              {rebalancing ? "Training..." : "Train Model"}
            </button>

            {/* Auth Section in Header */}
            <div className="flex items-center pl-3 border-l border-border gap-2">
              {currentUserEmail ? (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-bg-tertiary border border-border">
                    <div className="w-6 h-6 rounded-full bg-accent-cyan/20 border border-accent-cyan/40 flex items-center justify-center text-accent-cyan text-xs font-bold">
                      {currentUserEmail[0].toUpperCase()}
                    </div>
                    <div className="text-left hidden md:block">
                      <p className="text-xs font-semibold text-text-primary leading-tight truncate max-w-[140px]">{currentUserEmail}</p>
                      <p className="text-[10px] text-text-muted leading-tight">PostgreSQL User</p>
                    </div>
                    <button
                      onClick={() => {
                        localStorage.removeItem("token");
                        localStorage.removeItem("user_email");
                        window.location.reload();
                      }}
                      className="text-text-muted hover:text-danger ml-1 p-1"
                      title="Log out"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <button
                    onClick={() => setAuthModal(true)}
                    className="btn-ghost text-xs py-2 px-3 border border-border"
                  >
                    Switch User
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setAuthModal(true)}
                  className="btn-primary text-xs py-2 px-3.5 flex items-center gap-2 shadow-glow-cyan"
                >
                  <LogIn className="w-4 h-4" />
                  Log In / Sign Up
                </button>
              )}
            </div>
          </div>"""

if old_train not in text:
    print("Error: old_train not found")
    sys.exit(1)
text = text.replace(old_train, new_train, 1)

# 4. Add AuthModal at bottom
old_bottom = "      {/* Add Stock Modal */}"
new_bottom = """      {/* Auth Modal */}
      <AuthModal
        isOpen={authModal}
        onClose={() => setAuthModal(false)}
        onSuccess={(email) => {
          setCurrentUserEmail(email);
          window.location.reload();
        }}
      />

      {/* Add Stock Modal */}"""

if old_bottom not in text:
    print("Error: old_bottom not found")
    sys.exit(1)
text = text.replace(old_bottom, new_bottom, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Dashboard updated successfully!")
