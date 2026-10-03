"use client";

import { useState } from "react";
import Link from "next/link";

// Mirrors the Pydantic models in Backend/main.py.
type Risk = {
  description: string;
  explanation: string;
  affectedParty: string;
  riskLevel: "low" | "medium" | "high";
  citation: string;
  // Set by the backend: whether the quote was found in the analyzed text, and where.
  citationVerified: boolean;
  citationSpan: [number, number] | null;
  // Sections of Avtalslagen that may apply; null if the check didn't run.
  legalBasis: LegalBasis[] | null;
};

type LegalBasis = {
  section: string; // "36 §"
  law: string; // "AvtL"
  quote: string;
  explanation: string;
  url: string;
  quoteVerified: boolean;
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
      legalCheckAvailable: boolean;
    };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// Colour per risk level — used for both the badge text and its border/glow.
const RISK_STYLES: Record<Risk["riskLevel"], string> = {
  low: "border-[rgba(120,255,150,0.5)] text-[#7dffa0] bg-[rgba(120,255,150,0.08)]",
  medium: "border-[var(--hud-amber)] text-[var(--hud-amber)] bg-[rgba(255,180,84,0.08)]",
  high: "border-[#ff5c6a] text-[#ff5c6a] bg-[rgba(255,92,106,0.08)]",
};

// Background tint for the highlighted quote in the source text.
const MARK_STYLES: Record<Risk["riskLevel"], string> = {
  low: "bg-[rgba(120,255,150,0.2)]",
  medium: "bg-[rgba(255,180,84,0.25)]",
  high: "bg-[rgba(255,92,106,0.3)]",
};

type Segment = { text: string; risk?: { index: number; level: Risk["riskLevel"] } };

// Splits the analyzed text into plain and highlighted pieces. Overlapping
// citations are trimmed so each character is highlighted at most once.
function highlightSegments(text: string, risks: Risk[]): Segment[] {
  const spans = risks
    .map((r, index) => ({ span: r.citationSpan, index, level: r.riskLevel }))
    .filter((s): s is { span: [number, number]; index: number; level: Risk["riskLevel"] } => s.span !== null)
    .sort((a, b) => a.span[0] - b.span[0]);

  const segments: Segment[] = [];
  let pos = 0;
  for (const { span, index, level } of spans) {
    const start = Math.max(span[0], pos);
    if (start >= span[1]) continue;
    if (start > pos) segments.push({ text: text.slice(pos, start) });
    segments.push({ text: text.slice(start, span[1]), risk: { index, level } });
    pos = span[1];
  }
  if (pos < text.length) segments.push({ text: text.slice(pos) });
  return segments;
}

export default function AnalyzePage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  // The exact text that was analyzed; citation spans point into this, not the
  // textarea, which the user may have edited since.
  const [analyzedText, setAnalyzedText] = useState("");

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!res.ok) {
        setError(`Server responded with an error (HTTP ${res.status}).`);
        return;
      }

      const data = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        setResult(data.result as AnalysisResult);
        setAnalyzedText(text);
      }
    } catch {
      setError(
        "Could not reach the analysis server. If the demo has been idle, it can take up to a minute to wake up — try again shortly.",
      );
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

              {/* Source text with cited passages highlighted */}
              {result.risks.some((r) => r.citationSpan) && (
                <section>
                  <p className="hud-readout text-[var(--hud-cyan)]">Cited Passages</p>
                  <p className="hud-scroll mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap border border-[rgba(53,224,255,0.25)] bg-[rgba(2,6,11,0.4)] px-3 py-2 font-[family-name:var(--font-geist-mono)] text-sm leading-relaxed text-[var(--hud-text)]">
                    {highlightSegments(analyzedText, result.risks).map((seg, i) =>
                      seg.risk ? (
                        <mark key={i} className={`text-[var(--hud-text)] ${MARK_STYLES[seg.risk.level]}`}>
                          {seg.text}
                          <sup className="ml-0.5 text-[var(--hud-cyan)]">[{seg.risk.index + 1}]</sup>
                        </mark>
                      ) : (
                        <span key={i}>{seg.text}</span>
                      ),
                    )}
                  </p>
                </section>
              )}

              {/* Risks */}
              <section>
                <p className="hud-readout text-[var(--hud-cyan)]">Risks</p>
                {result.risks.length > 0 && !result.legalCheckAvailable && (
                  <p className="mt-1 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-amber)]">
                    ⚠ Legal basis check unavailable right now — risks are shown without references to Avtalslagen.
                  </p>
                )}
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
                          <span className="font-semibold">
                            [{i + 1}] {r.description}
                          </span>
                          <span className="hud-readout shrink-0">{r.riskLevel}</span>
                        </div>
                        <p className="mt-1 text-[var(--hud-text)]">{r.explanation}</p>
                        <p className="mt-1 text-[var(--hud-cyan-dim)]">Affects: {r.affectedParty}</p>
                        <p className="mt-1 text-[var(--hud-cyan-dim)]">Source: “{r.citation}”</p>
                        {r.citationVerified ? (
                          <p className="hud-readout mt-1 text-[#7dffa0]">✓ Quote found in text</p>
                        ) : (
                          <p className="hud-readout mt-1 text-[var(--hud-amber)]">
                            ⚠ Quote not found in text — treat this finding with caution
                          </p>
                        )}
                        {r.legalBasis && (
                          <div className="mt-2.5 border-t border-[rgba(53,224,255,0.2)] pt-2">
                            <p className="hud-readout text-[var(--hud-cyan)]">Legal Basis · Avtalslagen</p>
                            {r.legalBasis.length === 0 ? (
                              <p className="mt-1 text-[var(--hud-cyan-dim)]">
                                No directly applicable section in Avtalslagen.
                              </p>
                            ) : (
                              <ul className="mt-1 space-y-2">
                                {r.legalBasis.map((b) => (
                                  <li key={b.section} className="text-[var(--hud-text)]">
                                    <a
                                      href={b.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="font-semibold text-[var(--hud-cyan)] underline-offset-2 hover:underline"
                                    >
                                      {b.section} {b.law} ↗
                                    </a>
                                    <p className="mt-0.5 border-l-2 border-[rgba(53,224,255,0.35)] pl-2 italic text-[var(--hud-cyan-dim)]">
                                      ”{b.quote}”
                                    </p>
                                    <p className="mt-0.5">{b.explanation}</p>
                                    {!b.quoteVerified && (
                                      <p className="hud-readout mt-0.5 text-[var(--hud-amber)]">
                                        ⚠ Quote not found in the statute text
                                      </p>
                                    )}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
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
