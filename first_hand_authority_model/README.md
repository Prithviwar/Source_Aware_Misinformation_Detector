# First-hand authority model

Predicts, for a **claim–publisher pair**, the probability that the publisher has **first-hand authority** to establish the claim's central factual proposition:

`p_first_hand = P(first-hand authority | claim, publisher, eligible features)`

It does **not** predict whether the claim is true, whether a page is relevant or supportive, whether a publisher is generally reliable, or how often it appears in search results.

> **Current state (2026-10-29):** pipeline implemented and tested on **synthetic fixtures only**. No real data exist, no research model has been trained, and no empirical result has been produced. Real training is blocked by design until the decisions in `docs/DECISIONS.md` are made and dataset construction is authorised. See `STATUS.md`.

This project is independent of the frozen `Source_Aware_Misinformation_Detector` experiment. It reads nothing from it.

## Layout

| Path | Contents |
| --- | --- |
| `schemas/feature_schema.json` | Input features, allowed levels, sentinels (`UNKNOWN`, `NOT_COMPUTED`), prohibited input keys |
| `schemas/label_schema.json` | Human label schema and `CANNOT_JUDGE` policies |
| `config/config.template.json` | Real-run config; every methodological decision is `null` until approved |
| `config/synthetic_smoke.json` | Smoke-test config with **placeholder** decisions |
| `config/role_rules.draft.json` | Baseline 1 rule table, status `DRAFT_UNAPPROVED` |
| `src/fha/` | Package: `schema`, `labels`, `encoding`, `models`, `split`, `metrics`, `bootstrap`, `calibration`, `pipeline`, `cli`, `synthetic` |
| `tests/` | 68 pytest tests (`docs/test_results.txt`) |
| `docs/` | Decisions, reproducibility notes, draft model card, data-manifest template |
| `outputs/synthetic_smoke/` | Latest smoke run (stamped SYNTHETIC) |
| `models/` | Empty until an authorised real model is packaged |

## Setup

Requires Python 3.13 with the packages in `requirements.txt` (already present on the development machine; nothing was installed for this project). No package installation step is needed: run from the project root with `PYTHONPATH=src`.

```bash
python -m pytest -q                                   # run the tests
PYTHONPATH=src python -m fha.cli status                # list real-training blockers
PYTHONPATH=src python -m fha.cli smoke                 # synthetic end-to-end smoke test
PYTHONPATH=src python -m fha.cli validate --data pairs.jsonl [--labels]
PYTHONPATH=src python -m fha.cli predict --model <run>/model --input pairs.jsonl --rank
# real runs (blocked until decisions + authorised data exist):
PYTHONPATH=src python -m fha.cli train --config config/config.json --data <pairs.jsonl> \
    --data-manifest <manifest.json> --out outputs/<run> [--open-test]
PYTHONPATH=src python -m fha.cli package --run outputs/<run> --dest models/<version>
```

## Input record (one pair)

```json
{"pair_id": "C1::xr-stats", "claim_id": "C1", "claim_text": "...", "claim_group_id": null,
 "publisher_id": "xr-stats", "publisher_family_id": null, "publisher_resolved": true,
 "features": {"action_type": "OFFICIAL_STATISTIC", "claim_scope": "NATIONAL", "claim_topic": "LABOUR_ECONOMY",
              "publisher_type": "STATISTICS_OFFICE", "publisher_jurisdiction_level": "NATIONAL",
              "actor_relation": "NONE", "speaker_relation": "NONE", "jurisdiction_match": "SAME",
              "remit_match": "YES", "active_at_claim_date": "YES"},
 "is_synthetic": false}
```

Every feature must be present. Write `UNKNOWN` (extractor ran, no answer) or `NOT_COMPUTED` (no extractor) rather than omitting or guessing. Training records add a `label` object (see `schemas/label_schema.json`). Records containing prohibited keys (verdicts, gold evidence, retrieval rank, popularity, domain suffix, existing project predictions, …) are rejected.

## Output (one pair)

`p_first_hand` (or `null` if not scored), `info_status` (`SUFFICIENT`, `LIMITED`, `INSUFFICIENT`, `INELIGIBLE`), status reasons, `score_basis`, unavailable features, warnings (e.g. a category unseen in training), top feature contributions, and a disclaimer. A low score caused by missing information is reported as `LIMITED` or not scored, never as evidence of no authority.

## Models compared

1. `role_rules` – hand-written tiers (no learning)
2. `type_prior` – smoothed P(y=1 | publisher_type)
3. `publisher_only_lr` – L2 logistic regression on publisher features
4. `claim_conditioned_lr` – same learner, plus claim and claim–publisher interaction features

Primary comparison (pre-declared): AUPRC of model 4 minus model 3 on test pairs whose publisher (or corporate family) never appears in training, with a paired two-way (claim × publisher) bootstrap interval.
