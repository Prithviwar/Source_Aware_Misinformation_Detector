# Recovery verification, 2026-11-13

Full per-file detail is in `RECOVERY_MANIFEST.csv` (602 rows; every live file re-hashed after restore; **0 mismatches**).

## Project B: `first_hand_authority_model`
- Rebuilt from the original loose objects of commit `0bf11fc6edd65efb2b38d4ee0f5a75421ae68c0a` on branch `master`. That is git's default here; the original branch name was not recorded.
- `git fsck --full --strict`: OK.
- 34/34 tracked files present. The other 32 are byte-identical to the committed blobs.
- The original uncommitted state was reproduced exactly as it stood on 2026-11-02:

  | File | Original state | Verification |
  |---|---|---|
  | `STATUS.md` | ` M` (modified) | verbatim match with `cat` outputs of 2026-11-02 and 2026-11-03 |
  | `docs/DECISIONS.md` | ` M` (modified) | 110/110 lines match the Read of 2026-11-03 |
  | `docs/REAL_DATA_AND_TRAINING_PLAN_DRAFT.md` | `??` (untracked) | 203/203 lines match the Read of 2026-11-03 |

- Tests: `python -B -m pytest -q -p no:cacheprovider --basetemp=<scratch>` → **68 passed**. The run left nothing in the project folder.
- These are **synthetic-fixture** tests. They show the code mechanics work; they are not real-world validation. No real data, labels or trained model exist.

## Project A: `Source_Aware_Misinformation_Detector`
- The git clone is untouched: HEAD `9279eab`, with **0 modified tracked files**. Everything restored is untracked, or ignored for `data/raw`. Nothing was committed or pushed.
- 48 code/doc files:

  | Group | Count | Basis |
  |---|---|---|
  | Exact copies | 31 | SHA-256 equals a hash printed in the original sessions, or an original on-disk Blackbox snapshot |
  | Content-verified reconstructions | 4 | full later reads |
  | Reconstructed, not independently verified | 13 | no hash or later read exists |

- Notable exact matches:
  - `ESA_IMPLEMENTATION_AND_EXPERIMENT_REPORT.md` `2e40e919…`: final state after the 2026-11-09 fix
  - `ESA_DEMO_SCRIPT.md` `8c65d541…`
  - `authority_bottleneck_diagnostics.py` `66a962c0…`
  - all 24 authority-v2 code/prompt/config files
  - `authority_v2_preregistration.md`
  - `verdict_classifier_training_proposal_DRAFT.md`
- Blackbox snapshots equal to transcript replay: `authority_resolution_bottleneck_analysis.md`, `authority_v2_progress_report_steps1-9.md`.
- Data: 473 files (raw AVeriTeC JSON, 320-claim dev ks_sample, 147 dev rankings) copied from OneDrive. Each SHA-256 equals the inventory hash.
- OneDrive afterwards: 956 inventoried files re-hashed with 0 changed, and the file count is unchanged (1,726).
- Checks run:
  - all 75 Python files parse (AST)
  - `demo.py --list`, plus an in-memory frozen-mode demo for claim 2. It ran successfully and its output matches the original 2026-11-08 run (1,020 candidates, same query terms and ranks). No files were written.
- Not run (they write outputs or need missing inputs): the authority-v2 hash gate and manifest verification (freeze manifests lost), `reproduce_check.py`, `recall_ceiling.py`, `make_train_split.py`, the PU training/extraction scripts, the bottleneck diagnostics.

## Shared
- `RESEARCH_ROADMAP_2026-11-02.md`: 122/122 lines match the 2026-11-03 read.
- `storage/backups/claude_session_backup_2026-11-06/…`: 41 objects, byte-identical to the Recycle Bin originals.
- `storage/recovery_staging/*` READMEs and the manifest: single Writes, not independently verified.

## Separation
- No Project A path contains Project B files, and vice versa.
- The Project B repo has no remote. The Project A remote is unchanged and was not contacted.
