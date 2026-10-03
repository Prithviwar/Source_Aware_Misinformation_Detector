# Authority-quality ablation, Phase 1

**Status: exploratory. Not preregistered.** No existing protocol covers these comparisons. The
preregistered human-gold family, the frozen results and the manuscript are unchanged.

## Question

How does retrieval change as the authority information given to the same reranker improves from
none, to the predicted top-1 publisher, to the predicted top-3 publishers, to gold publishers?

## Conditions

All conditions rerank the same frozen hybrid top-100 pool with the same function
(`validation_heldout.rerank`, which calls `authority_retrieval.rerank`:
min-max relevance + lambda * prior) and lambda = 1. Only the publisher keys in the prior change.

| Condition | Publisher keys used by the prior |
|---|---|
| A0 | none (the frozen hybrid ranking; equal to stored system A) |
| D1 | keys of the highest-ranked predicted publisher entry with a usable publisher key |
| D3 | union of keys of up to three predicted entries (equal to stored system D) |
| O | ORACLE, diagnostic only: existing gold publisher-key construction (`gold_info()["gold_keys"]`) |

D1 definition note: for 1 of 200 claims (claim 180) the strict rank-1 entry has no usable key, so
the rank-2 entry is used. This is reported in `summary.json` and `per_claim.csv`.

O uses the publishers of all human gold URLs. Because the evaluation target is the same set of gold
documents, O is close to the ceiling set by pool coverage. It is not an achievable system.

## Reproduction gate

Before scoring D1 or O, the script checks that A0 and D3 reproduce:

- the stored top-100 URL order for systems A and D on all 200 claims;
- every field of the stored rows in `results/source_targeted/results_heldout.json`;
- every field of the stored AI-primary rows.

The script stops if any check fails. In this run all checks passed (see `log.txt`).

## Statistics

Exact McNemar tests and paired bootstrap 95% CIs use the existing functions in
`validation_heldout.py` (bootstrap seed 2026). The new family AQA-P1 contains four R@10 comparisons
(D1 vs A0, D3 vs D1, O vs D3, O vs A0), Holm-corrected within that family only. R@5, R@20 and all
within-stratum comparisons are descriptive and uncorrected.

## Files

- `run_ablation.py` - main experiment (gate, four conditions, tests, strata).
- `strata_paired.py` - descriptive paired tests within strata, read from `per_claim.csv`.
- `config.json` - design and parameters.
- Outputs in `results/authority_quality_ablation/`: `summary.json` (metadata, provenance hashes,
  all results), `log.txt`, `per_system_human_gold.csv`, `per_system_ai_primary.csv`, `tests.csv`,
  `strata.csv`, `strata_paired.csv`, `per_claim.csv`.

## Reproducibility

The project directory is not a git repository, so no commit hash exists. `summary.json` records the
SHA-256 of this code, the reused project code and every input artifact, together with the seeds,
lambda, pool size, model identifiers and denominators. No LLM calls are made.

```
python experiments/authority_quality_ablation/run_ablation.py
python experiments/authority_quality_ablation/strata_paired.py
```

Both scripts refuse to overwrite existing outputs.

## Not run in Phase 1

- the mismatched-authority condition (X);
- the Phase 2 targeting ladder.
