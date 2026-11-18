import sqlite3
from app.core.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
  customer_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT
);
CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT
);
CREATE TABLE IF NOT EXISTS cases (
  case_id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
  issue TEXT, status TEXT DEFAULT 'open',
  assigned_agent_id TEXT REFERENCES agents(agent_id),
  transferred_from TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS interactions (
  interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER NOT NULL REFERENCES cases(case_id),
  agent_id TEXT REFERENCES agents(agent_id), timestamp TEXT
);
CREATE TABLE IF NOT EXISTS messages (
  message_id INTEGER PRIMARY KEY AUTOINCREMENT,
  interaction_id INTEGER NOT NULL REFERENCES interactions(interaction_id),
  speaker TEXT NOT NULL CHECK (speaker IN ('customer','agent')),
  content TEXT NOT NULL, timestamp TEXT
);
CREATE TABLE IF NOT EXISTS case_memory (
  case_id INTEGER PRIMARY KEY REFERENCES cases(case_id),
  issue TEXT, summary TEXT, sentiment TEXT,
  concerns_json TEXT, troubleshooting_json TEXT, verify_json TEXT,
  evidence_coverage REAL, processed_at TEXT, last_message_id INTEGER
);
CREATE TABLE IF NOT EXISTS commitments (
  commitment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER NOT NULL REFERENCES cases(case_id),
  statement TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('promised','conditional','discussed','completed')),
  source_message_id INTEGER REFERENCES messages(message_id),
  quote TEXT, verified INTEGER DEFAULT 0, agent_id TEXT
);
CREATE TABLE IF NOT EXISTS actions (
  action_id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id INTEGER NOT NULL REFERENCES cases(case_id),
  description TEXT NOT NULL, status TEXT DEFAULT 'pending',
  assigned_agent TEXT, source_message_id INTEGER, verified INTEGER DEFAULT 0,
  action_key TEXT, source TEXT DEFAULT 'ai', completed_at TEXT, completed_by TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS checklist (
  case_id INTEGER NOT NULL REFERENCES cases(case_id), item_key TEXT NOT NULL,
  checked INTEGER DEFAULT 0, updated_by TEXT, updated_at TEXT, PRIMARY KEY (case_id, item_key)
);
CREATE TABLE IF NOT EXISTS events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL REFERENCES cases(case_id),
  event_type TEXT NOT NULL, detail TEXT, actor TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
  document_id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL, category TEXT, chunk_count INTEGER DEFAULT 0, uploaded_at TEXT
);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


MIGRATIONS = {
    "case_memory": [("last_message_id", "INTEGER")],
    "actions": [("action_key", "TEXT"), ("source", "TEXT DEFAULT 'ai'"), ("completed_at", "TEXT"),
                ("completed_by", "TEXT"), ("created_at", "TEXT")],
}


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # Lightweight migrations so databases created by earlier versions keep working.
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    conn.commit()


def get_db():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
