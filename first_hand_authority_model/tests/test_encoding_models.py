import numpy as np
import pytest

from conftest import make_record
from fha.encoding import RARE, Encoder
from fha.models import LogisticModel, RoleRuleModel, TypePriorModel, feature_set, load_rules, model_from_dict
from fha.schema import PROJECT_ROOT, FeatureSchema

S = FeatureSchema()


def _train(records):
    from fha.labels import attach_targets
    attach_targets(records, ["INSTITUTIONAL_ACT", "OFFICIAL_RECORD", "ORIGINAL_RESEARCH"])
    rs = [r for r in records if r["y"] is not None and r["features"]["publisher_type"] not in ("UNKNOWN",)]
    return rs, [r["y"] for r in rs]


def test_encoder_unknown_rare_and_unseen():
    recs = [make_record(features={"publisher_type": t}) for t in ["COURT"] * 3 + ["NEWS"] * 3 + ["NGO"]]
    enc = Encoder(["publisher_type"], min_count=2).fit(recs)
    assert enc.levels["publisher_type"] == ["COURT", "NEWS", "UNKNOWN", RARE]  # NGO pooled as rare
    notes = []
    X = enc.transform([make_record(features={"publisher_type": "JOURNAL"}),
                       make_record(features={"publisher_type": "NOT_COMPUTED"})], notes)
    assert X[0, enc.columns.index(f"publisher_type={RARE}")] == 1  # unseen -> rare, with a warning
    assert notes[0] and "unseen" in notes[0][0]
    assert X[1, enc.columns.index("publisher_type=UNKNOWN")] == 1  # NOT_COMPUTED shares the UNKNOWN column
    assert X.sum(axis=1).tolist() == [1, 1]


def test_interaction_cells_need_support_and_skip_unknown():
    recs = [make_record()] * 3 + [make_record(features={"action_type": "LEGAL_RULING"})] + \
           [make_record(features={"action_type": "UNKNOWN"})] * 3
    enc = Encoder(["action_type", "publisher_type"], [("action_type", "publisher_type")], min_count=2).fit(recs)
    assert enc.cells["action_type*publisher_type"] == ["OFFICIAL_STATISTIC|STATISTICS_OFFICE"]
    X = enc.transform([make_record(features={"action_type": "LEGAL_RULING"})])
    assert not any(X[0, i] for i, c in enumerate(enc.columns) if c.startswith("action_type*"))


def test_encoder_roundtrip():
    recs = [make_record(), make_record(features={"publisher_type": "NEWS"})]
    enc = Encoder(S.names, S.interactions, 1).fit(recs)
    enc2 = Encoder.from_dict(enc.to_dict())
    assert np.array_equal(enc.transform(recs), enc2.transform(recs))


def test_feature_sets_are_nested():
    po, po_i = feature_set("publisher_only_lr", S)
    cc, cc_i = feature_set("claim_conditioned_lr", S)
    assert set(po) < set(cc) and po_i == [] and cc_i
    assert all(S.group_of(f) == "publisher" for f in po)


def test_logistic_fit_save_load_identical(records):
    rs, y = _train(records)
    m = LogisticModel("claim_conditioned_lr", *feature_set("claim_conditioned_lr", S), C=1.0, min_count=2).fit(rs, y)
    m2 = model_from_dict(m.to_dict())
    assert np.allclose(m.predict_proba(rs), m2.predict_proba(rs))
    assert len(m.contributions(rs[0])) <= 3


def test_publisher_only_model_is_constant_per_publisher_features(records):
    rs, y = _train(records)
    m = LogisticModel("publisher_only_lr", *feature_set("publisher_only_lr", S)).fit(rs, y)
    a = make_record(features={"action_type": "LEGAL_RULING", "jurisdiction_match": "DIFFERENT"})
    b = make_record()
    assert m.predict_proba([a])[0] == pytest.approx(m.predict_proba([b])[0])


def test_single_class_training_refused(records):
    rs, _ = _train(records)
    with pytest.raises(ValueError, match="both classes"):
        LogisticModel("x", ["publisher_type"]).fit(rs[:5], [0] * 5)


def test_type_prior_smoothing_and_unseen_type():
    recs = [make_record(features={"publisher_type": "COURT"})] * 2 + [make_record(features={"publisher_type": "NEWS"})] * 2
    m = TypePriorModel(alpha=1.0).fit(recs, [1, 1, 0, 0])
    assert m.rates["COURT"] == pytest.approx((2 + 0.5) / 3)
    assert m.predict_proba([make_record(features={"publisher_type": "NGO"})])[0] == pytest.approx(0.5)


def test_role_rules_tiers():
    m = RoleRuleModel(load_rules(PROJECT_ROOT / "config" / "role_rules.draft.json"))
    assert m.tier(make_record()) == 2
    assert m.tier(make_record(features={"jurisdiction_match": "UNKNOWN"})) == 1
    assert m.tier(make_record(features={"action_type": "POLICY_DECISION", "actor_relation": "SAME_ENTITY",
                                        "publisher_type": "COMPANY"})) == 3
    assert m.tier(make_record(features={"publisher_type": "NEWS"})) == 0
