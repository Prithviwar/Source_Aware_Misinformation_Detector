"""Frozen-file hash gate (preregistration §8.2).

Every frozen file is checked against its ORIGINALLY recorded hash, in raw-byte and
CRLF->LF form; the form that matches is reported (earlier freezes recorded both).
Prefix...suffix records count as partially verified. Nothing is re-hashed to bless a
change. Also checks that no git-tracked file differs from HEAD.

  python hash_gate.py [--tag NAME]   exit 0 = pass, 2 = fail; result in the execution log
"""
import json
import sys

from v2common import ROOT, git, log_event, sha256_file, sha256_lf

PKG = ROOT / "data" / "annotations" / "heldout_primary_package"


def _recorded():
    """(path, recorded hash or (prefix, suffix), source). Machine-readable sources are parsed."""
    fz = json.loads((PKG / "ai" / "FROZEN_HASHES.json").read_text(encoding="utf-8"))["hashes"]
    pre = json.loads((PKG / "ai" / "PRE_PILOT_HASHES.json").read_text(encoding="utf-8"))["frozen_artifacts_unchanged"]
    man = json.loads((PKG / "MANIFEST.json").read_text(encoding="utf-8"))
    x1 = (ROOT / "results/authority_quality_ablation_phase2/x1_assignment.sha256").read_text().split()[0]
    vp, sp = "docs/validation_preregistration.md", "docs/source_targeted_preregistration.md"
    return [
        ("experiments/validation_heldout.py",
         "304984b62945def7ecbfeb49a7c5c4e4ff68b4d13f080e4bed9465a6235dfbc5", vp),
        ("experiments/authority_resolution.py", ("58714a83", "0e97"), vp + " (prefix…suffix)"),
        ("experiments/authority_retrieval.py", ("ac4c2e80", "9312"), vp + " (prefix…suffix)"),
        ("experiments/baseline_retrieval.py", ("2730f0b3", "bd9b"), vp + " (prefix…suffix)"),
        ("experiments/source_targeted.py",
         "6ec3172da035e815b275224742f9bf0a64482b955748c5dfaafeab85dcbba223", sp + " Addendum 1"),
        ("experiments/source_targeted_eval.py",
         "a686a075471b2fcb0ed5658a2fb372fc384d8f4f3437512e44f87fb386379e04", sp + " Addendum 1"),
        ("experiments/score_heldout_primary.py",
         "114bf0cac69cce3d43f718360852568199f5af4abb660a85cf924a4f7d046ad2", sp + " Addendum 2"),
        ("results/source_targeted/rankings_heldout.jsonl.gz",
         "9105a5da66a287de70fdc6e7e9b5135200589d58c542d61787e7ed883cb66558", sp + " Addendum 2"),
        ("data/annotations/heldout_primary_package/heldout_primary_annotation.csv",
         man["sheet_sha256_blank"], "heldout_primary_package/MANIFEST.json sheet_sha256_blank"),
        ("results/heldout/rankings_hybrid.jsonl.gz", pre["heldout/rankings_hybrid.jsonl.gz"],
         "ai/PRE_PILOT_HASHES.json frozen_artifacts_unchanged"),
        ("results/heldout/authority_raw.jsonl", pre["heldout/authority_raw.jsonl"],
         "ai/PRE_PILOT_HASHES.json frozen_artifacts_unchanged"),
        ("data/annotations/heldout_primary_package/ai/AI_EVIDENCE_PROMPT.md", fz["AI_EVIDENCE_PROMPT.md"], "ai/FROZEN_HASHES.json"),
        ("data/annotations/heldout_primary_package/ai/AI_CLAIM_PROMPT.md", fz["AI_CLAIM_PROMPT.md"], "ai/FROZEN_HASHES.json"),
        ("data/annotations/heldout_primary_package/ANNOTATION_GUIDE.md", fz["ANNOTATION_GUIDE.md"], "ai/FROZEN_HASHES.json"),
        ("experiments/ai_annotate.py", fz["ai_annotate.py"], "ai/FROZEN_HASHES.json"),
        ("experiments/score_ai_primary.py", fz["score_ai_primary.py"], "ai/FROZEN_HASHES.json"),
        ("results/authority_quality_ablation_phase2/x1_assignment.csv", x1, "x1_assignment.sha256"),
    ]


def check():
    rows, ok = [], True
    for path, rec, src in _recorded():
        p = ROOT / path
        if not p.exists():
            rows.append({"path": path, "status": "MISSING", "source": src})
            ok = False
            continue
        raw, lf = sha256_file(p), sha256_lf(p)
        if isinstance(rec, tuple):
            m = lambda h: h.startswith(rec[0]) and h.endswith(rec[1])
            status = "partial(prefix…suffix)"
            rec_s = f"{rec[0]}…{rec[1]}"
        else:
            m = lambda h: h == rec
            status = "full"
            rec_s = rec
        form = "raw" if m(raw) else "LF" if m(lf) else None
        rows.append({"path": path, "recorded": rec_s, "source": src, "raw_sha256": raw,
                     "matched_form": form, "status": status if form else "MISMATCH"})
        ok &= form is not None
    tracked = git("status", "--porcelain", "--untracked-files=no").strip()
    return {"pass": ok and not tracked, "n_files": len(rows),
            "n_full": sum(r["status"] == "full" for r in rows),
            "n_partial": sum(r["status"].startswith("partial") for r in rows),
            "git_tracked_changes": tracked.splitlines(), "git_head": git("rev-parse", "HEAD").strip(),
            "files": rows}


if __name__ == "__main__":
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "adhoc"
    res = check()
    for r in res["files"]:
        print(f"{r['status']:24} {r.get('matched_form') or '-':4} {r['path']}")
    print(f"git tracked changes: {res['git_tracked_changes'] or 'none'}; HEAD {res['git_head'][:12]}")
    print("HASH GATE", "PASS" if res["pass"] else "FAIL")
    log_event("hash_gate", tag=tag, **{k: v for k, v in res.items() if k != "files"},
              failures=[r for r in res["files"] if r["status"] in ("MISSING", "MISMATCH")])
    if "--json" in sys.argv:
        print(json.dumps(res, indent=1))
    sys.exit(0 if res["pass"] else 2)
