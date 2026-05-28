import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("CAREER_AGENT_DB", "data/career_agent.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                company TEXT,
                source TEXT,
                payload TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scored_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT,
                payload TEXT NOT NULL,
                scored_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tailor_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT NOT NULL,
                job_title TEXT,
                company TEXT,
                draft_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def _upsert_singleton(conn: sqlite3.Connection, table: str, payload: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(f"DELETE FROM {table}")
    conn.execute(
        f"INSERT INTO {table} (payload, updated_at) VALUES (?, ?)",
        (json.dumps(payload, ensure_ascii=False), now),
    )


def sync_pipeline_results(
    profile: dict,
    jobs: list,
    scored_jobs: list,
    decisions: dict,
    run_state: dict | None = None,
) -> None:
    """Mirror JSON pipeline outputs into SQLite for API/dashboard use."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        _upsert_singleton(conn, "profiles", profile)
        _upsert_singleton(conn, "decisions", decisions)

        conn.execute("DELETE FROM jobs")
        for job in jobs:
            conn.execute(
                """
                INSERT INTO jobs (url, title, company, source, payload, collected_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job.get("url"),
                    job.get("title"),
                    job.get("company"),
                    job.get("source"),
                    json.dumps(job, ensure_ascii=False),
                    now,
                ),
            )

        conn.execute("DELETE FROM scored_jobs")
        for job in scored_jobs:
            conn.execute(
                """
                INSERT INTO scored_jobs (job_url, payload, scored_at)
                VALUES (?, ?, ?)
                """,
                (
                    job.get("url"),
                    json.dumps(job, ensure_ascii=False),
                    now,
                ),
            )

        if run_state:
            conn.execute(
                "INSERT INTO agent_runs (payload, created_at) VALUES (?, ?)",
                (json.dumps(run_state, ensure_ascii=False), now),
            )

        conn.commit()


def save_profile(profile: dict) -> None:
    """Persist the latest parsed profile without requiring a full pipeline run."""
    init_db()
    with get_connection() as conn:
        _upsert_singleton(conn, "profiles", profile)
        conn.commit()


def load_latest_profile() -> dict:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT payload FROM profiles ORDER BY id DESC LIMIT 1").fetchone()
    return json.loads(row["payload"]) if row else {}


def load_latest_decisions() -> dict:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT payload FROM decisions ORDER BY id DESC LIMIT 1").fetchone()
    return json.loads(row["payload"]) if row else {}


def list_tailor_drafts(status: str | None = None) -> list[dict]:
    init_db()
    query = "SELECT * FROM tailor_drafts"
    params: tuple = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY updated_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def save_tailor_draft(
    job_url: str,
    job_title: str,
    company: str,
    draft_text: str,
    status: str = "draft",
    notes: str = "",
    draft_id: int | None = None,
) -> dict:
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        if draft_id:
            conn.execute(
                """
                UPDATE tailor_drafts
                SET draft_text = ?, status = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (draft_text, status, notes, now, draft_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO tailor_drafts
                (job_url, job_title, company, draft_text, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_url, job_title, company, draft_text, status, notes, now, now),
            )
            draft_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

    drafts = list_tailor_drafts()
    return next((item for item in drafts if item["id"] == draft_id), {})
