import numpy as np
import pytest

from fha.bootstrap import classify_outcome, paired_bootstrap, resample_weights
from fha.labels import attach_targets
from fha.metrics import (auprc, best_f1_threshold, calibration_slope_intercept, ranking_metrics,
                         within_publisher_auroc)
from fha.split import canonicalise, claim_groups, inner_folds, split_pairs, unit_of


@pytest.fixture
def labelled(records):
    attach_targets(records, ["INSTITUTIONAL_ACT", "OFFICIAL_RECORD", "ORIGINAL_RESEARCH"])
    return [r for r in records if r["y"] is not None]


def test_split_is_publisher_disjoint_and_claim_grouped(labelled, smoke_config):
    sp = split_pairs(labelled, smoke_config["split"] | {"merge_corporate_families": True, "hub_max_claim_share": 0.5})
    d = sp["diagnostics"]
    assert d["overlap_units_train_test_unseen"] == [] and d["overlap_units_train_val_unseen"] == []
    assert d["overlap_claim_groups_train_test"] == [] and d["overlap_claim_groups_train_val"] == []
    total = sum(len(sp[k]) for k in ("train", "val_unseen", "val_seen", "test_unseen", "test_seen", "discarded"))
    assert total == len(labelled)
    # corporate families: no family appears both in training and in test_unseen
    fam_train = {r["publisher_family_id"] for r in sp["train"] if r["publisher_family_id"]}
    fam_test = {r["publisher_family_id"] for r in sp["test_unseen"] if r["publisher_family_id"]}
    assert not fam_train & fam_test


def test_split_is_reproducible(labelled, smoke_config):
    a = split_pairs(labelled, smoke_config["split"])
    b = split_pairs(labelled, smoke_config["split"])
    assert [r["pair_id"] for r in a["test_unseen"]] == [r["pair_id"] for r in b["test_unseen"]]


def test_near_duplicates_grouped():
    recs = [{"claim_id": "a", "claim_text": "unemployment fell to four percent in march"},
            {"claim_id": "b", "claim_text": "unemployment fell to four percent in march again"},
            {"claim_id": "c", "claim_text": "the court ruled on the case"},
            {"claim_id": "d", "claim_text": "different", "claim_group_id": "G1"},
            {"claim_id": "e", "claim_text": "other words", "claim_group_id": "G1"}]
    g = claim_groups(recs, threshold=0.8)
    assert g["a"] == g["b"] != g["c"] and g["d"] == g["e"]


def test_aliases_canonicalised_and_family_units():
    recs = [{"publisher_id": "stats.xr"}, {"publisher_id": "@XRStats"}]
    canonicalise(recs, {"stats.xr": "xr-stats", "@XRStats": "stats.xr"})
    assert {r["publisher_id"] for r in recs} == {"xr-stats"}
    assert unit_of({"publisher_id": "p", "publisher_family_id": "F"}, True) == "family:F"
    assert unit_of({"publisher_id": "p", "publisher_family_id": "F"}, False) == "pub:p"


def test_inner_folds_are_publisher_disjoint(labelled, smoke_config):
    train = split_pairs(labelled, smoke_config["split"])["train"]
    for tr, va in inner_folds(train, smoke_config["split"], 2):
        assert not {r["publisher_id"] for r in tr} & {r["publisher_id"] for r in va}


def test_auprc_and_within_publisher():
    y = [1, 0, 1, 0]
    assert auprc(y, [0.9, 0.1, 0.8, 0.2]) == pytest.approx(1.0)
    assert auprc([0, 0], [0.1, 0.2]) is None  # undefined without positives
    w = within_publisher_auroc(["p", "p", "q", "q"], y, [0.5, 0.5, 0.3, 0.3])
    assert w["mean"] == pytest.approx(0.5) and w["n_publishers"] == 2  # constant per publisher -> 0.5


