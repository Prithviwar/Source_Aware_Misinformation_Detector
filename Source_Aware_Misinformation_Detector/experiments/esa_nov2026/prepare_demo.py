"""Prepare the Monday demo (run once before the review; offline, no LLM, no download).

  python experiments/esa_nov2026/prepare_demo.py            # stats + fallback pages (~10-15 min)
  python experiments/esa_nov2026/prepare_demo.py --live     # + pre-compute live BM25/MiniLM/RRF for claim 268
                                                             #   and one custom query (~5 min more)

Writes (all genuine outputs of the project code; nothing is edited by hand):
  results/esa_nov2026/demo/knowledge_store_stats.json
  results/esa_nov2026/demo/fallback/claim_<id>.{json,md,html}   via demo_pipeline.run (stored rankings)
  results/esa_nov2026/demo/fallback/INDEX.html                  links to every fallback page
  results/esa_nov2026/demo/live_cache/*.json.gz                 (with --live)
"""
from __future__ import annotations

import html
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_pipeline as P  # noqa: E402
from esa_common import claims, out_dir  # noqa: E402


def ks_stats():
    from common import KS_DIR, load_ks
    n_raw = n_ret = size = 0
    t0 = time.time()
    per = {}
    for i, cid in enumerate(sorted(claims()), 1):
        f = KS_DIR / f"{cid}.jsonl.gz"
        size += f.stat().st_size
        n_raw += len(load_ks(cid))
        n = len(P.corpus(cid))
        n_ret += n
        per[cid] = n
        if i % 40 == 0:
            print(f"  ks stats {i}/320 ({time.time() - t0:.0f}s)", flush=True)
        P.corpus.cache_clear()
    vals = sorted(per.values())
    rec = {"computed_at": datetime.now().isoformat(timespec="seconds"), "n_claims": len(per),
           "n_docs_raw": n_raw, "n_docs_retrievable": n_ret, "size_gb": size / 1e9,
           "retrievable_per_claim": {"min": vals[0], "median": vals[len(vals) // 2], "max": vals[-1]},
           "note": "AVeriTeC dev per-claim knowledge stores for the 120 dev-sample + 200 held-out claims "
                   "(data/raw/averitec/ks_sample). 'retrievable' = non-empty text after URL de-duplication "
                   "(baseline_retrieval.retrieval_corpus). The reserved-180 store (~139,397 docs) is NOT on disk."}
    json.dump(rec, open(out_dir("demo") / "knowledge_store_stats.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(rec, indent=1))


def to_md(o):
    L = [f"# Claim {o['claim_id']} ({o['split']}, mode={o['mode']})", "", f"> {o['claim']['claim']}", "",
         f"Speaker: {o['claim']['speaker_or_entity']} | date {o['claim']['claim_date']} | country "
         f"{o['claim']['location_ISO_code']} | candidates {o['n_candidates']}", "",
         f"BM25 query terms: {' '.join(o['processing']['bm25_tokens'])}", ""]
    for m in ("bm25", "dense", "hybrid"):
        R = o["retrieval"][m]
        L += [f"## {R['label']}", "", "| # | publisher | URL | score | B/M/H | evidence |", "|---|---|---|---|---|---|"]
        for x in R["top"]:
            L.append(f"| {x['rank']} | {x['publisher']} | {x['url'][:80]} | {x['score']} | "
                     f"{x['rank_bm25']}/{x['rank_dense']}/{x['rank_hybrid']} | {'yes' if x['evidence_marker'] else ''} |")
        L.append("")
    L.append(f"Top-k overlap: {o['overlap']} · best evidence rank: {o['best_evidence_rank']}")
    p = o["llm_prediction"]
    if p:
        L += ["", "## Stored LLM authority prediction (Sept 2026; not generated live)", "",
              f"Fact at issue: {p['fact_at_issue']}", ""]
        L += [f"{i}. {t['publisher']} ({t['domain']}, {t['type']})" for i, t in enumerate(p["top3"], 1)]
    for sid, A in o["authority"].items():
        L += ["", f"## {A['label']} — {A['desc']}", "", "| # | was | publisher | relevance | prior | final | factors | evidence |",
              "|---|---|---|---|---|---|---|---|"]
        for x in A["top"]:
            L.append(f"| {x['rank']} | {x['hybrid_rank']} | {x['publisher']} | {x['relevance']} | {x['prior']} | "
                     f"{x['final']} | {x['why']} | {'yes' if x['evidence_marker'] else ''} |")
        L.append(f"\nBest evidence rank in pool: {A['best_evidence_rank_in_pool']}")
    L += ["", o["evidence_note"], "", f"Generated {datetime.now():%Y-%m-%d %H:%M} by experiments/esa_nov2026/prepare_demo.py "
          "(project code, stored rankings, no LLM call)."]
    return "\n".join(L)


def to_html(o, md):
    e = lambda x: html.escape(str(x if x is not None else ""))

    def table(head, rows):
        h = "".join(f"<th>{e(c)}</th>" for c in head)
        b = "".join(f"<tr class='{'ev' if ev else ''}'>" + "".join(f"<td>{e(c)}</td>" for c in cells) + "</tr>"
                    for cells, ev in rows)
        return f"<table><tr>{h}</tr>{b}</table>"

    c = o["claim"]
    parts = [f"<h1>Claim {o['claim_id']} <small>({e(o['split'])}, stored rankings)</small></h1>",
             f"<blockquote>{e(c['claim'])}</blockquote>",
             f"<p>Speaker {e(c['speaker_or_entity'])} · {e(c['claim_date'])} · country {e(c['location_ISO_code'])} · "
             f"{o['n_candidates']} candidate documents · BM25 terms: {e(' '.join(o['processing']['bm25_tokens']))}</p>"]
    for m in ("bm25", "dense", "hybrid"):
        R = o["retrieval"][m]
        parts.append(f"<h2>{e(R['label'])}</h2>" + table(
            ["#", "publisher", "URL", "score", "ranks B/M/H", "snippet"],
            [([x["rank"], x["publisher"], x["url"][:90], x["score"], f"{x['rank_bm25']}/{x['rank_dense']}/{x['rank_hybrid']}",
               x["snippet"][:160]], x["evidence_marker"]) for x in R["top"]]))
    parts.append(f"<p>Top-k overlap {e(o['overlap'])} · best evidence rank {e(o['best_evidence_rank'])}</p>")
    p = o["llm_prediction"]
    if p:
        parts.append("<h2>Stored LLM authority prediction <small>(Sept 2026; not generated live)</small></h2>"
                     f"<p><b>Fact at issue:</b> {e(p['fact_at_issue'])}<br>kind {e(p['claim_kind'])} · "
                     f"situation {e(p['authority_situation'])} · confidence {e(p['confidence'])}</p><ol>"
                     + "".join(f"<li>{e(t['publisher'])} — {e(t['domain'])} ({e(t['type'])})</li>" for t in p["top3"]) + "</ol>")
    if o["llm_note"]:
        parts.append(f"<p><b>Note:</b> {e(o['llm_note'])}</p>")
    for sid, A in o["authority"].items():
        parts.append(f"<h2>{e(A['label'])} <small>{e(A['desc'])}</small></h2>" + table(
            ["#", "was", "publisher", "relevance", "prior", "final", "authority factors"],
            [([x["rank"], x["hybrid_rank"], x["publisher"], x["relevance"], x["prior"], x["final"], x["why"]],
              x["evidence_marker"]) for x in A["top"]])
            + f"<p>Best evidence rank in pool: {e(A['best_evidence_rank_in_pool'])}</p>")
    parts.append(f"<p>{e(o['evidence_note'])}</p><p>Generated {datetime.now():%Y-%m-%d %H:%M} by "
                 "experiments/esa_nov2026/prepare_demo.py (project code, stored rankings, no LLM call).</p>")
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Claim {o['claim_id']} demo output</title><style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#555;--ev:#fff3c4;--line:#ddd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e8e8e8;--mut:#a0a0a0;--ev:#4a3f10;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;max-width:1300px;margin:0 auto;padding:16px}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-bottom:8px}} td,th{{border-bottom:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top}}
tr.ev td{{background:var(--ev)}} blockquote{{font-size:17px;font-weight:600;margin:8px 0}} p,small{{color:var(--mut)}}
</style></head><body><p><a href="INDEX.html">&larr; all fallback pages</a> · highlighted rows = AVeriTeC evidence documents</p>
{''.join(parts)}</body></html>"""


def fallbacks():
    d = out_dir("demo", "fallback")
    links = []
    for cid, (dom, why) in P.SUGGESTED.items():
        o = P.run(cid, mode="frozen", k=10, show_gold=True)
        json.dump(o, open(d / f"claim_{cid}.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        md = to_md(o)
        (d / f"claim_{cid}.md").write_text(md, encoding="utf-8")
        (d / f"claim_{cid}.html").write_text(to_html(o, md), encoding="utf-8")
        links.append(f"<li><a href='claim_{cid}.html'>Claim {cid}</a> — <b>{html.escape(dom)}</b>: {html.escape(why)}<br>"
                     f"<small>{html.escape(o['claim']['claim'])}</small></li>")
        print(f"  fallback claim {cid} written", flush=True)
    (d / "INDEX.html").write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Demo fallback pages</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px}} li{{margin-bottom:10px}}</style></head><body>
<h1>IR_03 demo — fallback pages</h1>
<p>Genuine outputs of <code>experiments/esa_nov2026/demo_pipeline.py</code> (stored Sept-2026 rankings and stored LLM
predictions; no LLM call), generated {datetime.now():%Y-%m-%d %H:%M}. Use these if the live app cannot start. Highlighted rows =
AVeriTeC evidence documents (relevance evidence, NOT authority labels).</p><ul>{''.join(links)}</ul>
<p>Evaluation evidence: <code>results/source_targeted/results_heldout.json</code>, <code>results/heldout/validation_heldout.json</code>,
<code>results/esa_nov2026/figures/</code>.</p></body></html>""", encoding="utf-8")


def live():
    for cid, q in ((268, None), (268, "Trump executive order protects people with pre-existing conditions")):
        row = P.assert_allowed(cid)
        qq = q or row["claim"].strip()
        from common import tokenize_query
        _, meta = P.live_rankings(cid, tokenize_query(qq), use_cache=True, progress=print)
        print(f"  live cache claim {cid} query={qq[:50]!r}: computed {meta['computed_at']} timing {meta.get('timing_s')}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ks_stats()
    fallbacks()
    if "--live" in sys.argv:
        live()
    print("done")
