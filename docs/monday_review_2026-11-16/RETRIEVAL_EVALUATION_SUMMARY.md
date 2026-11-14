# Retrieval Evaluation Summary (verified 14 Nov 2026)

**Dataset:** frozen, preregistered held-out sample of **200 AVeriTeC development claims** (`data/processed/averitec_heldout.jsonl`, seed 2027).
- 192 claims have at least one web evidence URL. **167 have at least one *reachable* (non-empty) evidence document**: the evaluation denominator.
- 305 of 422 evidence URLs are reachable; 117 are empty in the store.

**Verification performed today:**
1. Hash gate: the 8 frozen scripts and rankings match their preregistered SHA-256 values (after CRLF→LF).
2. Re-scoring of BM25, MiniLM and A/B/C/D from the frozen rankings with the frozen scorer: **every value identical** to `results/source_targeted/results_{heldout,dev}.json`.
3. Live BM25 / MiniLM / RRF recompute for claim 268: identical top-100 order (`test_demo_pipeline.py --live`).
4. Stage-wise recall recomputed from the frozen full rankings (`recall_ceiling.py`).

Logs: `results/esa_nov2026/logs_2026-11-14/`. Outputs: `results/esa_nov2026/reproduction/reproduction_check.json` and `results/esa_nov2026/recall_ceiling/recall_ceiling.json`.

## 1. Main table: evidence Recall@K, n = 167 [FROZEN, re-verified]

| System | R@1 | R@5 | R@10 | R@20 | R@50 | R@100 | MRR@100 | Pool coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25 | 0.036 | 0.132 | 0.180 | 0.251 | 0.443 | 0.599 | 0.085 | 0.599 |
| MiniLM dense | 0.060 | 0.180 | 0.251 | 0.353 | 0.539 | 0.701 | 0.130 | 0.701 |
| **A** Hybrid RRF | 0.060 | 0.156 | **0.251** | 0.383 | 0.563 | 0.671 | 0.125 | 0.671 |
| **B** + generic credibility prior | 0.024 | 0.174 | 0.263 | 0.383 | 0.569 | 0.671 | 0.099 | 0.671 |
| **C** + heuristic claim prior | 0.030 | 0.186 | 0.275 | 0.407 | 0.569 | 0.671 | 0.109 | 0.671 |
| **D** + LLM authority prior | 0.066 | 0.198 | **0.293** | 0.437 | 0.581 | 0.671 | 0.138 | 0.671 |

B, C and D re-rank the hybrid top-100, so their pool coverage equals A's.

## 2. Paired statistical tests [FROZEN] (`results/heldout/validation_heldout.json`)

| Test | Wins / losses / ties | Exact McNemar p | Holm p | Δ [95% bootstrap CI] |
|---|---|---:|---:|---|
| **D vs A, R@10 (primary)** | +13 / −6 / 148 | **0.167** | — | +0.042 [−0.006, 0.096] |
| D vs A, R@5 | +11 / −4 | 0.118 | 0.373 | +0.042 [−0.006, 0.090] |
| D vs A, R@20 | +12 / −3 | 0.035 | 0.176 | +0.054 [0.012, 0.102] |
| D vs B, R@10 | +16 / −11 | 0.442 | 0.884 | +0.030 [−0.030, 0.090] |

**Conclusion:** the LLM authority prior gives a directional improvement that is **not statistically significant** on the primary endpoint, and no secondary test survives Holm correction. On best-evidence rank D won on 20 claims, lost on 52 and tied on 95.

## 3. Candidate-pool coverage and the recall ceiling [recomputed, exploratory]

| Stage | Value |
|---|---|
| Collection: claims with web evidence → reachable evidence | 167/192 = 0.870 |
| Collection: evidence URLs reachable | 305/422 = 0.723 |
| Candidates per claim | min 417, median 781.5, max 1,639 |
| Hybrid claim-level recall by depth | @10 0.251 · @20 0.383 · @50 0.563 · **@100 0.671** · @200 0.850 · **@300 0.922** · @500 0.964 |
| MiniLM claim-level recall | @100 0.701 · @200 0.904 · @300 0.940 |
| BM25 claim-level recall | @100 0.599 · @300 0.850 |
| Pool ceiling for any re-ranker of the hybrid top-100 | **112/167 = 0.671** (55 claims lost before re-ranking) |
| D's R@10 as a fraction of the ceiling | 49/167 = 0.293 → 0.438 of the ceiling |
| Predicted-authority evidence document inside the pool | top-100: 23/56 claims · top-200: 37/56 · all candidates: 56/56 |

**A source that is never retrieved cannot be selected by the Authority Resolution Module.** Retrieval recall is an upper bound on anything the authority module can achieve. Raising the pool from 100 to 300 lifts the ceiling from 0.671 to 0.922, at three times the scoring and annotation cost.

Figures: `results/esa_nov2026/figures/fig1_heldout_recall_at_10.png`, `fig2_heldout_recall_curves.png`, `fig3_recall_ceiling_by_depth.png`.

## 4. Three different metrics: do not mix them

| Metric | Question | Labels | Status |
|---|---|---|---|
| **Retrieval (evidence) Recall@K** | Is at least one AVeriTeC evidence document in the top K? | AVeriTeC annotators' evidence URLs (include news and fact-checks) | **Measured** (this document) |
| **Authority Recall@K** | Is at least one document *human-labelled as authoritative and relevant for this claim* in the top K? | New human claim–document authority labels | **Not measurable yet**: no labels exist. Phase-II primary metric |
| **Relevance-ranking evaluation (PU baseline)** | Does a learned ranker put weakly labelled evidence higher than Hybrid RRF? | AVeriTeC **train** evidence URLs as weak positives; the rest unlabelled | Recorded 8 Nov on a **different dataset** (train sample); see `PU_BASELINE_REPRODUCTION_GUIDE.md` |

The LLM-authority "accuracy" proxy (top-1 0.292, top-3 0.391 against the publishers of *all* evidence URLs) is a lower-bound proxy, not authority accuracy.

## 5. Limitations
- AVeriTeC evidence includes secondary pages, so evidence recall ≠ authority recall.
- Retrieval happens inside AVeriTeC's per-claim stores, which were built partly from gold-derived queries; open-web recall would be lower.
- 167 claims means only fairly large differences are detectable.
- MiniLM sees only the first 1,000 characters of each document.
- The historical **reserved-180** retrieval outputs and LLM predictions were **lost**. They are not part of these results and were not reconstructed.
- Stage-wise ceiling numbers are exploratory (computed after the frozen evaluation, on the same claims).
