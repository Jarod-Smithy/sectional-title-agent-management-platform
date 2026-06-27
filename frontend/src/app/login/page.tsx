"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { ready, isAuthenticated, signIn, completeNewPassword } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // When Cognito raises a first-sign-in challenge we swap the card to a
  // "choose a permanent password" form instead of bouncing users to an admin.
  const [needsNewPassword, setNeedsNewPassword] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  useEffect(() => {
    if (ready && isAuthenticated) {
      router.replace("/");
    }
  }, [ready, isAuthenticated, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await signIn(email, password);
      if (result === "NEW_PASSWORD_REQUIRED") {
        setNeedsNewPassword(true);
        return;
      }
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onSetNewPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await completeNewPassword(newPassword);
      router.replace("/");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not set the new password.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (needsNewPassword) {
    return (
      <div className="center-screen">
        <div className="login-card">
          <h1>Set a new password</h1>
          <p className="scheme">
            Choose a permanent password to finish setting up your account.
          </p>
          <form onSubmit={onSetNewPassword}>
            <label>
              New password
              <input
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </label>
            <label>
              Confirm new password
              <input
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </label>
            {error && (
              <div className="banner error" role="alert">
                {error}
              </div>
            )}
            <button
              className="btn"
              type="submit"
              disabled={busy}
              style={{ width: "100%" }}
            >
              {busy ? "Saving…" : "Set password and sign in"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="center-screen">
      <div className="login-card">
        <h1>Trustee Platform</h1>
        <p className="scheme">Acacia Heights Body Corporate</p>
        <form onSubmit={onSubmit}>
          <label>
            Email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && (
            <div className="banner error" role="alert">
              {error}
            </div>
          )}
          <button
            className="btn"
            type="submit"
            disabled={busy}
            style={{ width: "100%" }}
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p style={{ marginTop: 16, fontSize: 13 }}>
          <Link href="/forgot-password">Forgot password?</Link>
        </p>
      </div>
    </div>
  );
}
