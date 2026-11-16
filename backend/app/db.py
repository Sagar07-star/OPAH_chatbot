"""SQLite storage for conversations, working memory, uploads and support stubs.

The mock kit's JSON dataset remains the business-data source of truth; SQLite
holds the assistant's own persistent state.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    project_id TEXT,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_scope
    ON conversations(client_id, IFNULL(project_id, ''));

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    envelope TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS working_memory (
    client_id TEXT NOT NULL,
    project_id TEXT NOT NULL DEFAULT '',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (client_id, project_id, key)
);

CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    pages INTEGER,
    path TEXT NOT NULL,
    extracted_text TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_uploads_client ON uploads(client_id, created_at);

CREATE TABLE IF NOT EXISTS support_tickets (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    category TEXT NOT NULL,
    body TEXT NOT NULL,
    diagnosis TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    stub INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS app_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    route TEXT NOT NULL,
    message TEXT NOT NULL,
    status INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anon_usage (
    session_key TEXT PRIMARY KEY,
    messages INTEGER NOT NULL DEFAULT 0,
    uploads INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
