"""Step 5: relevance + a simple, transparent authority prior (re-ranks the top 100
of a relevance ranking: bm25, dense or hybrid).

score = minmax(relevance score within the claim's top-100 pool) + LAMBDA * prior

Variants:
  auth_generic  claim-INDEPENDENT domain prior (gov/intergov > academic > major
                news > reference > unknown > social/blog). Analogue of RAVE /
                CONFACT-style credibility weighting.
  auth_claim    claim-CONDITIONED prior: 1 if the domain / social handle matches
                an entity named in the claim or the speaker field, or is a
                government domain of the claim's country; else 0.
  auth_entity   claim-conditioned, entity part only: 1 if the domain / social
                handle matches an entity named in the claim or speaker; else 0.
  auth_full     max(generic prior with jurisdiction adjustment, claim prior).
  oracle        1 if the domain is the domain of an annotated PRIMARY gold source
                of this claim (perfect authority resolution; upper bound only).

The rules are hand-written and NOT tuned on the sample's gold labels, except
the oracle, which uses them by construction. LAMBDA=0.25 is the pre-specified
headline value; every LAMBDA in the grid is reported instead of picking the best
one on the sample.

Inputs of every non-oracle prior: the candidate's un-archived normalised URL, the
claim text, and the claim metadata fields `speaker` and `location_ISO_code`
(both present in the unlabeled AVeriTeC test release, i.e. available at
inference time). No gold URL, ks_type, ks_query, label or role annotation. This is not an optimal
authority model; it only probes whether source priors move primary evidence up.
"""
import re

import spacy

import csv
import sys

from baseline_retrieval import load_rankings, save_rankings
from common import ANNOTATIONS, RESULTS, full_host, load_sample, normalize_url, registered_domain, _TLD

LAMBDAS = (0.1, 0.25, 0.5, 1.0)
POOL = 100

INTERGOV = {"who.int", "un.org", "worldbank.org", "imf.org", "oecd.org", "oecd-ilibrary.org",
            "europa.eu", "wto.org", "unicef.org", "unesco.org", "unhcr.org", "undp.org", "ilo.org"}
ACADEMIC_HOSTS = {"nature.com", "thelancet.com", "sciencedirect.com", "springer.com", "wiley.com",
                  "jstor.org", "plos.org", "bmj.com", "nejm.org", "jamanetwork.com", "arxiv.org",
                  "science.org", "cochranelibrary.com", "tandfonline.com", "oup.com", "cambridge.org"}
MAJOR_NEWS = {"reuters.com", "apnews.com", "bbc.co.uk", "bbc.com", "nytimes.com", "washingtonpost.com",
              "theguardian.com", "cnn.com", "nbcnews.com", "cbsnews.com", "abcnews.go.com", "npr.org",
              "bloomberg.com", "ft.com", "wsj.com", "aljazeera.com", "dw.com", "france24.com",
              "economist.com", "latimes.com", "usatoday.com", "politico.com", "axios.com", "time.com",
              "indiatimes.com", "hindustantimes.com", "indianexpress.com", "thehindu.com", "ndtv.com",
              "abc.net.au", "cbc.ca", "theglobeandmail.com", "scmp.com", "punchng.com", "premiumtimesng.com",
              "nzherald.co.nz", "stuff.co.nz", "news24.com", "rappler.com", "inquirer.net", "thetimes.co.uk",
              "telegraph.co.uk", "independent.co.uk", "sky.com", "channel4.com", "cnbc.com", "foxnews.com"}
REFERENCE = {"wikipedia.org", "britannica.com", "wikiwand.com"}
PLATFORMS = {"twitter.com", "x.com", "facebook.com", "youtube.com", "instagram.com", "tiktok.com",
             "reddit.com", "medium.com", "blogspot.com", "wordpress.com", "quora.com", "pinterest.com",
             "linkedin.com", "t.co", "archive.ph", "archive.org"}
