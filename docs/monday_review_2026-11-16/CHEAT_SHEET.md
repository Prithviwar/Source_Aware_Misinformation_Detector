# IR_03 Demo Cheat Sheet (16 Nov 2026)

**Start:** double-click `run_demo.bat` → `http://localhost:8501` (first start 1–2 min). **Backup:** `results\esa_nov2026\demo\fallback\INDEX.html`. **Terminal backup:** `python experiments\esa_nov2026\demo.py --claim-id 268`
**Mode:** *Stored rankings*. Live / custom only for claim 268 (pre-computed).

### Demo claims
| ID | Domain | Shows | Evidence rank Hybrid → D |
|---|---|---|---|
| **268** | Govt / health policy | Authority ≠ credibility: B lifts senate.gov press release; D lifts the executive order itself | **28 → 1** |
| 328 | Govt statistics | Statistics producer promoted | 43 → 3 |
| 89 | Health / science | NIH / journal predicted | 21 → 10 |
| 464 | Science / environment | NPS / FWS predicted | 18 → 1 |
| 436 | Limitation | Boost pushes good evidence down | 1 → 16 |
| 326 | Failure | Off-topic pages from boosted publisher | 24 → 28 |
| 2 | No effect | Predicted authority not in pool | 17 → 17 |

### Numbers to know
| Item | Value | Status |
|---|---|---|
| Held-out claims / with reachable evidence | 200 / **167** | frozen, preregistered |
| R@10 BM25 / MiniLM / Hybrid (A) | 0.180 / 0.251 / **0.251** | re-verified 14 Nov |
| R@10 B generic / C heuristic / **D LLM prior** | 0.263 / 0.275 / **0.293** | re-verified 14 Nov |
| D vs A at R@10 | +13 / −6, **exact McNemar p = 0.167**, Δ +0.042, CI [−0.006, 0.096] | **not significant** |
| Pool ceiling (hybrid top-100) | **0.671** (112/167); top-200 0.850, top-300 0.922 | recomputed from frozen rankings |
| D best-evidence rank vs hybrid | won 20, lost 52, tied 95 | frozen |
| PU baseline (TRAIN 300 claims: 179/60/61) | 5,587 pairs = 217 weak positive + 5,370 unlabelled | recorded 8 Nov |
| PU test R@10 (n = 42) | Hybrid **13/42 = 0.310** · LR 10/42 · **HistGBDT 12/42 (selected)** · LR+MiniLM 8/42; p = 1.0 | recorded; model files lost |
| Pilot annotation packet | 20 dev-sample claims × 10 docs = 200 blank pairs | built 14 Nov, **no labels** |

### Say clearly
- **Relevance** = is the page about the claim? **Authority** = is this source the origin of this claim's fact? **Credibility** = is the publisher trustworthy in general?
- Evidence Recall@K (measured) ≠ Authority Recall@K (needs human labels; not measured yet).
- LLM predictions are **stored** (Sept 2026), not generated live. No API call in the demo.
- Reserved-180 outputs: executed historically, **files lost, not used**.
- Supervised authority model: **designed, not trained**. Human dataset: **protocol ready, not collected**.
- The PU model is a **relevance** ranker, not an authority model; negative result.
- Three domains: **illustrated, not validated**.
