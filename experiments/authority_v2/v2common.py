"""Shared helpers for authority v2 (docs/authority_v2_preregistration.md).

Paths, raw-byte hashing, write-once outputs (LF line endings) and the append-only
execution log. Frozen modules in experiments/ are imported unmodified.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parent
EXP = V2.parent
ROOT = EXP.parent
if str(EXP) not in sys.path:
    sys.path.insert(0, str(EXP))

RES = ROOT / "results" / "authority_v2"
LOGS = RES / "logs"
EXEC_LOG = LOGS / "execution_log.jsonl"
MANIFESTS = RES / "manifests"
CONFIG = V2 / "config.json"
PREREG = ROOT / "docs" / "authority_v2_preregistration.md"
DECISION_LOG = ROOT / "docs" / "authority_v2_decision_log.md"


def now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    """Raw-byte SHA-256 (the convention for every new v2 artifact)."""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_lf(p: Path) -> str:
    """SHA-256 after CRLF->LF; only used to verify frozen files recorded in LF form."""
    return sha256_bytes(Path(p).read_bytes().replace(b"\r\n", b"\n"))


def rel(p: Path) -> str:
    return Path(p).resolve().relative_to(ROOT).as_posix()


def write_new_bytes(path: Path, data: bytes) -> str:
    """Write once; refuse to overwrite. Returns the raw SHA-256."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {rel(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as fh:
        fh.write(data)
    return sha256_bytes(data)


def write_new_text(path: Path, text: str) -> str:
    if "\r" in text:
        raise ValueError("new text artifacts must use LF line endings")
    return write_new_bytes(path, text.encode("utf-8"))


def write_new_json(path: Path, obj) -> str:
    return write_new_text(path, json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n")


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def log_event(event: str, **fields) -> dict:
    """Append one timestamped entry to the execution log (append-only, LF)."""
    LOGS.mkdir(parents=True, exist_ok=True)
    rec = {"ts": now(), "event": event, **fields}
    with open(EXEC_LOG, "ab") as fh:
        fh.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
    return rec


def read_log() -> list[dict]:
    if not EXEC_LOG.exists():
        return []
    return [json.loads(l) for l in EXEC_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def lib_versions() -> dict:
    import importlib.metadata as md
    out = {"python": sys.version.split()[0]}
    for p in ("spacy", "en_core_web_sm", "bm25s", "tldextract", "sentence-transformers", "torch",
              "transformers", "numpy", "fsspec"):
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    try:
        out["claude_cli"] = subprocess.run(["claude", "--version"], capture_output=True, text=True,
                                           shell=sys.platform == "win32", timeout=60).stdout.strip()
    except Exception as e:  # recorded, not fatal here
        out["claude_cli"] = f"unavailable: {e!r}"
    return out


def halt(msg: str, **fields):
    log_event("HALT", reason=msg, **fields)
    print(f"HALT: {msg}", file=sys.stderr)
    sys.exit(2)
