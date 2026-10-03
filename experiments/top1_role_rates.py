"""Step 7c: Metric 3 -- role of the rank-1 document per method (blind pilot labels).

Labels in data/annotations/top1_blind_roles.csv were assigned by one annotator
(Claude, pilot) from claim + URL + first 400 chars, WITHOUT knowing which method
retrieved the item or whether it was gold. Scheme (role relative to the claim):
  P  primary & on-topic: official body / organisation itself / original data producer / court or
     legislative record that directly bears on the claim's fact
  A  claim artifact: the claim-maker's own statement/page (primary for "did X say it", but an
     interested party, not an independent authority on the fact)
  O  official/academic/IGO-looking publisher but OFF-TOPIC or WRONG JURISDICTION for this claim
  S  secondary: news, fact-checkers, explainers, blogs, advocacy, analyses
  D  derived: encyclopedias, aggregators, forums, mirrors/re-hosted copies of other content
  U  unclear / irrelevant
"""
import csv
import json
from collections import Counter

from common import ANNOTATIONS, RESULTS

# item_id -> label (blind; see scheme above)
LABELS = {
    1: "S", 2: "O", 3: "D", 4: "S", 5: "P", 6: "S", 7: "S", 8: "S", 9: "S", 10: "S", 11: "S", 12: "S", 13: "D", 14: "A", 15: "D",
    16: "D", 17: "O", 18: "P", 19: "S", 20: "S", 21: "S", 22: "S", 23: "S", 24: "S", 25: "O", 26: "O", 27: "S", 28: "S", 29: "S", 30: "S",
    31: "S", 32: "O", 33: "S", 34: "S", 35: "O", 36: "S", 37: "O", 38: "O", 39: "S", 40: "D", 41: "S", 42: "O", 43: "O", 44: "D", 45: "S",
    46: "U", 47: "A", 48: "D", 49: "S", 50: "O", 51: "S", 52: "S", 53: "S", 54: "S", 55: "S", 56: "O", 57: "S", 58: "S", 59: "S", 60: "S",
    61: "S", 62: "S", 63: "S", 64: "S", 65: "S", 66: "S", 67: "S", 68: "S", 69: "S", 70: "D", 71: "P", 72: "S", 73: "S", 74: "S", 75: "S",
    76: "S", 77: "P", 78: "S", 79: "O", 80: "S", 81: "S", 82: "S", 83: "D", 84: "O", 85: "A", 86: "D", 87: "S", 88: "P", 89: "S", 90: "S",
    91: "S", 92: "O", 93: "S", 94: "P", 95: "S", 96: "O", 97: "S", 98: "P", 99: "S", 100: "O", 101: "S", 102: "O", 103: "S", 104: "U", 105: "S",
    106: "O", 107: "S", 108: "O", 109: "S", 110: "O", 111: "S", 112: "S", 113: "O", 114: "S", 115: "S", 116: "O", 117: "S", 118: "S", 119: "D", 120: "P",
    121: "S", 122: "O", 123: "S", 124: "O", 125: "S", 126: "O", 127: "S", 128: "O", 129: "S", 130: "S", 131: "S", 132: "S", 133: "O", 134: "S", 135: "S",
    136: "S", 137: "S", 138: "U", 139: "O", 140: "S", 141: "O", 142: "O", 143: "S", 144: "S", 145: "S", 146: "S", 147: "S", 148: "S", 149: "A", 150: "S",
    151: "S", 152: "S", 153: "S", 154: "D", 155: "D", 156: "O",
}
METHODS = ["bm25", "dense", "hybrid", "bm25+generic_l0.25", "bm25+full_l0.25", "bm25+wikidata_l0.25",
           "bm25+full_l1.0_poolall"]


def main():
    items = list(csv.DictReader(open(ANNOTATIONS / "top1_blind_items.csv", encoding="utf-8")))
    assert sorted(LABELS) == [int(it["item_id"]) for it in items]
    with open(ANNOTATIONS / "top1_blind_roles.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "claim_id", "url", "role", "annotator"])
        for it in items:
            w.writerow([it["item_id"], it["claim_id"], it["url"], LABELS[int(it["item_id"])], "claude-pilot-blind"])
    role = {f"{it['claim_id']}|{it['url']}": LABELS[int(it["item_id"])] for it in items}
    where = json.load(open(RESULTS / "top1_method_map.json", encoding="utf-8"))
    out = {}
    for m in METHODS:
        c = Counter(role[k] for k, ms in where.items() if m in ms)
        n = sum(c.values())
        out[m] = {"n": n, **{r: c[r] for r in "PAOSDU"},
                  **{f"share_{r}": round(c[r] / n, 3) for r in "PAOSDU"}}
    json.dump(out, open(RESULTS / "top1_role_rates.json", "w"), indent=1)
    print("method".ljust(26), "n  ", "  ".join(f"{r:>5}" for r in "PAOSDU"))
    for m, v in out.items():
        print(m.ljust(26), str(v["n"]).ljust(4), "  ".join(f"{v['share_' + r]:5.2f}" for r in "PAOSDU"))


if __name__ == "__main__":
    main()
