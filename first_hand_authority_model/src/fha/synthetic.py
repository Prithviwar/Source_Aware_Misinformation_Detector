"""Synthetic fixtures for testing pipeline mechanics ONLY.

Every record carries is_synthetic=True. The label rule below is planted by
construction, so any score obtained on these fixtures shows only that the
code runs and can recover a planted signal. It is never evidence about real
first-hand authority, and real-mode training refuses synthetic records.
"""

from __future__ import annotations

import numpy as np

COUNTRIES = ["XA", "XB", "XC", "XD"]
TOPICS = ["LABOUR_ECONOMY", "HEALTH", "JUSTICE", "ENVIRONMENT", "ELECTIONS"]
ACTIONS = ["POLICY_DECISION", "LEGAL_RULING", "OFFICIAL_STATISTIC", "RESEARCH_FINDING",
           "EVENT_OCCURRENCE", "OWN_CONDUCT", "UTTERANCE"]
SELF_ACT = {"POLICY_DECISION", "LEGAL_RULING", "OWN_CONDUCT"}
RESPONSIBLE = {"OFFICIAL_STATISTIC": {"STATISTICS_OFFICE"}, "LEGAL_RULING": {"COURT"},
               "POLICY_DECISION": {"EXECUTIVE_GOV", "REGULATOR"}, "RESEARCH_FINDING": {"JOURNAL", "RESEARCH_ORG"}}
TYPES_NATIONAL = ["EXECUTIVE_GOV", "COURT", "STATISTICS_OFFICE", "REGULATOR", "NEWS", "COMPANY", "NGO"]
TYPES_GLOBAL = ["INTERGOVERNMENTAL", "JOURNAL", "RESEARCH_ORG", "NEWS", "FACT_CHECKER"]


def _publishers(rng, n_per_country: int = 9, n_global: int = 10) -> list[dict]:
    pubs = []
    for c in COUNTRIES:
        for i in range(n_per_country):
            t = TYPES_NATIONAL[i % len(TYPES_NATIONAL)]
            pubs.append({"id": f"{c.lower()}-{t.lower()}-{i}", "type": t, "country": c,
                         "level": "NATIONAL" if t not in ("NEWS", "COMPANY", "NGO") else "NONE",
                         "topic": TOPICS[i % len(TOPICS)], "family": None})
    for i in range(n_global):
        t = TYPES_GLOBAL[i % len(TYPES_GLOBAL)]
        pubs.append({"id": f"global-{t.lower()}-{i}", "type": t, "country": None,
                     "level": "INTERNATIONAL" if t != "NEWS" else "NONE",
                     "topic": TOPICS[i % len(TOPICS)], "family": None})
    # two corporate families of news publishers spanning countries
    news = [p for p in pubs if p["type"] == "NEWS"]
    for j, p in enumerate(news[:6]):
        p["family"] = f"newsgroup-{j % 2}"
    return pubs


def _mask(rng, value: str, p_unknown: float) -> str:
    return "UNKNOWN" if rng.random() < p_unknown else value


def generate(n_claims: int = 240, candidates: int = 7, seed: int = 0, noise: float = 0.05) -> list[dict]:
    rng = np.random.default_rng(seed)
    pubs = _publishers(rng)
    records = []
    for k in range(n_claims):
        cid = f"SYN{k:04d}"
        country = COUNTRIES[rng.integers(len(COUNTRIES))]
        action = ACTIONS[rng.integers(len(ACTIONS))]
        topic = TOPICS[rng.integers(len(TOPICS))]
        local = [p for p in pubs if p["country"] == country]
        actor = local[rng.integers(len(local))] if action in SELF_ACT | {"UTTERANCE"} else None
        speaker = local[rng.integers(len(local))]
        chosen = {p["id"]: p for p in rng.choice(pubs, size=candidates, replace=False)}
        responsible = [p for p in local if p["type"] in RESPONSIBLE.get(action, set())]
        for p in responsible[:1] + ([actor] if actor else []):
            chosen[p["id"]] = p
        text = f"synthetic claim {k} about {topic.lower()} {action.lower()} in {country.lower()} token{k}"
        if k % 40 == 1:  # near-duplicate of the previous claim
            text = records[-1]["claim_text"] + " again"
        for p in chosen.values():
            same_country = p["country"] == country
            truth = (actor is not None and p["id"] == actor["id"] and action in SELF_ACT) or \
                    (p["type"] in RESPONSIBLE.get(action, set()) and same_country and p["topic"] == topic) or \
                    (p["type"] in ("JOURNAL", "RESEARCH_ORG") and action == "RESEARCH_FINDING" and p["topic"] == topic)
            if rng.random() < noise:
                truth = not truth
            if rng.random() < 0.05:
                label = {"final": "CANNOT_JUDGE", "cannot_judge_reason": "INSUFFICIENT_EVIDENCE"}
            elif truth:
                basis = "INSTITUTIONAL_ACT" if action in SELF_ACT else (
                    "ORIGINAL_RESEARCH" if action == "RESEARCH_FINDING" else "OFFICIAL_RECORD")
                label = {"final": "FIRST_HAND_AUTHORITY", "basis": basis}
            else:
                label = {"final": "NOT_FIRST_HAND_AUTHORITY", "not_fha_reason": "UNRELATED"}
            label.update({"flags": [], "adjudicated": False, "guideline_version": "SYNTHETIC"})
            if p["country"] is None:
                jm = "ENCOMPASSING" if p["level"] == "INTERNATIONAL" else "NOT_APPLICABLE"
            else:
                jm = "SAME" if same_country else "DIFFERENT"
            feats = {
                "action_type": _mask(rng, action, 0.05),
                "claim_scope": "NATIONAL",
                "claim_topic": _mask(rng, topic, 0.05),
                "publisher_type": _mask(rng, p["type"], 0.02),
                "publisher_jurisdiction_level": p["level"],
                "actor_relation": _mask(rng, "SAME_ENTITY" if actor and p["id"] == actor["id"] else "NONE", 0.15),
                "speaker_relation": _mask(rng, "SAME_ENTITY" if p["id"] == speaker["id"] else "NONE", 0.15),
                "jurisdiction_match": _mask(rng, jm, 0.1),
                "remit_match": _mask(rng, "YES" if p["topic"] == topic else "NO", 0.2),
                "active_at_claim_date": "NO" if rng.random() < 0.02 else "YES",
            }
            records.append({
                "pair_id": f"{cid}::{p['id']}", "claim_id": cid, "claim_text": text,
                "publisher_id": p["id"], "publisher_family_id": p["family"],
                "publisher_resolved": bool(rng.random() > 0.02),
                "features": feats, "label": label, "is_synthetic": True,
            })
    return records
