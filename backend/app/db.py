"""SQLite persistence for test cases, the audit log and ingested documents."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS test_cases (
  id TEXT PRIMARY KEY, seq INTEGER NOT NULL, source TEXT NOT NULL, sid INTEGER NOT NULL, kind TEXT NOT NULL,
  title TEXT NOT NULL, pre TEXT NOT NULL, request TEXT NOT NULL, expected TEXT NOT NULL, criteria TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft', comment TEXT NOT NULL DEFAULT '', actual TEXT, passed INTEGER, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
  chunk_id TEXT PRIMARY KEY, name TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _case(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["pre"] = json.loads(d["pre"])
    d["passed"] = None if d["passed"] is None else bool(d["passed"])
    return d


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    # ---- test cases -------------------------------------------------------
    def replace_generated(self, cases: list) -> int:
        with self.conn() as c:
            c.execute("DELETE FROM test_cases WHERE source='generated'")
            for i, t in enumerate(cases, 1):
                self._insert(c, f"TC-{i:03d}", i, "generated", t)
        return len(cases)

    def add_manual(self, t: dict) -> str:
        with self.conn() as c:
            seq = (c.execute("SELECT COALESCE(MAX(seq),0) FROM test_cases WHERE source='manual'").fetchone()[0]) + 1
            tid = f"TC-M{seq:02d}"
            self._insert(c, tid, seq, "manual", t)
        return tid

    @staticmethod
    def _insert(c, tid, seq, source, t):
        c.execute(
            "INSERT INTO test_cases (id,seq,source,sid,kind,title,pre,request,expected,criteria,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (tid, seq, source, t["sid"], t["kind"], t["title"], json.dumps(t["pre"]), t["request"], t["expected"], t["criteria"], now()),
        )

    def list_tests(self, status: str | None = None) -> list:
        q, args = "SELECT * FROM test_cases", ()
        if status:
            q, args = q + " WHERE status=?", (status,)
        with self.conn() as c:
            return [_case(r) for r in c.execute(q + " ORDER BY source DESC, seq", args)]

    def get_test(self, tid: str) -> dict | None:
        with self.conn() as c:
            r = c.execute("SELECT * FROM test_cases WHERE id=?", (tid,)).fetchone()
        return _case(r) if r else None

    def set_review(self, tid: str, status: str, comment: str) -> bool:
        with self.conn() as c:
            return c.execute("UPDATE test_cases SET status=?, comment=?, updated_at=? WHERE id=?", (status, comment, now(), tid)).rowcount > 0

    def approve_drafts(self) -> int:
        with self.conn() as c:
            return c.execute("UPDATE test_cases SET status='Approved', updated_at=? WHERE status='Draft'", (now(),)).rowcount

    def save_results(self, results: dict) -> None:
        with self.conn() as c:
            for tid, r in results.items():
                c.execute("UPDATE test_cases SET actual=?, passed=? WHERE id=?", (r["actual"], int(r["passed"]), tid))

    # ---- audit ------------------------------------------------------------
    def audit(self, actor: str, action: str, detail: str = "") -> None:
        with self.conn() as c:
            c.execute("INSERT INTO audit_log (ts,actor,action,detail) VALUES (?,?,?,?)", (now(), actor, action, detail))

    def list_audit(self, limit: int = 200) -> list:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]

    # ---- documents --------------------------------------------------------
    def add_documents(self, name: str, chunks: list) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM documents WHERE name=?", (name,))
            c.executemany("INSERT INTO documents (chunk_id,name,title,text) VALUES (?,?,?,?)", [(ch.id, name, ch.title, ch.text) for ch in chunks])

    def list_documents(self) -> list:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM documents ORDER BY name, chunk_id")]
