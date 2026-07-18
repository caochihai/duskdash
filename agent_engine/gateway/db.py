"""Store của gateway: cases, events (audit/trace), plans, approval tokens."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from common import config


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.GATEWAY_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _conn() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS cases(
          case_id TEXT PRIMARY KEY, state TEXT, payload_json TEXT,
          package_json TEXT, approver TEXT, replan_count INTEGER DEFAULT 0,
          sla_deadline REAL, created_at REAL, updated_at REAL);
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, case_id TEXT,
          agent TEXT, type TEXT, payload_json TEXT);
        CREATE TABLE IF NOT EXISTS plans(
          case_id TEXT, version INTEGER, plan_json TEXT, ts REAL,
          PRIMARY KEY (case_id, version));
        CREATE TABLE IF NOT EXISTS tokens(
          token TEXT PRIMARY KEY, case_id TEXT, package_hash TEXT,
          policy_version TEXT, approver TEXT, expires_at REAL, used INTEGER DEFAULT 0);
        """)
        db.execute("PRAGMA journal_mode=WAL")


# ---- cases ----
def create_case(case_id: str, payload: dict) -> None:
    now = time.time()
    with _conn() as db:
        db.execute(
            "INSERT INTO cases(case_id, state, payload_json, created_at, updated_at) "
            "VALUES (?,?,?,?,?)",
            (case_id, "Draft", json.dumps(payload, ensure_ascii=False), now, now),
        )


def get_case(case_id: str) -> dict | None:
    with _conn() as db:
        row = db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["payload"] = json.loads(d.pop("payload_json") or "{}")
    d["package"] = json.loads(d.pop("package_json") or "null")
    return d


def update_case(case_id: str, **fields: Any) -> None:
    sets, vals = ["updated_at=?"], [time.time()]
    for k, v in fields.items():
        if k in ("payload", "package"):
            sets.append(f"{k}_json=?")
            vals.append(json.dumps(v, ensure_ascii=False, default=str))
        else:
            sets.append(f"{k}=?")
            vals.append(v)
    vals.append(case_id)
    with _conn() as db:
        db.execute(f"UPDATE cases SET {', '.join(sets)} WHERE case_id=?", vals)


def list_pending_approval() -> list[dict]:
    with _conn() as db:
        rows = db.execute("SELECT * FROM cases WHERE state='Pending Approval'").fetchall()
    return [dict(r) for r in rows]


# ---- events ----
def add_event(case_id: str, agent: str, etype: str, payload: dict) -> dict:
    ts = time.time()
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO events(ts, case_id, agent, type, payload_json) VALUES (?,?,?,?,?)",
            (ts, case_id, agent, etype, json.dumps(payload, ensure_ascii=False, default=str)),
        )
        eid = cur.lastrowid
    return {"id": eid, "ts": ts, "case_id": case_id, "agent": agent,
            "type": etype, "payload": payload}


def get_events(case_id: str, after_id: int = 0) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM events WHERE case_id=? AND id>? ORDER BY id", (case_id, after_id)
        ).fetchall()
    return [
        {**dict(r), "payload": json.loads(r["payload_json"] or "{}")} for r in rows
    ]


# ---- plans ----
def save_plan(case_id: str, version: int, plan: dict) -> None:
    with _conn() as db:
        db.execute(
            "INSERT OR REPLACE INTO plans VALUES (?,?,?,?)",
            (case_id, version, json.dumps(plan, ensure_ascii=False), time.time()),
        )


def get_latest_plan(case_id: str) -> dict | None:
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM plans WHERE case_id=? ORDER BY version DESC LIMIT 1", (case_id,)
        ).fetchone()
    return json.loads(row["plan_json"]) if row else None


# ---- tokens ----
def save_token(token: str, case_id: str, package_hash: str, policy_version: str,
               approver: str, expires_at: float) -> None:
    with _conn() as db:
        db.execute("INSERT INTO tokens VALUES (?,?,?,?,?,?,0)",
                   (token, case_id, package_hash, policy_version, approver, expires_at))


def get_token(token: str) -> dict | None:
    with _conn() as db:
        row = db.execute("SELECT * FROM tokens WHERE token=?", (token,)).fetchone()
    return dict(row) if row else None


def mark_token_used(token: str) -> None:
    with _conn() as db:
        db.execute("UPDATE tokens SET used=1 WHERE token=?", (token,))
