"""Merkle-batched append-only chain (sqlite locally, Postgres in prod)."""
import datetime
import hashlib
import json

from . import store


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _pair_up(level):
    if len(level) % 2:
        level = level + [level[-1]]  # RFC 9162-style: duplicate last if odd
    return [h(level[i] + level[i + 1]) for i in range(0, len(level), 2)], level


def merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return h("")
    level = list(leaves)
    while len(level) > 1:
        level, _ = _pair_up(level)
    return level[0]


def merkle_proof(leaves: list[str], idx: int) -> list[dict]:
    proof, level, i = [], list(leaves), idx
    while len(level) > 1:
        nxt, padded = _pair_up(level)
        sib = i ^ 1
        proof.append({"hash": padded[sib], "position": "left" if sib < i else "right"})
        level, i = nxt, i // 2
    return proof


def verify_proof(leaf: str, proof: list[dict], root: str) -> bool:
    cur = leaf
    for p in proof:
        cur = h(p["hash"] + cur) if p["position"] == "left" else h(cur + p["hash"])
    return cur == root


def block_hash(idx: int, ts: str, prev: str, root: str) -> str:
    return h(f"{idx}|{ts}|{prev}|{root}")


def _row_to_block(r) -> dict:
    leaves = json.loads(r["leaves"])
    return {"index": r["idx"], "hash": r["hash"], "prev_hash": r["prev_hash"],
            "merkle_root": r["merkle_root"], "tx_count": len(leaves),
            "timestamp": r["timestamp"], "leaves": leaves}


def _append(leaves: list[str]) -> dict:
    with store.LOCK:
        last = store.run("SELECT * FROM blocks ORDER BY idx DESC LIMIT 1", fetch="one")
        idx = last["idx"] + 1 if last else 0
        prev = last["hash"] if last else "0" * 64
        ts, root = now(), merkle_root(leaves)
        bh = block_hash(idx, ts, prev, root)
        store.run("INSERT INTO blocks VALUES(?,?,?,?,?,?)", (idx, ts, prev, root, bh, json.dumps(leaves)))
        return _row_to_block(store.run("SELECT * FROM blocks WHERE idx=?", (idx,), "one"))


def genesis():
    if not store.run("SELECT 1 FROM blocks LIMIT 1", fetch="one"):
        _append([])


def add_leaf(leaf: str):
    store.run("INSERT INTO pending(leaf) VALUES(?)", (leaf,))


def flush() -> dict | None:
    with store.LOCK:
        rows = store.run("SELECT leaf FROM pending ORDER BY seq", fetch="all")
        if not rows:
            return None
        block = _append([r["leaf"] for r in rows])
        store.run("DELETE FROM pending")
        return block


def anchor(leaf: str) -> dict:
    """Demo path: append + flush synchronously so the response carries a proof."""
    with store.LOCK:
        add_leaf(leaf)
        block = flush()
    idx = block["leaves"].index(leaf)
    return {"batch_id": block["index"], "block_hash": block["hash"], "merkle_root": block["merkle_root"],
            "leaf_hash": leaf, "proof": merkle_proof(block["leaves"], idx), "tx_index": idx,
            "timestamp": block["timestamp"]}


def blocks(limit: int) -> list[dict]:
    return [_row_to_block(r) for r in store.run("SELECT * FROM blocks ORDER BY idx DESC LIMIT ?", (limit,), "all")]


def block(idx: int) -> dict | None:
    r = store.run("SELECT * FROM blocks WHERE idx=?", (idx,), "one")
    return _row_to_block(r) if r else None


def find_block_with(leaf: str) -> dict | None:
    r = store.run("SELECT * FROM blocks WHERE leaves LIKE ? ORDER BY idx LIMIT 1", (f'%"{leaf}"%',), "one")
    return _row_to_block(r) if r else None


def proof_for(leaf: str) -> dict | None:
    b = find_block_with(leaf)
    if not b:
        return None
    proof = merkle_proof(b["leaves"], b["leaves"].index(leaf))
    return {"block_index": b["index"], "merkle_root": b["merkle_root"], "proof": proof,
            "valid": verify_proof(leaf, proof, b["merkle_root"])}


def verify_chain() -> dict:
    prev, n = "0" * 64, 0
    for b in store.run("SELECT * FROM blocks ORDER BY idx", fetch="all"):
        n += 1
        leaves = json.loads(b["leaves"])
        ok = (b["prev_hash"] == prev and b["merkle_root"] == merkle_root(leaves)
              and b["hash"] == block_hash(b["idx"], b["timestamp"], prev, b["merkle_root"]))
        if not ok:
            return {"valid": False, "blocks": n, "broken_at": b["idx"]}
        prev = b["hash"]
    return {"valid": True, "blocks": n, "broken_at": None}


def revocation_leaf(vid: str) -> str:
    # revocations are leaves too: a hash, never a readable id, so the chain carries no identifiers
    return hashlib.sha256(f"REVOKE:{vid}".encode()).hexdigest()


def revoke(vid: str) -> dict:
    return anchor(revocation_leaf(vid))


def is_revoked(vid: str) -> bool:
    return find_block_with(revocation_leaf(vid)) is not None


def count() -> int:
    return store.run("SELECT COUNT(*) c FROM blocks", fetch="one")["c"]
