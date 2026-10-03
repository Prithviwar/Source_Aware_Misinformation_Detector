"""Shared helpers for the AVeriTeC data audit (URL normalisation, I/O, metrics).

Kept deliberately small: this is audit code, not the future pipeline.
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import tldextract

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "averitec"
KS_DIR = RAW / "ks_sample"  # per-claim extracts of the dev knowledge store
PROCESSED = ROOT / "data" / "processed"
ANNOTATIONS = ROOT / "data" / "annotations"
RESULTS = ROOT / "results"

KS_ZIP_URL = (
    "https://huggingface.co/chenxwh/AVeriTeC/resolve/main/"
    "data_store/knowledge_store/dev_knowledge_store.zip"
)

# Offline suffix list snapshot bundled with tldextract; no network calls.
_TLD = tldextract.TLDExtract(suffix_list_urls=())

_WAYBACK = re.compile(r"^(https?://)?(web\.)?archive\.org/web/\d+[a-z_]*/", re.I)
_TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|ocid|cmpid|ref|smid|mc_cid|mc_eid)$", re.I)


def is_placeholder_url(url: str) -> bool:
    """AVeriTeC uses 'http://Metadata' etc. for evidence that is not a web page."""
    return bool(re.match(r"^(https?://)?(metadata|n/?a|none)?/?$", (url or "").strip(), re.I))


def strip_wayback(url: str) -> str:
    """Remove (possibly nested) web.archive.org/web/<ts>/ prefixes and repair
    malformed prefixes seen in the gold data ('web.archivehttps://', 'http://https:/')."""
    url = (url or "").strip()
    url = re.sub(r"^(https?://)?web\.archive(?=https?:)", "", url, flags=re.I)
    url = re.sub(r"^https?://(https?):/+", r"\1://", url, flags=re.I)
    while _WAYBACK.match(url):
        url = _WAYBACK.sub("", url, count=1)
    url = re.sub(r"^(https?):/(?!/)", r"\1://", url, flags=re.I)
    if url and not re.match(r"^[a-z]+://", url, re.I):
        url = "http://" + url
    return url


def normalize_url(url: str) -> str:
    """Canonical form used to match gold evidence URLs to knowledge-store documents."""
    url = strip_wayback(url)
    if not url:
        return ""
    parts = urlsplit(url)
    host = parts.netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+$", "", parts.path) or ""
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)])
    return host + path + ("?" + query if query else "")


def registered_domain(url: str) -> str:
    """eTLD+1 of the (un-archived) URL, e.g. 'bbc.co.uk', 'cdc.gov'."""
    ext = _TLD(strip_wayback(url))
    return ext.top_domain_under_public_suffix or ext.domain


def full_host(url: str) -> str:
    host = urlsplit(strip_wayback(url)).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def read_jsonl(path: Path) -> list[dict]:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_sample() -> list[dict]:
    return read_jsonl(PROCESSED / "averitec_sample.jsonl")


def load_ks(claim_id: int) -> list[dict]:
    return read_jsonl(KS_DIR / f"{claim_id}.jsonl.gz")


def tokenize_query(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ---------------------------------------------------------------- metrics

def recall_at_k(ranked_norm_urls: list[str], gold: set[str], k: int) -> float | None:
    """Fraction of gold URLs found in the top-k. None if there is no gold to find."""
    if not gold:
        return None
    return len(gold & set(ranked_norm_urls[:k])) / len(gold)


def hit_at_k(ranked_norm_urls: list[str], gold: set[str], k: int) -> float | None:
    if not gold:
        return None
    return float(bool(gold & set(ranked_norm_urls[:k])))


def precision_at_k(ranked_norm_urls: list[str], gold: set[str], k: int) -> float | None:
    if not gold:
        return None
    return len(gold & set(ranked_norm_urls[:k])) / k


def mrr(ranked_norm_urls: list[str], gold: set[str]) -> float | None:
    if not gold:
        return None
    for i, u in enumerate(ranked_norm_urls, 1):
        if u in gold:
            return 1.0 / i
    return 0.0


def mean(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
