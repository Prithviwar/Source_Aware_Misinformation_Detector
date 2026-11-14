# Recovery sources: Phase 2 findings, 2026-11-13

Status vocabulary: VERIFIED ORIGINAL · RECOVERED EXACT COPY · RECOVERED OLDER VERSION · RECONSTRUCTED · MISSING · NOT VERIFIED

## A. Git (live Project A clone)
- **No recoverable post-3-Oct work.** The only objects are the 4 GitHub commits.
- Recycle Bin `$RPQMCKT\.git\objects\pack\pack-631ee304….pack` has SHA-256 `3dfb1751…`, **byte-identical** to the fresh clone's pack. It adds nothing.

## B. Backup `storage\backups\claude_session_backup_2026-11-06`
- Survives only in the Recycle Bin (`$R4I77XK`). It holds just 41 loose Git objects, from `old_scratchpads_capstone/74fa2414…/scratchpad/clone_audit/.git/objects`.
- **These objects are Project B's complete baseline commit:**
  - commit `0bf11fc6edd65efb2b38d4ee0f5a75421ae68c0a`, tree `4e325ffc…`
  - author RachitSMane, 2026-10-29 ~15:40 IST
  - message: "chore: establish first-hand authority model project baseline … tests (68 passing on synthetic fixtures) … No real data, no trained research model."
- Tree walk: **34/34 files present.** Every object passes Git's SHA-1 content check.
- Everything else that was in `storage` is **not** in the Recycle Bin and appears permanently deleted:
  - `datasets/averitec_train_ks_sample` (1.2 GB)
  - `recovery_staging/` from 6 Nov
  - the rest of the 6 Nov backup
- Copy preserved under `_preserved_sources/recyclebin_storage_R4I77XK/`.

