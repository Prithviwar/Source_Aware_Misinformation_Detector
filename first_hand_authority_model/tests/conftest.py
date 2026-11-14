import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fha.pipeline import load_json  # noqa: E402
from fha.synthetic import generate  # noqa: E402


@pytest.fixture(scope="session")
def synthetic_records():
    return generate(n_claims=160, seed=1)


@pytest.fixture
def records(synthetic_records):
    return copy.deepcopy(synthetic_records)


@pytest.fixture
def smoke_config():
    return load_json(ROOT / "config" / "synthetic_smoke.json")


@pytest.fixture
def template_config():
    return load_json(ROOT / "config" / "config.template.json")


def make_record(**overrides):
    """A single valid, synthetic inference record (no label)."""
    feats = {
        "action_type": "OFFICIAL_STATISTIC", "claim_scope": "NATIONAL", "claim_topic": "LABOUR_ECONOMY",
        "publisher_type": "STATISTICS_OFFICE", "publisher_jurisdiction_level": "NATIONAL",
        "actor_relation": "NONE", "speaker_relation": "NONE", "jurisdiction_match": "SAME",
        "remit_match": "YES", "active_at_claim_date": "YES",
    }
    feats.update(overrides.pop("features", {}))
    rec = {"pair_id": "C1::p1", "claim_id": "C1", "publisher_id": "p1", "publisher_resolved": True,
           "features": feats, "is_synthetic": True}
    rec.update(overrides)
    return rec
