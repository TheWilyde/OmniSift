"use client";

import { ReactNode } from "react";

// No-op provider - Clerk removed, using X-Impersonate-Role for dev
export function ClerkAuthProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}