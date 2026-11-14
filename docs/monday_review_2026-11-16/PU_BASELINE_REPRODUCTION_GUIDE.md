# PU Relevance-Ranking Baseline: Status and Reproduction Guide

> **This is a RELEVANCE / citation-ranking baseline trained on weak positive-unlabelled labels. It is NOT a claim-specific authority model.**

## 1. What exists today (14 Nov 2026)

| Artifact | Status | Provenance |
|---|---|---|
| Scripts `experiments/esa_nov2026/relevance_baseline/*.py` | **Present** | Reconstructed from the 8 Nov session transcript (13 Nov recovery). `features.py` content-verified 103/103 lines; others behaviourally checked (§4) |
| Original run outputs `results/esa_nov2026/relevance_baseline/run1_pu/` (report JSON sha `0f49c165…`, `per_claim.csv`, `models/M1–M3.joblib`, `feature_cache/`, `unlabelled_samples.json`) | **LOST (13 Nov)** | Not restored, not re-created |
| **Original console output of run1_pu**, with every split/model metric | **Recovered as a record** | `results/esa_nov2026/relevance_baseline/run1_pu_RECORDED_OUTPUT_FROM_TRANSCRIPT/run1_pu_console_output.txt`: verbatim tool output from the original session (2026-11-08 14:42 UTC) |
| Train knowledge-store sample (300 files, 1.28 GB) `capstone/storage/datasets/averitec_train_ks_sample/` | **LOST (13 Nov)** | Re-extraction needs network access and **owner approval** |
| `EXTRACTION_MANIFEST.json`, `extraction_log.jsonl`, `unlabelled_sampling_check.json` | **LOST** | Recorded values are in the ESA report §6 |

**Consequence:** the PU results can be **reported** (recorded output) but cannot be **re-run** until the train store is re-extracted.

## 2. Recorded configuration and results (from the original console output)

- **Data:** 300 AVeriTeC **train** claims, label-stratified, seed 2051. Claim-disjoint split: fit 179 / validation 60 / test 61. Split sha `1b994a96…`.
- **Documents:** 303,594 extracted (82,200 empty). Labels:
  - weak positive (s = 1): the knowledge-store document URL matches an AVeriTeC evidence URL and has non-empty text;
  - everything else is **unlabelled**, not negative.
- **Fit data:** 179 fit claims (131 with ≥ 1 positive). 5,587 pairs = **217 weak positives + 5,370 unlabelled**. Unlabelled documents were sampled uniformly, 30 per fit claim, seed 2052. Sampling hash `090ccf6f…`.
- **Models:** M1 logistic regression; M2 HistGradientBoosting (200 iterations, learning rate 0.05); M3 logistic regression + frozen MiniLM claim⊙doc features. All use balanced class weights.
- **Selection:** by validation claim-level R@10, a rule fixed in code before the run. Selected **M2 HistGBDT**.
- **Common candidate pool:** every system re-ranks the same hybrid RRF top-100 of the same eligible claims.

| Test (n = 42 eligible claims) | R@1 | R@5 | **R@10** | R@20 | MRR@100 | hit@10 vs hybrid |
|---|---|---|---|---|---|---|
| Hybrid RRF | 4/42 | 10/42 | **13/42 = 0.310** | 16/42 | 0.162 | — |
| M1 LogReg | 2/42 | 6/42 | 10/42 = 0.238 | 18/42 | 0.117 | +3/−6, p = 0.508 |
| **M2 HistGBDT (selected)** | 6/42 | 11/42 | **12/42 = 0.286** | 14/42 | 0.204 | **+0/−1, p = 1.000 (primary)** |
| M3 LogReg + MiniLM | 1/42 | 5/42 | 8/42 = 0.190 | 11/42 | 0.081 | +4/−9, p = 0.267 |

**Pool ceiling (test):** 30/42 = 0.714. **Validation:** hybrid 11/37 beat every learned model; M2 9/37. **In-sample (fit):** M2 85/131 = the pool ceiling, which indicates overfitting.

**Conclusion:** no learned model improved test Recall@10 over Hybrid RRF. This is a valid negative result. Secondary differences (M2 R@1 and MRR) are exploratory and untested.

