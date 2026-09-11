import { GoogleGenAI } from "@google/genai";
import { NextResponse } from "next/server";

// Same pattern as app/api/chat/route.ts: one shared client, key stays server-side.
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// The exact contract we ask Gemini to follow. Kept in one place so the
// frontend (app/analyze/page.tsx) and this route agree on field names.
const SYSTEM_PROMPT = `You are a legal document analyzer. You will receive a piece of text and must return your analysis as a single valid JSON object — no markdown, no code fences, no text outside the JSON.

First, determine whether the input is a legal document or clause at all. If it is NOT legal text (e.g. a grocery list, casual conversation, unrelated content), return only:
{
  "isLegalDocument": false,
  "reason": "<one short sentence explaining why this doesn't appear to be legal text>"
}

If it IS legal text, return exactly this structure:

{
  "isLegalDocument": true,
  "summary": "<a 3-sentence summary of the document>",
  "documentType": "<the type of document or clause, e.g. 'Confidentiality clause', 'Termination clause', 'Employment contract'. If uncertain, say 'Unclear' rather than guessing.>",
  "definitions": [
    {
      "term": "<exact term as it appears in the document>",
      "definition": "<the definition, stated explicitly or clearly supported by the document's wording>"
    }
  ],
  "risks": [
    {
      "description": "<what the risk is>",
      "explanation": "<why this is risky, in one or two sentences>",
      "affectedParty": "<who this risk applies to>",
      "riskLevel": "low" | "medium" | "high",
      "citation": "<the exact paragraph, section title, or keyword phrase from the document where this risk was found>"
    }
  ]
}

Rules:
- Return definitions only when they are explicitly stated or clearly supported by the document. Do not invent or infer a legal definition that is not supported by the text.
- If no such definitions exist, return "definitions": [] (empty array).
- If no risks are found, return "risks": [] (empty array) — do not invent one.
- Do not state anything in any field that is not actually present or directly implied in the document. Do not provide legal advice or conclusions beyond what the text says.
- "riskLevel" must be exactly one of: "low", "medium", "high" — no other values.
- Output must be valid JSON and nothing else — no explanations, no markdown formatting, no surrounding text.`;

// The shapes the frontend can expect back from this route, mirroring the
// schema above so both sides agree on what a "risk" or "definition" looks like.
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

export async function POST(request: Request) {
  try {
    const { text } = (await request.json()) as { text: string };

    if (!text || !text.trim()) {
      return NextResponse.json({ error: "No text provided to analyze." }, { status: 400 });
    }

    if (!process.env.GEMINI_API_KEY || process.env.GEMINI_API_KEY === "PASTE_YOUR_KEY_HERE") {
      return NextResponse.json(
        { error: "No Gemini API key found. Open .env.local, paste your key, then restart the dev server." },
        { status: 500 },
      );
    }

    const response = await ai.models.generateContent({
      model: "gemini-3.6-flash",
      contents: [{ role: "user", parts: [{ text }] }],
      config: {
        systemInstruction: SYSTEM_PROMPT,
        responseMimeType: "application/json",
      },
    });

    const raw = response.text ?? "";

    let result: AnalysisResult;
    try {
      result = JSON.parse(raw) as AnalysisResult;
    } catch {
      console.error("Gemini returned non-JSON output:", raw);
      return NextResponse.json(
        { error: "The model returned an unexpected format. Check the terminal for the raw output." },
        { status: 500 },
      );
    }

    return NextResponse.json(result);
  } catch (err) {
    console.error(err);
    return NextResponse.json(
      { error: "Something went wrong talking to Gemini. Check the terminal for details." },
      { status: 500 },
    );
  }
}
