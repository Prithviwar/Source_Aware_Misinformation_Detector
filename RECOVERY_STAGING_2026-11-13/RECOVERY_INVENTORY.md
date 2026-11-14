# Recovery inventory: Phase 1 (read-only), 2026-11-13

Prepared by Claude Code. Nothing in either live project was changed.

## 1. Capstone root as found (2026-11-13 ~18:10 IST)

```
C:\Users\Lenovo\Downloads\capstone\
└── Source_Aware_Misinformation_Detector\   (created 18:04:04 today: fresh git clone)
```

- `first_hand_authority_model\`: **ABSENT**
- `storage\`: **ABSENT** (it went to the Recycle Bin at 18:02; see the source comparison)
- `RESEARCH_ROADMAP_2026-11-02.md` (was in the root): **ABSENT**

Recycle Bin metadata (`$I` files) shows three deletions:

| Item | Deleted at |
|---|---|
| `capstone\Source_Aware_Misinformation_Detector` | 2026-11-13 18:02 |
| `capstone\storage` | 2026-11-13 18:02 |
| `capstone` (empty) | 2026-11-13 18:03 |

The new clone was made at 18:04.

## 2. Project A: `Source_Aware_Misinformation_Detector` (live)

| Item | Value |
|---|---|
| Files (excluding .git) | 228, 64 MB |
| Branch | `main` → `9279eab` "docs: add research project README" (tracks origin/main) |
| Other branches / tags / stash | none |
| Remote | origin = github.com/Prithviwar/Source_Aware_Misinformation_Detector (not contacted) |
| Reflog | one entry: `clone` (18:04 today). No earlier history. |
| `git status` | clean (nothing staged, modified or untracked) |
| `git fsck --unreachable` | nothing unreachable; 255 objects in one pack, 0 loose |
| Submodules / extra worktrees | none |
| core.autocrlf | true |
| History | 106a02c → e7d3cd0 → 40e412c → 9279eab (all ≤ 2026-10-03) |

**Conclusion:** the live repo matches the GitHub state of 3 Oct exactly. It contains **none** of the work done after 3 Oct:
- authority-v2
- bottleneck and diagnostic audits
- ESA Nov 2026
- PU relevance baseline
- research proposal package
- `data/raw`

The 6 Nov recovery restores are also gone. Git cannot recover any of this, because the work was never committed or pushed.

Present directories: `data/annotations` (with heldout_primary_package), `data/processed` (averitec_heldout.jsonl, averitec_sample.jsonl), `docs` (7 pre-v2 docs), `experiments` (41 pre-v2 scripts + authority_quality_ablation), `results` (pre-v2 results, heldout, source_targeted, etc.). There is **no** `data/raw`.

## 3. Project B: `first_hand_authority_model`

Not present on disk. It is not in the Recycle Bin as a project folder. See the source comparison for its recoverable Git snapshot.

## 4. Other locations inspected

| Location | Finding |
|---|---|
| Recycle Bin | 4 items: the 3 capstone deletions above, plus an unrelated `prompt mini project` (10 Nov) |
| OneDrive `Desktop\sourceawaremisinformation\` | Copy dated 3 Oct (1,726 files, 3.1 GB) plus a `.zip` from 29 Sep. Includes `data/raw/averitec` (train/dev/test.json, 320-claim ks_sample). Read only. |
| `~/.claude/projects/C--Users-Lenovo-Downloads-capstone/` | 12 transcripts, 28 Oct – 13 Nov (~30 MB) |
| `%TEMP%\claude\abd4a463a89ed7db\` | Scratchpads of the 6 Nov recovery session and the 8 Nov ESA session |
| `~/.cache/huggingface/hub` | all-MiniLM-L6-v2 (88 MB), bge-small-en-v1.5, gpt2. No AVeriTeC dataset cache. |
| Volume Shadow Copies | not checkable without admin rights (vssadmin refused) |
| File History | not configured |
| Downloads | `ESA_CapstoneProject_Report\` (university guideline .docx files, not project output), `CapstoneProject_IR_03.pptx` (13 Nov 11:33, a presentation; not inspected further) |
| Session active at 18:01 today (`476df4c7`) | empty scratchpad, no transcript. Not a source. |

Free space on C: about 27 GB.

---
## Post-recovery state (2026-11-13, after restoration)

```
capstone\
├── Source_Aware_Misinformation_Detector\  1.6 GB. Clone untouched (HEAD 9279eab, 0 tracked changes)
│     + 48 restored code/doc files (untracked)
│     + data/raw/averitec (326 files) + results/rankings_*.jsonl.gz (147), from OneDrive, hash-verified
├── first_hand_authority_model\            git master @ 0bf11fc, 34 files + 2 uncommitted edits + 1 untracked draft
├── storage\                               backups/ (41 original objects), recovery_staging/ (3 docs), datasets/ (note only)
├── RESEARCH_ROADMAP_2026-11-02.md
└── RECOVERY_STAGING_2026-11-13\           preserved sources, reconstructions, tools, manifests (keep)
```

See `RECOVERY_MANIFEST.csv` (602 rows), `RECOVERY_VERIFICATION.md` and `RECOVERY_MISSING_FILES.md`.
