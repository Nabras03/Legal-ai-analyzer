# Evaluation report

Run 2026-10-03T21:38:34 · model `gemini-3.5-flash-lite` · embeddings `gemini-embedding-001` · 23 cases, 0 errors

| Metric | Result |
|---|---|
| Legal / not-legal classification | 100% (23/23) |
| Risk recall: expected risky clauses found | 100% (18/18) |
| Risk precision: flagged risks that are labelled risky | 90% (18/20) |
|   – balanced clauses wrongly flagged | 1 |
|   – unlabelled passages flagged | 1 |
| Contract citations verified in text | 100% (20/20) |
| Severity: exact match | 83% (15/18) |
| Severity: within one level | 100% (18/18) |
| Legal basis: expected section cited | 100% (18/18) |
| Retrieval: expected section in top 5 | 100% (18/18) |
| Legal basis: correctly cites nothing | n/a |
| Statute quotes verified | 100% (27/27) |

## Notes

- short-acceptance-window: severity high, expected medium
- long-auto-renewal: severity high, expected medium
- perpetual-confidentiality: severity high, expected medium
- balanced-sale: flagged an unlabelled passage (medium): Short notice window for defect claims
- balanced-service-sv: flagged a benign clause (medium): Short termination notice period
