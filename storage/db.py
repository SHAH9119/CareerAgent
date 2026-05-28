import hashlib
import json
import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

PASSWORD_ITERATIONS = 210_000
SQLITE_PATH = os.getenv("CAREER_AGENT_DB", "data/career_agent.db")


def database_url() -> str:
    raw = os.getenv("DATABASE_URL") or os.getenv("CAREER_AGENT_DB_URL")
    if raw:
        if raw.startswith("postgresql://"):
            raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
        return raw
    return f"sqlite:///{SQLITE_PATH}"


def is_postgres() -> bool:
    return database_url().startswith("postgresql")


def get_engine():
    url = database_url()
    if url.startswith("sqlite"):
        os.makedirs(os.path.dirname(SQLITE_PATH) or ".", exist_ok=True)
        return create_engine(url, future=True, connect_args={"check_same_thread": False})
    return create_engine(url, future=True, pool_pre_ping=True, connect_args={"sslmode": "require"})


def _row_to_dict(row) -> dict | None:
    return dict(row._mapping) if row else None


def _scalar(row, key: str):
    return row._mapping[key] if row else None


def _id_column() -> str:
    return "SERIAL PRIMARY KEY" if is_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"


def init_db() -> None:
    id_col = _id_column()
    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id {id_col},
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_api_keys (
            user_id INTEGER PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS profiles (
            id {id_col},
            user_id INTEGER,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS jobs (
            id {id_col},
            user_id INTEGER,
            url TEXT,
            title TEXT,
            company TEXT,
            source TEXT,
            payload TEXT NOT NULL,
            collected_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS scored_jobs (
            id {id_col},
            user_id INTEGER,
            job_url TEXT,
            payload TEXT NOT NULL,
            scored_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS decisions (
            id {id_col},
            user_id INTEGER,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS tailor_drafts (
            id {id_col},
            user_id INTEGER,
            job_url TEXT NOT NULL,
            job_title TEXT,
            company TEXT,
            draft_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS agent_runs (
            id {id_col},
            user_id INTEGER,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
    ]

    engine = get_engine()
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        if not is_postgres():
            _migrate_sqlite_user_columns(conn)


def _migrate_sqlite_user_columns(conn) -> None:
    for table in ["profiles", "jobs", "scored_jobs", "decisions", "tailor_drafts", "agent_runs"]:
        columns = {row._mapping["name"] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
        if "user_id" not in columns:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"))


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
    engine = get_engine()
    with engine.begin() as conn:
        try:
            result = conn.execute(
                text(
                    """
                    INSERT INTO users (email, name, password_hash, created_at, updated_at)
                    VALUES (:email, :name, :password_hash, :created_at, :updated_at)
                    """
                    + (" RETURNING id" if is_postgres() else "")
                ),
                {
                    "email": clean_email,
                    "name": display_name,
                    "password_hash": _hash_password(password),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            user_id = result.scalar_one() if is_postgres() else result.lastrowid
        except IntegrityError as exc:
            raise ValueError("User already exists") from exc
    return {"id": user_id, "email": clean_email, "name": display_name}


def get_user_by_email(email: str) -> dict | None:
    init_db()
    with get_engine().begin() as conn:
        row = conn.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": email.strip().lower()},
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_id(user_id: int) -> dict | None:
    init_db()
    with get_engine().begin() as conn:
        row = conn.execute(
            text("SELECT id, email, name, created_at, updated_at FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
    return _row_to_dict(row)


def verify_user(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)
    if not user or not _verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


def save_user_api_keys(user_id: int, keys: dict) -> dict:
    init_db()
    current = load_user_api_keys(user_id, masked=False)
    merged = {**current, **{key: value for key, value in keys.items() if value}}
    with get_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO user_api_keys (user_id, payload, updated_at)
                VALUES (:user_id, :payload, :updated_at)
                ON CONFLICT(user_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """
            ),
            {"user_id": user_id, "payload": json.dumps(merged, ensure_ascii=False), "updated_at": _now()},
        )
    return load_user_api_keys(user_id, masked=True)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def load_user_api_keys(user_id: int, masked: bool = False) -> dict:
    init_db()
    with get_engine().begin() as conn:
        row = conn.execute(
            text("SELECT payload FROM user_api_keys WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
    keys = json.loads(_scalar(row, "payload")) if row else {}
    if masked:
        return {key: _mask(value) for key, value in keys.items()}
    return keys


def _user_clause(user_id: int | None) -> tuple[str, dict]:
    if user_id is None:
        return "user_id IS NULL", {}
    return "user_id = :user_id", {"user_id": user_id}


def _upsert_singleton(conn, table: str, payload: dict, user_id: int | None = None) -> None:
    clause, params = _user_clause(user_id)
    conn.execute(text(f"DELETE FROM {table} WHERE {clause}"), params)
    conn.execute(
        text(f"INSERT INTO {table} (user_id, payload, updated_at) VALUES (:user_id, :payload, :updated_at)"),
        {"user_id": user_id, "payload": json.dumps(payload, ensure_ascii=False), "updated_at": _now()},
    )


def sync_pipeline_results(
    profile: dict,
    jobs: list,
    scored_jobs: list,
    decisions: dict,
    run_state: dict | None = None,
    user_id: int | None = None,
) -> None:
    init_db()
    now = _now()
    clause, params = _user_clause(user_id)

    with get_engine().begin() as conn:
        _upsert_singleton(conn, "profiles", profile, user_id=user_id)
        _upsert_singleton(conn, "decisions", decisions, user_id=user_id)

        conn.execute(text(f"DELETE FROM jobs WHERE {clause}"), params)
        for job in jobs:
            conn.execute(
                text(
                    """
                    INSERT INTO jobs (user_id, url, title, company, source, payload, collected_at)
                    VALUES (:user_id, :url, :title, :company, :source, :payload, :collected_at)
                    """
                ),
                {
                    "user_id": user_id,
                    "url": job.get("url"),
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "source": job.get("source"),
                    "payload": json.dumps(job, ensure_ascii=False),
                    "collected_at": now,
                },
            )

        conn.execute(text(f"DELETE FROM scored_jobs WHERE {clause}"), params)
        for job in scored_jobs:
            conn.execute(
                text(
                    """
                    INSERT INTO scored_jobs (user_id, job_url, payload, scored_at)
                    VALUES (:user_id, :job_url, :payload, :scored_at)
                    """
                ),
                {
                    "user_id": user_id,
                    "job_url": job.get("url"),
                    "payload": json.dumps(job, ensure_ascii=False),
                    "scored_at": now,
                },
            )

        if run_state:
            conn.execute(
                text("INSERT INTO agent_runs (user_id, payload, created_at) VALUES (:user_id, :payload, :created_at)"),
                {"user_id": user_id, "payload": json.dumps(run_state, ensure_ascii=False), "created_at": now},
            )


def save_profile(profile: dict, user_id: int | None = None) -> None:
    init_db()
    with get_engine().begin() as conn:
        _upsert_singleton(conn, "profiles", profile, user_id=user_id)


def load_latest_profile(user_id: int | None = None) -> dict:
    init_db()
    clause, params = _user_clause(user_id)
    with get_engine().begin() as conn:
        row = conn.execute(text(f"SELECT payload FROM profiles WHERE {clause} ORDER BY id DESC LIMIT 1"), params).fetchone()
    return json.loads(_scalar(row, "payload")) if row else {}


def load_latest_decisions(user_id: int | None = None) -> dict:
    init_db()
    clause, params = _user_clause(user_id)
    with get_engine().begin() as conn:
        row = conn.execute(text(f"SELECT payload FROM decisions WHERE {clause} ORDER BY id DESC LIMIT 1"), params).fetchone()
    return json.loads(_scalar(row, "payload")) if row else {}


def load_scored_jobs(user_id: int | None = None) -> list[dict]:
    init_db()
    clause, params = _user_clause(user_id)
    with get_engine().begin() as conn:
        rows = conn.execute(text(f"SELECT payload FROM scored_jobs WHERE {clause} ORDER BY scored_at DESC"), params).fetchall()
    return [json.loads(row._mapping["payload"]) for row in rows]


def list_tailor_drafts(status: str | None = None, user_id: int | None = None) -> list[dict]:
    init_db()
    clause, params = _user_clause(user_id)
    if status:
        clause += " AND status = :status"
        params = {**params, "status": status}
    with get_engine().begin() as conn:
        rows = conn.execute(text(f"SELECT * FROM tailor_drafts WHERE {clause} ORDER BY updated_at DESC"), params).fetchall()
    return [_row_to_dict(row) for row in rows]


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
    now = _now()
    with get_engine().begin() as conn:
        if draft_id:
            clause, params = _user_clause(user_id)
            conn.execute(
                text(
                    f"""
                    UPDATE tailor_drafts
                    SET draft_text = :draft_text, status = :status, notes = :notes, updated_at = :updated_at
                    WHERE id = :draft_id AND {clause}
                    """
                ),
                {
                    **params,
                    "draft_text": draft_text,
                    "status": status,
                    "notes": notes,
                    "updated_at": now,
                    "draft_id": draft_id,
                },
            )
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO tailor_drafts
                    (user_id, job_url, job_title, company, draft_text, status, notes, created_at, updated_at)
                    VALUES (:user_id, :job_url, :job_title, :company, :draft_text, :status, :notes, :created_at, :updated_at)
                    """
                    + (" RETURNING id" if is_postgres() else "")
                ),
                {
                    "user_id": user_id,
                    "job_url": job_url,
                    "job_title": job_title,
                    "company": company,
                    "draft_text": draft_text,
                    "status": status,
                    "notes": notes,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            draft_id = result.scalar_one() if is_postgres() else result.lastrowid

    drafts = list_tailor_drafts(user_id=user_id)
    return next((item for item in drafts if item["id"] == draft_id), {})
