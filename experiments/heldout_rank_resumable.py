"""Resumable driver for the FROZEN held-out dense ranking (validation_heldout.py `rank`).

Why: `validation_heldout.cmd_rank` writes rankings_dense.jsonl.gz only after all 200
claims are done; the first run died at 55/200 and lost everything. This driver calls
the *unchanged* frozen functions (`baseline_retrieval.rank_dense`, `retrieval_corpus`)
per claim, checkpoints each claim to results/heldout/dense_ckpt.jsonl, then writes the
dense file in the frozen format and calls the frozen `cmd_rank()` (which skips the
existing bm25/dense files and builds the RRF hybrid). No retrieval logic is changed.
"""
import json
import time

from baseline_retrieval import rank_dense, retrieval_corpus
from validation_heldout import HO, _save, cmd_rank, load_heldout

CKPT = HO / "dense_ckpt.jsonl"


def main():
    done = {}
    if CKPT.exists():
        for line in open(CKPT, encoding="utf-8"):
            x = json.loads(line)
            done[int(x["claim_id"])] = [tuple(p) for p in x["ranked"]]
    sample = load_heldout()
    t0 = time.time()
    with open(CKPT, "a", encoding="utf-8") as fh:
        for i, r in enumerate(sample, 1):
            cid = int(r["claim_id"])
            if cid in done:
                continue
            docs = retrieval_corpus(cid)
            done[cid] = rank_dense(r["claim"], docs)
            fh.write(json.dumps({"claim_id": cid, "ranked": done[cid]}) + "\n")
            fh.flush()
            print(f"[dense {i}/{len(sample)}] claim {cid} ({len(docs)} docs, {time.time() - t0:.0f}s)", flush=True)
    assert len(done) == len(sample)
    # same order and format as the frozen cmd_rank would have written
    _save("dense", {r["claim_id"]: done[int(r["claim_id"])] for r in sample})
    cmd_rank()


if __name__ == "__main__":
    main()
