"""String check of the gold-blind code (preregistration §3.5): T, X, their input loader, the
prompts and (once written) the reserved-side T/X/wrapper scripts must not name a gold-informed
list or module; the T/X/input files must not name gold fields at all.

  python leak_check.py     prints the result; exit 2 on any hit
"""
import json
import sys

from v2common import V2, rel

GOLD_INFORMED = ["DOMAIN_OVERRIDES", "FACTCHECK", "OFFICIAL_MISSED_BY_GENERIC", "SECONDARY_CLASSES", "_OV",
                 "x1_assignment", "authority_bottleneck_diagnostics", "authority_diagnostic_audit",
                 "authority_quality_ablation", "source_roles", "load_targets", "oracle_primary_domains",
                 "oracle_candidates", "AI_ROLES",
                 "MODEL_GENERATED", "heldout_annotator_key"]
GOLD_FIELDS = ["gold", "fact_checking_article", "justification", "ks_type", "ks_query", "evidence_urls",
               "reserved180_gold", "SEALED", "merged_sample"]
GOLD_BLIND = ["t_resolver.py", "x_control.py", "dev_data.py", "reserved_inputs.py", "reserved_x.py"]


def code_text(p):
    """Python: the code with docstrings and comments removed (string literals in code are kept)."""
    import ast
    if p.suffix != ".py":
        return p.read_text(encoding="utf-8")
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def check():
    files = sorted(set(V2.glob("prompts/*.md")) | {V2 / f for f in GOLD_BLIND if (V2 / f).exists()})
    wrapper = [p for p in (V2 / "family_R_replication.py", V2 / "family_N_score.py") if p.exists()]
    hits = []
    for p in files + wrapper:
        text = code_text(p)
        for tok in GOLD_INFORMED + (GOLD_FIELDS if p in files else []):
            if tok in text:
                hits.append({"file": rel(p), "token": tok})
    return {"pass": not hits, "checked": [rel(p) for p in files + wrapper], "hits": hits,
            "gold_informed_tokens": GOLD_INFORMED, "gold_field_tokens": GOLD_FIELDS}


if __name__ == "__main__":
    r = check()
    print(json.dumps(r, indent=1))
    sys.exit(0 if r["pass"] else 2)
