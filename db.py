import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional
import datetime as dt

DB_PATH = Path(__file__).parent / "finance.db"

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind TEXT CHECK(kind IN ('income','expense')) NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            '''
        )
        conn.commit()

def add_record(user_id: int, kind: str, category: str, amount: float, created_at: Optional[str] = None):
    if created_at is None:
        created_at = dt.datetime.utcnow().isoformat()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO records (user_id, kind, category, amount, created_at) VALUES (?,?,?,?,?)',
            (user_id, kind, category.strip(), float(amount), created_at)
        )
        conn.commit()

def get_records(user_id: int, start_iso: str, end_iso: str):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT kind, category, amount, created_at
            FROM records
            WHERE user_id = ? AND created_at >= ? AND created_at < ?
            ORDER BY created_at ASC
            """,
            (user_id, start_iso, end_iso)
        )
        rows = cur.fetchall()
    return rows
