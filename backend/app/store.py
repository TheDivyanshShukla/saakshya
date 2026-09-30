"""sqlite locally, Postgres when DATABASE_URL is set; plus on-disk artifact layout."""
import json
import os
import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARTIFACTS = DATA / "artifacts"
SAMPLES = DATA / "samples"
KEYS = DATA / "keys"
DB_PATH = DATA / "saakshya.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

LOCK = threading.RLock()  # ponytail: one global connection + lock; fine for a demo box
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS verifications(
  id TEXT PRIMARY KEY, created_at TEXT, trust_level INT, needs_human INT,
  total_ms REAL, salt TEXT, leaf_hash TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS blocks(
  idx INTEGER PRIMARY KEY, timestamp TEXT, prev_hash TEXT, merkle_root TEXT, hash TEXT, leaves TEXT);
CREATE TABLE IF NOT EXISTS pending(seq INTEGER PRIMARY KEY AUTOINCREMENT, leaf TEXT);
CREATE TABLE IF NOT EXISTS rgpv_results(roll_no TEXT PRIMARY KEY, name TEXT, cgpa REAL, year INT, course TEXT);
CREATE TABLE IF NOT EXISTS mpbse_results(roll_no TEXT PRIMARY KEY, name TEXT, percentage REAL, year INT);
CREATE TABLE IF NOT EXISTS pan_registry(pan TEXT PRIMARY KEY, name TEXT, dob TEXT);
"""


def init():
    global _conn
    for d in (ARTIFACTS, SAMPLES, KEYS):
        d.mkdir(parents=True, exist_ok=True)
    if PG:
        import psycopg
        from psycopg.rows import dict_row
        # ponytail: single connection, no reconnect; a Postgres restart fails the healthcheck and the container restarts
        _conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
        _conn.execute(SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
                      .replace("REAL", "DOUBLE PRECISION"))
    else:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)


def _sql(sql: str) -> str:
    return sql.replace("?", "%s") if PG else sql


def run(sql, params=(), fetch=None):
    with LOCK:
        cur = _conn.execute(_sql(sql), params)
        _conn.commit()
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return cur


def run_many(sql, rows):
    with LOCK:
        if PG:
            with _conn.cursor() as cur:
                cur.executemany(_sql(sql), rows)
        else:
            _conn.executemany(sql, rows)
            _conn.commit()


def artifact_dir(vid: str) -> Path:
    p = ARTIFACTS / vid
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_verification(res: dict, salt: str, leaf: str):
    run(
        "INSERT INTO verifications VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
        "created_at=excluded.created_at, trust_level=excluded.trust_level, needs_human=excluded.needs_human, "
        "total_ms=excluded.total_ms, salt=excluded.salt, leaf_hash=excluded.leaf_hash, result=excluded.result",
        (res["id"], res["created_at"], res["trust_level"], int(res["needs_human"]),
         res["timings_ms"]["total"], salt, leaf, json.dumps(res)),
    )


def get_verification(vid: str) -> dict | None:
    row = run("SELECT result FROM verifications WHERE id=?", (vid,), "one")
    return json.loads(row["result"]) if row else None


def list_verifications(limit: int) -> list[dict]:
    rows = run("SELECT result FROM verifications ORDER BY created_at DESC LIMIT ?", (limit,), "all")
    return [json.loads(r["result"]) for r in rows]


def stats() -> dict:
    total = run("SELECT COUNT(*) c, AVG(total_ms) a, SUM(needs_human) h FROM verifications", fetch="one")
    by_level = {str(i): 0 for i in range(4)}
    for r in run("SELECT trust_level l, COUNT(*) c FROM verifications GROUP BY l", fetch="all"):
        by_level[str(r["l"])] = r["c"]
    return {"total": total["c"], "by_level": by_level,
            "avg_ms": round(total["a"] or 0, 1), "human_review": total["h"] or 0}
