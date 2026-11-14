"""End-to-end training, evaluation, serialisation and prediction.

Two modes:
- synthetic_smoke: generated fixtures, placeholder decisions; outputs are
  stamped SYNTHETIC and are never research results.
- real: refuses to start unless every decision is approved, the rule table
  is approved, the data manifest authorises the data, and no record is
  synthetic. The test partition is evaluated once; a lock file records it.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import platform
from pathlib import Path

import numpy as np

from . import __version__
from .bootstrap import classify_outcome, paired_bootstrap
from .calibration import PlattCalibrator, needs_recalibration
from .labels import attach_targets
from .metrics import (auprc, auroc, best_f1_threshold, brier, by_category, calibration_slope_intercept, log_loss,
                      ranking_metrics, reliability_table, within_publisher_auroc, within_publisher_ci)
from .models import LogisticModel, RoleRuleModel, TypePriorModel, feature_set, load_rules, model_from_dict
from .schema import (LIMITED, PROJECT_ROOT, SUFFICIENT, FeatureSchema, LabelSchema,
                     ValidationError, file_sha256, info_status, unavailable_features, validate_record)
from .split import canonicalise, inner_folds, split_pairs

SYNTHETIC_BANNER = ("SYNTHETIC SMOKE TEST - generated fixtures with a planted label rule and placeholder "
                    "decisions. These numbers show only that the code runs. They are NOT research results.")
MODEL_ORDER = ["role_rules", "type_prior", "publisher_only_lr", "claim_conditioned_lr"]
LR_MODELS = ["publisher_only_lr", "claim_conditioned_lr"]
DISCLAIMER = ("p_first_hand estimates first-hand standing of the publisher for this claim. It is not the "
              "probability that the claim is true, that any page supports it, or that the publisher is reliable.")


class BlockedError(RuntimeError):
    """Raised when a real-mode step is blocked by an unresolved decision, data or permission."""


# ----------------------------------------------------------------- config & guards
def load_json(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve(path: str | None) -> Path | None:
    if path is None:
        return None
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def real_mode_blockers(config: dict, records: list[dict] | None = None, data_manifest: dict | None = None) -> list[str]:
    """Everything that must be true before a real training run may start."""
    blockers = []
    for k, v in config["decisions"].items():
        if v is None:
            blockers.append(f"decision '{k}' is unresolved (null)")
        elif v == "PLACEHOLDER":
            blockers.append(f"decision '{k}' holds a synthetic placeholder")
    rules_path = _resolve(config["paths"]["role_rules"])
    if rules_path is None or not rules_path.exists():
        blockers.append("role-rule table not found")
    elif load_rules(rules_path)["status"] != "APPROVED":
        blockers.append("role-rule table is not APPROVED (must be frozen before labels are seen)")
    if data_manifest is None:
        blockers.append("no data manifest supplied (dataset construction is DEFERRED until authorised)")
    else:
        if data_manifest.get("authorised") is not True:
            blockers.append("data manifest does not record authorisation ('authorised': true)")
        if data_manifest.get("is_synthetic") is not False:
            blockers.append("data manifest must state 'is_synthetic': false")
        for key in ("provenance", "usage_rights", "label_source", "guideline_version"):
            if not data_manifest.get(key):
                blockers.append(f"data manifest missing '{key}'")
        if str(data_manifest.get("label_source", "")).lower() in ("ai", "llm", "model"):
            blockers.append("labels must be human; AI-generated labels are not ground truth")
    if records is not None and any(r.get("is_synthetic", True) for r in records):
        blockers.append("records are synthetic or lack 'is_synthetic': false")
    return blockers


def available_feature_names(config: dict, schema: FeatureSchema) -> list[str]:
    av = config["decisions"].get("available_features")
    if av in (None, "ALL_SCHEMA_FEATURES"):
        return schema.names
    unknown = set(av) - set(schema.names)
    if unknown:
        raise ValidationError(f"available_features lists unknown features {sorted(unknown)}")
    return [n for n in schema.names if n in av]


# ----------------------------------------------------------------- preparation
def prepare(records: list[dict], config: dict, schema: FeatureSchema) -> dict:
    ls = LabelSchema()
    warnings = {}
    for r in records:
        w = validate_record(r, schema, require_label=True, label_schema=ls)
        if w:
            warnings[r["pair_id"]] = w
    if len({r["pair_id"] for r in records}) != len(records):
        raise ValidationError("duplicate pair_id values")
    alias_path = _resolve(config["paths"].get("alias_map"))
    canonicalise(records, load_json(alias_path) if alias_path else None)
    d = config["decisions"]
    target_counts = attach_targets(records, d["positive_bases"], d["cannot_judge_policy"])
    status_counts = {}
    for r in records:
        r["info_status"], r["status_reasons"] = info_status(r, schema)
        status_counts[r["info_status"]] = status_counts.get(r["info_status"], 0) + 1
    scorable = {SUFFICIENT, LIMITED} if d["score_limited_pairs"] else {SUFFICIENT}
    usable = [r for r in records if r["y"] is not None and r["info_status"] in scorable]
    missing = {n: sum(r["features"][n] in ("UNKNOWN", "NOT_COMPUTED") for r in records) / len(records)
               for n in schema.names}
    return {"usable": usable, "target_counts": target_counts, "status_counts": status_counts,
            "feature_missing_share": missing, "n_records": len(records), "n_validation_warnings": len(warnings),
            "validation_warning_examples": dict(list(warnings.items())[:5])}


def _weights(records: list[dict], per_claim: bool):
    if not per_claim:
        return None
    counts = {}
    for r in records:
        counts[r["claim_id"]] = counts.get(r["claim_id"], 0) + 1
    return np.array([1.0 / counts[r["claim_id"]] for r in records])


# ----------------------------------------------------------------- tuning & fitting
def tune_lr(name: str, train: list[dict], config: dict, schema: FeatureSchema, feats_avail: list[str]) -> dict:
    """Grid search over C and min_count by log loss on grouped, publisher-disjoint inner folds.
    Ties go to the simpler setting (smaller C, larger min_count)."""
    feats, inter = feature_set(name, schema)
    feats = [f for f in feats if f in feats_avail]
    inter = [i for i in inter if i[0] in feats and i[1] in feats]
    mc = config["model"]
    folds = list(inner_folds(train, config["split"], mc["inner_folds"]))
    results = []
    for C in mc["C_grid"]:
        for m in mc["min_count_grid"]:
            losses = []
            for tr, va in folds:
                ytr = [r["y"] for r in tr]
                yva = [r["y"] for r in va]
                if len(set(ytr)) < 2 or not va:
                    continue
                model = LogisticModel(name, feats, inter, C, m, mc["class_weight"])
                model.fit(tr, ytr, _weights(tr, config["decisions"]["per_claim_weighting"]))
                losses.append(log_loss(yva, model.predict_proba(va)))
            if losses:
                results.append({"C": C, "min_count": m, "mean_log_loss": float(np.mean(losses)), "folds": len(losses)})
    if not results:
        raise ValueError(f"{name}: no usable inner folds for tuning")
    best = min(results, key=lambda r: (round(r["mean_log_loss"], 6), r["C"], -r["min_count"]))
    return {"features": feats, "interactions": [list(i) for i in inter], "grid": results, "best": best}


def fit_all(train: list[dict], val: list[dict], config: dict, schema: FeatureSchema) -> tuple[dict, dict]:
    feats_avail = available_feature_names(config, schema)
    ytr = [r["y"] for r in train]
    w = _weights(train, config["decisions"]["per_claim_weighting"])
    models, info = {}, {"tuning": {}, "calibration": {}}
    models["role_rules"] = RoleRuleModel(load_rules(_resolve(config["paths"]["role_rules"])))
    models["type_prior"] = TypePriorModel(alpha=config["model"]["type_prior_alpha"]).fit(train, ytr)
    for name in LR_MODELS:
        t = tune_lr(name, train, config, schema, feats_avail)
        info["tuning"][name] = t
        models[name] = LogisticModel(name, t["features"], [tuple(i) for i in t["interactions"]], t["best"]["C"],
                                     t["best"]["min_count"], config["model"]["class_weight"]).fit(train, ytr, w)
    calibrators = {}
    yva = [r["y"] for r in val]
    for name in ("type_prior",) + tuple(LR_MODELS):
        p = models[name].predict_proba(val)
        method = config["model"]["calibration"]
        cal = None
        if method == "platt":
            cal = PlattCalibrator().fit(p, yva)
            info["calibration"][name] = {"applied": True, "reason": "configured"}
        elif method == "platt_if_outside_acceptable":
            need, si = needs_recalibration(yva, p, config["decisions"]["calibration_acceptable"])
            if need:
                cal = PlattCalibrator().fit(p, yva)
            info["calibration"][name] = {"applied": need, "validation_slope_intercept": si}
        else:
            info["calibration"][name] = {"applied": False, "reason": "disabled"}
        calibrators[name] = cal
    return {"models": models, "calibrators": calibrators}, info


def scores_for(bundle: dict, records: list[dict]) -> dict:
    out = {}
    for name in MODEL_ORDER:
        p = bundle["models"][name].predict_proba(records)
        cal = bundle["calibrators"].get(name)
        out[name] = cal.transform(p) if cal is not None else p
    return out


# ----------------------------------------------------------------- evaluation
def evaluate_set(records: list[dict], scores: dict, config: dict, thresholds: dict | None = None,
                 bootstrap: bool = False) -> dict:
    y = np.array([r["y"] for r in records])
    claims = [r["claim_id"] for r in records]
    pubs = [r["publisher_id"] for r in records]
    pairs = [r["pair_id"] for r in records]
    ev = config["evaluation"]
    res = {"n_pairs": len(records), "n_claims": len(set(claims)), "n_publishers": len(set(pubs)),
           "positives": int(y.sum()) if len(y) else 0, "prevalence": float(y.mean()) if len(y) else None,
           "models": {}}
    for name, s in scores.items():
        wp = within_publisher_auroc(pubs, y, s)
        m = {"auprc": auprc(y, s), "auroc": auroc(y, s), "brier": brier(y, s), "log_loss": log_loss(y, s),
             "calibration": calibration_slope_intercept(y, s), "reliability": reliability_table(y, s),
             "ranking": ranking_metrics(claims, pairs, y, s, ev["ranking_k"]),
             "within_publisher_auroc": {"mean": wp["mean"], "n_publishers": wp["n_publishers"],
                                        **{k: v for k, v in within_publisher_ci(
                                            wp["per_publisher"], ev["bootstrap_n"], ev["bootstrap_seed"]).items()
                                           if k != "n_publishers"}},
             "by_publisher_type": by_category([r["features"]["publisher_type"] for r in records], y, s),
             "by_action_type": by_category([r["features"]["action_type"] for r in records], y, s)}
        if name == "role_rules":
            m["note"] = "tier score (0, 1/3, 2/3, 1); not a probability, so calibration metrics are not meaningful"
        res["models"][name] = m
    if bootstrap:
        a, b = ev["primary_comparison"]
        comps = [(a, b)] + [tuple(c) for c in ev["secondary_comparisons"]]
        res["bootstrap"] = {sch: paired_bootstrap(y, scores, claims, pubs, auprc, comps, sch,
                                                  ev["bootstrap_n"], ev["bootstrap_seed"])
                            for sch in ev["bootstrap_schemes"]}
        prim = res["bootstrap"]["two_way"]
        res["primary"] = {"metric": "auprc", "comparison": f"{a} - {b}",
                          "difference": prim["differences"][f"{a} - {b}"],
                          "degenerate_share": prim["n_degenerate"] / prim["n_resamples"]}
        res["primary"]["outcome"] = classify_outcome(res["primary"]["difference"],
                                                     config["decisions"]["delta_min_auprc"],
                                                     res["primary"]["degenerate_share"], ev["max_degenerate_share"])
    if thresholds:
        res["errors"] = error_analysis(records, scores, thresholds)
    return res


def error_analysis(records: list[dict], scores: dict, thresholds: dict, top: int = 15) -> dict:
    out = {}
    for name in LR_MODELS:
        t = thresholds[name]
        rows = []
        for r, s in zip(records, scores[name]):
            pred = int(s >= t)
            if pred != r["y"]:
                rows.append({"pair_id": r["pair_id"], "y": r["y"], "score": round(float(s), 4),
                             "type": "false_positive" if pred else "false_negative",
                             "publisher_type": r["features"]["publisher_type"],
                             "action_type": r["features"]["action_type"], "info_status": r["info_status"],
                             "flags": r["label"].get("flags", [])})
        by = {}
        for key in ("publisher_type", "action_type", "info_status"):
            tot, err = {}, {}
            for r, s in zip(records, scores[name]):
                v = r["features"][key] if key != "info_status" else r["info_status"]
                tot[v] = tot.get(v, 0) + 1
                err[v] = err.get(v, 0) + int(int(s >= t) != r["y"])
            by[key] = {v: {"n": tot[v], "error_rate": err[v] / tot[v]} for v in sorted(tot)}
        rows.sort(key=lambda e: -abs(e["score"] - t))
        out[name] = {"threshold_from_validation": t, "n_errors": len(rows), "by": by, "most_confident_errors": rows[:top]}
    return out


def shuffled_pairing_control(records: list[dict], bundle: dict, schema: FeatureSchema, seed: int) -> dict:
    """Permute the claim-side and relation features across pairs (labels stay with
    publishers). If claim information is genuinely used, the claim-conditioned
    model's advantage over the publisher-only model should largely disappear."""
    rng = np.random.default_rng(seed)
    cols = schema.names_in("claim", "interaction")
    perm = rng.permutation(len(records))
    shuffled = []
    for i, r in enumerate(records):
        src = records[perm[i]]
        f = dict(r["features"])
        f.update({c: src["features"][c] for c in cols})
        shuffled.append(dict(r, features=f))
    y = [r["y"] for r in records]
    s_cc = bundle["models"]["claim_conditioned_lr"].predict_proba(shuffled)
    s_po = bundle["models"]["publisher_only_lr"].predict_proba(records)
    return {"claim_conditioned_auprc_shuffled": auprc(y, s_cc), "publisher_only_auprc": auprc(y, s_po),
            "claim_conditioned_auprc_unshuffled": auprc(y, bundle["models"]["claim_conditioned_lr"].predict_proba(records))}


