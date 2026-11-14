# RECOVERY_STAGING_2026-11-13 (published subset)

On 13 Nov 2026 the workspace was deleted and then restored. The restore was rebuilt from git objects, VS Code
snapshots, OneDrive and Claude session transcripts. Start with `RECOVERY_INVENTORY.md`, then read
`RECOVERY_SOURCE_COMPARISON.md`, `RECOVERY_VERIFICATION.md` and `RECOVERY_MISSING_FILES.md`.

**Published here:** the recovery reports, `RECOVERY_MANIFEST.csv` (per-file source and hash), the manifests,
`PRESERVED_SOURCES_SHA256.txt` (hashes only), the recovery scripts in `recovery_tools/`, and the replay reports in `reconstructed/`.

**Kept local (root `.gitignore`):**
- `_preserved_sources/`: raw Claude transcripts, scratchpads and recycle-bin metadata. These are private conversation data.
- `recovery_tools/events.pkl`: a binary extract of transcript events.
- `reconstructed/project_A`, `project_A_final` and `project_B`. These were verified byte-identical to the live
  files in `Source_Aware_Misinformation_Detector/` and `first_hand_authority_model/`. The only differences are the
  update banners added on 14 Nov to two Project A docs. The Project B copy also has its own `.git`.

Files marked missing in `RECOVERY_MISSING_FILES.md` were **not** recreated or fabricated.
