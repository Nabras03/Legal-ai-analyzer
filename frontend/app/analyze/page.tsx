"use client";

import { useState } from "react";
import Link from "next/link";

// Mirrors the JSON shape app/api/analyze/route.ts promises to return.
type Risk = {
  description: string;
  explanation: string;
  affectedParty: string;
  riskLevel: "low" | "medium" | "high";
  citation: string;
};

type Definition = { term: string; definition: string };

type AnalysisResult =
  | { isLegalDocument: false; reason: string }
  | {
      isLegalDocument: true;
      summary: string;
      documentType: string;
      definitions: Definition[];
      risks: Risk[];
    };

// Colour per risk level — used for both the badge text and its border/glow.
const RISK_STYLES: Record<Risk["riskLevel"], string> = {
  low: "border-[rgba(120,255,150,0.5)] text-[#7dffa0] bg-[rgba(120,255,150,0.08)]",
  medium: "border-[var(--hud-amber)] text-[var(--hud-amber)] bg-[rgba(255,180,84,0.08)]",
  high: "border-[#ff5c6a] text-[#ff5c6a] bg-[rgba(255,92,106,0.08)]",
};

export default function AnalyzePage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        setResult(data as AnalysisResult);
      }
    } catch {
      setError("Could not reach the server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-dvh w-full items-center justify-center overflow-hidden px-4 py-6">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 50%, transparent 40%, rgba(2,6,11,0.7) 100%)",
        }}
      />

      <main className="hud-panel hud-corner animate-boot relative z-10 flex h-[86dvh] w-full max-w-3xl flex-col">
        {/* ---- Header ---- */}
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--hud-line)] px-5 py-4">
          <div>
            <h1
              className="text-glow font-[family-name:var(--font-rajdhani)] text-2xl font-bold tracking-[0.35em] text-[var(--hud-cyan)]"
            >
              TEXT&nbsp;ANALYZER
            </h1>
            <p className="hud-readout mt-1">Clause &amp; Risk Scanner</p>
          </div>
          <Link href="/" className="hud-readout border border-[var(--hud-cyan)] px-3 py-1.5 text-[var(--hud-cyan)] transition-all hover:bg-[rgba(53,224,255,0.15)]">
            ← Chat
          </Link>
        </header>

        {/* ---- Body ---- */}
        <div className="hud-scroll flex-1 space-y-5 overflow-y-auto px-5 py-5">
          <form onSubmit={analyze} className="space-y-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Paste a clause or document to analyze…"
              rows={6}
              className="hud-scroll w-full resize-y border border-[rgba(53,224,255,0.35)] bg-[rgba(2,6,11,0.4)] px-3 py-2 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-text)] caret-[var(--hud-cyan)] outline-none transition-colors placeholder:text-[var(--hud-cyan-dim)] focus:border-[var(--hud-cyan)]"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="hud-readout border border-[var(--hud-cyan)] px-4 py-2 text-[var(--hud-cyan)] transition-all hover:bg-[rgba(53,224,255,0.15)] hover:shadow-[0_0_16px_rgba(53,224,255,0.4)] disabled:opacity-40 disabled:shadow-none"
            >
              {loading ? "Analyzing…" : "Analyze"}
            </button>
          </form>

          {loading && (
            <div className="animate-msg hud-readout flex items-center gap-2 font-[family-name:var(--font-geist-mono)]">
              Processing
              <span className="processing-bar" />
              <span className="processing-bar" />
              <span className="processing-bar" />
            </div>
          )}

          {error && (
            <div className="animate-msg border border-[var(--hud-amber)] bg-[rgba(255,180,84,0.08)] px-4 py-2.5 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-amber)]">
              ⚠️ {error}
            </div>
          )}

          {result && !result.isLegalDocument && (
            <div className="animate-msg border border-[var(--hud-amber)] bg-[rgba(255,180,84,0.08)] px-4 py-3 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-amber)]">
              <p className="hud-readout mb-1 text-[var(--hud-amber)]">Not Legal Text</p>
              <p>{result.reason}</p>
            </div>
          )}

          {result && result.isLegalDocument && (
            <div className="animate-msg space-y-5">
              {/* Document type */}
              <section>
                <p className="hud-readout text-[var(--hud-cyan)]">Document Type</p>
                <p className="mt-1 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-text)]">
                  {result.documentType}
                </p>
              </section>

              {/* Summary */}
              <section>
                <p className="hud-readout text-[var(--hud-cyan)]">Summary</p>
                <p className="mt-1 font-[family-name:var(--font-geist-mono)] text-sm leading-relaxed text-[var(--hud-text)]">
                  {result.summary}
                </p>
              </section>

              {/* Definitions */}
              <section>
                <p className="hud-readout text-[var(--hud-cyan)]">Definitions</p>
                {result.definitions.length === 0 ? (
                  <p className="mt-1 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-cyan-dim)]">
                    No legal definition
                  </p>
                ) : (
                  <ul className="mt-1 space-y-2">
                    {result.definitions.map((d, i) => (
                      <li
                        key={i}
                        className="border border-[rgba(53,224,255,0.25)] bg-[rgba(53,224,255,0.05)] px-3 py-2 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-text)]"
                      >
                        <span className="text-[var(--hud-cyan)]">{d.term}:</span> {d.definition}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Risks */}
              <section>
                <p className="hud-readout text-[var(--hud-cyan)]">Risks</p>
                {result.risks.length === 0 ? (
                  <p className="mt-1 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-cyan-dim)]">
                    No risk
                  </p>
                ) : (
                  <ul className="mt-1 space-y-3">
                    {result.risks.map((r, i) => (
                      <li
                        key={i}
                        className={`border px-3 py-2.5 font-[family-name:var(--font-geist-mono)] text-sm ${RISK_STYLES[r.riskLevel]}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold">{r.description}</span>
                          <span className="hud-readout shrink-0">{r.riskLevel}</span>
                        </div>
                        <p className="mt-1 text-[var(--hud-text)]">{r.explanation}</p>
                        <p className="mt-1 text-[var(--hud-cyan-dim)]">Affects: {r.affectedParty}</p>
                        <p className="mt-1 text-[var(--hud-cyan-dim)]">Source: “{r.citation}”</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
