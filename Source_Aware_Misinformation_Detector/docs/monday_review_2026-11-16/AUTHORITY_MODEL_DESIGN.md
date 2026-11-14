# Supervised Claim-Specific Document Authority Model: Design and Evaluation Protocol

**Status: PROPOSED. NOT TRAINED.** It cannot be trained until human authority labels exist (see `annotation/`).
This document supersedes `docs/ESA_PROPOSED_AUTHORITY_MODEL_ARCHITECTURE.md` (2026-11-08); that file pre-dates the PU baseline run and its "not trained / awaiting approval" lines about the relevance baseline are stale.

---

## 1. Problem definition

- **One example = one pair `(claim c, candidate document d)`.** Here `d` is drawn from the hybrid RRF pool of `c`.
- **Two targets, kept separate:**
  - **Relevance** `y_R ∈ {relevant, partial, not, cannot_determine}`: does `d` address `c`'s fact?
  - **Authority** `y_A ∈ {primary, authoritative_secondary, secondary_derivative, not_authoritative, cannot_determine}`: is `d`'s publisher the origin (or an expert faithful reporter) of `c`'s fact?
- **Authority hit** = relevant (or partial; mentor decision) **AND** (primary or authoritative_secondary).

Why the current module needs replacing: prior D is **binary and publisher-level**. Because min-max relevance lies in [0, 1] and the prior is 0 or 1, every document from a boosted publisher outranks every other document. On the frozen held-out set this placed 267 documents from below hybrid rank 50 into some claim's top 10, and 263 of them were not evidence documents (`authority_promotion_stats.py`, exploratory). The model must therefore be **graded and document-level**.

## 2. Features (prediction-time information only)

| Group | Features | Source |
|---|---|---|
| Retrieval relevance | BM25 score and rank, MiniLM cosine and rank, RRF score and rank, rank agreement | existing frozen retrievers |
| Claim–document semantics | MiniLM claim embedding ⊙ document embedding (384-d), cosine; claim-term and number overlap; entity overlap (claim entities found in document text) | existing code / spaCy |
| Document type | URL patterns: `.pdf`, `/press-release`, `/news`, `/statistics`, `/data`, `/legislation`, `/opinion`; social-post URL; archive host; path depth; document length | URL + text |
| Primary-source indicators | text cues: "By the authority vested in…", "Table", "Release", "Abstract / Methods / DOI", "Section 1.", first-person official statement; official-archive host | text + URL |
| Publisher / domain metadata | domain type (gov, intergov, academic, news, reference, platform), country of the government domain vs the claim country, Wikidata official-website match for claim entities | `authority_retrieval` + Wikidata cache |
| Claim–source expertise | claim topic (health, economy, law, science, elections…) × publisher type; claim-entity ↔ domain/handle match | spaCy + rules (+ topic classifier later) |
| Publication information | document date vs claim date (where extractable), "updated" markers | text |
| Evidence provenance | does the document cite or link a primary record (outbound official links, "according to")? Does it embed a quote? | text |
| LLM prior (optional feature, ablated) | is `d`'s publisher in the stored LLM top-3 for `c`? | stored predictions; new claims need approved LLM calls |

**Forbidden as features and hidden from annotators:** AVeriTeC verdict, justification, Q/A, fact-check article, gold/evidence indicator, KS `type`/`query`, file order (`doc_idx`), raw archive-wrapped URL, and pool publisher counts (the store was built from gold-derived queries). This list is already enforced in code for the relevance baseline (`relevance_baseline/rb_common.py FORBIDDEN_FEATURE_SOURCES`).

## 3. Models (ladder, simplest first)

| ID | Model | Notes |
|---|---|---|
| A0 | Heuristic prior C (existing) | baseline |
| A1 | Logistic regression on hand features | interpretable coefficients |
| A2 | Gradient boosting (HistGBDT) on hand features | strong regularisation needed. In the PU baseline, the same model family **overfit**: it reached the pool ceiling on its own training claims |
| A3 | Logistic regression + frozen MiniLM pair features | |
| A4 *(future)* | Fine-tuned two-head cross-encoder (relevance head + authority head) | GPU; Phase-II stretch |

**Two heads.** Head R predicts relevance and can be pre-trained on AVeriTeC weak evidence labels (the PU baseline is this head in isolation). Head A predicts authority and is trained **only on human authority labels**.

**Ranking score:** `s(c,d) = P_R(d) · (1 + β · P_A(d))`, with β chosen on validation claims only. This is multiplicative, so an authoritative but irrelevant page cannot outrank a relevant one. That fixes the binary-boost failure. β = 0 gives the relevance-only ranking, and the comparison against it is reported.

**PU labels are never used as authority labels.** Weak evidence-URL labels may only pre-train Head R.

## 4. Data split

- **Claim-disjoint** train / validation / test, from the frozen AVeriTeC train sample (fit 179 / val 60 / test 61, seed 2051, sha `1b994a96…`). Optionally also **event-disjoint**: near-duplicate claims about the same event are kept in the same split, checked by MiniLM claim similarity > 0.8 and manual review.
- **Never** the 200 held-out dev claims (frozen study), the 180 reserved dev claims, or the AVeriTeC test split.
- **Common candidate pool:** every system re-ranks the **same** hybrid top-N per claim (N = annotation depth, 20–30), so differences come from ranking, not retrieval.

## 5. Metrics

| Level | Metric | Role |
|---|---|---|
| Final ranking | **Authority Recall@10**: share of eligible test claims (≥ 1 human authority hit in the pool) with ≥ 1 authority hit in the top 10 | **Primary** |
| Final ranking | Authority Precision@10, MRR, nDCG@10 (graded: primary 3, auth-secondary 2, secondary 1, not 0, gated by relevance) | Secondary |
| Head A | per-class P/R/F1, macro-F1, binary-hit F1, PR-AUC | Secondary |
| Head A | Calibration: Brier score, expected calibration error, reliability plot | Secondary |
| Pool | Pool ceiling: share of claims whose top-N contains any authority hit | Reported, so results are read against the ceiling |

**Statistics.** Paired exact McNemar on per-claim hit@10 (primary model vs each baseline) and a paired bootstrap 95% CI. Holm correction across the baseline family. The selection rule (validation Authority R@10, ties → simpler model) is fixed before the test set is opened, and the test set is scored once.

**Power warning.** With about 60 test claims, only large effects (≳ 15 points of R@10) are detectable. The project will state this up front, as it did for the PU baseline.

## 6. Baselines on the common human-annotated test set

1. **A: Hybrid RRF** (relevance only).
2. **B: generic credibility prior** (publisher type).
3. **C: heuristic claim-specific prior** (entity / country rules).
4. **D: LLM authority prior.** For new claims this needs new LLM calls, which require owner approval and must use the frozen prompt.
5. **Head R only** (supervised relevance).
6. **Proposed:** Head R × Head A.

## 7. What this design deliberately does not claim

- No authority model has been trained, and no Authority Recall@K has been measured.
- The frozen held-out results measure **evidence (relevance) recall** against AVeriTeC citations, not authority.
- The PU result shows that a relevance ranker trained on citation proxies did not beat Hybrid RRF. That supports, but does not prove, the need for human authority labels.
