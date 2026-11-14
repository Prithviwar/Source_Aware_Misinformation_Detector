# AI annotation protocol (MODEL_GENERATED labels)

**Every label produced under this protocol is AI-generated.** It is never a human annotation, human ground truth, an independent human label or an expert annotation. Files carrying these labels are named `MODEL_GENERATED_*`.

Pre-registered in `docs/source_targeted_preregistration.md` Addendum 3. The human held-out primary-source endpoint (Addendum 2) was **pre-registered but not executed**.

## 1. Tasks

| Task | Role in the analysis | Unit | Input sheet | Prompt |
|---|---|---|---|---|
| **Evidence-level roles** | **Main AI endpoint**: AI-labelled primary-evidence recall | one held-out gold evidence URL (422) | `data/annotations/heldout_annotator_template.csv` | `ai/AI_EVIDENCE_PROMPT.md` |
| Claim-level authorities | Secondary, **descriptive only**: overlap with the authority predictor. Never used to test or validate method D. | one held-out claim (192) | `heldout_primary_annotation.csv` (blank canonical sheet) | `ai/AI_CLAIM_PROMPT.md` (embeds `ANNOTATION_GUIDE.md` verbatim) |

## 2. Annotator

- **Model:** Claude Opus 5.5, model ID `claude-opus-5-5`.
- **This is the same model as the L+Wctx authority predictor** used by methods D and G (`validation_preregistration.md`). See §6.
- **Call:** `claude -p --tools "" --strict-mcp-config --no-session-persistence --model claude-opus-5-5 --system-prompt <frozen system part> --output-format json`. The user part goes to stdin.
- **Isolation:**
  - each call runs in a **new, empty temporary working directory**, with no tools, no web access, no MCP servers and no session memory;
  - one call per item;
  - no user-level `CLAUDE.md` exists (checked 2026-10-02).
- **Not the orchestrating session.** The project session that writes code and analyses results has seen held-out results and gold statistics, so it never produces labels.
- **Lookups:** none are possible. `research_used` is always `none`.
- **Retry:** one retry if the output is not valid JSON or has an invalid value. A second failure is recorded as a failure, never fixed by hand.
- **Parallelism:** 4 concurrent calls. Items are independent, so this has no effect on content.

## 3. What the annotator sees and never sees

| Evidence-level: shown | Claim-level: shown |
|---|---|
| claim text, speaker, claim date, country | claim text, speaker, claim date, country |
| the one gold URL being judged, its publisher domain, title, text excerpt (≤ 400 characters, from the knowledge store) | the annotation guide (verbatim) |
| the fact-checkers' question this URL was cited for, and their answer | – |

**Never shown (either task):**
- authority predictions;
- rankings or method names;
- any result;
- the verdict label or justification;
- the fact-check article;
- other gold URLs of the same claim;
- `source_roles.csv` or any other annotation (human, pilot or AI).

The runner reads only the two input sheets, the prompts, the guide and the two manifests (for claim IDs).

## 4. Outputs

All outputs go to `data/annotations/heldout_primary_package/ai/`:
- `MODEL_GENERATED_<task>_<items>_run<ID>_<MODEL>.jsonl`: raw CLI output, parsed object, error, attempt, cost, `num_turns`, model usage, time, and the SHA-256 of the prompts, guide, runner and converter at run time.
- `MODEL_GENERATED_<task>_<items>_run<ID>_<MODEL>.csv`: the clean labels. `annotator_id` is `MODEL_GENERATED_<MODEL>`.
- `MODEL_GENERATED_heldout_primary_sheet_from_evidence_roles.csv`: evidence labels converted to the frozen scorer's 192-row sheet (`experiments/score_ai_primary.py convert`).

Scores go to `results/heldout_ai_primary/MODEL_GENERATED_ai_primary_evidence_recall_heldout.json`.

## 5. Sequence

1. `python experiments/ai_annotate.py hashes`: record the hashes.
2. **Pilot.** Pilot labels are never scored.
   - `evidence pilot --run A` and `evidence pilot --run B`: 34 gold URLs of the 15 pilot claims, two independent runs.
   - `claim pilot --run A`.
3. Review with `pilot/PILOT_REVIEW_CRITERIA.md`, Addendum (AI annotator). Wording changes, if any, are logged in `CHANGELOG.md`, and the pilot is re-run. At most 2 rounds.
4. **Freeze.** `python experiments/ai_annotate.py freeze` writes `ai/FROZEN_HASHES.json`. The hashes are copied into the Addendum 3 freeze record. **The runner refuses held-out labelling if any protocol file differs from the freeze.**
5. Full run:
   - `evidence heldout --run A` (422 URLs);
   - `claim heldout --run A` (192 claims, descriptive only).
6. Run `score_ai_primary.py selftest`, then `score`, then `overlap`.
7. **Optional cross-family sensitivity** (§7).

## 6. Circularity: what it is and how it is handled

- **Why it matters.** The annotator is the same model as the authority predictor behind D and G. A claim-level annotation from the same inputs would be close to a second sample of the predictor, so D would be scored against itself.
- **Main endpoint.** It uses **evidence-level** labels. The annotator only judges pages that AVeriTeC's human annotators already selected; it cannot add a publisher.
- **The claim-level task has no tests.** It is used only to report overlap with the predictor.
- **Diagnostics reported**, from `score_ai_primary.py overlap`, reading the frozen predictions read-only:
  1. the share of AI-primary gold URLs whose publisher is in the predictor's top-3, against the same share for the other gold URLs;
  2. claim-level any-key overlap and authority-1 overlap with the predictor's top-3.
- **Stated limitation, binding on every write-up:** annotator and predictor share one model's notion of "first-hand"; this cannot be separated without an independent annotator.
- **Binding interpretation rule:** the AI endpoint cannot change the validation outcome (B). The human-grounded evidence remains gold R@K.

## 7. Cross-family sensitivity (AI–AI agreement only)

- **Subset:** 40 claims sampled with seed 2028 from the 177 non-pilot held-out claims (`ai_annotate.py`, `xfam_ids()`), with all their gold URLs.
- **Same frozen evidence prompt**, run by a model from a different family:
  - **(a) local:** `--backend ollama --ollama-model <model>` (temperature 0, JSON mode). The only local model now is `deepseek-coder` 1.3B, which is not suitable. A suitable model has to be pulled first, and the C: drive has about 5.5 GB free.
  - **(b) external:** `export-xfam` writes the prompts with no labels. They are run in another family's interface, and the returned labels are saved as `MODEL_GENERATED_evidence_xfam_runX_<MODEL>.csv`.
- **Reported:**
  - % agreement and Cohen's κ (4 labels, and primary vs not);
  - descriptive AI-PrimR@10 per method on the subset under both label sets.
- **No tests.** It is always called "AI–AI agreement", never validation. If it is not run, it is reported as not run.

## 8. Terminology (binding)

| Use | Never use |
|---|---|
| "AI-labelled primary-evidence recall" (AI-PrimR@K, AI-PrimMRR@100, AI-primary coverage) | human-annotated, human-validated |
| "AI-named authority (descriptive)" | ground truth |
| "MODEL_GENERATED", "AI-generated labels" | expert annotation |
| "AI–AI agreement" | independent human labels, reliability |