# ----------------------------------------------------------------- run
def run(config: dict, records: list[dict], out_dir: Path, open_test: bool = False,
        data_manifest: dict | None = None, data_sha256: str | None = None) -> dict:
    schema = FeatureSchema()
    mode = config["mode"]
    if mode == "real":
        blockers = real_mode_blockers(config, records, data_manifest)
        if blockers:
            raise BlockedError("real-mode run blocked:\n- " + "\n- ".join(blockers))
    elif mode != "synthetic_smoke":
        raise ValueError("config mode must be 'real' or 'synthetic_smoke'")
    elif not all(r.get("is_synthetic") is True for r in records):
        raise BlockedError("synthetic_smoke mode only accepts records marked is_synthetic=true")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = out_dir / "TEST_OPENED.lock"
    if open_test and lock.exists():
        raise BlockedError(f"test partition already opened ({lock}); re-running would make results exploratory")

    prep = prepare(records, config, schema)
    sp = split_pairs(prep["usable"], config["split"])
    train, val = sp["train"], sp["val_unseen"]
    for part in ("train", "val_unseen"):
        if len({r["y"] for r in sp[part]}) < 2:
            raise ValueError(f"split '{part}' lacks one class; cannot train or validate")
    diag = sp["diagnostics"]
    if diag["overlap_units_train_test_unseen"] or diag["overlap_units_train_val_unseen"]:
        raise RuntimeError("publisher overlap between training and held-out sets; split is invalid")

    bundle, fit_info = fit_all(train, val, config, schema)
    val_scores = scores_for(bundle, val)
    thresholds = {n: best_f1_threshold([r["y"] for r in val], val_scores[n]) for n in LR_MODELS}
    bundle["thresholds"] = thresholds

    report = {
        "banner": SYNTHETIC_BANNER if mode == "synthetic_smoke" else None,
        "mode": mode, "package_version": __version__,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "data": {k: prep[k] for k in ("n_records", "target_counts", "status_counts", "feature_missing_share",
                                       "n_validation_warnings")} | {"n_usable": len(prep["usable"]),
                                                                     "data_sha256": data_sha256},
        "split_diagnostics": diag, "fit": fit_info,
        "validation": evaluate_set(val, val_scores, config, thresholds),
        "shuffled_pairing_control_validation": shuffled_pairing_control(val, bundle, schema, config["split"]["seed"]),
        "test": None,
    }
    if open_test:
        lock.write_text(report["created_utc"] + "\n", encoding="utf-8")
        report["test"] = {}
        for part in ("test_unseen", "test_seen"):
            recs = sp[part]
            if recs and len({r["y"] for r in recs}) == 2:
                report["test"][part] = evaluate_set(recs, scores_for(bundle, recs), config, thresholds,
                                                    bootstrap=(part == "test_unseen"))
            else:
                report["test"][part] = {"n_pairs": len(recs), "note": "empty or single-class; not evaluated"}

    save_bundle(bundle, out_dir / "model", config, mode, data_sha256)
    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=_json_default)
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    write_manifest(out_dir, config, mode)
    return report


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


