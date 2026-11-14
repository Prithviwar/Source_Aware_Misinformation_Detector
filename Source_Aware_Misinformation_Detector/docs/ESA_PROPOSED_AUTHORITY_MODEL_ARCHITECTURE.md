> **Update 2026-11-14:** superseded by `docs/monday_review_2026-11-16/AUTHORITY_MODEL_DESIGN.md`. This file was written before the PU relevance baseline ran (8 Nov). Its statements that the relevance baseline is "not trained" and the extraction is "awaiting approval" are stale. Kept unchanged below for the record.

# Proposed Claim-Specific Document Authority Model (PROPOSED — NOT IMPLEMENTED, NOT TRAINED)

**Status:** design proposal for Capstone Phase II, written 2026-11-08 for the Phase-I ESA.
**No part of this model has been implemented or trained.** No human claim–document authority labels exist in the project (`data/annotations/heldout_primary_package/README.md` states the human protocol was "NOT executed"). It must not be presented as a result.

The only learned component prepared in Phase I is a separate **relevance** baseline (`experiments/esa_nov2026/relevance_baseline/`). It is code-complete but **not trained**, because the AVeriTeC train knowledge-store extracts are not on disk; see the ESA report, §5–6.

---

## 1. Why two outputs

| Concept | Question it answers | Property of | Example |
|---|---|---|---|
| **Relevance** | Does this document contain information about the claim's fact? | (claim, document) | A news article quoting the unemployment figure is relevant |
| **Publisher credibility** | Is this publisher generally trustworthy? | publisher only | Reuters is credible for every claim |
| **Claim-specific authority** | Is this document a first-hand or authoritative source *for this claim's fact*? | (claim, document) | The statistics office's release is authoritative; the news article is secondary |

The existing system has only a **binary, publisher-level** authority signal (`authority_retrieval.rerank`: `minmax(hybrid score) + 1·prior`). Because the min-max score is in [0, 1] and the prior is 0 or 1, **every boosted document outranks every non-boosted one**. Measured on the frozen held-out set, D moved 267 documents from below hybrid rank 50 into a top-10. 263 of them are not AVeriTeC evidence documents (`results/esa_nov2026/authority/promotion_stats.json`). The proposed model separates the two questions and works at **document level**.

## 2. Architecture

```
             claim c (text, speaker, date, country)
                      │
   ┌──────────────────┴───────────────────┐
   │ Stage 1  Candidate generation (EXISTING, frozen)                     │
   │   BM25 + MiniLM dense -> RRF (k=60) over the claim's collection      │
   │   pool = hybrid top-N  (N = 100 now; N≈300 proposed, coverage 0.922) │
   └──────────────────┬───────────────────┘
                      │ for each candidate document d in pool
   ┌──────────────────┴───────────────────┐
   │ Stage 2  Pair encoder f(c, d)                                        │
   │   features: retrieval scores/ranks, URL-derived source type,         │
   │   claim-entity ↔ domain match, Wikidata official-site match,         │
   │   frozen MiniLM claim⊙doc embedding; (stretch) cross-encoder         │
   └───────┬──────────────────────────────┬───────┘
           │                              │
   ┌───────┴────────┐            ┌────────┴──────────────┐
   │ Head R:        │            │ Head A:               │
   │ P(relevant|c,d)│            │ P(authoritative|c,d,  │
   │ trained on     │            │   relevant)           │
   │ AVeriTeC gold  │            │ trained ONLY on new   │
   │ (+ human rel.) │            │ HUMAN authority labels│
   └───────┬────────┘            └────────┬──────────────┘
           └──────────────┬───────────────┘
   ┌──────────────────────┴───────────────────────┐
   │ Stage 3  Ranking score  s = P(R) · (1 + β · P(A | R))                │
   │   β tuned on validation claims only; β = 0 -> relevance-only ranking │
   │   graded, document-level (no hard publisher filter)                  │
   └──────────────────────┬───────────────────────┘
                          │
              ranked evidence list (+ optional publisher aggregation
              max_d P(A) for source-targeted retrieval)
```

### Design notes
- **Head R** can be trained on AVeriTeC train gold as a weak relevance label. The Phase-I relevance baseline is this head in isolation.
- **Head A** needs new labels. The proposed classes are primary, authoritative secondary, secondary/derivative, not authoritative and cannot determine. A document counts as an *authority hit* only if it is relevant **and** primary or authoritative secondary (`RESEARCH_PROPOSAL_INFORMATION_PACKAGE.md` §7.2). Whether partial relevance counts needs mentor approval.
- **Combination** is multiplicative, so an authoritative but irrelevant page cannot outrank a relevant one. This directly targets the binary-boost failure.
- **Model ladder:** M1 logistic regression, then M2 gradient boosting, then M3 with frozen MiniLM features. M4 (fine-tuned two-head cross-encoder) is a GPU stretch goal (§8 of the information package).

## 3. Data the model needs (does not exist yet)

| Need | Source | Status |
|---|---|---|
| Claims and candidate documents | AVeriTeC **train** split + train knowledge-store extracts for a sampled set | Split frozen (`results/esa_nov2026/relevance_baseline/train_sample_split.json`, sha `1b994a96…`); extraction **awaiting approval** |
| Relevance labels | AVeriTeC evidence URLs (weak) + human relevance judgements | Weak labels available once extracted; human labels not collected |
| **Authority labels** | **New human annotation**, two annotators on the test set, adjudication | **Not collected.** Guide must be adapted from `data/annotations/heldout_primary_package/ANNOTATION_GUIDE.md` |

## 4. Leakage controls (carried over and extended)
These are never used as features and are hidden from annotators: AVeriTeC questions, answers, justification, verdict, fact-checking article, gold indicators, the knowledge-store `type`/`query` fields, file order and raw archive-wrapped URLs. Publisher document counts in the pool are excluded by default, because the store was built from gold-derived queries. Splits are claim-disjoint (and ideally event-disjoint). The reserved-180 dev claims and any sealed gold are never used.

## 5. Evaluation (proposed)
Each stage is reported separately against an empirical ceiling:
1. collection coverage;
2. candidate recall at N = 100/200/300;
3. Head R: precision, recall, F1 and PR-AUC;
4. Head A: per-class P/R/F1 and macro-F1;
5. final Authority Recall@5/10/20, MRR and nDCG@10.

Baselines A (hybrid), C (heuristic) and D (LLM prior) run on the same pool. Running D on new claims needs new LLM calls, which require approval.
