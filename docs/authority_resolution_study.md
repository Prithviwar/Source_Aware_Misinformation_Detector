# Authority-resolution study

*2026-09-29. Script: `experiments/authority_resolution.py`. Outputs: `results/authority_resolution_summary.json`, `results/authority_resolution_predictions.csv` and `results/authority_resolution_raw.jsonl`.*

**Question.** Given only a claim, can an LLM (optionally with Wikidata) name the publisher that is authoritative *for this claim*? No retrieval is involved.

**Target.** The pilot-primary publisher of the claim's gold evidence: one annotator (Claude), **not validated**.

- 73 claims have a pilot primary.
- 71 are evaluable. For #388 and #395 the only primary is an opaque `archive.ph` link.
- Matching is at registered domain, or platform/handle for social accounts. `gov.uk` is treated as one publisher and `x.com` as equal to `twitter.com`.

**Leakage controls.**

- Model inputs are claim text, speaker, claim date and country only.
- The model never sees gold URLs, evidence, QA pairs, justification, label, `original_claim_url` or role labels. An automated scan of all prompts found 0 gold strings.
- The predictor is `claude -p` (Opus 5.5) with **no tools and no web access**, run in a fresh context from an empty directory.
- The orchestrating session had seen gold domains; the predictor had not.
- Pilot labels are read only in `evaluate()`.

## Results (n = 71)

| Condition | Top-1 | Top-3 | Coverage |
|---|---|---|---|
| W: Wikidata official sites of claim entities | 0.06 (4) | 0.11 (8) | 0.55 |
| G: generic guess (most frequent primary publishers of same-country claims, leave-one-out) | 0.11 (8) | 0.20 (14) | 1.0 |
| L: LLM only | 0.59 (42) | 0.77 (55) | 1.0 |
| **L+Wctx: LLM + Wikidata context** | **0.63 (45)** | **0.77 (55)** | 1.0 |
| L+Wctx, independent re-run (stability) | 0.58 (41) | 0.76 (54) | 1.0 |
| L+Wgnd: predicted names grounded to Wikidata official sites | 0.63 | 0.77 | 1.0 |

- **Stability.** The two runs give the same top-1 publisher on 65/71 claims; top-3 hit/miss agrees on 70/71.
- **Claims that do not name the authority** (54): top-1 0.59, top-3 0.74. Claims that do name it (17): 0.76 / 0.88.
- **By claim kind** (top-1 / top-3):
  - organisation action/policy: 0.76 / 0.86
  - official statistic: 0.67 / 0.78
  - legal: 0.54 / 0.77
  - **scientific/health: 0.25 / 0.50**, where the model falls back to WHO/CDC/FDA instead of the specific research producer
- **Ambiguity.** The model labelled 64/71 claims `multiple_legitimate_authorities`, so that flag does not discriminate.
- **Authority, not credibility.** Only 1 of the 213 predicted publishers was a news outlet.

## Failure categories (manual, from the 26 top-1 misses)