# ----------------------------------------------------------------- persistence
def save_bundle(bundle: dict, model_dir: Path, config: dict, mode: str, data_sha256: str | None) -> None:
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "package_version": __version__, "mode": mode, "is_synthetic": mode != "real",
        "feature_schema_sha256": FeatureSchema().sha256(), "label_schema_sha256": LabelSchema().sha256(),
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "data_sha256": data_sha256, "score_limited_pairs": config["decisions"]["score_limited_pairs"],
        "models": {n: m.to_dict() for n, m in bundle["models"].items()},
        "calibrators": {n: (c.to_dict() if c else None) for n, c in bundle["calibrators"].items()},
        "thresholds": bundle.get("thresholds", {}),
    }
    path = model_dir / "bundle.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
    (model_dir / "bundle.sha256").write_text(file_sha256(path) + "\n", encoding="utf-8")


def load_bundle(model_dir: Path) -> dict:
    model_dir = Path(model_dir)
    path = model_dir / "bundle.json"
    expected = (model_dir / "bundle.sha256").read_text(encoding="utf-8").strip()
    if file_sha256(path) != expected:
        raise ValueError("bundle.json checksum mismatch; refusing to load")
    payload = load_json(path)
    if payload["feature_schema_sha256"] != FeatureSchema().sha256():
        raise ValueError("feature schema changed since this model was trained; refusing to load")
    payload["models"] = {n: model_from_dict(d) for n, d in payload["models"].items()}
    payload["calibrators"] = {n: PlattCalibrator.from_dict(d) for n, d in payload["calibrators"].items()}
    return payload


