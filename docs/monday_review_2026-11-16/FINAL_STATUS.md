# Final Status, 14 Nov 2026 (for the 16 Nov review)

## 1. What you can demonstrate LIVE on Monday
| Item | How | Verified |
|---|---|---|
| Load the knowledge store (320 AVeriTeC claim stores) and pick or enter a claim | `run_demo.bat` → sidebar | ✓ launched from a clean environment; browser-driven run of claim 268 (4.8 s) |
| Claim processing: query, BM25 terms, spaCy entities, country | Step 2 | ✓ |
| BM25, MiniLM and Hybrid RRF ranked documents with publisher, URL, score, cross-ranks, snippet | Step 3 (stored rankings, re-verified identical to a live re-run) | ✓ |
| Generic (B) and heuristic (C) authority priors with per-document factor explanations, computed live | Step 4 | ✓ |
| Final re-ranking with the relevance and authority parts separated | Step 5 | ✓ |
| Failure and limitation cases (436, 326, 2) | sidebar | ✓ |
| Frozen held-out evaluation table, tests, curves, recall by depth | Evaluation tab | ✓ |
| Custom claim text over a claim's store (LLM prior correctly disabled) | sidebar | ✓ (claim 268 pre-computed) |
| Full live recompute of BM25 + MiniLM + RRF | sidebar | ✓ but **2–8 min on this CPU**. Use the pre-computed claim-268 run |

**Test record (14 Nov):**
- `test_demo_pipeline.py`: 10/10 with `--live` (09:30; `test_report_with_live_0930.json`) and 9/9 on the final code.
- `test_demo_app.py` (headless UI): 21/21.
- `agreement.py --selftest`: PASS.
- `run_demo.bat` started from a clean environment; Chromium-driven screenshots in `results/esa_nov2026/demo/screenshots/`.

## 2. What is a RECORDED / stored result (show it, but say so)
- **LLM authority predictions (D):** generated Sept 2026 by Claude Opus 5.5 with no web access, for 120 dev + 200 held-out claims. Not generated live; no API call is made.
- **Frozen held-out evaluation:** preregistered and run earlier. **Re-verified today** (hash gate PASS; every value identical).
- **PU relevance baseline:** run on 8 Nov. Metrics come from the original console output preserved in the session transcript. **Model files and per-claim outputs were lost on 13 Nov.**
- **Recall ceiling / promotion statistics:** exploratory, recomputed today from frozen rankings (identical to the 8 Nov figures).

## 3. Completed (today or earlier)
- Retrieval pipeline (BM25, MiniLM, Hybrid RRF), heuristic and LLM priors: completed earlier.
- Frozen held-out evaluation (n = 167): completed earlier; re-verified today.
- Recall ceiling (top-100 0.671 → top-300 0.922): completed.
- PU relevance baseline: completed earlier. Negative result: Hybrid 13/42 vs selected HistGBDT 12/42, p = 1.0.
- Dataset investigation (AVeriTeC, NELA-GT-2020, Wikidata, AuFIN/AuRED): completed. No claim–document authority labels exist.
- Live demo app, tests, fallback pages and figures: completed today.
- Annotation guidelines, instruction sheet, templates, agreement tool, pilot packet: completed today (protocol ready).
- Authority model design and evaluation protocol: completed today (design only).
- Three-domain applicability material: completed today (illustration only).
- Updated deck copy, demo script, cheat sheet, viva Q&A: completed today.

## 4. Incomplete / pending
- **Human annotation:** not started. It needs annotators and mentor sign-off on the label scheme.
- **Supervised claim-specific authority model:** not trained, because no labels exist. No Authority Recall@K exists.
- **PU baseline re-run:** blocked until the train knowledge store is re-extracted (network, ~6 GB traffic, owner approval).
- **Three-domain validation:** not done; it needs domain-stratified labelled data.
- **Reserved-180 outputs:** lost; not reconstructed and not claimed.

## 5. Limitations to state if asked
- Evidence recall ≠ authority recall.
- AVeriTeC stores were built partly from gold-derived queries, so the setting is optimistic. There is no open-web retrieval.
- n = 167 (held-out) and n = 42 (PU test) give low statistical power.
- Binary publisher-level priors promote off-topic pages.
- The LLM prior's gain is not significant.

## 6. Exact next steps after Monday
1. **Commit or back up** today's untracked work. Two data-loss incidents so far. Suggested paths: `experiments/esa_nov2026/`, `docs/monday_review_2026-11-16/`, `data/annotations/authority_pilot_2026-11/`, `results/esa_nov2026/`, `run_demo.bat`, `.streamlit/`.
2. Mentor decisions: partial relevance and authoritative-secondary in the hit definition; pool depth (20 vs 30); annotator plan.
3. Run the 200-pair pilot with 2 annotators → `agreement.py` → adjudicate → guide v1.1.
4. Decide whether to approve re-extraction of the train knowledge store (needed for the main annotation pool and the PU re-run).
5. Main annotation on AVeriTeC train claims (all test pairs double-annotated, ≥ 20 % of training pairs).
6. Train A1–A3 per `AUTHORITY_MODEL_DESIGN.md`; compare with hybrid, generic, heuristic and LLM baselines on the common human-labelled test set; report Authority Recall@10 with McNemar + bootstrap.
