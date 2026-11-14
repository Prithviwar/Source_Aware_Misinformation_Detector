import json

import pytest

from conftest import make_record
from fha import cli
from fha.pipeline import (SYNTHETIC_BANNER, BlockedError, load_bundle, predict, rank_candidates,
                          real_mode_blockers, run)
from fha.schema import ValidationError


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory, synthetic_records):
    import copy
    from fha.pipeline import load_json
    from conftest import ROOT
    cfg = load_json(ROOT / "config" / "synthetic_smoke.json")
    cfg["evaluation"]["bootstrap_n"] = 50
    out = tmp_path_factory.mktemp("smoke")
    report = run(cfg, copy.deepcopy(synthetic_records), out, open_test=True)
    return out, report


def test_smoke_report_is_stamped_synthetic(smoke_run):
    out, report = smoke_run
    assert report["banner"] == SYNTHETIC_BANNER
    assert (out / "report.md").read_text(encoding="utf-8").startswith(f"> **{SYNTHETIC_BANNER}**")
    manifest = json.loads((out / "MANIFEST.json").read_text())
    assert manifest["is_synthetic"] is True and "model/bundle.json" in manifest["files"]


def test_identical_rows_for_compared_models(smoke_run):
    _, report = smoke_run
    v = report["validation"]
    # every model is scored on the same pairs (one n_pairs per evaluated set)
    assert set(v["models"]) == {"role_rules", "type_prior", "publisher_only_lr", "claim_conditioned_lr"}
    assert report["split_diagnostics"]["overlap_units_train_test_unseen"] == []


def test_test_lock_prevents_second_opening(smoke_run, smoke_config, synthetic_records):
    import copy
    out, _ = smoke_run
    with pytest.raises(BlockedError, match="already opened"):
        run(smoke_config, copy.deepcopy(synthetic_records), out, open_test=True)


def test_bundle_reload_gives_identical_predictions(smoke_run):
    out, _ = smoke_run
    b1, b2 = load_bundle(out / "model"), load_bundle(out / "model")
    recs = [make_record(), make_record(pair_id="C1::p2", publisher_id="p2", features={"publisher_type": "NEWS"})]
    assert predict(b1, recs) == predict(b2, recs)


def test_tampered_bundle_refused(smoke_run, tmp_path):
    import shutil
    out, _ = smoke_run
    shutil.copytree(out / "model", tmp_path / "m")
    p = tmp_path / "m" / "bundle.json"
    p.write_text(p.read_text().replace('"intercept"', '"intercept" ', 1))
    with pytest.raises(ValueError, match="checksum"):
        load_bundle(tmp_path / "m")


def test_prediction_statuses(smoke_run):
    out, _ = smoke_run
    b = load_bundle(out / "model")
    recs = [
        make_record(pair_id="C1::ok"),
        make_record(pair_id="C1::lim", features={k: "UNKNOWN" for k in
                                                 ["actor_relation", "speaker_relation", "jurisdiction_match", "remit_match"]}),
        make_record(pair_id="C1::unres", publisher_resolved=False),
        make_record(pair_id="C1::gone", features={"active_at_claim_date": "NO"}),
        make_record(pair_id="C1::nc", features={"remit_match": "NOT_COMPUTED"}),
    ]
    by = {p["pair_id"]: p for p in predict(b, recs)}
    assert by["C1::ok"]["info_status"] == "SUFFICIENT" and 0 < by["C1::ok"]["p_first_hand"] < 1
    assert by["C1::lim"]["info_status"] == "LIMITED" and "type_prior_only" in by["C1::lim"]["score_basis"]
    assert by["C1::unres"]["p_first_hand"] is None and by["C1::unres"]["info_status"] == "INSUFFICIENT"
    assert by["C1::gone"]["p_first_hand"] is None and by["C1::gone"]["info_status"] == "INELIGIBLE"
    assert by["C1::nc"]["unavailable_features"] == ["remit_match"]
    assert all(p["is_synthetic_model"] for p in by.values())
    ranked = rank_candidates(list(by.values()))["C1"]
    assert [p["p_first_hand"] for p in ranked["scored"]] == sorted((p["p_first_hand"] for p in ranked["scored"]), reverse=True)
    assert {p["pair_id"] for p in ranked["not_scored"]} == {"C1::unres", "C1::gone"}


def test_predict_rejects_malformed_input(smoke_run):
    out, _ = smoke_run
    b = load_bundle(out / "model")
    with pytest.raises(ValidationError):
        predict(b, [make_record(features={"publisher_type": "SPACESHIP"})])


def test_real_mode_blocked_by_template(template_config, records, tmp_path):
    blockers = real_mode_blockers(template_config, records, None)
    text = "\n".join(blockers)
    assert "positive_bases" in text and "not APPROVED" in text and "data manifest" in text and "synthetic" in text
    with pytest.raises(BlockedError):
        run(template_config, records, tmp_path)


def test_real_mode_rejects_synthetic_data_even_with_decisions(smoke_config, records, tmp_path):
    cfg = dict(smoke_config, mode="real")
    manifest = {"authorised": True, "is_synthetic": False, "provenance": "x", "usage_rights": "x",
                "label_source": "human", "guideline_version": "v1"}
    blockers = real_mode_blockers(cfg, records, manifest)
    assert any("placeholder" in b for b in blockers) and any("synthetic" in b for b in blockers)


def test_ai_labels_blocked(template_config):
    blockers = real_mode_blockers(template_config, None, {"authorised": True, "is_synthetic": False,
                                                          "provenance": "x", "usage_rights": "x",
                                                          "label_source": "llm", "guideline_version": "v1"})
    assert any("human" in b for b in blockers)


def test_smoke_mode_rejects_unmarked_records(smoke_config, records, tmp_path):
    records[0]["is_synthetic"] = False
    with pytest.raises(BlockedError):
        run(smoke_config, records, tmp_path)


def test_cli_status_and_package_blocked(smoke_run, tmp_path, capsys):
    out, _ = smoke_run
    assert cli.main(["status"]) == 2
    assert "REAL TRAINING BLOCKED" in capsys.readouterr().out
    assert cli.main(["package", "--run", str(out), "--dest", str(tmp_path / "pkg")]) == 2
    assert "synthetic" in capsys.readouterr().out
    assert not (tmp_path / "pkg").exists()


def test_cli_predict(smoke_run, tmp_path):
    out, _ = smoke_run
    inp = tmp_path / "in.jsonl"
    inp.write_text(json.dumps(make_record()) + "\n")
    dest = tmp_path / "o.json"
    assert cli.main(["predict", "--model", str(out / "model"), "--input", str(inp), "--output", str(dest), "--rank"]) == 0
    assert "C1" in json.loads(dest.read_text())


def test_planted_signal_recovered_mechanics_only(smoke_run):
    """Code-correctness check: on fixtures with a planted claim-publisher rule, the
    claim-conditioned model must separate one publisher's claims, the publisher-only
    model cannot, and shuffling claim-side features must remove the advantage.
    This says nothing about real data."""
    _, report = smoke_run
    v = report["validation"]["models"]
    assert v["publisher_only_lr"]["within_publisher_auroc"]["mean"] == pytest.approx(0.5)
    assert v["claim_conditioned_lr"]["within_publisher_auroc"]["mean"] > 0.5
    c = report["shuffled_pairing_control_validation"]
    assert c["claim_conditioned_auprc_shuffled"] < c["claim_conditioned_auprc_unshuffled"]
