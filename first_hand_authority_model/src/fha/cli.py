"""Command-line interface.

    python -m fha.cli status   [--config C] [--data-manifest M]
    python -m fha.cli validate --data pairs.jsonl [--labels]
    python -m fha.cli smoke    [--out outputs/synthetic_smoke]
    python -m fha.cli train    --config C --data D --data-manifest M --out DIR [--open-test]
    python -m fha.cli predict  --model DIR/model --input pairs.jsonl [--output out.jsonl] [--rank]
    python -m fha.cli package  --run DIR --dest models/<version>

Run with PYTHONPATH=src from the project root.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .pipeline import (SYNTHETIC_BANNER, BlockedError, load_bundle, load_json, predict, rank_candidates,
                       real_mode_blockers, run)
from .schema import PROJECT_ROOT, FeatureSchema, LabelSchema, ValidationError, file_sha256, read_jsonl, \
    validate_record, write_jsonl


def cmd_status(a) -> int:
    config = load_json(a.config)
    manifest = load_json(a.data_manifest) if a.data_manifest else None
    blockers = real_mode_blockers(config, None, manifest)
    if blockers:
        print("REAL TRAINING BLOCKED:")
        for b in blockers:
            print(" -", b)
        return 2
    print("No configuration blockers found (records are checked again at train time).")
    return 0


def cmd_validate(a) -> int:
    schema, ls = FeatureSchema(), LabelSchema()
    n_err = 0
    for r in read_jsonl(a.data):
        try:
            for w in validate_record(r, schema, require_label=a.labels, label_schema=ls):
                print("WARN", r.get("pair_id"), w)
        except ValidationError as e:
            n_err += 1
            print("ERROR", e)
    print(f"{n_err} invalid record(s)")
    return 1 if n_err else 0


def cmd_smoke(a) -> int:
    from .synthetic import generate
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = out / "synthetic_pairs.jsonl"
    write_jsonl(data, generate(seed=a.seed))
    lock = out / "TEST_OPENED.lock"
    if lock.exists():
        lock.unlink()  # synthetic runs may be repeated; real runs may not
    report = run(load_json(PROJECT_ROOT / "config" / "synthetic_smoke.json"), read_jsonl(data), out,
                 open_test=True, data_sha256=file_sha256(data))
    print(SYNTHETIC_BANNER)
    print(f"report: {out / 'report.md'}")
    print("primary outcome (synthetic, meaningless):", report["test"]["test_unseen"].get("primary", {}).get("outcome"))
    return 0


def cmd_train(a) -> int:
    config = load_json(a.config)
    manifest = load_json(a.data_manifest) if a.data_manifest else None
    try:
        run(config, read_jsonl(a.data), Path(a.out), open_test=a.open_test, data_manifest=manifest,
            data_sha256=file_sha256(a.data))
    except BlockedError as e:
        print(e)
        return 2
    print(f"done: {a.out}")
    return 0


def cmd_predict(a) -> int:
    bundle = load_bundle(Path(a.model))
    if bundle["is_synthetic"]:
        print("WARNING: this model was trained on SYNTHETIC fixtures; its scores mean nothing.", file=sys.stderr)
    preds = predict(bundle, read_jsonl(a.input), a.model_name)
    result = rank_candidates(preds) if a.rank else preds
    text = json.dumps(result, indent=2)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_package(a) -> int:
    run_dir = Path(a.run)
    bundle = load_bundle(run_dir / "model")
    report = load_json(run_dir / "report.json")
    problems = []
    if bundle["is_synthetic"] or report["mode"] != "real":
        problems.append("run is synthetic; only an authorised real-mode run can be packaged")
    if not report.get("test"):
        problems.append("test partition was not evaluated")
    if not (PROJECT_ROOT / "docs" / "MODEL_CARD.md").exists():
        problems.append("docs/MODEL_CARD.md missing")
    if problems:
        print("PACKAGING BLOCKED:")
        for p in problems:
            print(" -", p)
        return 2
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=False)
    for name in ("model", "report.json", "report.md", "MANIFEST.json"):
        src = run_dir / name
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dest / name)
    for rel in ("schemas", "docs/MODEL_CARD.md", "README.md", "requirements.txt"):
        src = PROJECT_ROOT / rel
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dest / Path(rel).name)
    print(f"packaged to {dest}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fha", description="First-hand authority prediction (claim-publisher pairs)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status"); s.add_argument("--config", default=str(PROJECT_ROOT / "config" / "config.template.json"))
    s.add_argument("--data-manifest"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("validate"); s.add_argument("--data", required=True); s.add_argument("--labels", action="store_true")
    s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("smoke"); s.add_argument("--out", default=str(PROJECT_ROOT / "outputs" / "synthetic_smoke"))
    s.add_argument("--seed", type=int, default=0); s.set_defaults(fn=cmd_smoke)
    s = sub.add_parser("train"); s.add_argument("--config", required=True); s.add_argument("--data", required=True)
    s.add_argument("--data-manifest"); s.add_argument("--out", required=True); s.add_argument("--open-test", action="store_true")
    s.set_defaults(fn=cmd_train)
    s = sub.add_parser("predict"); s.add_argument("--model", required=True); s.add_argument("--input", required=True)
    s.add_argument("--output"); s.add_argument("--rank", action="store_true")
    s.add_argument("--model-name", default="claim_conditioned_lr"); s.set_defaults(fn=cmd_predict)
    s = sub.add_parser("package"); s.add_argument("--run", required=True); s.add_argument("--dest", required=True)
    s.set_defaults(fn=cmd_package)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except (ValidationError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
