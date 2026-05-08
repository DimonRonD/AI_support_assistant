from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class SqliteStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_cache (
                    query TEXT PRIMARY KEY,
                    answer TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    hit_count INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_files (
                    filename TEXT PRIMARY KEY,
                    chunk_count INTEGER NOT NULL,
                    loaded_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_modes (
                    session_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL DEFAULT 'text'
                )
                """
            )

    def add_memory(self, session_id: str, role: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO memories(session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )

    def get_last_memories(self, session_id: str, limit: int = 5) -> list[dict[str, str]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM memories
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def clear_memory(self, session_id: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
        return cur.rowcount

    def set_mode(self, session_id: str, mode: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO chat_modes(session_id, mode) VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET mode = excluded.mode
                """,
                (session_id, mode),
            )

    def get_mode(self, session_id: str) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT mode FROM chat_modes WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row["mode"] if row else "text"

    def get_cached_answer(self, query: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT answer FROM query_cache WHERE query = ?",
                (query,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE query_cache SET hit_count = hit_count + 1 WHERE query = ?",
                (query,),
            )
            return row["answer"]

    def save_cache(self, query: str, answer: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO query_cache(query, answer) VALUES (?, ?)
                ON CONFLICT(query) DO UPDATE SET
                    answer = excluded.answer,
                    hit_count = query_cache.hit_count + 1
                """,
                (query, answer),
            )

    def clear_cache(self, max_hits: int | None, older_than: str | None) -> int:
        with self._conn() as conn:
            if max_hits is None and older_than is None:
                cur = conn.execute(
                    """
                    DELETE FROM query_cache
                    WHERE hit_count <= 1
                      AND datetime(created_at) <= datetime('now', '-3 months')
                    """
                )
                return cur.rowcount
            if max_hits is None or older_than is None:
                raise ValueError("Both max_hits and older_than must be provided together.")

            cur = conn.execute(
                """
                DELETE FROM query_cache
                WHERE hit_count < ?
                  AND datetime(created_at) < datetime(?)
                """,
                (max_hits, older_than),
            )
            return cur.rowcount

    def get_cache_rows(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT created_at, hit_count, query, answer
                FROM query_cache
                ORDER BY datetime(created_at) DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_rag_file(self, filename: str, chunk_count: int) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO rag_files(filename, chunk_count) VALUES (?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    chunk_count = excluded.chunk_count,
                    loaded_at = datetime('now')
                """,
                (filename, chunk_count),
            )

    def remove_rag_file(self, filename: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM rag_files WHERE filename = ?", (filename,))

    def get_rag_files(self) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute("SELECT filename, chunk_count FROM rag_files").fetchall()
        return {row["filename"]: row["chunk_count"] for row in rows}

    def clear_rag_files(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM rag_files")
