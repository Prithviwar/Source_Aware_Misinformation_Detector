"""X: gold-blind mismatched-authority control (preregistration §2.2).

Inputs: T's retained keys (in T's order), K_c(D), and the claim's pool URLs. No gold, no
ranks beyond pool membership, no outcomes, no RNG: ties are broken by a SHA-256 digest.
"""
import hashlib
from collections import Counter

from authority_retrieval import generic_prior
import validation_heldout as V

TAG = b"2029"
SEP = b"\x1f"


def pool_attrs(pool_urls):
    """count(k) and type(k) = modal generic_prior over k's pool docs (ties -> larger value)."""
    docs = {}
    for u in pool_urls:
        k = V.cand_key(u)
        if k:
            docs.setdefault(k, []).append(generic_prior(u))
    count = {k: len(v) for k, v in docs.items()}
    typ = {k: max(Counter(v).items(), key=lambda kv: (kv[1], kv[0]))[0] for k, v in docs.items()}
    return count, typ


def digest(claim_id: int, i: int, q: str) -> bytes:
    return hashlib.sha256(TAG + SEP + str(int(claim_id)).encode("ascii") + SEP + str(i).encode("ascii")
                          + SEP + q.encode("utf-8")).digest()


def build_x(claim_id, t_keys, d_keys, pool_urls):
    """Returns (X keys, per-slot log, budget record)."""
    count, typ = pool_attrs(pool_urls)
    Q = sorted(set(count) - set(t_keys) - set(d_keys or ()))
    slots, x = [], []
    for i, p in enumerate(t_keys, 1):
        same = [q for q in Q if typ[q] == typ[p]]
        cand, flag = (same, "same_type") if same else (Q, "type_relaxed") if Q else ([], "unmatched")
        q = None
        if cand:
            # big-endian digest bytes compare like the unsigned integer
            q = min(cand, key=lambda q: (abs(count[q] - count[p]), digest(claim_id, i, q), q))
            Q.remove(q)
            x.append(q)
        slots.append({"slot": i, "p": p, "q": q, "flag": flag, "count_p": count[p],
                      "count_q": count[q] if q else None, "type_p": typ[p], "type_q": typ[q] if q else None,
                      "digest": digest(claim_id, i, q).hex() if q else None})
    budget = {"n_T": len(t_keys), "n_X": len(x), "B_T": sum(count[p] for p in t_keys),
              "B_X": sum(count[q] for q in x)}
    return x, slots, budget
