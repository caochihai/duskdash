"""Store của gateway: cases, events (audit/trace), plans, approval tokens."""
from __future__ import annotations

import json
import sqlite3
import time
import hashlib
from typing import Any

from common import config
from common import pii
from .state_machine import validate_transition


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
          agent TEXT, type TEXT, payload_json TEXT, previous_hash TEXT, event_hash TEXT);
        CREATE TABLE IF NOT EXISTS plans(
          case_id TEXT, version INTEGER, plan_json TEXT, ts REAL,
          PRIMARY KEY (case_id, version));
        CREATE TABLE IF NOT EXISTS documents(
          document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_type TEXT NOT NULL,
          file_hash TEXT NOT NULL, mime_type TEXT NOT NULL, storage_path TEXT NOT NULL,
          original_filename TEXT, processing_status TEXT NOT NULL, metadata_json TEXT,
          created_at REAL NOT NULL, updated_at REAL NOT NULL,
          UNIQUE(case_id, file_hash));
        CREATE TABLE IF NOT EXISTS extracted_facts(
          fact_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, key TEXT NOT NULL,
          value_json TEXT, normalized_value TEXT, confidence REAL,
          page INTEGER, bbox_json TEXT, evidence_text TEXT, extractor_version TEXT NOT NULL,
          created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS tokens(
          token_hash TEXT PRIMARY KEY, case_id TEXT NOT NULL, package_hash TEXT NOT NULL,
          policy_version TEXT NOT NULL, plan_version INTEGER NOT NULL, scope TEXT NOT NULL,
          approver TEXT NOT NULL, expires_at REAL NOT NULL, used INTEGER DEFAULT 0);
        """)
        db.execute("PRAGMA journal_mode=WAL")
        event_columns = {row[1] for row in db.execute("PRAGMA table_info(events)")}
        if "previous_hash" not in event_columns:
            db.execute("ALTER TABLE events ADD COLUMN previous_hash TEXT")
        if "event_hash" not in event_columns:
            db.execute("ALTER TABLE events ADD COLUMN event_hash TEXT")
        # Backfill legacy rows once, preserving chronological chain order.
        import hashlib
        case_rows = db.execute("SELECT DISTINCT case_id FROM events").fetchall()
        for case_row in case_rows:
            previous_hash = ""
            rows = db.execute("SELECT * FROM events WHERE case_id=? ORDER BY id", (case_row[0],)).fetchall()
            for row in rows:
                canonical = row["payload_json"]
                event_hash = hashlib.sha256(
                    f"{previous_hash}|{case_row[0]}|{row['agent']}|{row['type']}|{canonical}".encode()
                ).hexdigest()
                if row["previous_hash"] != previous_hash or row["event_hash"] != event_hash:
                    db.execute("UPDATE events SET previous_hash=?, event_hash=? WHERE id=?",
                               (previous_hash, event_hash, row["id"]))
                previous_hash = event_hash

        # One-time migration from the original schema which persisted raw tokens.
        columns = {row[1] for row in db.execute("PRAGMA table_info(tokens)")}
        if "token" in columns:
            legacy_rows = db.execute("SELECT * FROM tokens").fetchall()
            db.execute("ALTER TABLE tokens RENAME TO tokens_legacy")
            db.execute("""
                CREATE TABLE tokens(
                  token_hash TEXT PRIMARY KEY, case_id TEXT NOT NULL, package_hash TEXT NOT NULL,
                  policy_version TEXT NOT NULL, plan_version INTEGER NOT NULL, scope TEXT NOT NULL,
                  approver TEXT NOT NULL, expires_at REAL NOT NULL, used INTEGER DEFAULT 0)
            """)
            for row in legacy_rows:
                token_hash = hashlib.sha256(row["token"].encode()).hexdigest()
                db.execute(
                    "INSERT INTO tokens VALUES (?,?,?,?,?,?,?,?,?)",
                    (token_hash, row["case_id"], row["package_hash"], row["policy_version"],
                     0, "commit", row["approver"], row["expires_at"], row["used"]),
                )
            db.execute("DROP TABLE tokens_legacy")


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
    if "state" in fields:
        current = get_case(case_id)
        if current is None:
            raise KeyError(f"Case not found: {case_id}")
        validate_transition(current["state"], fields["state"])
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
    redacted_payload = pii.mask(payload)
    ts = time.time()
    with _conn() as db:
        previous = db.execute("SELECT event_hash FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
        previous_hash = previous[0] if previous and previous[0] else ""
        import hashlib
        canonical = json.dumps(redacted_payload, ensure_ascii=False, sort_keys=True, default=str)
        event_hash = hashlib.sha256(f"{previous_hash}|{case_id}|{agent}|{etype}|{canonical}".encode()).hexdigest()
        cur = db.execute(
            "INSERT INTO events(ts, case_id, agent, type, payload_json, previous_hash, event_hash) VALUES (?,?,?,?,?,?,?)",
            (ts, case_id, agent, etype,
             canonical, previous_hash, event_hash),
        )
        eid = cur.lastrowid
    return {"id": eid, "ts": ts, "case_id": case_id, "agent": agent,
            "type": etype, "payload": redacted_payload, "event_hash": event_hash}


def get_events(case_id: str, after_id: int = 0) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM events WHERE case_id=? AND id>? ORDER BY id", (case_id, after_id)
        ).fetchall()
    return [
        {**dict(r), "payload": json.loads(r["payload_json"] or "{}")} for r in rows
    ]


def verify_event_chain(case_id: str) -> dict:
    """Verify the append-only event hash chain for a case."""
    import hashlib
    previous_hash = ""
    with _conn() as db:
        rows = db.execute("SELECT * FROM events WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
    for row in rows:
        expected = hashlib.sha256(
            f"{previous_hash}|{case_id}|{row['agent']}|{row['type']}|{row['payload_json']}".encode()
        ).hexdigest()
        if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
            return {"valid": False, "event_id": row["id"], "checked": len(rows)}
        previous_hash = row["event_hash"]
    return {"valid": True, "checked": len(rows), "head_hash": previous_hash}


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


# ---- documents and provenance ----
def save_document(document: dict) -> None:
    now = time.time()
    with _conn() as db:
        db.execute(
            """INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (document["document_id"], document["case_id"], document["document_type"],
             document["file_hash"], document["mime_type"], document["storage_path"],
             document.get("original_filename"), document["processing_status"],
             json.dumps(document.get("metadata", {}), ensure_ascii=False), now, now),
        )