def test_by_category_and_within_publisher_ci():
    from fha.metrics import by_category, within_publisher_ci
    out = by_category(["A", "A", "B", "B"], [1, 0, 0, 0], [0.9, 0.1, 0.2, 0.3])
    assert out["A"]["auprc"] == pytest.approx(1.0) and out["B"]["auprc"] is None and out["B"]["n"] == 2
    ci = within_publisher_ci({"p": 0.6, "q": 0.8, "r": 0.7}, n=500, seed=0)
    assert 0.6 - 1e-9 <= ci["lo"] <= ci["hi"] <= 0.8 + 1e-9
    assert within_publisher_ci({"p": 0.6})["lo"] is None


def test_ranking_metrics():
    r = ranking_metrics(["c1", "c1", "c1", "c2", "c2"], ["a", "b", "c", "d", "e"], [0, 1, 0, 0, 0],
                        [0.9, 0.5, 0.1, 0.3, 0.2], ks=(1, 3))
    assert r["claims_with_positive"] == 1 and r["claims_without_positive"] == 1
    assert r["hit@1"] == 0 and r["hit@3"] == 1
    assert r["ndcg@3"] == pytest.approx(1 / np.log2(3))


def test_calibration_of_perfectly_calibrated_scores():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 20000)
    y = (rng.uniform(size=p.size) < p).astype(int)
    ci = calibration_slope_intercept(y, p)
    assert ci["slope"] == pytest.approx(1, abs=0.1) and ci["intercept"] == pytest.approx(0, abs=0.1)


def test_threshold():
    assert best_f1_threshold([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.35)


def test_two_way_weights():
    rng = np.random.default_rng(0)
    w = resample_weights(["a", "a", "b"], ["x", "y", "x"], "two_way", rng)
    assert w.shape == (3,) and (w >= 0).all()
    with pytest.raises(ValueError):
        resample_weights(["a"], ["x"], "pairs", rng)


def test_paired_bootstrap_reproducible_and_counts_degenerate():
    rng = np.random.default_rng(1)
    n = 200
    y = rng.integers(0, 2, n)
    s1 = y + rng.normal(0, 0.5, n)
    s2 = rng.normal(0, 1, n)
    claims = [f"c{i // 4}" for i in range(n)]
    pubs = [f"p{i % 10}" for i in range(n)]
    args = (y, {"a": s1, "b": s2}, claims, pubs, auprc, [("a", "b")])
    r1 = paired_bootstrap(*args, scheme="two_way", n=100, seed=3)
    r2 = paired_bootstrap(*args, scheme="two_way", n=100, seed=3)
    assert r1 == r2
    d = r1["differences"]["a - b"]
    assert d["lo"] <= d["point"] <= d["hi"]
    tiny = paired_bootstrap([1, 0], {"a": [0.9, 0.1], "b": [0.5, 0.5]}, ["c", "d"], ["p", "q"], auprc,
                            [("a", "b")], n=50, seed=0)
    assert tiny["n_degenerate"] > 0


@pytest.mark.parametrize("diff,delta,expected", [
    ({"point": 0.1, "lo": 0.02, "hi": 0.2}, 0.05, "SUPPORTED"),
    ({"point": 0.01, "lo": -0.01, "hi": 0.03}, 0.05, "UNSUPPORTED"),
    ({"point": 0.04, "lo": -0.02, "hi": 0.1}, 0.05, "INCONCLUSIVE"),
    ({"point": -0.1, "lo": -0.2, "hi": -0.01}, 0.05, "HARMFUL"),
])
def test_outcome_classes(diff, delta, expected):
    assert classify_outcome(diff, delta, 0.0) == expected


def test_outcome_needs_delta_and_enough_resamples():
    d = {"point": 0.1, "lo": 0.02, "hi": 0.2}
    assert classify_outcome(d, None, 0.0).startswith("NOT_CLASSIFIABLE")
    assert classify_outcome(d, 0.05, 0.2).startswith("INCONCLUSIVE")
