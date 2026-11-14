import pytest

from conftest import make_record
from fha.labels import attach_targets, to_binary
from fha.schema import (INELIGIBLE, INSUFFICIENT, LIMITED, SUFFICIENT, FeatureSchema, LabelSchema, ValidationError,
                        info_status, unavailable_features, validate_record)

S = FeatureSchema()


def test_valid_record_passes_with_provisional_topic_warning():
    warnings = validate_record(make_record(), S)
    assert any("claim_topic" in w for w in warnings)  # taxonomy not frozen yet


def test_missing_feature_is_an_error_not_silently_filled():
    r = make_record()
    del r["features"]["remit_match"]
    with pytest.raises(ValidationError, match="missing feature"):
        validate_record(r, S)


@pytest.mark.parametrize("value", ["BANANA", "same", 3, None])
def test_bad_values_rejected(value):
    with pytest.raises(ValidationError):
        validate_record(make_record(features={"jurisdiction_match": value}), S)


def test_unknown_feature_rejected():
    r = make_record()
    r["features"]["mystery"] = "X"
    with pytest.raises(ValidationError, match="unknown feature"):
        validate_record(r, S)


@pytest.mark.parametrize("key", ["verdict", "gold_evidence", "retrieval_rank", "popularity", "domain_suffix"])
def test_prohibited_inputs_rejected_top_level_and_in_features(key):
    r = make_record()
    r[key] = "x"
    with pytest.raises(ValidationError, match="prohibited"):
        validate_record(r, S)
    r = make_record()
    r["features"][key] = "x"
    with pytest.raises(ValidationError, match="prohibited"):
        validate_record(r, S)


@pytest.mark.parametrize("bad", [None, [], "rec"])
def test_malformed_records(bad):
    with pytest.raises(ValidationError):
        validate_record(bad, S)


def test_missing_ids():
    with pytest.raises(ValidationError, match="pair_id"):
        validate_record(make_record(pair_id=""), S)


def test_label_requirements():
    ls = LabelSchema()
    r = make_record(label={"final": "FIRST_HAND_AUTHORITY"})
    with pytest.raises(ValidationError, match="basis"):
        validate_record(r, S, require_label=True, label_schema=ls)
    r = make_record(label={"final": "MAYBE"})
    with pytest.raises(ValidationError):
        validate_record(r, S, require_label=True, label_schema=ls)
    with pytest.raises(ValidationError, match="need a 'label'"):
        validate_record(make_record(), S, require_label=True, label_schema=ls)


def test_status_levels():
    assert info_status(make_record(), S)[0] == SUFFICIENT
    assert info_status(make_record(features={"active_at_claim_date": "NO"}), S)[0] == INELIGIBLE
    assert info_status(make_record(publisher_resolved=False), S)[0] == INSUFFICIENT
    assert info_status(make_record(features={"publisher_type": "NOT_COMPUTED"}), S)[0] == INSUFFICIENT
    limited = make_record(features={k: "UNKNOWN" for k in S.relation_features})
    assert info_status(limited, S)[0] == LIMITED
    partial = make_record(features={"remit_match": "NOT_COMPUTED"})
    status, reasons = info_status(partial, S)
    assert status == SUFFICIENT and "remit_match" in reasons[0]
    assert unavailable_features(partial) == ["remit_match"]


APPROVED = ["INSTITUTIONAL_ACT", "OFFICIAL_RECORD"]


@pytest.mark.parametrize("label,policy,expected", [
    ({"final": "FIRST_HAND_AUTHORITY", "basis": "OFFICIAL_RECORD"}, "exclude", 1),
    ({"final": "FIRST_HAND_AUTHORITY", "basis": "DIRECT_OBSERVATION"}, "exclude", None),
    ({"final": "NOT_FIRST_HAND_AUTHORITY"}, "exclude", 0),
    ({"final": "CANNOT_JUDGE"}, "exclude", None),
    ({"final": None}, "exclude", None),
    ({"final": "CANNOT_JUDGE"}, "as_negative", 0),
    ({"final": None}, "as_positive", 1),
    ({"final": "NOT_FIRST_HAND_AUTHORITY", "flags": ["INTERESTED_PARTY"]}, "exclude", 0),
])
def test_to_binary(label, policy, expected):
    assert to_binary(label, APPROVED, policy)[0] == expected


def test_bad_policy():
    with pytest.raises(ValueError):
        to_binary({"final": "CANNOT_JUDGE"}, APPROVED, "drop")


def test_attach_targets_counts(records):
    counts = attach_targets(records, APPROVED + ["ORIGINAL_RESEARCH"])
    assert sum(counts.values()) == len(records)
    assert all(r["y"] in (0, 1, None) for r in records)