## C. OneDrive (read only, not modified)
- `Desktop\sourceawaremisinformation\` is a pre-v2 project snapshot from 3 Oct.
- Raw data:
  - `data/raw/averitec/` holds train.json (`ae5eda7c…`), dev.json (`4997937…`, matches the hash recorded in Step 6), test.json, dev_urls.zip and ks_sample (320 claims)
  - this is the source of `data/raw`, which is needed by the held-out reproduction and by `make_train_split.py`
- Contains **no** authority-v2, ESA, PU baseline or Project B files.

## D. Windows locations
- Recycle Bin: see A and B. The working files of both deleted folders are **not** there: only read-only Git files went to the bin. The same pattern was seen on 6 Nov.
- Shadow copies: unknown (admin rights needed).
- File History: off.
- Filesystem name search of the user profile: see the addendum at the end.

## E. Claude Code artifacts (the main source for November work)
Transcripts (28 Oct – 10 Nov) contain the Write/Edit tool calls with full file contents for the files below. Replaying them in memory (deduplicated by tool-call ID) gives every listed file with **all edits applying cleanly**, with one exception noted.

**Project A: ESA Nov 2026 (session 36c390a8, 2026-11-08)**
- `experiments/esa_nov2026/`: `esa_common.py`, `reproduce_check.py`, `demo.py`, `recall_ceiling.py`, `authority_promotion_stats.py`
- `experiments/esa_nov2026/relevance_baseline/`: `rb_common.py`, `make_train_split.py`, `extract_train_ks_sample.py` (1 edit fails; the file was also changed by `sed`), `features.py`, `train_relevance.py` (final rewrite at 12:19), `verify_extraction.py`, `verify_unlabelled_sampling.py`
- `docs/`: `ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md`, `ESA_DEMO_SCRIPT.md`, `ESA_PROPOSED_AUTHORITY_MODEL_ARCHITECTURE.md`
  - The report and the demo script were later changed by `sed` and by scratchpad scripts (`update_report.py` with `sec6.md`/`sec71.md`, and `fix_ad.py` on 9 Nov). All of those scripts survive in the 36c390a8 scratchpad, so the final state can be **reconstructed**, not recovered.

**Project A: other**
- `docs/RESEARCH_PROPOSAL_INFORMATION_PACKAGE.md` (9f95cbdc, 7 Nov; 1 later Bash reference to check)
- `docs/authority_v2_*.md`, `experiments/authority_v2/**` (24 files, including prompts and config)
- `experiments/authority_bottleneck_diagnostics.py`, `authority_diagnostic_audit.py` and their two docs
- `docs/proposals/verdict_classifier_training_proposal_DRAFT.md`
- The 6 Nov session already replayed authority-v2 into its scratchpad `replay_work/`, which survives.

**Project B (session 74fa2414, 29 Oct; 5b5c3a16, 2 Nov)**
- Baseline files are better recovered from the Git commit (B).
- `docs/REAL_DATA_AND_TRAINING_PLAN_DRAFT.md` (2 Nov) is **after** the commit, so it exists only in the transcript.
- Root `RESEARCH_ROADMAP_2026-11-02.md` likewise exists only in the transcript.

**Script-generated outputs: NOT in transcripts as files, so NOT recoverable**
- `results/esa_nov2026/**`, including:
  - `relevance_baseline/EXTRACTION_MANIFEST.json/.md`
  - `run1_pu/` (models, feature_cache, per-claim CSVs, `relevance_baseline_report.json`, `run_stdout.log`)
  - the sampling verification output
- The train KS sample (1.2 GB), the authority-v2 Step-11 predictions and the reserved-180 outputs (already lost on 6 Nov).
- Some of their **numbers** appear in transcript tool output and in the ESA report text. They can be cited as *reported values*, never as recovered files.
- Exception: `sampling_check_2.json` survives as a scratchpad copy (36c390a8 scratchpad).

**Preserved (copy-only, verified byte-identical, 157 files, SHA-256 in `PRESERVED_SOURCES_SHA256.txt`):**
- `_preserved_sources/claude_transcripts/` (11 transcripts, plus tool-result folders and a memory snapshot)
- `_preserved_sources/temp_scratchpads/` (398127e0 and 36c390a8)
- `_preserved_sources/recyclebin_storage_R4I77XK/` (plus the `$I` metadata files)

## Addendum: filesystem name search (finished)
No surviving copies of `results/esa_nov2026`, `EXTRACTION_MANIFEST*`, `run1_pu`, the train KS sample, `first_hand_authority_model` or the ESA docs were found anywhere under `C:\Users\Lenovo`.

**New independent source: VS Code Blackbox extension snapshots** (`%APPDATA%\Code\User\globalStorage\blackboxapp.blackbox\…`)

| File | Snapshot date | Uncompressed SHA-256 | Transcript replay (dry run) |
|---|---|---|---|
| `docs/authority_resolution_bottleneck_analysis.md` | 2026-10-28 22:21 | `0fcd49b54fe01793…` | **identical** |
| `docs/authority_v2_progress_report_steps1-9.md` | 2026-11-02 17:47 | `04b90203014660fc…` | **identical** |

- These two files therefore count as RECOVERED EXACT COPY. The snapshot is an original on-disk version, cross-confirmed by the transcript.
- They also independently validate the transcript-replay method.
- Copies are preserved in `_preserved_sources/vscode_blackbox_snapshots/`, and the gzip integrity test passes.

**Recent-files shortcuts point to further deleted files.** None of them exist now, and none were found anywhere else:
- `Downloads\First_Hand_Authority_Model_Handover_2026-10-29.md`: MISSING. Its content may correspond to a transcript (74fa2414); still to be checked.
- `Downloads\CapstoneProject_Phase-1_Review-2_PPT_Template.pptx`, `Downloads\ESA_CapstoneProject_PPT.pptx`, `Downloads\ESA_CapstoneProject_Report.zip`, `…\Page_1-2.docx`, `…\Page_3-8.docx`: MISSING. These are not Claude-written, so no transcript source exists. Check email, WhatsApp, Google Drive or the university portal for copies.
- `docs/authority_resolution_diagnostic_audit.md`, `docs/RESEARCH_PROPOSAL_INFORMATION_PACKAGE.md`: transcript source available (RECONSTRUCTED).

---
## Sources actually used for restoration (2026-11-13)

| Source | Used for | Files |
|---|---|---|
| Recycle Bin `$R4I77XK` (git loose objects) | Project B commit 0bf11fc; storage/backups | 34 (B) + 41 (storage) |
| VS Code Blackbox snapshots | bottleneck analysis doc, authority-v2 progress report | 2 |
| Claude transcripts (deduplicated Write/Edit plus re-executed recorded `sed`/python edits) | Project A ESA, PU baseline, docs, diagnostics; B post-commit edits; roadmap; storage notes | 21 + 3 + 1 + 3 |
| 2026-11-06 authority-v2 replay (scratchpad, hash-verified against the execution log) | `experiments/authority_v2/**`, `docs/authority_v2_{preregistration,decision_log}.md` | 25 |
| OneDrive (read only; re-hashed afterwards, 0 changes) | data/raw/averitec, dev ks_sample, dev rankings | 473 |

The 2026-11-06 recovery renamed the decision log `*.PARTIALLY_VERIFIED.md`. This time it was restored under its **original name** `docs/authority_v2_decision_log.md`. Its status (text verified by reads; bytes verified only at the Freeze-1 state) is recorded in the manifest.

`recovery_tools/` contains every script used, so the whole recovery can be re-run and audited.
