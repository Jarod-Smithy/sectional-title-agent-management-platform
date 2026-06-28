"use client";

import { AuthProvider } from "@/lib/auth";
import { NotificationProvider } from "@/components/Notifications";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <NotificationProvider>
      <AuthProvider>{children}</AuthProvider>
    </NotificationProvider>
  );
}