## 3. Limitations
- Labels are weak citation proxies, not human relevance judgements, and certainly not authority labels.
- SCAR (selected completely at random) is very likely violated, because fact-checkers cite selectively. The model learns "what fact-checkers cite".
- Most relevant pages are never cited, so measured recall underestimates true recall.
- 90 of 300 claims have no non-empty evidence document and are not evaluable.
- 42 test claims means low power.

## 4. Verification performed on 14 Nov (offline)

| Check | Result |
|---|---|
| **R1 split regenerated** with the reconstructed `make_train_split.py` from `train.json` | **split_sha256 = `1b994a96974e3e7bbcda6994b1c0b08a5bbdbb580de42fcf383b5e11709e5765`: identical to the recorded hash.** Sizes 179/60/61; label allocation 169/84/27/20; 0 shared claim IDs between splits. The frozen split manifest is therefore restored exactly (`results/esa_nov2026/relevance_baseline/train_sample_split.json`) |
| **Synthetic smoke test** (`train_relevance.py --synthetic`; 18 invented claims; verifies code only) | Ran end to end (389 s). Selected `M1_logreg`; test M1 3/4, 4/4, MRR 3.50/4; M2 3/4, MRR 3.50/4; M3 2/4, MRR 3.00/4. **Identical to the 8 Nov synthetic output recorded in the transcript.** This shows the reconstructed training and evaluation code behaves like the original on the fixture. It is **not** a real-data result |
| Training-set leakage | The split draws only from AVeriTeC **train**. The dev (120/200/180) and test splits are never read (asserted in `rb_common.py`) |
| Weak-positive / unlabelled sampling logic | Code inspected: uniform, claim-seeded, labelled URLs excluded (`rb_common.sample_unlabelled`). The determinism check `verify_unlabelled_sampling.py` needs the train store, so it was **not re-run** |
| Common Hybrid RRF pool | Code inspected: every model re-ranks the same hybrid top-100 (`POOL = 100`). It cannot be re-executed without the train store |
| Saved model / feature artifacts | **Lost; not available for checking** |

Logs: `results/esa_nov2026/logs_2026-11-14/make_train_split.log` and `pu_synthetic_smoke.log`.

## 5. Exact reproduction procedure (needs approval for step 2)

```bat
cd C:\Users\Lenovo\Downloads\capstone\Source_Aware_Misinformation_Detector
set HF_HUB_OFFLINE=1

REM R1: claim-disjoint split (offline; refuses to overwrite an existing manifest). Expected split_sha256 = 1b994a96...
python experiments\esa_nov2026\relevance_baseline\make_train_split.py

REM R2: NETWORK, owner approval required. Streams only the 300 claims' members from the 3 official train zips
REM     (Hugging Face chenxwh/AVeriTeC @ 2ca9dee23a2a6fa64c5bd918e0cd28ed0aa09031, CC BY-NC 4.0) with HTTP range requests:
REM     ~6.2 GB traffic, ~1.28 GB on disk in capstone\storage\datasets\averitec_train_ks_sample\. Check free space first (>= 7 GB).
set HF_HUB_OFFLINE=
python experiments\esa_nov2026\relevance_baseline\extract_train_ks_sample.py --preflight
python experiments\esa_nov2026\relevance_baseline\extract_train_ks_sample.py --approved
set HF_HUB_OFFLINE=1

REM Verify the extraction: expect 300/300 files, 303,594 docs, 593/593 evidence URLs aligned
python experiments\esa_nov2026\relevance_baseline\verify_extraction.py

REM Verify PU sampling determinism: expect 179 fit claims, 5,370 samples, hash 090ccf6f...
python experiments\esa_nov2026\relevance_baseline\verify_unlabelled_sampling.py

REM R3: train + evaluate (~2 h 20 min on 8 CPU cores). Use a NEW tag; the script refuses to overwrite.
python experiments\esa_nov2026\relevance_baseline\train_relevance.py --tag run2_pu_repro
```

**Acceptance criteria for a successful reproduction:** the same split sha, document count, positive/unlabelled counts and sampling hash. The test table in §2 should then be reproduced exactly; scikit-learn 1.6.1 and NumPy 2.2.3 make this deterministic. Any difference must be reported, not hidden.

**Rules:** never train on dev claims (the 120 dev sample, 200 held-out or 180 reserved) or on AVeriTeC test. Never substitute other data or splits silently. Never describe the result as authority prediction.
