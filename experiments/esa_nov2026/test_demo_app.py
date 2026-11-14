"""Headless end-to-end test of the Streamlit demo app (streamlit.testing AppTest; no browser, offline).

  python experiments/esa_nov2026/test_demo_app.py

Simulates the presenter: start app -> pick claim 268 -> stored mode -> Run -> checks every step renders; then the
custom-query mode on claim 268 (pre-computed live run), a failure claim (436) and the evaluation / PU tabs.
Appends results to results/esa_nov2026/demo/test_app_report.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
HERE = Path(__file__).resolve().parent
APP = HERE / "demo_app.py"
OUT = HERE.parent.parent / "results" / "esa_nov2026" / "demo" / "test_app_report.json"

from streamlit.testing.v1 import AppTest  # noqa: E402

RES = []


def rec(name, ok, detail=""):
    RES.append({"test": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {detail}" if detail else ""), flush=True)


def texts(at):
    out = []
    for kind in ("markdown", "caption", "info", "warning", "error", "subheader", "metric", "success"):
        for el in getattr(at, kind, []):
            v = getattr(el, "value", None)
            lab = getattr(el, "label", None)
            out.append(f"{lab or ''} {v if v is not None else ''}")
    return "\n".join(out)


def main():
    t0 = time.time()
    at = AppTest.from_file(str(APP), default_timeout=900)
    at.run()
    rec("app starts without exception", not at.exception, f"{time.time() - t0:.0f}s; exceptions={len(at.exception)}")
    rec("knowledge-store stats shown in sidebar", "Knowledge store loaded" in texts(at))

    # ---- claim 268, stored mode
    at.sidebar.radio[0].set_value("Suggested demo claims")
    at.sidebar.selectbox[0].set_value(268)
    at.sidebar.radio[1].set_value("Stored rankings (fast, exact)")
    at.sidebar.button[0].click()
    t1 = time.time()
    at.run()
    T = texts(at)
    rec("claim 268 run: no exception", not at.exception, f"{time.time() - t1:.0f}s")
    for step in ("Step 1", "Step 2", "Step 3", "Step 4", "Step 5"):
        rec(f"claim 268: '{step}' rendered", step in T)
    rec("claim 268: retrieval + authority dataframes rendered (>= 7)", len(at.dataframe) >= 7, f"{len(at.dataframe)} dataframes")
    rec("claim 268: stored LLM prediction labelled NOT live", "NOT generated live" in T)
    rec("claim 268: best evidence rank metric 45 / 44 / 28", "45 / 44 / 28" in T)
    df_d = None
    for d in at.dataframe:
        v = d.value
        if "prior" in v.columns and "hybrid_rank" in v.columns and v["prior"].iloc[0] == 1.0 \
                and str(v["link"].iloc[0]).startswith("https://trumpwhitehouse.archives.gov"):
            df_d = v
    rec("claim 268: D ranks the executive order first (from hybrid rank 28)",
        df_d is not None and int(df_d["hybrid_rank"].iloc[0]) == 28)
    urls_ok = all(str(u).startswith("https://") for d in at.dataframe if "link" in d.value.columns for u in d.value["link"])
    rec("all URL links are well-formed https links", urls_ok)
    pubs_ok = all(str(p) for d in at.dataframe if "publisher" in d.value.columns for p in d.value["publisher"])
    rec("all rows carry a publisher/source name", pubs_ok)
    rec("evaluation tab: primary test p = 0.167 shown", "p = 0.167" in T)
    rec("PU tab: 13/42 and 12/42 shown", any("13/42" in str(d.value.to_string()) for d in at.dataframe)
        and any("12/42" in str(d.value.to_string()) for d in at.dataframe))
    rec("PU tab: 'NOT an authority model' banner", "NOT an authority model" in T)

    # ---- custom query on 268 (uses the pre-computed live run if present)
    at.sidebar.radio[1].set_value("Custom claim text (live)")
    at.run()
    at.sidebar.text_area[0].set_value("Trump executive order protects people with pre-existing conditions")
    at.sidebar.button[0].click()
    t2 = time.time()
    at.run()
    T = texts(at)
    rec("custom query: no exception", not at.exception, f"{time.time() - t2:.0f}s")
    rec("custom query: LLM prior OFF with explanation", "never makes" in T)

    # ---- empty query is handled
    at.sidebar.text_area[0].set_value("   ")
    at.sidebar.button[0].click()
    at.run()
    rec("empty custom query: readable warning, no crash", not at.exception and "needs some query text" in texts(at))

    # ---- failure claim 436, stored
    at.sidebar.radio[1].set_value("Stored rankings (fast, exact)")
    at.sidebar.selectbox[0].set_value(436)
    at.sidebar.button[0].click()
    at.run()
    rec("claim 436 (failure case) runs", not at.exception and "Step 5" in texts(at))

    ok = all(r["status"] == "PASS" for r in RES)
    rep = {"run_at": datetime.now().isoformat(timespec="seconds"), "all_pass": ok,
           "n_pass": sum(r["status"] == "PASS" for r in RES), "n": len(RES), "total_s": round(time.time() - t0),
           "results": RES}
    json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1)
    print(f"\n{rep['n_pass']}/{rep['n']} passed in {rep['total_s']}s -> {OUT}")
    if at.exception:
        for e in at.exception:
            print(e.value)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
