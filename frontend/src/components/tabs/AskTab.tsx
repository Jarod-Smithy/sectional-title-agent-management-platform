"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useNotify } from "@/components/Notifications";
import { reportAndNotify } from "@/lib/errorReporting";
import type { AskOut } from "@/lib/types";

export function AskTab() {
  const api = useApi();
  const notify = useNotify();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.ask({ question }));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong.");
      void reportAndNotify({ error: err, context: "ask.submit", api, notify });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="ask-heading">
      <h2 id="ask-heading">Ask the scheme&rsquo;s records</h2>
      <form onSubmit={onSubmit}>
        <label>
          Your question
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What are the quiet hours? Can we charge interest on arrears?"
            required
          />
        </label>
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Searching…" : "Ask"}
        </button>
      </form>
      <p className="hint">
        Answers are guidance drawn from your documents, not formal legal advice.
      </p>
      {error && <div className="banner error">{error}</div>}
      {result && (
        <div>
          <p style={{ whiteSpace: "pre-wrap" }}>{result.answer}</p>
          {result.sources.length > 0 && (
            <>
              <h3 style={{ fontSize: 14 }}>Sources</h3>
              {result.sources.map((s, i) => (
                <div key={i} className="list-row">
                  <strong>{s.title}</strong>{" "}
                  <span className="hint">({s.kind})</span>
                  <div className="hint">{s.snippet}</div>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </section>
  );
}
