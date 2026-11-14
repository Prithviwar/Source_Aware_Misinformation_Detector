"""Offline invariants for T post-processing (U12) and X (§2.2). No LLM, no gold.

  python offline_checks.py     exit 0 = all pass; result appended to the execution log
"""
import hashlib
import sys

from v2common import log_event

from t_resolver import postprocess, schema_error
from x_control import build_x, digest, pool_attrs

POOL = ["who.int", "cdc.gov", "nytimes.com", "twitter.com/who", "example.org"]
results = []


def check(name, cond):
    results.append((name, bool(cond)))


# ---- U12 schema (rule 2)
check("schema: abstain string 'true' is a parse failure", schema_error({"selections": [], "abstain": "true"}))
check("schema: missing selections", schema_error({"abstain": False}))
check("schema: selections not a list", schema_error({"selections": {}, "abstain": False}))
check("schema: non-object", schema_error(["x"]))
check("schema: valid", schema_error({"selections": [], "abstain": True}) is None)
# ---- rules 3-9
k, s, f = postprocess(None, POOL)
check("rule 3: unparsed -> no keys, parse_failure", k == [] and s == "parse_failure")
k, s, f = postprocess({"abstain": True, "selections": [{"key": "who.int"}]}, POOL)
check("rule 4: abstain overrides selections, abstain_conflict", k == [] and s == "abstain" and f["abstain_conflict"] == 1)
k, s, f = postprocess({"abstain": True, "selections": []}, POOL)
check("rule 4: plain abstain, no conflict", k == [] and s == "abstain" and f["abstain_conflict"] == 0)
k, s, f = postprocess({"abstain": False, "selections": [{"key": "  WHO.int "}, {"key": "www.cdc.gov"},
                                                         {"key": "https://nytimes.com"}, "who.int", {"key": 3}, {}]}, POOL)
check("rule 5: strip+lower only; no www/URL repair; non-objects and non-strings invalid",
      k == ["who.int"] and f["invalid_key"] == 5)
k, s, f = postprocess({"abstain": False, "selections": [{"key": "cdc.gov"}, {"key": "CDC.gov"}, {"key": "who.int"}]}, POOL)
check("rule 6: duplicates after normalisation, first kept", k == ["cdc.gov", "who.int"] and f["duplicate_key"] == 1)
k, s, f = postprocess({"abstain": False, "selections": [{"key": x} for x in
                                                         ["example.org", "who.int", "who.int", "cdc.gov", "twitter.com/who"]]}, POOL)
check("rule 7: >3 valid keys truncated in model order (after dedup)",
      k == ["example.org", "who.int", "cdc.gov"] and f["truncated"] == 1 and f["duplicate_key"] == 1)
k, s, f = postprocess({"abstain": False, "selections": [{"key": "nope.com"}]}, POOL)
check("rule 8: abstain=false with no valid key -> empty_selection", k == [] and s == "empty_selection")
k, s, f = postprocess({"abstain": False, "selections": []}, POOL)
check("rule 8: abstain=false, empty list -> empty_selection", s == "empty_selection")

# ---- X digest layout
exp = hashlib.sha256(b"2029\x1f" + b"42\x1f" + b"1\x1f" + "café.fr".encode("utf-8")).digest()
check("X digest: b'2029' 0x1F ascii(id) 0x1F ascii(i) 0x1F utf8(q)", digest(42, 1, "café.fr") == exp)
check("X digest: big-endian bytes order == integer order",
      (digest(1, 1, "a") < digest(1, 1, "b")) == (int.from_bytes(digest(1, 1, "a"), "big") < int.from_bytes(digest(1, 1, "b"), "big")))
# ---- X attributes and matching
urls = ["who.int/a", "who.int/b", "un.org/x", "cdc.gov/y", "nytimes.com/1", "nytimes.com/2", "cnn.com/3",
        "someblog.net/1", "someblog.net/2", "facebook.com/someone/posts/1", ""]
count, typ = pool_attrs(urls)
check("X pool_attrs: counts", count["who.int"] == 2 and count["nytimes.com"] == 2 and count["cnn.com"] == 1)
check("X pool_attrs: types are frozen generic_prior floats", typ["who.int"] == 1.0 and typ["nytimes.com"] == 0.6
      and typ["someblog.net"] == 0.3)
x, slots, b = build_x(7, ["who.int", "nytimes.com"], {"cdc.gov"}, urls)
check("X: excludes T and D keys", not set(x) & {"who.int", "nytimes.com", "cdc.gov"})
check("X: same-type, nearest count", slots[0]["q"] == "un.org" and slots[0]["flag"] == "same_type"
      and slots[1]["q"] == "cnn.com" and slots[1]["flag"] == "same_type")
check("X: budget record", b == {"n_T": 2, "n_X": 2, "B_T": 4, "B_X": 2})
x2, s2, _ = build_x(7, ["who.int", "nytimes.com"], {"cdc.gov"}, list(reversed(urls)))
check("X: independent of pool order", x2 == x)
x3, s3, _ = build_x(7, ["who.int", "nytimes.com", "someblog.net"], {"cdc.gov", "un.org", "cnn.com"}, urls)
check("X: type_relaxed then unmatched when candidates run out",
      [s["flag"] for s in s3] == ["type_relaxed", "unmatched", "unmatched"])
x4, s4, b4 = build_x(7, [], set(), urls)
check("X: T abstains/fails -> X empty", x4 == [] and s4 == [] and b4["n_T"] == 0)
# tie-break by digest: two same-type candidates at equal count distance
u2 = ["a.gov/1", "b.gov/1", "c.gov/1"]
xa, sa, _ = build_x(11, ["a.gov"], set(), u2)
want = min(["b.gov", "c.gov"], key=lambda q: (digest(11, 1, q), q))
check("X: equal distance broken by digest", xa == [want])

bad = [n for n, ok in results if not ok]
for n, ok in results:
    print("PASS" if ok else "FAIL", n)
log_event("offline_checks", n=len(results), n_fail=len(bad), failures=bad)
sys.exit(0 if not bad else 2)
