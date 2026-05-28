import json
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timezone

DB_PATH = os.getenv("CAREER_AGENT_DB", "data/career_agent.db")
PASSWORD_ITERATIONS = 210_000


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_api_keys (
                user_id INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                title TEXT,
                company TEXT,
                source TEXT,
                payload TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scored_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                job_url TEXT,
                payload TEXT NOT NULL,
                scored_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tailor_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
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
                user_id INTEGER,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        _migrate_user_columns(conn)
        conn.commit()


def _migrate_user_columns(conn: sqlite3.Connection) -> None:
    """Add user_id to older local SQLite files created before auth existed."""
    for table in ["profiles", "jobs", "scored_jobs", "decisions", "tailor_drafts", "agent_runs"]:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "user_id" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return secrets.compare_digest(candidate.hex(), digest)
    except Exception:
        return False


def create_user(email: str, password: str, name: str = "") -> dict:
    init_db()
    clean_email = email.strip().lower()
    display_name = name.strip() or clean_email.split("@")[0]
    now = _now()
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (email, name, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_email, display_name, _hash_password(password), now, now),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("User already exists") from exc
    return {"id": cursor.lastrowid, "email": clean_email, "name": display_name}


def get_user_by_email(email: str) -> dict | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT id, email, name, created_at, updated_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def verify_user(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)
    if not user or not _verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


def save_user_api_keys(user_id: int, keys: dict) -> dict:
    init_db()
    current = load_user_api_keys(user_id, masked=False)
    merged = {**current, **{key: value for key, value in keys.items() if value}}
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_api_keys (user_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (user_id, json.dumps(merged, ensure_ascii=False), now),
        )
        conn.commit()
    return load_user_api_keys(user_id, masked=True)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def load_user_api_keys(user_id: int, masked: bool = False) -> dict:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT payload FROM user_api_keys WHERE user_id = ?", (user_id,)).fetchone()
    keys = json.loads(row["payload"]) if row else {}
    if masked:
        return {key: _mask(value) for key, value in keys.items()}
    return keys


def _upsert_singleton(conn: sqlite3.Connection, table: str, payload: dict, user_id: int | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    if user_id is None:
        conn.execute(f"DELETE FROM {table} WHERE user_id IS NULL")
    else:
        conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
    conn.execute(
        f"INSERT INTO {table} (user_id, payload, updated_at) VALUES (?, ?, ?)",
        (user_id, json.dumps(payload, ensure_ascii=False), now),
    )


def sync_pipeline_results(
    profile: dict,
    jobs: list,
    scored_jobs: list,
    decisions: dict,
    run_state: dict | None = None,
    user_id: int | None = None,
) -> None:
    """Mirror JSON pipeline outputs into SQLite for API/dashboard use."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        _upsert_singleton(conn, "profiles", profile, user_id=user_id)
        _upsert_singleton(conn, "decisions", decisions, user_id=user_id)

        if user_id is None:
            conn.execute("DELETE FROM jobs WHERE user_id IS NULL")
        else:
            conn.execute("DELETE FROM jobs WHERE user_id = ?", (user_id,))
        for job in jobs:
            conn.execute(
                """
                INSERT INTO jobs (user_id, url, title, company, source, payload, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    job.get("url"),
                    job.get("title"),
                    job.get("company"),
                    job.get("source"),
                    json.dumps(job, ensure_ascii=False),
                    now,
                ),
            )

        if user_id is None:
            conn.execute("DELETE FROM scored_jobs WHERE user_id IS NULL")
        else:
            conn.execute("DELETE FROM scored_jobs WHERE user_id = ?", (user_id,))
        for job in scored_jobs:
            conn.execute(
                """
                INSERT INTO scored_jobs (user_id, job_url, payload, scored_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    job.get("url"),
                    json.dumps(job, ensure_ascii=False),
                    now,
                ),
            )

        if run_state:
            conn.execute(
                "INSERT INTO agent_runs (user_id, payload, created_at) VALUES (?, ?, ?)",
                (user_id, json.dumps(run_state, ensure_ascii=False), now),
            )

        conn.commit()


def save_profile(profile: dict, user_id: int | None = None) -> None:
    """Persist the latest parsed profile without requiring a full pipeline run."""
    init_db()
    with get_connection() as conn:
        _upsert_singleton(conn, "profiles", profile, user_id=user_id)
        conn.commit()


def load_latest_profile(user_id: int | None = None) -> dict:
    init_db()
    with get_connection() as conn:
        if user_id is None:
            row = conn.execute("SELECT payload FROM profiles WHERE user_id IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        else:
            row = conn.execute("SELECT payload FROM profiles WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    return json.loads(row["payload"]) if row else {}


def load_latest_decisions(user_id: int | None = None) -> dict:
    init_db()
    with get_connection() as conn:
        if user_id is None:
            row = conn.execute("SELECT payload FROM decisions WHERE user_id IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        else:
            row = conn.execute("SELECT payload FROM decisions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    return json.loads(row["payload"]) if row else {}


def load_scored_jobs(user_id: int | None = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if user_id is None:
            rows = conn.execute("SELECT payload FROM scored_jobs WHERE user_id IS NULL ORDER BY scored_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT payload FROM scored_jobs WHERE user_id = ? ORDER BY scored_at DESC", (user_id,)).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def list_tailor_drafts(status: str | None = None, user_id: int | None = None) -> list[dict]:
    init_db()
    query = "SELECT * FROM tailor_drafts WHERE "
    params: tuple
    if user_id is None:
        query += "user_id IS NULL"
        params = ()
    else:
        query += "user_id = ?"
        params = (user_id,)
    if status:
        query += " AND status = ?"
        params = (*params, status)
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
    user_id: int | None = None,
) -> dict:
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        if draft_id:
            conn.execute(
                """
                UPDATE tailor_drafts
                SET draft_text = ?, status = ?, notes = ?, updated_at = ?
                WHERE id = ? AND (user_id IS ? OR user_id = ?)
                """,
                (draft_text, status, notes, now, draft_id, user_id, user_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO tailor_drafts
                (user_id, job_url, job_title, company, draft_text, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, job_url, job_title, company, draft_text, status, notes, now, now),
            )
            draft_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

    drafts = list_tailor_drafts(user_id=user_id)
    return next((item for item in drafts if item["id"] == draft_id), {})
