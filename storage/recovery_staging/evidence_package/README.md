# Authority-v2 recovery evidence package (staging only)

Created 2026-11-06 from backup ZIP `claude_session_backup_2026-11-06.zip` (SHA-256 `074d9433…acb7`). **Nothing here is an original project artefact, and nothing here has been copied into the project repository.**

| File | What it is |
|---|---|
| `execution_log_TRANSCRIPT_EXCERPT_NOT_ORIGINAL.json` | **Reconstructed excerpt, NOT the original execution log.** It has 43 slots in time order. 41 entries are kept verbatim (`raw_line`) as printed in transcript output, each with its provenance (session, transcript line, print time) and a check that repeated printings agree (0 conflicts). Slots 41 (`reserved_D_start`) and 43 (`step11_verification`) are **MISSING**: no content is reconstructed, and their positions are inferred. It is deliberately a single JSON object, not JSONL, so `v2common.read_log()` cannot mistake it for the log. |
| `timeline.md` | One row per slot: time, authority-v2 step number, event, status, and the hashes recorded in each entry |
| `known_hashes.json` | Every historically recorded hash for authority-v2 files and artefacts, with its current status (present and verified, missing, re-derivable, permanently unavailable, or protected) |
| `RECOVERY_LIMITATIONS.md` | Ten limitations covering the log, manifests, LLM and API outputs, gzip reproducibility, protected re-derivations, approvals, DL-012, step numbering, unverifiable documents, and dependence on the transcripts |
| `recovery_tools/` | The read-only scripts used (`log_collect.py`, `build_packages.py`) |

**Content checks performed:**
- No recovered entry has a label-like field name.
- No recovered entry contains an AVeriTeC verdict string.
- Nothing from the reserved-180 labels or sealed gold was read; the sealed file appears only as its recorded hash.