SOCIAL_HANDLE_HOSTS = {"twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com"}
GOV_LABELS = {"gov", "govt", "gouv", "gob", "gc", "mil", "nic", "gv", "go"}
ISO_TO_TLD = {"GB": "uk", "US": "us"}
STOP_ENTITY = {"the", "a", "an", "of", "and", "for", "in", "on", "de", "us", "uk"}


def is_gov(host: str) -> bool:
    labels = host.split(".")
    return host.endswith(".gov") or host.endswith(".mil") or any(l in GOV_LABELS for l in labels[1:])


def country_of(host: str) -> str | None:
    suffix = _TLD("http://" + host).suffix
    last = suffix.split(".")[-1] if suffix else ""
    if host.endswith(".gov") or host.endswith(".mil"):
        return "us"
    return last if len(last) == 2 else None


def generic_prior(url: str) -> float:
    host, dom = full_host(url), registered_domain(url)
    if is_gov(host) or dom in INTERGOV or host.endswith(".int"):
        return 1.0
    if dom in ACADEMIC_HOSTS or ".edu" in host or ".ac." in host:
        return 0.8
    if dom in MAJOR_NEWS:
        return 0.6
    if dom in REFERENCE:
        return 0.5
    if dom in PLATFORMS:
        return 0.2
    return 0.3


# ------------------------------------------------------------- claim entities

_NLP = None


def claim_entities(row: dict) -> list[tuple[str, str]]:
    """(mention, label) pairs from spaCy NER on the claim, plus the speaker field."""
    global _NLP
    if _NLP is None:
        _NLP = spacy.load("en_core_web_sm")
    ents = [(e.text, e.label_) for e in _NLP(row["claim"]).ents
            if e.label_ in {"PERSON", "ORG", "FAC", "PRODUCT", "EVENT", "LAW"}]
    if row.get("speaker_or_entity"):
        ents.append((row["speaker_or_entity"], "SPEAKER"))
    return ents


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def entity_keys(ents: list[tuple[str, str]]) -> set[str]:
    """Strings that may equal/contain a domain label or social handle.

    - every mention: its collapsed name ("iowafarmbureau") and explicit
      upper-case acronyms inside it ("NNPC", "SANA")
    - multi-word ORG/speaker mentions: their initials acronym
    - PERSON (and short speaker) mentions: surnames/long tokens ("buhari")
    GPE/NORP mentions are ignored: jurisdiction is handled via location_ISO_code.
    """
    keys = set()
    for text, label in ents:
        text = re.sub(r"^(the|The)\s+", "", text.strip())
        words = [w for w in re.findall(r"[A-Za-z0-9]+", text) if w.lower() not in STOP_ENTITY]
        if not words:
            continue
        keys.add(_alnum(text))
        keys.update(c.lower() for c in re.findall(r"\b[A-Z]{2,6}\b", text))
        if label in {"ORG", "SPEAKER", "FAC", "LAW", "EVENT"} and len(words) >= 2:
            keys.add("".join(w[0] for w in words).lower())
        if label == "PERSON" or (label == "SPEAKER" and len(words) <= 3):
            keys.update(w.lower() for w in words if len(w) >= 5)
    return {k for k in keys if len(k) >= 3}


def entity_match(url: str, keys: set[str]) -> bool:
    host, dom = full_host(url), registered_domain(url)
    label = _alnum(dom.split(".")[0])
    if dom in SOCIAL_HANDLE_HOSTS:  # match the account handle, not the platform
        m = re.match(r"^[^/]+/(?:@)?([A-Za-z0-9_.]+)", normalize_url(url))
        handle = _alnum(m.group(1)) if m else ""
        return bool(handle) and any(k == handle or (len(k) >= 5 and k in handle) for k in keys)
    if dom in PLATFORMS or dom in MAJOR_NEWS or dom in REFERENCE:
        return False
    return any(k == label or (len(k) >= 4 and (k in label or label in k and len(label) >= 4)) for k in keys)


def claim_prior(url: str, keys: set[str], iso: str | None) -> float:
    if entity_match(url, keys):
        return 1.0
    host = full_host(url)
    if iso and is_gov(host) and country_of(host) == ISO_TO_TLD.get(iso, iso.lower()):
        return 1.0
    return 0.0


