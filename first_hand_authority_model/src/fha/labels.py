"""Mapping human labels to the binary training target."""

from __future__ import annotations

POLICIES = ("exclude", "as_negative", "as_positive")


def to_binary(label: dict, approved_bases: list[str], cannot_judge_policy: str = "exclude"):
    """Return (y, reason) where y is 1, 0 or None (no target).

    - FIRST_HAND_AUTHORITY with an approved basis -> 1
    - FIRST_HAND_AUTHORITY with an unapproved basis -> None (reported separately)
    - NOT_FIRST_HAND_AUTHORITY -> 0
    - CANNOT_JUDGE or unresolved (final is None) -> None, unless a
      sensitivity policy maps them to 0 or 1.
    Flags such as INTERESTED_PARTY never change the target.
    """
    if cannot_judge_policy not in POLICIES:
        raise ValueError(f"cannot_judge_policy must be one of {POLICIES}")
    final = label.get("final")
    if final == "FIRST_HAND_AUTHORITY":
        if label.get("basis") in approved_bases:
            return 1, "fha_approved_basis"
        return None, "fha_unapproved_basis"
    if final == "NOT_FIRST_HAND_AUTHORITY":
        return 0, "not_fha"
    reason = "cannot_judge" if final == "CANNOT_JUDGE" else "unresolved"
    if cannot_judge_policy == "as_negative":
        return 0, reason + "_as_negative"
    if cannot_judge_policy == "as_positive":
        return 1, reason + "_as_positive"
    return None, reason


def attach_targets(records: list[dict], approved_bases: list[str], policy: str = "exclude") -> dict:
    """Set record['y'] and record['y_reason'] in place; return counts by reason."""
    counts: dict[str, int] = {}
    for r in records:
        y, why = to_binary(r["label"], approved_bases, policy)
        r["y"], r["y_reason"] = y, why
        counts[why] = counts.get(why, 0) + 1
    return counts
