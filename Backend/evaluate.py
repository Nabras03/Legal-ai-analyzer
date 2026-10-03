"""Evaluates the analysis pipeline against a hand-labelled test set.

    python evaluate.py                  # run all cases, save the run, print a report
    python evaluate.py --only vite-sv   # run selected cases
    python evaluate.py --score eval/results/<run>.json   # re-score a saved run, no API calls

Each case in eval/cases.json marks risky clauses with an "anchor" (an exact
substring of the case text). A predicted risk counts as finding that clause
when its *verified* citation span overlaps the anchor, so matching reuses the
app's own citation check instead of comparing free-text descriptions.
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from google.genai import errors

EVAL_DIR = Path(__file__).parent / "eval"
CASES_PATH = EVAL_DIR / "cases.json"
RESULTS_DIR = EVAL_DIR / "results"
REPORT_PATH = EVAL_DIR / "REPORT.md"
LEVELS = ["low", "medium", "high"]


def load_cases() -> list[dict]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    for case in cases:
        for anchor in [r["anchor"] for r in case.get("risks", [])] + case.get("benign", []):
            if anchor not in case["text"]:
                raise ValueError(f"{case['id']}: anchor not found in text: {anchor!r}")
    return cases


# ---------------------------------------------------------------- running


def run_case(case: dict) -> dict:
    """Run one case through the real pipeline, waiting out per-minute limits."""
    import main
    from legal_check import CANDIDATES_PER_RISK, risk_query

    for attempt in range(4):
        try:
            result = main.run_analysis(case["text"])
            break
        except errors.ClientError as e:
            if e.code != 429 or attempt == 3:
                return {"error": f"{e.code} {e.status}"}
            print("    rate limited, waiting 60 s")
            time.sleep(60)
        except (errors.ServerError, ValueError) as e:
            return {"error": str(e)[:200]}

    output = result.model_dump()
    # Retrieval is deterministic, so re-running the search shows which
    # sections the model was shown, to tell retrieval misses from judgement misses.
    if output["isLegalDocument"] and output["risks"] and main.legal_index:
        hits = main.legal_index.search(main.client, [risk_query(r) for r in result.risks], k=CANDIDATES_PER_RISK)
        for risk, candidates in zip(output["risks"], hits):
            risk["retrieved"] = [s.id for s, _ in candidates]
    return {"output": output}


def run(cases: list[dict], delay: float) -> dict:
    import main
    from retrieval import EMBEDDING_MODEL

    outputs = {}
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']}")
        start = time.time()
        outputs[case["id"]] = run_case(case) | {"seconds": round(time.time() - start, 1)}
        if i < len(cases):
            time.sleep(delay)
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": main.MODEL,
        "embeddingModel": EMBEDDING_MODEL,
        "outputs": outputs,
    }


# ---------------------------------------------------------------- scoring


def _overlaps(a: list[int] | tuple[int, int], b: tuple[int, int]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def _span(text: str, anchor: str) -> tuple[int, int]:
    start = text.index(anchor)
    return start, start + len(anchor)


def score(cases: list[dict], run_data: dict) -> tuple[dict, list[str]]:
    c = dict.fromkeys([
        "cases", "errors", "classified", "expected", "found", "predicted", "predicted_tp",
        "benign_flagged", "unlabelled", "unverified", "level_exact", "level_close",
        "basis_cases", "basis_hit", "retrieval_hit", "none_cases", "none_correct",
        "legal_unavailable", "statute_quotes", "statute_quotes_verified",
    ], 0)
    notes: list[str] = []

    for case in cases:
        entry = run_data["outputs"].get(case["id"])
        if entry is None:
            continue
        c["cases"] += 1
        if "error" in entry:
            c["errors"] += 1
            notes.append(f"{case['id']}: error {entry['error']}")
            continue
        out = entry["output"]
        if out["isLegalDocument"] == case["isLegal"]:
            c["classified"] += 1
        else:
            notes.append(f"{case['id']}: classified isLegal={out['isLegalDocument']}, expected {case['isLegal']}")
        if not case["isLegal"]:
            continue

        expected = [(r, _span(case["text"], r["anchor"])) for r in case["risks"]]
        benign = [_span(case["text"], b) for b in case.get("benign", [])]
        preds = out.get("risks", []) if out["isLegalDocument"] else []
        if out["isLegalDocument"] and preds and not out["legalCheckAvailable"]:
            c["legal_unavailable"] += 1

        # Precision side: classify every predicted risk.
        for p in preds:
            c["predicted"] += 1
            span = p.get("citationSpan")
            for b in p.get("legalBasis") or []:
                c["statute_quotes"] += 1
                c["statute_quotes_verified"] += b["quoteVerified"]
            if span is None:
                c["unverified"] += 1
                notes.append(f"{case['id']}: unverified citation {p['citation'][:60]!r}")
            elif any(_overlaps(span, s) for _, s in expected):
                c["predicted_tp"] += 1
            elif any(_overlaps(span, s) for s in benign):
                c["benign_flagged"] += 1
                notes.append(f"{case['id']}: flagged a benign clause ({p['riskLevel']}): {p['description'][:60]}")
            else:
                c["unlabelled"] += 1
                notes.append(f"{case['id']}: flagged an unlabelled passage ({p['riskLevel']}): {p['description'][:60]}")

        # Recall side: was each expected risk found, and how well?
        for exp, span in expected:
            c["expected"] += 1
            matches = [p for p in preds if p.get("citationSpan") and _overlaps(p["citationSpan"], span)]
            if not matches:
                notes.append(f"{case['id']}: missed expected {exp['level']} risk")
                continue
            c["found"] += 1
            level = max((p["riskLevel"] for p in matches), key=LEVELS.index)
            c["level_exact"] += level == exp["level"]
            c["level_close"] += abs(LEVELS.index(level) - LEVELS.index(exp["level"])) <= 1
            if level != exp["level"]:
                notes.append(f"{case['id']}: severity {level}, expected {exp['level']}")

            if "sections" not in exp or not out["legalCheckAvailable"]:
                continue
            cited = {b["section"] for p in matches for b in (p.get("legalBasis") or [])}
            retrieved = {s for p in matches for s in p.get("retrieved", [])}
            if exp["sections"]:
                c["basis_cases"] += 1
                hit = bool(cited & set(exp["sections"]))
                c["basis_hit"] += hit
                c["retrieval_hit"] += bool(retrieved & set(exp["sections"]))
                if not hit:
                    notes.append(f"{case['id']}: cited {sorted(cited) or 'nothing'}, expected one of {exp['sections']}"
                                 f" (retrieved: {sorted(retrieved)})")
            else:
                c["none_cases"] += 1
                c["none_correct"] += not cited
                if cited:
                    notes.append(f"{case['id']}: cited {sorted(cited)}, expected no applicable section")
    return c, notes


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}% ({n}/{d})" if d else "n/a"


def report(c: dict, notes: list[str], run_data: dict) -> str:
    rows = [
        ("Legal / not-legal classification", _pct(c["classified"], c["cases"] - c["errors"])),
        ("Risk recall: expected risky clauses found", _pct(c["found"], c["expected"])),
        ("Risk precision: flagged risks that are labelled risky", _pct(c["predicted_tp"], c["predicted"])),
        ("  – balanced clauses wrongly flagged", str(c["benign_flagged"])),
        ("  – unlabelled passages flagged", str(c["unlabelled"])),
        ("Contract citations verified in text", _pct(c["predicted"] - c["unverified"], c["predicted"])),
        ("Severity: exact match", _pct(c["level_exact"], c["found"])),
        ("Severity: within one level", _pct(c["level_close"], c["found"])),
        ("Legal basis: expected section cited", _pct(c["basis_hit"], c["basis_cases"])),
        ("Retrieval: expected section in top 5", _pct(c["retrieval_hit"], c["basis_cases"])),
        ("Legal basis: correctly cites nothing", _pct(c["none_correct"], c["none_cases"])),
        ("Statute quotes verified", _pct(c["statute_quotes_verified"], c["statute_quotes"])),
    ]
    lines = [
        "# Evaluation report",
        "",
        f"Run {run_data['timestamp']} · model `{run_data['model']}` · embeddings `{run_data['embeddingModel']}` · "
        f"{c['cases']} cases, {c['errors']} errors"
        + (f", legal check unavailable in {c['legal_unavailable']}" if c["legal_unavailable"] else ""),
        "",
        "| Metric | Result |",
        "|---|---|",
        *[f"| {name} | {value} |" for name, value in rows],
        "",
        "## Notes",
        "",
        *([f"- {n}" for n in notes] or ["- none"]),
    ]
    return "\n".join(lines) + "\n"


def main_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--score", type=Path, help="re-score a saved run instead of calling the API")
    parser.add_argument("--only", nargs="+", metavar="ID", help="run only these case ids")
    parser.add_argument("--delay", type=float, default=8.0,
                        help="seconds between cases (default 8; each case makes two generation calls and the Flash-Lite free tier allows 15 per minute)")
    args = parser.parse_args()

    cases = load_cases()
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]

    if args.score:
        run_data = json.loads(args.score.read_text(encoding="utf-8"))
    else:
        run_data = run(cases, args.delay)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = RESULTS_DIR / f"run-{run_data['timestamp'].replace(':', '')}.json"
        path.write_text(json.dumps(run_data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Saved run to {path}")

    text = report(*score(cases, run_data), run_data)
    print("\n" + text)
    if not args.only:
        REPORT_PATH.write_text(text, encoding="utf-8")
        print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main_cli()
