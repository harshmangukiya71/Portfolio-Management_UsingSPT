/**
 * useAuth — client-side auth guard hook.
 *
 * Call this at the top of any protected page.
 * It redirects to /login if no token is stored.
 */
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export function useAuth() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
      return;
    }
    setUserEmail(localStorage.getItem("user_email"));
    setReady(true);
  }, [router]);

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user_email");
    router.replace("/login");
  };

  return { ready, userEmail, logout };
}
