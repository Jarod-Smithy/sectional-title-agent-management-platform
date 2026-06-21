"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";

export default function DashboardPage() {
  const { ready, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !isAuthenticated) {
      router.replace("/login");
    }
  }, [ready, isAuthenticated, router]);

  if (!ready) {
    return <div className="center-screen">Loading…</div>;
  }
  if (!isAuthenticated) {
    return <div className="center-screen">Redirecting to sign in…</div>;
  }
  return <AppShell />;
}
