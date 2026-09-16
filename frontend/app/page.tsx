"use client"; // this component runs in the browser (it uses state + clicks)

import { useEffect, useState } from "react";
import Link from "next/link";

// The shape of one chat message.
type Message = { role: "user" | "assistant"; content: string };

export default function Home() {
  // React "state": values that, when changed, re-draw the screen.
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // Cosmetic HUD clock. Empty until mounted so server and browser markup match.
  const [now, setNow] = useState("");
  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString("en-GB"));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault(); // stop the browser from reloading the page on submit
    const text = input.trim();
    if (!text || loading) return;

    // Add the user's message to the list right away.
    const nextMessages: Message[] = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    try {
      // Call our own backend route (which then calls Gemini).
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: nextMessages }),
      });
      const data = await res.json();

      const reply: string = data.error ? "⚠️ " + data.error : data.reply;
      setMessages([...nextMessages, { role: "assistant", content: reply }]);
    } catch {
      setMessages([
        ...nextMessages,
        { role: "assistant", content: "⚠️ Could not reach the server." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-dvh w-full items-center justify-center overflow-hidden px-4 py-6">
      {/* Decorative overlays — never capture clicks. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 50%, transparent 40%, rgba(2,6,11,0.7) 100%)",
        }}
      />
      <div
        aria-hidden
        className="animate-scan pointer-events-none fixed inset-x-0 top-0 z-0 h-24"
        style={{
          background:
            "linear-gradient(180deg, transparent, rgba(53,224,255,0.10) 50%, transparent)",
        }}
      />

      {/* The console panel */}
      <main className="hud-panel hud-corner animate-boot relative z-10 flex h-[86dvh] w-full max-w-3xl flex-col">
        {/* ---- Header ---- */}
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--hud-line)] px-5 py-4">
          <div>
            <h1
              className="text-glow font-[family-name:var(--font-rajdhani)] text-2xl font-bold tracking-[0.35em] text-[var(--hud-cyan)]"
            >
              LEGAL&nbsp;AI
            </h1>
            <p className="hud-readout mt-1">Jarvis Interface</p>
            <Link
              href="/analyze"
              className="hud-readout mt-2 inline-block border border-[var(--hud-cyan)] px-3 py-1.5 text-[var(--hud-cyan)] transition-all hover:bg-[rgba(53,224,255,0.15)]"
            >
              Text Analyzer →
            </Link>
          </div>

          <div className="text-right">
            <div className="text-glow font-[family-name:var(--font-geist-mono)] text-lg text-[var(--hud-cyan)] tabular-nums">
              {now || "--:--:--"}
            </div>
            <div className="hud-readout mt-1 flex items-center justify-end gap-2">
              <span className="animate-blink text-[var(--hud-cyan)]">●</span>
              <span>Sys Online</span>
            </div>
            <div className="hud-readout mt-0.5">Gemini-3.6-Flash · Link Stable</div>
            <div className="hud-readout mt-0.5">Pwr 98%</div>
          </div>
        </header>

        {/* ---- Transcript ---- */}
        <div className="hud-scroll flex-1 space-y-5 overflow-y-auto px-5 py-5">
          {messages.length === 0 && (
            <p className="hud-readout font-[family-name:var(--font-geist-mono)]">
              &gt; Awaiting input
              <span className="animate-blink ml-1 inline-block">_</span>
            </p>
          )}

          {messages.map((m, i) => {
            const isUser = m.role === "user";
            const isWarning = m.content.startsWith("⚠️");
            return (
              <div
                key={i}
                className={`animate-msg flex flex-col ${isUser ? "items-end" : "items-start"}`}
              >
                <span className="hud-readout mb-1">
                  {isUser ? "User" : "J.A.R.V.I.S."}
                </span>
                <div
                  className={[
                    "max-w-[85%] border px-4 py-2.5 font-[family-name:var(--font-geist-mono)] text-sm leading-relaxed",
                    isUser ? "clip-corner-r" : "clip-corner-l",
                    isWarning
                      ? "border-[var(--hud-amber)] bg-[rgba(255,180,84,0.08)] text-[var(--hud-amber)]"
                      : isUser
                        ? "border-[rgba(53,224,255,0.4)] bg-[rgba(53,224,255,0.08)] text-[var(--hud-text)]"
                        : "border-[rgba(53,224,255,0.55)] bg-[rgba(53,224,255,0.12)] text-[var(--hud-text)] shadow-[0_0_18px_rgba(53,224,255,0.15)]",
                  ].join(" ")}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="animate-msg flex flex-col items-start">
              <span className="hud-readout mb-1">J.A.R.V.I.S.</span>
              <div className="hud-readout flex items-center gap-2 font-[family-name:var(--font-geist-mono)]">
                Processing
                <span className="processing-bar" />
                <span className="processing-bar" />
                <span className="processing-bar" />
              </div>
            </div>
          )}
        </div>

        {/* ---- Input ---- */}
        <form
          onSubmit={sendMessage}
          className="flex items-center gap-3 border-t border-[var(--hud-line)] px-5 py-4"
        >
          <span className="hud-readout text-[var(--hud-cyan)]">&gt;</span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="ENTER COMMAND…"
            className="flex-1 border-b border-[rgba(53,224,255,0.35)] bg-transparent py-1.5 font-[family-name:var(--font-geist-mono)] text-sm text-[var(--hud-text)] caret-[var(--hud-cyan)] outline-none transition-colors placeholder:text-[var(--hud-cyan-dim)] focus:border-[var(--hud-cyan)]"
          />
          <button
            type="submit"
            disabled={loading}
            className="hud-readout border border-[var(--hud-cyan)] px-4 py-2 text-[var(--hud-cyan)] transition-all hover:bg-[rgba(53,224,255,0.15)] hover:shadow-[0_0_16px_rgba(53,224,255,0.4)] disabled:opacity-40 disabled:shadow-none"
          >
            Transmit
          </button>
        </form>
      </main>
    </div>
  );
}
