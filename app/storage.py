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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dialogues (
                    session_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'active',
                    controlled_by TEXT NOT NULL DEFAULT 'ai',
                    rating INTEGER,
                    comment TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    closed_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dialogue_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS synonyms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical TEXT NOT NULL,
                    synonym TEXT NOT NULL,
                    UNIQUE(canonical, synonym)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_users (
                    email TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_sessions (
                    session_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    last_auth_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
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

    def ensure_dialogue(self, session_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO dialogues(session_id) VALUES (?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id,),
            )

    def append_dialogue_message(self, session_id: str, actor: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO dialogue_messages(session_id, actor, content)
                VALUES (?, ?, ?)
                """,
                (session_id, actor, content),
            )
            conn.execute(
                "UPDATE dialogues SET updated_at = datetime('now') WHERE session_id = ?",
                (session_id,),
            )

    def set_controller(self, session_id: str, controlled_by: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE dialogues
                SET controlled_by = ?, updated_at = datetime('now')
                WHERE session_id = ?
                """,
                (controlled_by, session_id),
            )

    def get_dialogue(self, session_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT session_id, status, controlled_by, rating, comment, created_at, updated_at, closed_at
                FROM dialogues
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def close_dialogue(self, session_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE dialogues
                SET status = 'closed',
                    controlled_by = 'support',
                    closed_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE session_id = ?
                """,
                (session_id,),
            )

    def set_rating(self, session_id: str, rating: int) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE dialogues
                SET rating = ?, updated_at = datetime('now')
                WHERE session_id = ?
                """,
                (rating, session_id),
            )

    def set_comment(self, session_id: str, comment: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE dialogues
                SET comment = ?, updated_at = datetime('now')
                WHERE session_id = ?
                """,
                (comment, session_id),
            )

    def list_active_dialogues(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT session_id, status, controlled_by, rating, comment, created_at, updated_at, closed_at
                FROM dialogues
                ORDER BY datetime(updated_at) DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_dialogue_messages(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, actor, content, created_at
                FROM dialogue_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_support_messages(self, session_id: str, after_id: int = 0) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, actor, content, created_at
                FROM dialogue_messages
                WHERE session_id = ?
                  AND actor = 'support'
                  AND id > ?
                ORDER BY id ASC
                """,
                (session_id, after_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_themes(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT name FROM themes ORDER BY name ASC").fetchall()
        return [row["name"] for row in rows]

    def add_theme(self, name: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO themes(name) VALUES (?)",
                (name,),
            )

    def remove_theme(self, name: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM themes WHERE name = ?", (name,))
        return cur.rowcount

    def clear_themes(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM themes")

    def list_synonyms(self) -> dict[str, list[str]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT canonical, synonym FROM synonyms ORDER BY canonical ASC, synonym ASC"
            ).fetchall()
        result: dict[str, list[str]] = {}
        for row in rows:
            result.setdefault(row["canonical"], []).append(row["synonym"])
        return result

    def add_synonym(self, canonical: str, synonym: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO synonyms(canonical, synonym) VALUES (?, ?)",
                (canonical, synonym),
            )

    def remove_synonym_group(self, canonical: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM synonyms WHERE canonical = ?", (canonical,))
        return cur.rowcount

    def clear_synonyms(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM synonyms")

    def auth_user(self, session_id: str, name: str, email: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO api_users(email, name) VALUES (?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name = excluded.name,
                    updated_at = datetime('now')
                """,
                (email, name),
            )
            conn.execute(
                """
                INSERT INTO api_sessions(session_id, email, name) VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    email = excluded.email,
                    name = excluded.name,
                    last_auth_at = datetime('now')
                """,
                (session_id, email, name),
            )
            conn.execute(
                "INSERT INTO auth_logs(session_id, email, name) VALUES (?, ?, ?)",
                (session_id, email, name),
            )

    def is_authorized_session(self, session_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM api_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row is not None

    def get_previous_session(self, session_id: str) -> str | None:
        with self._conn() as conn:
            current = conn.execute(
                "SELECT email FROM api_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if current is None:
                return None
            row = conn.execute(
                """
                SELECT session_id
                FROM api_sessions
                WHERE email = ? AND session_id != ?
                ORDER BY datetime(last_auth_at) DESC
                LIMIT 1
                """,
                (current["email"], session_id),
            ).fetchone()
        return row["session_id"] if row else None

    def clear_session_history(self, session_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM dialogue_messages WHERE session_id = ?", (session_id,))
            conn.execute(
                """
                UPDATE dialogues
                SET status = 'active',
                    controlled_by = 'ai',
                    rating = NULL,
                    comment = NULL,
                    closed_at = NULL,
                    updated_at = datetime('now')
                WHERE session_id = ?
                """,
                (session_id,),
            )

    def list_log_dates(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT date(created_at) AS log_date
                FROM dialogue_messages
                ORDER BY log_date DESC
                """
            ).fetchall()
        return [row["log_date"] for row in rows if row["log_date"]]

    def get_log_rows_for_date(
        self,
        date_value: str,
        session_id: str | None = None,
        email: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            base_query = """
                SELECT
                    date(um.created_at) AS msg_date,
                    time(um.created_at) AS msg_time,
                    COALESCE(s.name, um.session_id) AS user_name,
                    COALESCE(s.email, '') AS email,
                    um.content AS question,
                    COALESCE((
                        SELECT dm2.content
                        FROM dialogue_messages dm2
                        WHERE dm2.session_id = um.session_id
                          AND dm2.id > um.id
                          AND dm2.actor IN ('ai', 'support')
                        ORDER BY dm2.id ASC
                        LIMIT 1
                    ), '') AS answer,
                    COALESCE((
                        SELECT dm2.actor
                        FROM dialogue_messages dm2
                        WHERE dm2.session_id = um.session_id
                          AND dm2.id > um.id
                          AND dm2.actor IN ('ai', 'support')
                        ORDER BY dm2.id ASC
                        LIMIT 1
                    ), '') AS answer_actor,
                    COALESCE(d.rating, '') AS rating,
                    COALESCE(d.comment, '') AS comment
                FROM dialogue_messages um
                LEFT JOIN api_sessions s ON s.session_id = um.session_id
                LEFT JOIN dialogues d ON d.session_id = um.session_id
                WHERE um.actor = 'user'
                  AND date(um.created_at) = date(?)
            """
            params: list[Any] = [date_value]
            if session_id:
                base_query += " AND um.session_id = ?"
                params.append(session_id)
            if email:
                base_query += " AND lower(COALESCE(s.email, '')) = lower(?)"
                params.append(email.strip())
            base_query += " ORDER BY um.created_at ASC"
            rows = conn.execute(base_query, params).fetchall()
        return [dict(row) for row in rows]
