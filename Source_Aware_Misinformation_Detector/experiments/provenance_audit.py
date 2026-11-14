"""Step 6: are the top-ranked documents independent?

For each claim's BM25 top-10 (non-empty) documents:
  * near-duplicate / syndicated pairs: word 5-gram shingles on the first 20k
    chars; a pair is "derived-copy" if Jaccard >= 0.5 or containment >= 0.6
    (share of the shorter doc's shingles present in the other)
  * wire / attribution markers: '(Reuters)', 'Associated Press', '(AP)', 'AFP',
    'according to ...', 'said in a statement', 'press release'
  * independent groups = connected components of the copy graph

Heuristic, no stance detection: it measures redundancy, not agreement.
Writes results/provenance_top10.csv and prints examples to inspect manually.
"""
import csv
import re
from collections import Counter

from baseline_retrieval import claim_docs, load_rankings
from common import RESULTS, load_sample, registered_domain

TOP = 10
WIRE = {
    "reuters": re.compile(r"\(Reuters\)|Reuters reported|told Reuters|Reuters\s*[-—]", re.I),
    "ap": re.compile(r"\(AP\)|Associated Press", re.I),
    "afp": re.compile(r"\bAFP\b|Agence France-Presse", re.I),
    "pti/ani/ians": re.compile(r"\((PTI|ANI|IANS)\)|\bPress Trust of India\b", re.I),
}
ATTRIB = re.compile(r"according to (?:a |the )?(?:statement|report|press release|[A-Z][\w.&-]+)|"
                    r"said in a statement|press release|in a tweet|posted on (?:Twitter|Facebook)", re.I)


def shingles(text: str, n: int = 5) -> set[int]:
    w = re.findall(r"\w+", text.lower()[:20_000])
    return {hash(" ".join(w[i:i + n])) for i in range(max(0, len(w) - n + 1))}


def components(n: int, edges: list[tuple[int, int]]) -> list[set[int]]:
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in edges:
        parent[find(a)] = find(b)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), set()).add(i)
    return list(groups.values())


def main():
    bm25 = load_rankings("bm25")
    rows, examples = [], []
    for r in load_sample():
        docs = {d["url_norm"]: d for d in claim_docs(r["claim_id"], audit=True)}
        top = [docs[u] for u, _ in bm25[r["claim_id"]] if docs[u]["text"].strip()][:TOP]
        sh = [shingles(d["text"]) for d in top]
        edges = []
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                if not sh[i] or not sh[j]:
                    continue
                inter = len(sh[i] & sh[j])
                jac = inter / len(sh[i] | sh[j])
                cont = inter / min(len(sh[i]), len(sh[j]))
                if jac >= 0.5 or cont >= 0.6:
                    edges.append((i, j))
                    examples.append((r["claim_id"], top[i]["url"], top[j]["url"], round(jac, 2), round(cont, 2)))
        comps = components(len(top), edges)
        wire = Counter(k for d in top for k, rx in WIRE.items() if rx.search(d["text"][:20_000]))
        attrib = sum(bool(ATTRIB.search(d["text"][:20_000])) for d in top)
        rows.append({
            "claim_id": r["claim_id"], "n_top_docs": len(top), "copy_pairs": len(edges),
            "independent_groups": len(comps), "largest_group": max((len(c) for c in comps), default=0),
            "distinct_domains": len({registered_domain(d["url"]) for d in top}),
            "docs_with_wire_marker": sum(any(rx.search(d["text"][:20_000]) for rx in WIRE.values()) for d in top),
            "wire_markers": dict(wire), "docs_with_attribution_phrase": attrib,
        })
    with open(RESULTS / "provenance_top10.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    docs_total = sum(x["n_top_docs"] for x in rows)
    print(f"claims: {n}; top docs: {docs_total}")
    print(f"claims with >=1 copy pair in top-{TOP}: {sum(x['copy_pairs'] > 0 for x in rows)} "
          f"({sum(x['copy_pairs'] > 0 for x in rows) / n:.1%})")
    print(f"docs absorbed into another doc's group: {docs_total - sum(x['independent_groups'] for x in rows)} "
          f"({(docs_total - sum(x['independent_groups'] for x in rows)) / docs_total:.1%})")
    print(f"mean independent groups per claim: {sum(x['independent_groups'] for x in rows) / n:.2f} "
          f"(mean docs {docs_total / n:.2f})")
    print(f"docs with wire-service marker: {sum(x['docs_with_wire_marker'] for x in rows)} "
          f"({sum(x['docs_with_wire_marker'] for x in rows) / docs_total:.1%})")
    print(f"docs with attribution phrase: {sum(x['docs_with_attribution_phrase'] for x in rows)} "
          f"({sum(x['docs_with_attribution_phrase'] for x in rows) / docs_total:.1%})")
    print("\nEXAMPLE COPY PAIRS (claim, doc a, doc b, jaccard, containment):")
    for e in examples[:40]:
        print(" ", e)


if __name__ == "__main__":
    main()
