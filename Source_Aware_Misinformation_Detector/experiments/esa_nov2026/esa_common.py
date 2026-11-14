"""Shared, read-only helpers for the Phase-I ESA (November 2026) demonstration code.

SAFETY CONTRACT (enforced here, relied on by every script in this folder):
  * Only the 120 development-sample claims and the 200 held-out claims may be loaded.
    Any other AVeriTeC dev claim id (the 180 reserved claims of authority-v2) is refused.
  * No sealed or reserved file is ever opened. `data/processed/averitec_reserved180_gold.jsonl`
    is not referenced anywhere in this folder.
  * Frozen project code is IMPORTED, never edited. Frozen outputs are READ, never written.
  * Everything this folder writes goes to results/esa_nov2026/ (see `out_dir`).
  * No LLM / API / network call is made by any script in this folder.

Gold note: the "gold" used for display and scoring is the public AVeriTeC dev annotators'
evidence URLs for the 120 + 200 claims, which the frozen study already used and published.
It is RELEVANCE / evidence-citation information, NOT a claim-specific authority label.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parent
if str(EXP) not in sys.path:
    sys.path.insert(0, str(EXP))

from common import PROCESSED, RESULTS, read_jsonl  # noqa: E402  (frozen module)

OUT = RESULTS / "esa_nov2026"
DEV_SAMPLE = PROCESSED / "averitec_sample.jsonl"
HO_SAMPLE = PROCESSED / "averitec_heldout.jsonl"
DEV_PRED_RAW = RESULTS / "authority_resolution_raw.jsonl"
HO_PRED_RAW = RESULTS / "heldout" / "authority_raw.jsonl"

FORBIDDEN_SUBSTRINGS = ("reserved180", "reserved_180", "ks_reserved", "probe_reserved")


def out_dir(*parts: str) -> Path:
    p = OUT.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _guard_path(p: Path) -> Path:
    s = str(p).lower()
    if any(f in s for f in FORBIDDEN_SUBSTRINGS):
        raise PermissionError(f"refusing to touch protected/reserved path: {p}")
    return p


def load_claims() -> dict[int, dict]:
    """claim_id -> row (with an added 'split' field: 'dev120' or 'heldout200')."""
    rows = {}
    for split, path in (("dev120", DEV_SAMPLE), ("heldout200", HO_SAMPLE)):
        for r in read_jsonl(_guard_path(path)):
            r = dict(r)
            r["split"] = split
            rows[int(r["claim_id"])] = r
    assert len(rows) == 320, f"expected 120 + 200 = 320 allowed claims, got {len(rows)}"
    return rows


_CLAIMS: dict[int, dict] | None = None


def claims() -> dict[int, dict]:
    global _CLAIMS
    if _CLAIMS is None:
        _CLAIMS = load_claims()
    return _CLAIMS


def assert_allowed(cid: int) -> dict:
    """Return the claim row, or refuse (reserved / unknown claim ids)."""
    c = claims()
    if int(cid) not in c:
        raise PermissionError(
            f"claim {cid} is not in the 120 development or 200 held-out samples. "
            "It may be one of the 180 reserved authority-v2 claims, which this demo never loads.")
    return c[int(cid)]


def load_frozen_rankings(split: str) -> dict[str, dict[int, list[tuple[str, float]]]]:
    """Frozen full BM25 / dense / hybrid rankings (read-only)."""
    import validation_heldout as V
    heldout = split == "heldout200"
    return {m: V.load_rk(m, heldout) for m in ("bm25", "dense", "hybrid")}


def load_frozen_predictions(split: str) -> dict[int, dict]:
    """Frozen L+Wctx LLM authority predictions (already generated in Sept/Oct 2026; NOT re-run)."""
    path = _guard_path(HO_PRED_RAW if split == "heldout200" else DEV_PRED_RAW)
    out = {}
    for line in open(path, encoding="utf-8"):
        x = json.loads(line)
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            out[int(x["claim_id"])] = x["pred"]
    return out


def sha256_lf(path: Path) -> str:
    """SHA-256 after CRLF->LF normalisation (git core.autocrlf=true converts on checkout)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha256_raw(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
