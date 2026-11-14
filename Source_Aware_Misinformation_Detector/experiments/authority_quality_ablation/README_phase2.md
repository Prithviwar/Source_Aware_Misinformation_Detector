# Authority-quality ablation, Phase 2: matched mismatched-authority perturbation

**Status: exploratory. Not preregistered.** The preregistered human-gold family, the frozen results
and the manuscript are unchanged.

## Question

On claims where the predicted top-1 publisher (D1) actually changes the ranking, how does a
deliberately mismatched publisher of the same kind and similar visibility (X1) compare with no
authority (A0) and with D1?

## Terminology

X1 is a **deliberately mismatched authority** (a matched mismatched-authority perturbation). By
construction it is only: visible in the same frozen retrieval pool, not a reachable human-gold
publisher, outside the predictor's top-3, in the same generic publisher category as D1, and matched as
closely as possible on the number of pool documents. It is **not** claimed to be factually wrong or
non-authoritative; gold evidence is one valid path and a non-gold publisher may still hold the fact.

## Design

- Analysis set S: the 79 gold-reachable held-out claims whose D1 publisher has at least one document in
  the frozen hybrid top-100. Outside S, D1 equals A0.
- Eligibility (all must hold): E1 in the pool; E2 not a reachable human-gold publisher; E3 not among the
  predicted top-3 publisher keys; E4 same generic-prior category as D1's publisher.
- Selection: closest pool document count to D1's publisher; ties broken by
  `random.Random(2029 * 100000 + claim_id)`.
- The assignment (`x1_assignment.csv`) was written once, hashed and made read-only before scoring; the
  scorer verifies the hash before and after scoring.
- All three conditions use the same frozen hybrid top-100 pool, `validation_heldout.rerank`, lambda = 1.

## Gate

A0 must equal the stored system A top-100 rankings (200 claims), and A0 and D1 must reproduce the
Phase 1 per-claim first-gold ranks (167 claims). The gate passed.

## Statistics

Family AQA-P2: R@10 comparisons D1 vs A0, X1 vs A0, X1 vs D1; exact McNemar; paired bootstrap 95% CI
(seed 2026); Holm within these three only. R@5 and R@20 are descriptive and uncorrected.

## Structural properties to keep in mind

- X1 never boosts a reachable gold document, so X1 cannot place a gold document higher than A0 does.
- X1 moves its own documents to the top ranks, so its low-rank metrics (R@1, R@5) fall mechanically
  in proportion to how many documents the X1 publisher has in the pool.
- 42 of 79 X1 picks were tie-breaks among equivalent candidates; the effect of the tie-break seed has
  not yet been measured.

## Files

- `build_x1_assignment.py`, `run_x1.py`, `config_phase2.json`, this README.
- Outputs in `results/authority_quality_ablation_phase2/`: `x1_assignment.csv`, `x1_assignment.sha256`,
  `summary.json`, `log.txt`, `per_system.csv`, `tests.csv`, `per_claim.csv`.

## Not run

20-seed tie-break sensitivity; Phase 2 targeting; the 180 untouched development claims; the
AI-primary endpoint.