def update_document(document_id: str, *, processing_status: str,
                    metadata: dict | None = None) -> None:
    with _conn() as db:
        if metadata is None:
            db.execute("UPDATE documents SET processing_status=?, updated_at=? WHERE document_id=?",
                       (processing_status, time.time(), document_id))
        else:
            db.execute("""UPDATE documents SET processing_status=?, metadata_json=?, updated_at=?
                          WHERE document_id=?""",
                       (processing_status, json.dumps(metadata, ensure_ascii=False),
                        time.time(), document_id))


def get_document(document_id: str) -> dict | None:
    with _conn() as db:
        row = db.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
    return _document_row(row) if row else None


def list_documents(case_id: str) -> list[dict]:
    with _conn() as db:
        rows = db.execute("SELECT * FROM documents WHERE case_id=? ORDER BY created_at", (case_id,)).fetchall()
    return [_document_row(row) for row in rows]


def _document_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
    return data


def save_extracted_facts(document_id: str, facts: list[dict]) -> None:
    now = time.time()
    with _conn() as db:
        db.execute("DELETE FROM extracted_facts WHERE document_id=?", (document_id,))
        for fact in facts:
            evidence = fact.get("evidence", {})
            db.execute(
                "INSERT INTO extracted_facts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (fact["fact_id"], document_id, fact["key"],
                 json.dumps(fact.get("value"), ensure_ascii=False), fact.get("normalized_value"),
                 fact.get("confidence"), evidence.get("page"),
                 json.dumps(evidence.get("bbox")), evidence.get("text"),
                fact.get("extractor_version", "native-text-v1"), now),
            )


def list_case_facts(case_id: str) -> list[dict]:
    with _conn() as db:
        rows = db.execute("""SELECT f.*, d.document_type FROM extracted_facts f
                             JOIN documents d ON d.document_id=f.document_id
                             WHERE d.case_id=? ORDER BY f.created_at""", (case_id,)).fetchall()
    facts = []
    for row in rows:
        item = dict(row)
        item["value"] = json.loads(item.pop("value_json") or "null")
        item["bbox"] = json.loads(item.pop("bbox_json") or "null")
        facts.append(item)
    return facts


# ---- tokens ----
def save_token(token_hash: str, case_id: str, package_hash: str, policy_version: str,
               plan_version: int, scope: str, approver: str, expires_at: float) -> None:
    with _conn() as db:
        db.execute("INSERT INTO tokens VALUES (?,?,?,?,?,?,?,?,0)",
                   (token_hash, case_id, package_hash, policy_version, plan_version, scope,
                    approver, expires_at))


def get_token(token_hash: str) -> dict | None:
    with _conn() as db:
        row = db.execute("SELECT * FROM tokens WHERE token_hash=?", (token_hash,)).fetchone()
    return dict(row) if row else None


def mark_token_used(token_hash: str) -> None:
    with _conn() as db:
        db.execute("UPDATE tokens SET used=1 WHERE token_hash=?", (token_hash,))
