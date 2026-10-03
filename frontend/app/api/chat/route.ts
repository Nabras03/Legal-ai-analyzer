import { GoogleGenAI } from "@google/genai";
import { NextResponse } from "next/server";

// One shared client. It reads the key from .env.local (never sent to the browser).
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// A single message in our chat, in the simple shape our page uses.
type Message = { role: "user" | "assistant"; content: string };

// This runs when the page sends a POST request to /api/chat
export async function POST(request: Request) {
  try {
    const { messages } = (await request.json()) as { messages: Message[] };

    // Friendly error if the key hasn't been pasted in yet.
    if (!process.env.GEMINI_API_KEY || process.env.GEMINI_API_KEY === "PASTE_YOUR_KEY_HERE") {
      return NextResponse.json(
        { error: "No Gemini API key found. Open .env.local, paste your key, then restart the dev server." },
        { status: 500 },
      );
    }

    // Gemini wants { role, parts } and uses "model" instead of "assistant".
    const contents = messages.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    }));

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash-lite", // highest free-tier quota; see aistudio.google.com for other model names
      contents,
    });

    return NextResponse.json({ reply: response.text ?? "(no response)" });
  } catch (err) {
    // The real details go to your terminal; the browser gets a short message.
    console.error(err);
    return NextResponse.json(
      { error: "Something went wrong talking to Gemini. Check the terminal for details." },
      { status: 500 },
    );
  }
}
