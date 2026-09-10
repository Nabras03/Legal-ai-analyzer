"use client"; // this component runs in the browser (it uses state + clicks)

import { useState } from "react";

// The shape of one chat message.
type Message = { role: "user" | "assistant"; content: string };

export default function Home() {
  // React "state": values that, when changed, re-draw the screen.
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

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
    <main className="mx-auto flex h-screen w-full max-w-2xl flex-col p-4">
      <h1 className="mb-4 text-xl font-semibold">LegalAI Chat</h1>

      {/* The scrollable list of messages */}
      <div className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-black/10 p-4 dark:border-white/15">
        {messages.length === 0 && (
          <p className="text-sm text-black/50 dark:text-white/50">
            Ask something to get started.
          </p>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-auto max-w-[80%] rounded-lg bg-blue-600 px-3 py-2 text-white"
                : "mr-auto max-w-[80%] rounded-lg bg-black/5 px-3 py-2 dark:bg-white/10"
            }
          >
            <p className="whitespace-pre-wrap text-sm">{m.content}</p>
          </div>
        ))}

        {loading && (
          <p className="mr-auto text-sm text-black/50 dark:text-white/50">Thinking…</p>
        )}
      </div>

      {/* The input box + Send button */}
      <form onSubmit={sendMessage} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message…"
          className="flex-1 rounded-lg border border-black/15 px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-white/20 dark:bg-transparent"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </main>
  );
}