def write_manifest(out_dir: Path, config: dict, mode: str) -> None:
    files = sorted(p for p in Path(out_dir).rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    manifest = {
        "package_version": __version__, "mode": mode, "is_synthetic": mode != "real",
        "python": platform.python_version(), "platform": platform.platform(),
        "libraries": _library_versions(),
        "feature_schema_version": FeatureSchema().version,
        "files": {str(p.relative_to(out_dir)).replace("\\", "/"): file_sha256(p) for p in files},
    }
    with open(Path(out_dir) / "MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _library_versions() -> dict:
    import scipy
    import sklearn
    return {"numpy": np.__version__, "scipy": scipy.__version__, "scikit-learn": sklearn.__version__}


# ----------------------------------------------------------------- prediction
def predict(bundle: dict, records: list[dict], model_name: str = "claim_conditioned_lr") -> list[dict]:
    """Score claim-publisher pairs. Unscorable pairs get p_first_hand = None."""
    schema = FeatureSchema()
    model = bundle["models"][model_name]
    cal = bundle["calibrators"].get(model_name)
    out = []
    for r in records:
        warnings = validate_record(r, schema)
        status, reasons = info_status(r, schema)
        row = {"pair_id": r["pair_id"], "claim_id": r["claim_id"], "publisher_id": r["publisher_id"],
               "info_status": status, "status_reasons": reasons, "unavailable_features": unavailable_features(r),
               "p_first_hand": None, "score_basis": None, "top_contributions": [], "warnings": list(warnings),
               "model": model_name, "is_synthetic_model": bundle["is_synthetic"], "disclaimer": DISCLAIMER}
        scorable = status == SUFFICIENT or (status == LIMITED and bundle["score_limited_pairs"])
        if scorable:
            enc_notes: list[list[str]] = []
            p = model.predict_proba([r], enc_notes)
            if cal is not None:
                p = cal.transform(p)
            row["p_first_hand"] = round(float(p[0]), 6)
            row["score_basis"] = "claim_and_publisher_features" if status == SUFFICIENT else \
                "publisher_type_prior_only (LIMITED: relation features missing)"
            row["warnings"] += enc_notes[0]
            if hasattr(model, "contributions"):
                row["top_contributions"] = model.contributions(r)
        else:
            row["score_basis"] = "not scored: " + "; ".join(reasons)
        out.append(row)
    return out


def rank_candidates(predictions: list[dict]) -> dict:
    """Group by claim; scored pairs sorted by p_first_hand (ties keep pair_id order)."""
    by = {}
    for p in predictions:
        by.setdefault(p["claim_id"], {"scored": [], "not_scored": []})
        (by[p["claim_id"]]["scored"] if p["p_first_hand"] is not None else by[p["claim_id"]]["not_scored"]).append(p)
    for v in by.values():
        v["scored"].sort(key=lambda p: (-p["p_first_hand"], p["pair_id"]))
    return by


# ----------------------------------------------------------------- report
def _f(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def render_markdown(report: dict) -> str:
    L = []
    if report["banner"]:
        L += [f"> **{report['banner']}**", ""]
    L += [f"# First-hand authority model report ({report['mode']})", "",
          f"Created {report['created_utc']}; package {report['package_version']}.", "",
          "## Data", "",
          f"- Records: {report['data']['n_records']}; usable (labelled and scorable): {report['data']['n_usable']}",
          f"- Targets: {report['data']['target_counts']}",
          f"- Information status: {report['data']['status_counts']}", ""]
    d = report["split_diagnostics"]
    L += ["## Split", "", "| Partition | Pairs | Claims | Publishers | Positives | Prevalence |", "|---|---|---|---|---|---|"]
    for k, v in d["per_split"].items():
        L.append(f"| {k} | {v['pairs']} | {v['claims']} | {v['publishers']} | {v['positives']} | {_f(v['prevalence'])} |")
    L += ["", f"- Unit overlap train/test-unseen: {len(d['overlap_units_train_test_unseen'])}; "
              f"claim-group overlap train/test: {len(d['overlap_claim_groups_train_test'])}; "
              f"discarded positives: {d['discarded_positives']}", ""]

    def table(title, ev):
        L.extend([f"## {title}", "", f"Pairs {ev['n_pairs']}, claims {ev['n_claims']}, publishers {ev['n_publishers']}, "
                  f"prevalence {_f(ev['prevalence'])}.", "",
                  "| Model | AUPRC | AUROC | Brier | Cal. slope | Cal. intercept | NDCG@3 | Within-publisher AUROC [95% CI] (n) |",
                  "|---|---|---|---|---|---|---|---|"])
        for n in MODEL_ORDER:
            m = ev["models"][n]
            w = m["within_publisher_auroc"]
            L.append(f"| {n} | {_f(m['auprc'])} | {_f(m['auroc'])} | {_f(m['brier'])} | {_f(m['calibration']['slope'], 2)} | "
                     f"{_f(m['calibration']['intercept'], 2)} | {_f(m['ranking'].get('ndcg@3'))} | "
                     f"{_f(w['mean'])} [{_f(w['lo'])}, {_f(w['hi'])}] ({w['n_publishers']}) |")
        L.append("")
        L.append("role_rules outputs tiers (0, 1/3, 2/3, 1), so its calibration columns are not meaningful.")
        if title.startswith("Validation"):
            L.append("Calibrators (where applied) were fitted on this validation set, so calibration figures here are "
                     "in-sample; pre-calibration values are in report.json under fit.calibration.")
        L.append("")
        if "primary" in ev:
            p = ev["primary"]
            diff = p["difference"]
            L.extend([f"**Primary ({p['metric']}, {p['comparison']}, two-way bootstrap):** "
                      f"{_f(diff['point'])} [{_f(diff['lo'])}, {_f(diff['hi'])}]; degenerate share {_f(p['degenerate_share'])}. "
                      f"Outcome: **{p['outcome']}**", ""])
    table("Validation (unseen publishers)", report["validation"])
    c = report["shuffled_pairing_control_validation"]
    L += [f"Shuffled-pairing control (validation): claim-conditioned AUPRC {_f(c['claim_conditioned_auprc_unshuffled'])} "
          f"-> {_f(c['claim_conditioned_auprc_shuffled'])} when claim-side features are shuffled; "
          f"publisher-only {_f(c['publisher_only_auprc'])}.", ""]
    if report["test"]:
        for part, ev in report["test"].items():
            if "models" in ev:
                table(f"Test: {part}", ev)
            else:
                L += [f"## Test: {part}", "", ev["note"], ""]
    else:
        L += ["## Test", "", "Test partition not opened in this run.", ""]
    return "\n".join(L)
