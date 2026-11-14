"""Step 5b (POST-HOC variant, added after seeing that the string-matching entity
prior fires in only 33/120 claims): claim-specific authority via entity -> Wikidata
official-web-presence resolution.

For every entity mention in the claim text / speaker field (same spaCy mentions
as authority_retrieval.claim_entities), take the top Wikidata search hit whose
label or alias matched, and collect
  P856  official website          -> registered domain
  P2002 X/Twitter username, P2013 Facebook username, P2003 Instagram username -> handle
prior(url) = 1 if the candidate's registered domain is one of those official
domains (platform domains excluded) or its social handle is an official handle.

Inputs: claim text + speaker only. No gold URL / ks_type / ks_query / label / role.
Caveat: Wikidata is queried as of 2026, not as of the claim date.
Resolutions are cached in results/wikidata_resolution.json (re-runs are offline).
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from authority_retrieval import LAMBDAS, PLATFORMS, SOCIAL_HANDLE_HOSTS, claim_entities, rerank, _alnum
from baseline_retrieval import load_rankings, save_rankings
from common import RESULTS, load_sample, normalize_url, registered_domain

API = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "sourceaware-feasibility-study/0.1 (research; contact via repo owner)"}
CACHE = RESULTS / "wikidata_resolution.json"
HANDLE_PROPS = {"P2002": "twitter", "P2013": "facebook", "P2003": "instagram"}


def _get(params: dict) -> dict:
    """Throttled (~1 req/s) GET honouring HTTP 429 Retry-After (Wikimedia rate limits)."""
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "maxlag": 5})
    for attempt in range(8):
        time.sleep(1.0)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as fh:
                return json.load(fh)
        except urllib.error.HTTPError as e:
            wait = int(e.headers.get("Retry-After") or 0) or 5 * 2 ** attempt
            print(f"HTTP {e.code}; waiting {wait}s", flush=True)
            time.sleep(min(wait, 300))
        except Exception as e:
            print(f"{e!r}; retrying", flush=True)
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"Wikidata request failed: {url}")


def search(mention: str) -> dict:
    hits = _get({"action": "wbsearchentities", "search": mention, "language": "en", "limit": 3}).get("search", [])
    hits = [h for h in hits if h.get("match", {}).get("type") in ("label", "alias")]
    if not hits:
        return {"qid": None}
    h = hits[0]
    return {"qid": h["id"], "label": h.get("label"), "description": h.get("description")}


def fetch_presence(qids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(qids), 50):
        ents = _get({"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "claims"})["entities"]
        for q, ent in ents.items():
            claims = ent.get("claims", {})
            val = lambda p: [c["mainsnak"]["datavalue"]["value"] for c in claims.get(p, [])
                             if c["mainsnak"].get("datavalue")]
            out[q] = {"websites": val("P856"), "handles": {HANDLE_PROPS[p]: val(p) for p in HANDLE_PROPS if val(p)}}
    return out


def official_presence(mentions: list[str], cache: dict) -> tuple[set[str], set[str]]:
    domains, handles = set(), set()
    for m in mentions:
        res = cache[m]
        for w in res.get("websites", []):
            d = registered_domain(w)
            if d and d not in PLATFORMS:
                domains.add(d)
        for hs in res.get("handles", {}).values():
            handles.update(_alnum(x) for x in hs if isinstance(x, str))
    return domains, handles


def wikidata_prior(url: str, domains: set[str], handles: set[str]) -> float:
    dom = registered_domain(url)
    if dom in SOCIAL_HANDLE_HOSTS:
        m = re.match(r"^[^/]+/(?:@)?([A-Za-z0-9_.]+)", normalize_url(url))
        return float(bool(m) and _alnum(m.group(1)) in handles)
    return float(dom in domains)


def main():
    bases = sys.argv[1:] or ["bm25", "dense", "hybrid"]
    sample = load_sample()
    cache = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}
    mentions = {r["claim_id"]: sorted({t for t, _ in claim_entities(r)}) for r in sample}
    todo = sorted({m for ms in mentions.values() for m in ms} - set(cache))
    for i, m in enumerate(todo, 1):
        cache[m] = search(m)
        if i % 25 == 0:
            print(f"searched {i}/{len(todo)}", flush=True)
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    need = sorted({v["qid"] for v in cache.values() if v.get("qid") and "websites" not in v})
    pres = fetch_presence(need)
    for v in cache.values():
        if v.get("qid") in pres:
            v.update(pres[v["qid"]])
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    presence = {cid: official_presence(ms, cache) for cid, ms in mentions.items()}
    n_res = sum(1 for v in cache.values() if v.get("qid"))
    n_site = sum(1 for v in cache.values() if v.get("websites") or v.get("handles"))
    print(f"mentions: {len(cache)}; resolved to a Wikidata item: {n_res}; with official website/handle: {n_site}")
    print(f"claims with >=1 official domain/handle: {sum(bool(d or h) for d, h in presence.values())}/{len(sample)}")
    json.dump({str(c): {"mentions": mentions[c], "domains": sorted(d), "handles": sorted(h)}
               for c, (d, h) in presence.items()},
              open(RESULTS / "wikidata_claim_authorities.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for base in bases:
        rk = load_rankings(base)
        fire = sum(any(wikidata_prior(u, *presence[c]) for u, _ in rk[c][:100]) for c in rk)
        print(f"[{base}] claims with >=1 Wikidata-official doc in top-100: {fire}/{len(rk)}; "
              f"in full candidate list: {sum(any(wikidata_prior(u, *presence[c]) for u, _ in rk[c]) for c in rk)}")
        for lam in LAMBDAS:
            for pool, suffix in ((100, ""), (None, "_poolall")):
                save_rankings(f"{base}+wikidata_l{lam}{suffix}",
                              {c: rerank(r, lambda u, p=presence[c]: wikidata_prior(u, *p), lam, pool) for c, r in rk.items()})


if __name__ == "__main__":
    main()