def full_prior(url: str, keys: set[str], iso: str | None) -> float:
    g = generic_prior(url)
    host = full_host(url)
    if iso and is_gov(host) and country_of(host) not in (None, ISO_TO_TLD.get(iso, iso.lower())):
        g = 0.6  # official, but another jurisdiction
    return max(g, claim_prior(url, keys, iso))


def rerank(base_ranked, prior_fn, lam, pool_size=POOL):
    """pool_size=None re-scores every candidate (sensitivity analysis: the top-100
    relevance pool contains only 17/48 reachable primary gold docs for bm25)."""
    pool = base_ranked[:pool_size]
    hi, lo = max(s for _, s in pool), min(s for _, s in pool)
    span = (hi - lo) or 1.0
    rescored = [(u, (s - lo) / span + lam * prior_fn(u)) for u, s in pool]
    rescored.sort(key=lambda x: -x[1])  # stable: ties keep the relevance order
    return rescored


def oracle_primary_domains() -> dict[int, set[str]]:
    """ORACLE ONLY (deliberate leakage, upper bound): domains of pilot-annotated primary gold sources."""
    out: dict[int, set[str]] = {}
    with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
        for x in csv.DictReader(fh):
            if x["source_role"] == "A_primary":
                out.setdefault(int(x["claim_id"]), set()).add(registered_domain(normalize_url(x["evidence_url"])))
    return out


def main():
    bases = sys.argv[1:] or ["bm25", "dense", "hybrid"]
    sample = load_sample()
    oracle = oracle_primary_domains()
    info = {r["claim_id"]: (entity_keys(claim_entities(r)), r.get("location_ISO_code")) for r in sample}
    variants = {
        "generic": lambda cid: generic_prior,
        "entity": lambda cid: (lambda u, k=info[cid][0]: float(entity_match(u, k))),
        "claim": lambda cid: (lambda u, k=info[cid][0], i=info[cid][1]: claim_prior(u, k, i)),
        "full": lambda cid: (lambda u, k=info[cid][0], i=info[cid][1]: full_prior(u, k, i)),
        "oracle": lambda cid: (lambda u, d=oracle.get(cid, set()): float(registered_domain(u) in d)),
    }
    for base in bases:
        ranked_base = load_rankings(base)
        for name, make in variants.items():
            for lam in LAMBDAS:
                save_rankings(f"{base}+{name}_l{lam}", {cid: rerank(rk, make(cid), lam) for cid, rk in ranked_base.items()})
                save_rankings(f"{base}+{name}_l{lam}_poolall",
                              {cid: rerank(rk, make(cid), lam, None) for cid, rk in ranked_base.items()})
            print("saved", base, name, flush=True)

        # diagnostics: how often does each prior fire inside the pool?
        diag = []
        for r in sample:
            cid, (keys, iso) = r["claim_id"], info[r["claim_id"]]
            pool = [u for u, _ in ranked_base[cid][:POOL]]
            diag.append({
                "claim_id": cid, "location_ISO_code": iso, "speaker": r.get("speaker_or_entity"),
                "entity_keys": " ".join(sorted(keys)),
                "pool_entity_matches": sum(entity_match(u, keys) for u in pool),
                "pool_claim_prior_1": sum(claim_prior(u, keys, iso) == 1.0 for u in pool),
                "pool_generic_1": sum(generic_prior(u) == 1.0 for u in pool),
                "entity_matched_examples": " ".join([u for u in pool if entity_match(u, keys)][:5]),
            })
        with open(RESULTS / f"authority_diagnostics_{base}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(diag[0]))
            w.writeheader()
            w.writerows(diag)
        n = len(diag)
        print(f"[{base}] claims with >=1 entity match in top-{POOL}: {sum(d['pool_entity_matches'] > 0 for d in diag)}/{n}; "
              f"with >=1 claim-prior hit: {sum(d['pool_claim_prior_1'] > 0 for d in diag)}/{n}; "
              f"with >=1 generic=1.0 doc: {sum(d['pool_generic_1'] > 0 for d in diag)}/{n}")


if __name__ == "__main__":
    main()
