"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

type Step = "request" | "confirm" | "done";

export default function ForgotPasswordPage() {
  const { forgotPassword, confirmForgotPassword } = useAuth();
  const [step, setStep] = useState<Step>("request");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onRequestCode(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await forgotPassword(email);
      setStep("confirm");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not send a verification code.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await confirmForgotPassword(email, code, newPassword);
      setStep("done");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not reset the password.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-screen">
      <div className="login-card">
        <h1>Reset your password</h1>

        {step === "request" && (
          <>
            <p className="scheme">
              Enter your email and we&apos;ll send you a verification code.
            </p>
            <form onSubmit={onRequestCode}>
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
                {busy ? "Sending…" : "Send verification code"}
              </button>
            </form>
          </>
        )}

        {step === "confirm" && (
          <>
            <p className="scheme">
              Enter the code sent to {email} and choose a new password.
            </p>
            <form onSubmit={onConfirm}>
              <label>
                Verification code
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                />
              </label>
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
                {busy ? "Resetting…" : "Reset password"}
              </button>
            </form>
          </>
        )}

        {step === "done" && (
          <div className="banner info" role="status">
            Your password has been reset. You can now sign in with your new
            password.
          </div>
        )}

        <p style={{ marginTop: 16, fontSize: 13 }}>
          <Link href="/login">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
