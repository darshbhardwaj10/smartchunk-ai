"""Small SQLite persistence layer for SmartChunk documents, versions, chunks and incidents.

This is a local/hackathon persistence layer, not a multi-tenant production database.
Keep the data directory private and out of version control.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def content_sha256(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class SmartChunkStore:
    """SQLite-backed store. Methods open short-lived connections for safe transactions."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        default_dir = Path(__file__).resolve().parent.parent / ".smartchunk_data"
        self.data_dir = Path(data_dir or os.getenv("SMARTCHUNK_DATA_DIR", str(default_dir))).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "smartchunk.db"
        self.initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    active_version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_versions (
                    version_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(document_id),
                    filename TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    normalized_sha256 TEXT NOT NULL,
                    normalized_markdown TEXT NOT NULL,
                    normalization_json TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    overlap INTEGER NOT NULL,
                    semantic INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    validation_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_versions_document
                    ON document_versions(document_id, created_at);
                CREATE TABLE IF NOT EXISTS chunks (
                    version_id TEXT NOT NULL REFERENCES document_versions(version_id) ON DELETE CASCADE,
                    chunk_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    chunk_json TEXT NOT NULL,
                    PRIMARY KEY(version_id, chunk_id)
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_version_position
                    ON chunks(version_id, position);
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(document_id),
                    version_id TEXT NOT NULL REFERENCES document_versions(version_id),
                    failure_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    config_json TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_created
                    ON incidents(created_at DESC);
                CREATE TABLE IF NOT EXISTS replay_runs (
                    replay_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version_id TEXT,
                    event_type TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def create_document(self, filename: str) -> str:
        document_id = new_id("doc")
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents(document_id, filename, active_version_id, created_at, updated_at) VALUES (?, ?, NULL, ?, ?)",
                (document_id, filename, now, now),
            )
            self._audit(conn, document_id, None, "document_created", {"filename": filename})
        return document_id

    def document_exists(self, document_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM documents WHERE document_id = ?", (document_id,)).fetchone()
        return row is not None

    def save_version(
        self,
        *,
        document_id: str,
        filename: str,
        source_bytes: bytes,
        normalized_markdown: str,
        normalization: dict[str, Any],
        chunks: list[dict[str, Any]],
        strategy: str,
        chunk_size: int,
        overlap: int,
        semantic: bool = False,
        status: str = "active",
    ) -> str:
        if status not in {"active", "candidate"}:
            raise ValueError("New versions must have status 'active' or 'candidate'.")
        version_id = new_id("ver")
        now = utc_now()
        with self._connect() as conn:
            document = conn.execute("SELECT document_id FROM documents WHERE document_id = ?", (document_id,)).fetchone()
            if not document:
                raise KeyError(f"Unknown document_id: {document_id}")
            if status == "active":
                conn.execute(
                    "UPDATE document_versions SET status = 'superseded' WHERE document_id = ? AND status = 'active'",
                    (document_id,),
                )
            conn.execute(
                """INSERT INTO document_versions(
                    version_id, document_id, filename, source_sha256, normalized_sha256,
                    normalized_markdown, normalization_json, strategy, chunk_size, overlap,
                    semantic, status, validation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?)""",
                (
                    version_id, document_id, filename, content_sha256(source_bytes),
                    content_sha256(normalized_markdown), normalized_markdown,
                    json_dumps(normalization), strategy, int(chunk_size), int(overlap),
                    int(semantic), status, now,
                ),
            )
            for position, chunk in enumerate(chunks):
                chunk_id = str(chunk.get("chunk_id") or f"chunk_{position + 1:04d}")
                conn.execute(
                    "INSERT INTO chunks(version_id, chunk_id, position, chunk_json) VALUES (?, ?, ?, ?)",
                    (version_id, chunk_id, position, json_dumps(chunk)),
                )
            conn.execute(
                "UPDATE documents SET filename = ?, updated_at = ? WHERE document_id = ?",
                (filename, now, document_id),
            )
            if status == "active":
                conn.execute(
                    "UPDATE documents SET active_version_id = ?, updated_at = ? WHERE document_id = ?",
                    (version_id, now, document_id),
                )
            self._audit(conn, document_id, version_id, "version_created", {"status": status, "chunk_count": len(chunks)})
        return version_id

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()
        return self._row_dict(row)

    def list_documents(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
        return [dict(row) for row in rows]

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM document_versions WHERE version_id = ?", (version_id,)).fetchone()
        value = self._row_dict(row)
        if value:
            value["normalization"] = json.loads(value.pop("normalization_json"))
            value["validation"] = json.loads(value.pop("validation_json"))
            value["semantic"] = bool(value["semantic"])
        return value

    def list_versions(self, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version_id, document_id, filename, source_sha256, normalized_sha256, strategy, chunk_size, overlap, semantic, status, validation_json, created_at FROM document_versions WHERE document_id = ? ORDER BY created_at DESC",
                (document_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["semantic"] = bool(item["semantic"])
            item["validation"] = json.loads(item.pop("validation_json"))
            result.append(item)
        return result

    def get_active_version(self, document_id: str) -> dict[str, Any] | None:
        document = self.get_document(document_id)
        if not document or not document.get("active_version_id"):
            return None
        return self.get_version(document["active_version_id"])

    def get_chunks(self, version_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT chunk_json FROM chunks WHERE version_id = ? ORDER BY position ASC",
                (version_id,),
            ).fetchall()
        return [json.loads(row["chunk_json"]) for row in rows]

    def save_validation(self, version_id: str, report: dict[str, Any]) -> None:
        status = "validated" if report.get("passed") else "blocked"
        with self._connect() as conn:
            row = conn.execute("SELECT document_id FROM document_versions WHERE version_id = ?", (version_id,)).fetchone()
            if not row:
                raise KeyError(f"Unknown version_id: {version_id}")
            conn.execute(
                "UPDATE document_versions SET status = ?, validation_json = ? WHERE version_id = ?",
                (status, json_dumps(report), version_id),
            )
            self._audit(conn, row["document_id"], version_id, "candidate_validated", {"status": status, "passed": bool(report.get("passed"))})

    def publish_version(self, version_id: str) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as conn:
            candidate = conn.execute("SELECT * FROM document_versions WHERE version_id = ?", (version_id,)).fetchone()
            if not candidate:
                raise KeyError(f"Unknown version_id: {version_id}")
            if candidate["status"] != "validated":
                raise ValueError("Candidate must pass SafeSync validation before publication.")
            doc_id = candidate["document_id"]
            conn.execute(
                "UPDATE document_versions SET status = 'superseded' WHERE document_id = ? AND status = 'active'",
                (doc_id,),
            )
            conn.execute("UPDATE document_versions SET status = 'active' WHERE version_id = ?", (version_id,))
            conn.execute("UPDATE documents SET active_version_id = ?, updated_at = ? WHERE document_id = ?", (version_id, now, doc_id))
            self._audit(conn, doc_id, version_id, "version_published", {"source_sha256": candidate["source_sha256"]})
        return self.get_version(version_id) or {}

    def create_incident(
        self, *, document_id: str, version_id: str, failure_type: str, summary: str,
        config: dict[str, Any] | None = None, details: dict[str, Any] | None = None,
    ) -> str:
        incident_id = new_id("inc")
        with self._connect() as conn:
            version = conn.execute("SELECT document_id FROM document_versions WHERE version_id = ?", (version_id,)).fetchone()
            if not version or version["document_id"] != document_id:
                raise KeyError("The version does not belong to the specified document.")
            conn.execute(
                "INSERT INTO incidents(incident_id, document_id, version_id, failure_type, summary, status, config_json, details_json, created_at) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
                (incident_id, document_id, version_id, failure_type, summary, json_dumps(config or {}), json_dumps(details or {}), utc_now()),
            )
            self._audit(conn, document_id, version_id, "incident_created", {"incident_id": incident_id, "failure_type": failure_type})
        return incident_id

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        value = self._row_dict(row)
        if value:
            value["config"] = json.loads(value.pop("config_json"))
            value["details"] = json.loads(value.pop("details_json"))
        return value

    def list_incidents(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT incident_id, document_id, version_id, failure_type, summary, status, created_at FROM incidents ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
        return [dict(row) for row in rows]

    def save_replay_run(self, incident_id: str, result: dict[str, Any]) -> str:
        replay_id = new_id("replay")
        with self._connect() as conn:
            incident = conn.execute("SELECT document_id, version_id FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
            if not incident:
                raise KeyError(f"Unknown incident_id: {incident_id}")
            conn.execute(
                "INSERT INTO replay_runs(replay_id, incident_id, result_json, created_at) VALUES (?, ?, ?, ?)",
                (replay_id, incident_id, json_dumps(result), utc_now()),
            )
            if result.get("resolved") is True:
                conn.execute("UPDATE incidents SET status = 'resolved' WHERE incident_id = ?", (incident_id,))
            self._audit(conn, incident["document_id"], incident["version_id"], "incident_replayed", {"incident_id": incident_id, "replay_id": replay_id, "resolved": bool(result.get("resolved"))})
        return replay_id

    def list_replays(self, incident_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT replay_id, incident_id, result_json, created_at FROM replay_runs WHERE incident_id = ? ORDER BY created_at DESC", (incident_id,)).fetchall()
        return [{"replay_id": row["replay_id"], "incident_id": row["incident_id"], "result": json.loads(row["result_json"]), "created_at": row["created_at"]} for row in rows]

    @staticmethod
    def _audit(conn: sqlite3.Connection, document_id: str, version_id: str | None, event_type: str, details: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO audit_events(event_id, document_id, version_id, event_type, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (new_id("evt"), document_id, version_id, event_type, json_dumps(details), utc_now()),
        )


# Default store used by the FastAPI application. SMARTCHUNK_DATA_DIR can override its location.
STORE = SmartChunkStore()
