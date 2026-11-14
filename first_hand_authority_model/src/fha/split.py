"""Claim-grouped, publisher-disjoint splitting by pair pruning.

1. Canonicalise publisher aliases.
2. Group near-duplicate claims (explicit claim_group_id wins; otherwise
   token-Jaccard on claim_text; otherwise one group per claim).
3. Assign claim groups to train / val / test.
4. Hold out publisher units (publisher, or corporate family if merging is
   enabled) from test claims, and a disjoint set from validation claims.
   Very common ("hub") units can be kept out of the held-out sets.
5. Prune: training keeps only pairs whose unit is not held out.

A fixed seed makes the split reproducible; it does not make it leakage-free.
The diagnostics returned are part of the evidence for that.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

import numpy as np

_WORD = re.compile(r"[a-z0-9]+")


def canonicalise(records: list[dict], alias_map: dict[str, str] | None) -> None:
    """Replace publisher_id by its canonical id in place (follows alias chains)."""
    if not alias_map:
        return
    for r in records:
        pid, seen = r["publisher_id"], set()
        while pid in alias_map and pid not in seen:
            seen.add(pid)
            pid = alias_map[pid]
        r["publisher_id"] = pid


def unit_of(record: dict, merge_families: bool) -> str:
    if merge_families and record.get("publisher_family_id"):
        return "family:" + record["publisher_family_id"]
    return "pub:" + record["publisher_id"]


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def claim_groups(records: list[dict], threshold: float = 0.8) -> dict[str, str]:
    """Map claim_id -> group id. Union-find over explicit ids and near-duplicates."""
    claims: dict[str, dict] = {}
    for r in records:
        c = claims.setdefault(r["claim_id"], {"group": r.get("claim_group_id"), "text": r.get("claim_text")})
        if r.get("claim_group_id") and c["group"] != r.get("claim_group_id"):
            raise ValueError(f"claim {r['claim_id']} has conflicting claim_group_id values")
    parent = {cid: cid for cid in claims}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_explicit = defaultdict(list)
    for cid, c in claims.items():
        if c["group"]:
            by_explicit[c["group"]].append(cid)
    for members in by_explicit.values():
        for m in members[1:]:
            union(members[0], m)

    ids = sorted(cid for cid, c in claims.items() if c["text"])
    toks = {cid: _tokens(claims[cid]["text"]) for cid in ids}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ta, tb = toks[a], toks[b]
            if ta and tb and len(ta & tb) / len(ta | tb) >= threshold:
                union(a, b)
    return {cid: "g:" + find(cid) for cid in claims}


def _cut(items: list, fracs: tuple[float, float, float], rng) -> tuple[list, list, list]:
    items = list(items)
    rng.shuffle(items)
    n = len(items)
    n_tr = int(round(fracs[0] * n))
    n_va = int(round(fracs[1] * n))
    return items[:n_tr], items[n_tr:n_tr + n_va], items[n_tr + n_va:]


def split_pairs(records: list[dict], cfg: dict) -> dict:
    """Return {'train', 'val_unseen', 'val_seen', 'test_unseen', 'test_seen', 'discarded', 'diagnostics'}.

    Records must carry a binary 'y' (used only to stratify claim groups by
    whether they contain a positive, so every split has positives).
    """
    rng = np.random.default_rng(cfg["seed"])
    merge = bool(cfg.get("merge_corporate_families"))
    fracs = (cfg["frac_train"], cfg["frac_val"], cfg["frac_test"])
    if abs(sum(fracs) - 1.0) > 1e-9:
        raise ValueError("split fractions must sum to 1")

    groups = claim_groups(records, cfg.get("near_duplicate_jaccard", 0.8))
    group_pos = defaultdict(bool)
    for r in records:
        group_pos[groups[r["claim_id"]]] |= r.get("y") == 1
    assign = {}
    for has_pos in (True, False):
        gs = sorted(g for g in set(groups.values()) if group_pos[g] == has_pos)
        tr, va, te = _cut(gs, fracs, rng)
        assign.update({g: "train" for g in tr} | {g: "val" for g in va} | {g: "test" for g in te})
    part_of = {r["pair_id"]: assign[groups[r["claim_id"]]] for r in records}

    n_claims = len({r["claim_id"] for r in records})
    unit_claims = defaultdict(set)
    unit_type = defaultdict(Counter)
    for r in records:
        u = unit_of(r, merge)
        unit_claims[u].add(r["claim_id"])
        unit_type[u][r["features"]["publisher_type"]] += 1
    hub_share = cfg.get("hub_max_claim_share")
    hubs = {u for u, cs in unit_claims.items() if hub_share is not None and len(cs) / n_claims > hub_share}

    def pick_units(part: str, frac: float, exclude: set) -> set:
        cands = sorted({unit_of(r, merge) for r in records if part_of[r["pair_id"]] == part} - hubs - exclude)
        by_type = defaultdict(list)
        for u in cands:
            by_type[unit_type[u].most_common(1)[0][0]].append(u)
        chosen = set()
        for t in sorted(by_type):
            us = by_type[t]
            rng.shuffle(us)
            k = int(round(frac * len(us)))
            if k == 0 and len(us) >= 2 and frac > 0:
                k = 1
            chosen.update(us[:k])
        return chosen

    test_units = pick_units("test", cfg["test_unit_fraction"], set())
    val_units = pick_units("val", cfg["val_unit_fraction"], test_units)
    held = test_units | val_units

    out = {k: [] for k in ("train", "val_unseen", "val_seen", "test_unseen", "test_seen", "discarded")}
    for r in records:
        u, part = unit_of(r, merge), part_of[r["pair_id"]]
        if part == "train":
            out["train" if u not in held else "discarded"].append(r)
        elif part == "val":
            if u in val_units:
                out["val_unseen"].append(r)
            elif u in test_units:
                out["discarded"].append(r)
            else:
                out["val_seen"].append(r)
        else:
            if u in test_units:
                out["test_unseen"].append(r)
            elif u in val_units:
                out["discarded"].append(r)
            else:
                out["test_seen"].append(r)

    out["diagnostics"] = split_diagnostics(out, merge, hubs, test_units, val_units, groups)
    return out


def split_diagnostics(out: dict, merge: bool, hubs: set, test_units: set, val_units: set, groups: dict) -> dict:
    def units(rs):
        return {unit_of(r, merge) for r in rs}

    def pubs(rs):
        return {r["publisher_id"] for r in rs}

    def summary(rs):
        ys = [r["y"] for r in rs if r.get("y") is not None]
        return {"pairs": len(rs), "claims": len({r["claim_id"] for r in rs}),
                "publishers": len(pubs(rs)), "positives": int(sum(ys)),
                "prevalence": (sum(ys) / len(ys)) if ys else None,
                "publisher_types": dict(Counter(r["features"]["publisher_type"] for r in rs))}

    train_units, train_pubs = units(out["train"]), pubs(out["train"])
    train_groups = {groups[r["claim_id"]] for r in out["train"]}
    test_groups = {groups[r["claim_id"]] for r in out["test_unseen"] + out["test_seen"]}
    val_groups = {groups[r["claim_id"]] for r in out["val_unseen"] + out["val_seen"]}
    return {
        "per_split": {k: summary(v) for k, v in out.items() if k != "diagnostics"},
        "overlap_units_train_test_unseen": sorted(train_units & units(out["test_unseen"])),
        "overlap_publishers_train_test_unseen": sorted(train_pubs & pubs(out["test_unseen"])),
        "overlap_units_train_val_unseen": sorted(train_units & units(out["val_unseen"])),
        "overlap_claim_groups_train_test": sorted(train_groups & test_groups),
        "overlap_claim_groups_train_val": sorted(train_groups & val_groups),
        "n_hub_units": len(hubs),
        "n_test_units": len(test_units),
        "n_val_units": len(val_units),
        "discarded_positives": int(sum(r.get("y") == 1 for r in out["discarded"])),
        "merge_corporate_families": merge,
        "note": "Zero overlap is necessary but not sufficient: aliases missing from the alias map are not detected.",
    }


def inner_folds(train: list[dict], cfg: dict, k: int):
    """Repeated grouped, publisher-disjoint holdouts inside the training set."""
    for i in range(k):
        sub = dict(cfg, seed=cfg["seed"] + 1000 + i, frac_train=1 - 1 / k, frac_val=1 / k, frac_test=0.0,
                   test_unit_fraction=0.0)
        s = split_pairs(train, sub)
        yield s["train"], s["val_unseen"]
