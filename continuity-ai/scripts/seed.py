"""Load the sample case into SQLite.  Usage: python -m scripts.seed"""
import json
import sys
from pathlib import Path

from app.core.config import ROOT
from app.database.connection import connect, init_db

SAMPLE = ROOT / "data" / "sample_conversations" / "aarav_double_charge.json"


def seed(conn, path: Path = SAMPLE) -> int:
    data = json.loads(Path(path).read_text())
    for a in data["agents"]:
        conn.execute("INSERT OR IGNORE INTO agents VALUES (?,?,?)", (a["agent_id"], a["name"], a["role"]))
    cur = conn.execute("INSERT INTO customers (name, email) VALUES (?,?)",
                       (data["customer"]["name"], data["customer"]["email"]))
    first_ts = data["interactions"][0]["timestamp"]
    last_ts = data["interactions"][-1]["messages"][-1]["timestamp"]
    c = data["case"]
    case = conn.execute(
        "INSERT INTO cases (customer_id, status, assigned_agent_id, transferred_from, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?)",
        (cur.lastrowid, c["status"], c["assigned_agent_id"], c.get("transferred_from"), first_ts, last_ts))
    case_id = case.lastrowid
    for inter in data["interactions"]:
        i = conn.execute("INSERT INTO interactions (case_id, agent_id, timestamp) VALUES (?,?,?)",
                         (case_id, inter["agent_id"], inter["timestamp"]))
        for m in inter["messages"]:
            conn.execute("INSERT INTO messages (interaction_id, speaker, content, timestamp) VALUES (?,?,?,?)",
                         (i.lastrowid, m["speaker"], m["content"], m["timestamp"]))
    conn.commit()
    return case_id


if __name__ == "__main__":
    conn = connect()
    init_db(conn)
    print("Seeded case", seed(conn))