- **Pilot primary is the claim-maker's own post** (#18, #320). The model named the authority on the fact instead.
- **Multiple legitimate authorities.** Examples: national agencies vs World Bank/UN on Nigerian statistics (#209, #217, #222); OECD vs NZ Treasury (#143); Reliance vs KKR (#275).
- **Generic canonical agency chosen over the specific primary producer** (#280 Cochrane, #454 lung.org, #321 UCSF TB centre, #428 FOP): the credibility trap inside authority resolution.
- **Same institution, different channel** (#187 White House press secretary; #466 DOJ AMBER Alert programme vs its Facebook page).
- **Claim misattributes the actor** (#450: a Florida governor's order attributed to Trump).
- **Agency ambiguity** (#373, #438).
- **Questionable pilot label** (#99, #323, #389).

## Plugging the predicted authorities into retrieval

Script: `experiments/predicted_authority_retrieval.py`. Output: `results/predicted_authority_retrieval.json`. Scored on the 48 claims with a reachable pilot primary.

| Base | PrimR@10 base | + predicted, λ=.25, top-100 (pre-specified) | + predicted, λ=1, all candidates | + generic, λ=1, all | oracle, λ=1, all |
|---|---|---|---|---|---|
| BM25 | 0.04 | 0.10 (+3/−0, p=.25) | **0.44** (+19/−0, p<.0001) | 0.17 | 0.75 |
| Dense | 0.10 | 0.19 (+4/−0, p=.13) | **0.46** (+17/−0) | 0.15 | 0.79 |
| Hybrid | 0.06 | 0.19 (+6/−0, p=.03) | **0.46** (+21/−2) | 0.21 | 0.77 |

## Caveats (important)

1. **Correlated annotator and predictor.** The pilot labels were made by Claude and the predictor is Claude, so accuracy may be inflated by shared notions of "primary". Human second annotation is needed (`data/annotations/second_annotator_template.csv`, 226 items, **PENDING**).
2. The claims are 2020 fact-checks, so the model may have memorised the answers.
3. The PrimR gains above are measured on the pilot-primary labels (Claude annotator). The circularity-free check below uses only the human AVeriTeC gold.

## Circularity-free check: human AVeriTeC gold recall, all 99 reachable-gold claims

*Completed 2026-09-29 after the usage-limit interruption. The 15 missing predictions were re-run (`python authority_resolution.py --all-claims`, 120/120 claims now have an L+Wctx prediction; log `results/log_authority_resolution_allclaims.txt`). Scored by `gold_all_claims()` in `experiments/predicted_authority_retrieval.py`; output `results/predicted_authority_retrieval.json` → `gold_recall_all_claims`. Pilot role labels are **not read**.*

Prior = 1 if the candidate's publisher key is in the claim's predicted top-3 publishers. Exact McNemar, uncorrected, wins/losses in claims (n = 99).

| Base | Setting | Base R@5/10/20 | + generic | **+ predicted authority** | predicted vs base (R@10) | predicted vs generic (R@10) |
|---|---|---|---|---|---|---|
| BM25 | λ=.25, top-100 (pre-specified) | .08 / .11 / .24 | .07 / .10 / .24 | .09 / .14 / .28 | +3/−0, p=.25 | +5/−1, p=.22 |
| BM25 | λ=1, top-100 | | .05 / .15 / .23 | **.16 / .21 / .33** | +11/−1, p=.006 | +10/−4, p=.18 |
| BM25 | λ=1, all candidates | | .05 / .10 / .14 | .15 / .25 / .38 | +20/−6, p=.009 | +17/−2, p<.001 |
| Dense | λ=.25, top-100 (pre-specified) | .15 / .24 / .33 | .15 / .25 / .31 | .19 / .27 / .35 | +3/−0, p=.25 | +4/−2, p=.69 |
| Dense | λ=1, top-100 | | .13 / .22 / .26 | .23 / .29 / .35 | +7/−2, p=.18 | +10/−3, p=.09 |
| Dense | λ=1, all candidates | | .04 / .08 / .13 | .19 / .30 / .42 | +15/−9, p=.31 | +23/−1, p<.001 |
| Hybrid | λ=.25, top-100 (pre-specified) | .14 / .24 / .36 | .14 / .22 / .37 | .16 / .28 / .39 | +5/−1, p=.22 | +7/−1, p=.07 |
| Hybrid | λ=1, top-100 | | .13 / .21 / .28 | **.24 / .34 / .44** | +15/−5, p=.04 | +17/−4, p=.007 |
| Hybrid | λ=1, all candidates | | .10 / .17 / .23 | .19 / .30 / .42 | +19/−13, p=.38 | +17/−4, p=.007 |

Reading:

- **At the pre-specified weight (λ=.25) the gain is small and not significant on any base**: +3 to +5 claims out of 99.
- **At λ=1 the predicted-authority prior raises human-gold recall**: BM25 R@10 .11 → .21 (p=.006); hybrid R@5/10/20 .14/.24/.36 → .24/.34/.44 (all p<.05 vs base).
- **The same weight applied to generic credibility lowers gold recall**, e.g. dense R@20 .33 → .13 when re-scoring all candidates (p<.001). So the effect is not "boost official-looking domains": it is claim-specific.
- **Predicted beats generic** in every λ=1 cell except BM25 and dense R@10 at top-100 (same direction, p=.18 and .09).
- **Status: exploratory.** λ=1 was a sensitivity setting, not the pre-specified headline; 27 cells were inspected and nothing is multiplicity-corrected. Memorisation (caveat 2) still applies, because the human gold evidence for 2020 fact-checks may be in the model's training data. The annotator/predictor correlation (caveat 1) is removed for these numbers.
