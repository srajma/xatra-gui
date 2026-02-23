import sys
import os
from pathlib import Path
import json
import traceback
import threading
import multiprocessing
import signal
import ast
import re
import io
import time
import tokenize
import sqlite3
import secrets
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from collections import OrderedDict, defaultdict

# Set matplotlib backend to Agg before importing anything else
import matplotlib
matplotlib.use('Agg')

# Add src to path so we can import xatra
sys.path.append(str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, HTTPException, Body, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any, Dict, Union

import xatra
from xatra.loaders import gadm, naturalearth, polygon, GADM_DIR
from xatra.render import export_html_string
from xatra.colorseq import Color, ColorSequence, LinearColorSequence, color_sequences
from xatra.icon import Icon

# Track one rendering process per task type so independent map generation can be cancelled safely.
current_processes: Dict[str, multiprocessing.Process] = {}
process_lock = threading.Lock()
render_cache_lock = threading.Lock()
RENDER_CACHE_MAX_ENTRIES = 24
render_cache = OrderedDict()

# Simple in-memory rate limiter (IP-keyed, sliding window)
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()

def _check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Raise HTTP 429 if this key has exceeded `limit` requests in `window_seconds`."""
    now = time.time()
    cutoff = now - window_seconds
    with _rate_limit_lock:
        timestamps = _rate_limit_store[key]
        timestamps[:] = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
        timestamps.append(now)

# Lock protecting GADM index globals against concurrent mutation from background thread
_gadm_lock = threading.Lock()

MAX_ARTIFACT_BYTES = 10 * 1024 * 1024  # 10 MB per-artifact content size limit

GADM_INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gadm_index.json")

HUB_DB_PATH = Path(__file__).parent / "xatra_hub.db"
HUB_NAME_PATTERN = re.compile(r"^[a-z0-9_.]+$")
HUB_USER_PATTERN = re.compile(r"^[a-z0-9_.-]+$")
HUB_KINDS = {"map", "lib", "css"}
GUEST_USERNAME = os.environ.get("XATRA_GUEST_USERNAME", "guest")
ANONYMOUS_USERNAME = os.environ.get("XATRA_ANONYMOUS_USERNAME", "anonymous")
ADMIN_USERNAME = os.environ.get("XATRA_ADMIN_USERNAME", "srajma")
ADMIN_PASSWORD_ENV = os.environ.get("XATRA_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
FRONTEND_PORT = int(os.environ.get("XATRA_FRONTEND_PORT", "5188"))
FRONTEND_PREVIEW_PORT = int(os.environ.get("XATRA_FRONTEND_PREVIEW_PORT", "4173"))
HUB_RESERVED_USERNAMES = {
    GUEST_USERNAME,
    ANONYMOUS_USERNAME,
    "admin",
    "explore",
    "users",
    "login",
    "logout",
    "new-map",
    "new_map",
    "map",
    "lib",
    "css",
    "user",
    "hub",
    "auth",
    "registry",
    "render",
    "sync",
    "health",
    "stop",
    "search",
    "docs",
    "redoc",
    "openapi.json",
    "favicon.ico",
}
SESSION_COOKIE = "xatra_session"
GUEST_COOKIE = "xatra_guest"
SESSION_TTL_DAYS = 30


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hub_db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(HUB_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _normalize_hub_name(name: str) -> str:
    cleaned = str(name or "").strip()
    if not HUB_NAME_PATTERN.fullmatch(cleaned):
        raise HTTPException(status_code=400, detail="Name must match ^[a-z0-9_.]+$")
    return cleaned


def _normalize_hub_user(username: str, allow_reserved: bool = False) -> str:
    cleaned = str(username or "").strip().lower()
    if not HUB_USER_PATTERN.fullmatch(cleaned):
        raise HTTPException(status_code=400, detail="Username must match ^[a-z0-9_.-]+$")
    if not allow_reserved and cleaned in HUB_RESERVED_USERNAMES:
        raise HTTPException(status_code=400, detail=f"Username '{cleaned}' is reserved")
    return cleaned


def _normalize_hub_kind(kind: str) -> str:
    cleaned = str(kind or "").strip().lower()
    if cleaned not in HUB_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {sorted(HUB_KINDS)}")
    return cleaned


def _json_text(value: Any) -> str:
    if value is None:
        return "{}"
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except Exception:
            return json.dumps({"value": value})
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return "{}"


def _json_parse(value: Any, default: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _artifact_metadata_dict(metadata: Any) -> Dict[str, Any]:
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str):
        parsed = _json_parse(metadata, {})
        if isinstance(parsed, dict):
            return dict(parsed)
    return {}


def _sanitize_artifact_metadata(kind: str, metadata: Any) -> Dict[str, Any]:
    cleaned = _artifact_metadata_dict(metadata)
    if _normalize_hub_kind(kind) == "map":
        cleaned.pop("description", None)
    return cleaned


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), 600000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def _territory_library_seed_code() -> str:
    """
    Load xatra.territory_library source from ../xatra.master and drop import lines.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / "xatra.master" / "src" / "xatra" / "territory_library.py",
        Path(__file__).resolve().parent / "src" / "xatra" / "territory_library.py",
    ]
    raw = ""
    for p in candidates:
        if p.exists():
            try:
                raw = p.read_text(encoding="utf-8")
                break
            except Exception:
                continue
    if not raw:
        return ""
    out_lines: List[str] = []
    for line in raw.splitlines():
        if re.match(r"^\s*(from\s+\S+\s+import\s+|import\s+)", line):
            continue
        out_lines.append(line)
    return ("\n".join(out_lines).strip() + "\n") if out_lines else ""


def _verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not isinstance(password_hash, str) or "$" not in password_hash:
        return False
    try:
        algo, salt, digest = password_hash.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), 600000).hex()
        return hmac.compare_digest(calc, digest)
    except Exception:
        return False


def _init_hub_db():
    conn = _hub_db_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hub_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                full_name TEXT NOT NULL DEFAULT '',
                bio TEXT NOT NULL DEFAULT '',
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hub_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES hub_users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                alpha_content TEXT NOT NULL DEFAULT '',
                alpha_metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, kind, name)
            );

            CREATE TABLE IF NOT EXISTS hub_artifact_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id INTEGER NOT NULL REFERENCES hub_artifacts(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(artifact_id, version)
            );

            CREATE TABLE IF NOT EXISTS hub_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES hub_users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hub_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id INTEGER NOT NULL REFERENCES hub_artifacts(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES hub_users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                UNIQUE(artifact_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS hub_map_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_id INTEGER NOT NULL REFERENCES hub_artifacts(id) ON DELETE CASCADE,
                viewer_key TEXT NOT NULL,
                viewed_at TEXT NOT NULL,
                UNIQUE(artifact_id, viewer_key)
            );

            CREATE TABLE IF NOT EXISTS hub_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_key TEXT NOT NULL UNIQUE,
                project_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_hub_artifacts_lookup ON hub_artifacts(user_id, kind, name);
            CREATE INDEX IF NOT EXISTS idx_hub_artifacts_kind_name ON hub_artifacts(kind, name);
            CREATE INDEX IF NOT EXISTS idx_hub_versions_artifact ON hub_artifact_versions(artifact_id, version);
            CREATE INDEX IF NOT EXISTS idx_hub_sessions_user ON hub_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_hub_votes_artifact ON hub_votes(artifact_id);
            CREATE INDEX IF NOT EXISTS idx_hub_views_artifact ON hub_map_views(artifact_id);
            """
        )
        # Schema migration: move from UNIQUE(user_id, kind, name) to UNIQUE(kind, name).
        schema_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='hub_artifacts'"
        ).fetchone()
        if schema_row and 'UNIQUE(kind, name)' not in (schema_row['sql'] or ''):
            _migrate_to_global_names(conn)
        # Lightweight migration for existing DBs.
        existing_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(hub_users)").fetchall()
        }
        if "password_hash" not in existing_cols:
            conn.execute("ALTER TABLE hub_users ADD COLUMN password_hash TEXT")
        if "full_name" not in existing_cols:
            conn.execute("ALTER TABLE hub_users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
        if "bio" not in existing_cols:
            conn.execute("ALTER TABLE hub_users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")
        if "is_admin" not in existing_cols:
            conn.execute("ALTER TABLE hub_users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")

        # Ensure default admin account exists.
        now = _utc_now_iso()
        admin_password = ADMIN_PASSWORD_ENV or secrets.token_urlsafe(16)
        result = conn.execute(
            """
            INSERT OR IGNORE INTO hub_users(username, password_hash, full_name, bio, is_admin, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (ADMIN_USERNAME, _hash_password(admin_password), ADMIN_USERNAME, "", 1, now),
        )
        if result.rowcount > 0:
            print(f"[xatra] Admin account '{ADMIN_USERNAME}' created. Password: {admin_password}")
            print("[xatra] Set XATRA_ADMIN_PASSWORD env var to configure this at startup, or change it after first login.")
        # Seed default public territory library.
        user_row = conn.execute("SELECT id FROM hub_users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        if user_row is not None:
            territory_seed = _territory_library_seed_code()
            seed_content = json.dumps({
                "predefined_code": territory_seed or "from xatra.territory_library import *\n",
                "map_name": "dtl",
                "description": "Default territory library",
            })
            conn.execute(
                """
                INSERT OR IGNORE INTO hub_artifacts(user_id, kind, name, alpha_content, alpha_metadata, created_at, updated_at)
                VALUES(?, 'lib', 'dtl', ?, ?, ?, ?)
                """,
                (user_row["id"], seed_content, json.dumps({"description": "Default territory library"}), now, now),
            )
            # Refresh lib 'dtl' if it still has placeholder/import-only content.
            existing_lib = conn.execute(
                """
                SELECT id, alpha_content, alpha_metadata
                FROM hub_artifacts
                WHERE kind = 'lib' AND name = 'dtl'
                """,
            ).fetchone()
            if existing_lib is not None and territory_seed.strip():
                try:
                    parsed_lib = _json_parse(existing_lib["alpha_content"], {})
                    old_pre = str(parsed_lib.get("predefined_code") or "")
                    meta = _json_parse(existing_lib["alpha_metadata"], {})
                    placeholderish = (
                        ('xatrahub(' in old_pre)
                        or old_pre.strip() in {"", "from xatra.territory_library import *"}
                        or str(meta.get("description", "")) in ("Default Indic territory library", "Default territory library")
                    )
                    if placeholderish:
                        parsed_lib["predefined_code"] = territory_seed
                        parsed_lib["map_name"] = "dtl"
                        conn.execute(
                            "UPDATE hub_artifacts SET alpha_content = ?, updated_at = ? WHERE id = ?",
                            (json.dumps(parsed_lib, ensure_ascii=False), now, existing_lib["id"]),
                        )
                except Exception:
                    pass
            # Seed default public map 'indic' if missing (uses new /lib/dtl/alpha import path).
            map_seed_content = json.dumps({
                "imports_code": 'indic = xatrahub("/lib/dtl/alpha")\n',
                "theme_code": "",
                "predefined_code": territory_seed,
                "map_code": 'import xatra\nxatra.TitleBox("<b>Indic Map</b>")\n',
                "runtime_code": "",
                "project": {
                    "elements": [],
                    "options": {
                        "basemaps": [{"url_or_provider": "Esri.WorldTopoMap", "default": True}],
                        "flag_color_sequences": [{"class_name": "", "colors": "", "step_h": 1.6180339887, "step_s": 0.0, "step_l": 0.0}],
                        "admin_color_sequences": [{"colors": "", "step_h": 1.6180339887, "step_s": 0.0, "step_l": 0.0}],
                        "data_colormap": {"type": "LinearSegmented", "colors": "yellow,orange,red"},
                    },
                    "predefinedCode": territory_seed,
                    "importsCode": 'indic = xatrahub("/lib/dtl/alpha")\n',
                    "themeCode": "",
                    "runtimeCode": "",
                },
            })
            conn.execute(
                """
                INSERT OR IGNORE INTO hub_artifacts(user_id, kind, name, alpha_content, alpha_metadata, created_at, updated_at)
                VALUES(?, 'map', 'indic', ?, ?, ?, ?)
                """,
                (user_row["id"], map_seed_content, json.dumps({}), now, now),
            )
            # Refresh indic map predefined_code if it was left empty.
            existing_map = conn.execute(
                "SELECT id, alpha_content FROM hub_artifacts WHERE kind = 'map' AND name = 'indic'"
            ).fetchone()
            if existing_map is not None:
                try:
                    parsed = _json_parse(existing_map["alpha_content"], {})
                    old_pre = str(parsed.get("predefined_code") or "")
                    old_project_pre = str((parsed.get("project") or {}).get("predefinedCode") or "")
                    defaultish = (not old_pre.strip() and not old_project_pre.strip())
                    if defaultish and territory_seed.strip():
                        parsed["predefined_code"] = territory_seed
                        project = parsed.get("project")
                        if not isinstance(project, dict):
                            project = {}
                        project["predefinedCode"] = territory_seed
                        parsed["project"] = project
                        conn.execute(
                            "UPDATE hub_artifacts SET alpha_content = ?, updated_at = ? WHERE id = ?",
                            (json.dumps(parsed, ensure_ascii=False), now, existing_map["id"]),
                        )
                except Exception:
                    pass
        # Migration: maps no longer support descriptions; strip description keys from stored metadata.
        map_rows = conn.execute(
            "SELECT id, alpha_metadata FROM hub_artifacts WHERE kind = 'map'"
        ).fetchall()
        for row in map_rows:
            meta = _sanitize_artifact_metadata("map", row["alpha_metadata"])
            conn.execute(
                "UPDATE hub_artifacts SET alpha_metadata = ? WHERE id = ?",
                (_json_text(meta), row["id"]),
            )
        map_version_rows = conn.execute(
            """
            SELECT v.id, v.metadata
            FROM hub_artifact_versions v
            JOIN hub_artifacts a ON a.id = v.artifact_id
            WHERE a.kind = 'map'
            """
        ).fetchall()
        for row in map_version_rows:
            meta = _sanitize_artifact_metadata("map", row["metadata"])
            conn.execute(
                "UPDATE hub_artifact_versions SET metadata = ? WHERE id = ?",
                (_json_text(meta), row["id"]),
            )
        # Ensure the anonymous user exists (for disassociated artifacts).
        conn.execute(
            "INSERT OR IGNORE INTO hub_users(username, created_at) VALUES(?, ?)",
            (ANONYMOUS_USERNAME, _utc_now_iso()),
        )
        # Backfill owner votes for any map missing its canonical self-vote.
        conn.execute(
            """
            INSERT OR IGNORE INTO hub_votes(artifact_id, user_id, created_at)
            SELECT a.id, a.user_id, ?
            FROM hub_artifacts a
            WHERE a.kind = 'map'
            """,
            (_utc_now_iso(),),
        )
        # Purge stale guest drafts (older than 90 days).
        conn.execute(
            """
            DELETE FROM hub_drafts
            WHERE owner_key LIKE 'guest:%'
              AND updated_at < datetime('now', '-90 days')
            """
        )
        conn.commit()
    finally:
        conn.close()


def _hub_ensure_user(conn: sqlite3.Connection, username: str) -> sqlite3.Row:
    cleaned = str(username or "").strip().lower()
    username = _normalize_hub_user(username, allow_reserved=(cleaned in (GUEST_USERNAME, ANONYMOUS_USERNAME)))
    now = _utc_now_iso()
    conn.execute(
        "INSERT OR IGNORE INTO hub_users(username, created_at) VALUES(?, ?)",
        (username, now),
    )
    row = conn.execute(
        "SELECT id, username, created_at FROM hub_users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create or load user")
    return row


def _hub_get_artifact(conn: sqlite3.Connection, username: str, kind: str, name: str) -> Optional[sqlite3.Row]:
    username = _normalize_hub_user(username, allow_reserved=True)
    kind = _normalize_hub_kind(kind)
    name = _normalize_hub_name(name)
    return conn.execute(
        """
        SELECT
            a.id, a.user_id, a.kind, a.name, a.alpha_content, a.alpha_metadata, a.created_at, a.updated_at,
            u.username
        FROM hub_artifacts a
        JOIN hub_users u ON u.id = a.user_id
        WHERE u.username = ? AND a.kind = ? AND a.name = ?
        """,
        (username, kind, name),
    ).fetchone()


def _hub_get_artifact_by_name(conn: sqlite3.Connection, kind: str, name: str) -> Optional[sqlite3.Row]:
    """Look up artifact by kind+name only (globally unique after migration)."""
    kind = _normalize_hub_kind(kind)
    name = _normalize_hub_name(name)
    return conn.execute(
        """
        SELECT
            a.id, a.user_id, a.kind, a.name, a.alpha_content, a.alpha_metadata, a.created_at, a.updated_at,
            u.username
        FROM hub_artifacts a
        JOIN hub_users u ON u.id = a.user_id
        WHERE a.kind = ? AND a.name = ?
        """,
        (kind, name),
    ).fetchone()


def _update_xatrahub_paths_in_code(text: str, rename_map: Dict[tuple, str]) -> str:
    """Replace old /username/kind/name[/version] xatrahub paths with new /kind/name[/version] format."""
    if not text:
        return text or ""
    pattern = re.compile(r'(xatrahub\s*\(\s*["\'])(/[^"\']+)(["\'])')
    def sub(m):
        path = m.group(2).strip()
        parts = [p for p in path.split('/') if p]
        if len(parts) < 3:
            return m.group(0)
        username = parts[0].lower()
        kind = parts[1].lower()
        old_name = parts[2]
        version = parts[3] if len(parts) > 3 else None
        key = (username, kind, old_name)
        if key not in rename_map:
            return m.group(0)
        new_name = rename_map[key]
        version_part = f'/{version}' if version else ''
        return f'{m.group(1)}/{kind}/{new_name}{version_part}{m.group(3)}'
    return pattern.sub(sub, text)


def _update_content_paths(content: str, rename_map: Dict[tuple, str]) -> str:
    """Update xatrahub paths in artifact content JSON."""
    if not content:
        return content or ""
    try:
        parsed = json.loads(content)
    except Exception:
        return _update_xatrahub_paths_in_code(content, rename_map)
    modified = False
    for key in ('imports_code', 'map_code', 'predefined_code', 'runtime_code', 'theme_code'):
        if isinstance(parsed.get(key), str):
            nv = _update_xatrahub_paths_in_code(parsed[key], rename_map)
            if nv != parsed[key]:
                parsed[key] = nv
                modified = True
    project = parsed.get('project')
    if isinstance(project, dict):
        for key in ('importsCode', 'predefinedCode', 'themeCode', 'runtimeCode'):
            if isinstance(project.get(key), str):
                nv = _update_xatrahub_paths_in_code(project[key], rename_map)
                if nv != project[key]:
                    project[key] = nv
                    modified = True
    if modified:
        return json.dumps(parsed, ensure_ascii=False)
    return content


def _migrate_to_global_names(conn: sqlite3.Connection) -> None:
    """Migrate hub_artifacts from UNIQUE(user_id, kind, name) to UNIQUE(kind, name).
    - indic lib (admin) → 'dtl'
    - all others → str(artifact_id)
    - Update all xatrahub path references in content/drafts
    - Recreate hub_artifacts table with new constraint
    """
    rows = conn.execute(
        "SELECT a.id, a.kind, a.name, u.username FROM hub_artifacts a JOIN hub_users u ON u.id = a.user_id"
    ).fetchall()
    # Build rename maps
    id_to_new: Dict[int, str] = {}
    rename_map: Dict[tuple, str] = {}  # (username, kind, old_name) -> new_name
    for row in rows:
        if (str(row['username']).lower() == ADMIN_USERNAME.lower()
                and row['kind'] == 'lib'
                and row['name'] == 'indic'):
            new_name = 'dtl'
        else:
            new_name = str(int(row['id']))
        id_to_new[int(row['id'])] = new_name
        rename_map[(str(row['username']).lower(), row['kind'], row['name'])] = new_name

    # Create new table with UNIQUE(kind, name)
    conn.execute("""
        CREATE TABLE hub_artifacts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES hub_users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            alpha_content TEXT NOT NULL DEFAULT '',
            alpha_metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(kind, name)
        )
    """)
    # Insert with new names and updated content
    all_arts = conn.execute("SELECT * FROM hub_artifacts").fetchall()
    for art in all_arts:
        new_name = id_to_new[int(art['id'])]
        new_content = _update_content_paths(art['alpha_content'], rename_map)
        conn.execute(
            "INSERT INTO hub_artifacts_new(id, user_id, kind, name, alpha_content, alpha_metadata, created_at, updated_at)"
            " VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (art['id'], art['user_id'], art['kind'], new_name, new_content, art['alpha_metadata'], art['created_at'], art['updated_at'])
        )
    # Update version content
    for ver in conn.execute("SELECT id, content FROM hub_artifact_versions").fetchall():
        if ver['content']:
            new_content = _update_content_paths(ver['content'], rename_map)
            if new_content != ver['content']:
                conn.execute("UPDATE hub_artifact_versions SET content = ? WHERE id = ?", (new_content, ver['id']))
    # Update drafts
    for draft in conn.execute("SELECT id, project_json FROM hub_drafts").fetchall():
        if draft['project_json']:
            try:
                parsed = json.loads(draft['project_json'])
            except Exception:
                continue
            modified = False
            project = parsed.get('project')
            if isinstance(project, dict):
                for key in ('importsCode', 'predefinedCode', 'themeCode', 'runtimeCode', 'code'):
                    if isinstance(project.get(key), str):
                        nv = _update_xatrahub_paths_in_code(project[key], rename_map)
                        if nv != project[key]:
                            project[key] = nv
                            modified = True
            if modified:
                conn.execute("UPDATE hub_drafts SET project_json = ? WHERE id = ?",
                             (json.dumps(parsed, ensure_ascii=False), draft['id']))
    # Swap tables
    conn.execute("DROP TABLE hub_artifacts")
    conn.execute("ALTER TABLE hub_artifacts_new RENAME TO hub_artifacts")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hub_artifacts_lookup ON hub_artifacts(user_id, kind, name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hub_artifacts_kind_name ON hub_artifacts(kind, name)")
    conn.execute("PRAGMA foreign_keys = ON")
    print(f"[xatra] Migrated hub_artifacts to globally-unique names (UNIQUE(kind, name)); renamed {len(id_to_new)} artifacts.")


def _ensure_owner_vote(conn: sqlite3.Connection, artifact_id: int, owner_user_id: int) -> None:
    """Ensure map owner has a canonical upvote on their own map."""
    conn.execute(
        """
        INSERT OR IGNORE INTO hub_votes(artifact_id, user_id, created_at)
        VALUES(?, ?, ?)
        """,
        (int(artifact_id), int(owner_user_id), _utc_now_iso()),
    )


def _viewer_has_voted(conn: sqlite3.Connection, artifact_id: int, request: Optional[Request]) -> bool:
    if request is None:
        return False
    user = _request_user(conn, request)
    if user is None:
        return False
    row = conn.execute(
        "SELECT id FROM hub_votes WHERE artifact_id = ? AND user_id = ?",
        (int(artifact_id), int(user["id"])),
    ).fetchone()
    return row is not None


def _hub_upsert_alpha(
    conn: sqlite3.Connection,
    username: str,
    kind: str,
    name: str,
    content: str,
    metadata: Any,
) -> sqlite3.Row:
    username = _normalize_hub_user(username, allow_reserved=(str(username or "").strip().lower() == GUEST_USERNAME))
    kind = _normalize_hub_kind(kind)
    name = _normalize_hub_name(name)
    if kind == "map" and name in HUB_RESERVED_USERNAMES:
        raise HTTPException(status_code=400, detail=f"Map name '{name}' is reserved")
    user = _hub_ensure_user(conn, username)
    now = _utc_now_iso()
    metadata_json = _json_text(_sanitize_artifact_metadata(kind, metadata))
    # Check for global name conflict (names are globally unique per kind after migration)
    existing_global = conn.execute(
        "SELECT id, user_id FROM hub_artifacts WHERE kind = ? AND name = ?", (kind, name)
    ).fetchone()
    if existing_global and int(existing_global['user_id']) != int(user['id']):
        raise HTTPException(status_code=409, detail="A map with this name already exists")
    conn.execute(
        """
        INSERT OR IGNORE INTO hub_artifacts(
            user_id, kind, name, alpha_content, alpha_metadata, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (user["id"], kind, name, content or "", metadata_json, now, now),
    )
    conn.execute(
        """
        UPDATE hub_artifacts
        SET alpha_content = ?, alpha_metadata = ?, updated_at = ?
        WHERE kind = ? AND name = ?
        """,
        (content or "", metadata_json, now, kind, name),
    )
    row = _hub_get_artifact(conn, username, kind, name)
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to persist artifact")
    if kind == "map":
        _ensure_owner_vote(conn, row["id"], row["user_id"])
    return row


def _hub_publish_version(
    conn: sqlite3.Connection,
    username: str,
    kind: str,
    name: str,
    content: str,
    metadata: Any,
) -> Dict[str, Any]:
    artifact = _hub_upsert_alpha(conn, username, kind, name, content, metadata)
    next_version = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM hub_artifact_versions WHERE artifact_id = ?",
        (artifact["id"],),
    ).fetchone()["v"]
    now = _utc_now_iso()
    metadata_json = _json_text(_sanitize_artifact_metadata(kind, metadata))
    conn.execute(
        """
        INSERT INTO hub_artifact_versions(artifact_id, version, content, metadata, created_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        (artifact["id"], int(next_version), content or "", metadata_json, now),
    )
    conn.commit()
    return {"version": int(next_version), "created_at": now}

# GADM Indexing
GADM_INDEX = []
INDEX_BUILDING = False
COUNTRY_LEVELS_INDEX = {}
COUNTRY_SEARCH_INDEX = []

def rebuild_country_indexes():
    global COUNTRY_LEVELS_INDEX, COUNTRY_SEARCH_INDEX
    # Called only from build_gadm_index which already holds _gadm_lock
    levels_map = {}
    names_map = {}

    for item in GADM_INDEX:
        gid = item.get("gid")
        if not gid:
            continue
        country_code = gid.split(".")[0]
        level = item.get("level")
        if level is None:
            continue
        levels_map.setdefault(country_code, set()).add(int(level))
        country_name = (item.get("country") or "").strip()
        if country_name and country_code not in names_map:
            names_map[country_code] = country_name

    COUNTRY_LEVELS_INDEX = {
        code: sorted(list(levels))
        for code, levels in levels_map.items()
    }
    COUNTRY_SEARCH_INDEX = sorted(
        [
            {
                "country_code": code,
                "country": names_map.get(code, code),
                "max_level": max(levels) if levels else 0,
            }
            for code, levels in COUNTRY_LEVELS_INDEX.items()
        ],
        key=lambda x: x["country_code"],
    )

def build_gadm_index():
    global INDEX_BUILDING, GADM_INDEX
    with _gadm_lock:
        if INDEX_BUILDING:
            return
        INDEX_BUILDING = True
    print("Building GADM index...")
    
    try:
        index = []
        seen_gids = set()
        if os.path.exists(GADM_DIR):
            files = sorted(os.listdir(GADM_DIR))
            for f in files:
                if not f.endswith(".json") or not f.startswith("gadm41_"): continue
                
                parts = f.replace(".json", "").split("_")
                if len(parts) < 3: continue
                try:
                    level = int(parts[2])
                except:
                    continue
                
                path = os.path.join(GADM_DIR, f)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                        data = json.load(fh)
                        for feat in data.get("features", []):
                            p = feat.get("properties", {})
                            gid = p.get(f"GID_{level}")
                            name = p.get(f"NAME_{level}")
                            country = p.get("COUNTRY")
                            varname = p.get(f"VARNAME_{level}")
                            
                            if gid:
                                if gid.endswith("_1"):
                                    gid = gid[:-2]
                                
                                if gid in seen_gids:
                                    continue
                                seen_gids.add(gid)
                                    
                                entry = {
                                    "gid": gid,
                                    "name": name,
                                    "country": country,
                                    "level": level
                                }
                                if varname and varname != "NA":
                                    entry["varname"] = varname
                                    
                                index.append(entry)
                except Exception as e:
                    pass
        
        with _gadm_lock:
            GADM_INDEX = index
            rebuild_country_indexes()
        with open(GADM_INDEX_PATH, "w") as f:
            json.dump(index, f)
        print(f"GADM index built: {len(index)} entries")

    except Exception as e:
        print(f"Error building index: {e}")
    finally:
        with _gadm_lock:
            INDEX_BUILDING = False

if os.path.exists(GADM_INDEX_PATH):
    try:
        with open(GADM_INDEX_PATH, "r") as f:
            _loaded_index = json.load(f)
        with _gadm_lock:
            GADM_INDEX = _loaded_index
            rebuild_country_indexes()
    except:
        threading.Thread(target=build_gadm_index).start()
else:
    threading.Thread(target=build_gadm_index).start()

app = FastAPI()
_init_hub_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{FRONTEND_PORT}",
        f"http://127.0.0.1:{FRONTEND_PORT}",
        f"http://localhost:{FRONTEND_PREVIEW_PORT}",
        f"http://127.0.0.1:{FRONTEND_PREVIEW_PORT}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/search/gadm")
def search_gadm(q: str):
    if not q: return []
    q = q.lower()
    results = []
    limit = 20
    
    for item in GADM_INDEX:
        score = 0
        gid = item["gid"].lower()
        name = item["name"].lower() if item["name"] else ""
        
        if gid == q: score = 100
        elif gid.startswith(q): score = 80
        elif name == q: score = 90
        elif name.startswith(q): score = 70
        elif q in name: score = 50
        elif item.get("varname") and q in item.get("varname").lower(): score = 40
        elif item["country"] and q in item["country"].lower(): score = 30
        
        if score > 0:
            tie_breaker = -len(gid)
            results.append((score, tie_breaker, item))
            
    results.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [r[2] for r in results[:limit]]

@app.get("/search/countries")
def search_countries(q: str):
    if not q:
        return COUNTRY_SEARCH_INDEX[:20]
    q = q.lower().strip()
    results = []

    for item in COUNTRY_SEARCH_INDEX:
        code = item["country_code"].lower()
        name = item["country"].lower()
        score = 0
        if code == q:
            score = 100
        elif code.startswith(q):
            score = 90
        elif name == q:
            score = 80
        elif name.startswith(q):
            score = 70
        elif q in name:
            score = 60
        if score > 0:
            results.append((score, item))

    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:20]]

@app.get("/gadm/levels")
def gadm_levels(country: str):
    if not country:
        return []
    country_code = country.strip().upper().split(".")[0]
    return COUNTRY_LEVELS_INDEX.get(country_code, [0, 1, 2, 3, 4])

class CodeRequest(BaseModel):
    code: str
    predefined_code: Optional[str] = None
    imports_code: Optional[str] = None
    theme_code: Optional[str] = None
    runtime_code: Optional[str] = None

class CodeSyncRequest(BaseModel):
    code: str
    predefined_code: Optional[str] = None

class MapElement(BaseModel):
    type: str
    label: Optional[str] = None
    value: Any = None
    args: Dict[str, Any] = {}

class BuilderRequest(BaseModel):
    elements: List[MapElement]
    options: Dict[str, Any] = {}
    predefined_code: Optional[str] = None
    imports_code: Optional[str] = None
    theme_code: Optional[str] = None
    runtime_code: Optional[str] = None

class PickerEntry(BaseModel):
    country: str
    level: int

class PickerRequest(BaseModel):
    entries: List[PickerEntry]
    adminRivers: bool = False
    basemaps: Optional[List[Dict[str, Any]]] = None

class TerritoryLibraryRequest(BaseModel):
    source: str = "builtin"  # "builtin" or "custom"
    predefined_code: Optional[str] = None
    selected_names: Optional[List[str]] = None
    basemaps: Optional[List[Dict[str, Any]]] = None
    hub_path: Optional[str] = None

class StopRequest(BaseModel):
    task_types: Optional[List[str]] = None


class HubEnsureUserRequest(BaseModel):
    username: str


class HubArtifactWriteRequest(BaseModel):
    content: str = ""
    metadata: Dict[str, Any] = {}


class AuthSignupRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = ""


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class UserProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = ""
    bio: Optional[str] = ""


class DraftRequest(BaseModel):
    map_name: str = "new_map"
    project: Dict[str, Any] = {}


class DraftPromoteRequest(BaseModel):
    name: str


class PasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str


def _hub_kind_label(kind: str) -> str:
    if kind == "map":
        return "map"
    if kind == "lib":
        return "lib"
    return "css"


def _hub_artifact_response(conn: sqlite3.Connection, artifact: sqlite3.Row, request: Optional[Request] = None) -> Dict[str, Any]:
    versions_rows = conn.execute(
        """
        SELECT version, created_at
        FROM hub_artifact_versions
        WHERE artifact_id = ?
        ORDER BY version DESC
        """,
        (artifact["id"],),
    ).fetchall()
    versions = [
        {"version": int(row["version"]), "created_at": row["created_at"]}
        for row in versions_rows
    ]
    latest_version = versions[0]["version"] if versions else None
    latest_content_hash = None
    if latest_version is not None:
        latest_content = conn.execute(
            "SELECT content FROM hub_artifact_versions WHERE artifact_id = ? AND version = ?",
            (artifact["id"], latest_version),
        ).fetchone()
        if latest_content is not None:
            latest_content_hash = _sha256_text(latest_content["content"] or "")
    alpha_meta = _sanitize_artifact_metadata(artifact["kind"], artifact["alpha_metadata"])
    return {
        "id": int(artifact["id"]),
        "username": artifact["username"],
        "kind": _hub_kind_label(artifact["kind"]),
        "name": artifact["name"],
        "slug": f'/{_hub_kind_label(artifact["kind"])}/{artifact["name"]}',
        "alpha": {
            "version": "alpha",
            "content": artifact["alpha_content"] or "",
            "metadata": alpha_meta,
            "content_hash": _sha256_text(artifact["alpha_content"] or ""),
            "updated_at": artifact["updated_at"],
        },
        "latest_published_version": latest_version,
        "latest_published_content_hash": latest_content_hash,
        "published_versions": versions,
        "created_at": artifact["created_at"],
        "updated_at": artifact["updated_at"],
        "votes": _map_vote_count(conn, artifact["id"]) if artifact["kind"] == "map" else 0,
        "viewer_voted": _viewer_has_voted(conn, artifact["id"], request) if artifact["kind"] == "map" else False,
        "views": _map_view_count(conn, artifact["id"]) if artifact["kind"] == "map" else 0,
    }


def _session_expiry_iso() -> str:
    expiry = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    return expiry.replace(microsecond=0).isoformat()


def _parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(str(ts))
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _user_public_profile(conn: sqlite3.Connection, user_row: sqlite3.Row) -> Dict[str, Any]:
    maps_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM hub_artifacts
        WHERE user_id = ? AND kind = 'map'
        """,
        (user_row["id"],),
    ).fetchone()["c"]
    views_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM hub_map_views mv
        JOIN hub_artifacts a ON a.id = mv.artifact_id
        WHERE a.user_id = ? AND a.kind = 'map'
        """,
        (user_row["id"],),
    ).fetchone()["c"]
    return {
        "username": user_row["username"],
        "full_name": user_row["full_name"] if "full_name" in user_row.keys() else "",
        "bio": user_row["bio"] if "bio" in user_row.keys() else "",
        "maps_count": int(maps_count or 0),
        "views_count": int(views_count or 0),
        "created_at": user_row["created_at"],
    }


def _session_user_from_token(conn: sqlite3.Connection, token: Optional[str]) -> Optional[sqlite3.Row]:
    if not token:
        return None
    token_hash = _sha256_text(token)
    row = conn.execute(
        """
        SELECT u.*
        FROM hub_sessions s
        JOIN hub_users u ON u.id = s.user_id
        WHERE s.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()
    if row is None:
        return None
    expiry_row = conn.execute(
        "SELECT expires_at FROM hub_sessions WHERE token_hash = ?",
        (token_hash,),
    ).fetchone()
    if expiry_row is None:
        return None
    expires_at = _parse_iso(expiry_row["expires_at"])
    if expires_at <= datetime.now(timezone.utc):
        conn.execute("DELETE FROM hub_sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()
        return None
    return row


def _request_user(conn: sqlite3.Connection, request: Request) -> Optional[sqlite3.Row]:
    token = request.cookies.get(SESSION_COOKIE)
    return _session_user_from_token(conn, token)


def _ensure_guest_id(request: Request, response: Optional[Response] = None) -> str:
    gid = request.cookies.get(GUEST_COOKIE)
    if gid and gid.strip():
        return gid
    gid = secrets.token_hex(12)
    if response is not None:
        response.set_cookie(
            GUEST_COOKIE,
            gid,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365,
        )
    return gid


def _request_actor_username(conn: sqlite3.Connection, request: Request, response: Optional[Response] = None) -> str:
    user = _request_user(conn, request)
    if user is not None:
        return user["username"]
    _ensure_guest_id(request, response=response)
    return GUEST_USERNAME


def _next_available_map_name(conn: sqlite3.Connection, username: str = "", base_name: str = "new_map") -> str:
    # Names are globally unique per kind now; check across all users.
    base = _normalize_hub_name(base_name)
    existing_rows = conn.execute("SELECT name FROM hub_artifacts WHERE kind = 'map'").fetchall()
    existing = {row["name"] for row in existing_rows}
    if base not in existing:
        return base
    i = 1
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"

def _python_value(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_python_value(el) for el in node.elts]
    if isinstance(node, ast.Tuple):
        return [_python_value(el) for el in node.elts]
    if isinstance(node, ast.Dict):
        return {_python_value(k): _python_value(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        return -node.operand.value
    if isinstance(node, ast.Name):
        if node.id == "None":
            return None
        if node.id == "True":
            return True
        if node.id == "False":
            return False
    return None

PYTHON_EXPR_KEY = "__xatra_python__"

def _is_python_expr_value(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get(PYTHON_EXPR_KEY), str)

def _python_expr_from_node(code: str, node: ast.AST) -> Optional[str]:
    try:
        expr = ast.get_source_segment(code or "", node)
    except Exception:
        expr = None
    if not isinstance(expr, str) or not expr.strip():
        try:
            expr = ast.unparse(node)
        except Exception:
            expr = None
    if not isinstance(expr, str):
        return None
    expr = expr.strip()
    return expr or None

def _builder_value_from_node(code: str, node: ast.AST) -> Any:
    if _is_simple_python_value(node):
        return _python_value(node)
    expr = _python_expr_from_node(code, node)
    if expr:
        return {PYTHON_EXPR_KEY: expr}
    return None

def _is_simple_python_value(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.List):
        return all(_is_simple_python_value(el) for el in node.elts)
    if isinstance(node, ast.Tuple):
        return all(_is_simple_python_value(el) for el in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (k is None or _is_simple_python_value(k)) and _is_simple_python_value(v)
            for k, v in zip(node.keys, node.values)
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        return isinstance(node.operand.value, (int, float))
    if isinstance(node, ast.Name) and node.id in ("None", "True", "False"):
        return True
    return False

def _call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None

def _parse_color_literal_node(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Call):
        cname = _call_name(node.func)
        if cname in ("Color.hex", "Color.named") and node.args:
            val = _python_value(node.args[0])
            if isinstance(val, str):
                return val
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None

def _parse_linear_sequence_row_expr(node: ast.AST) -> Optional[Dict[str, Any]]:
    if not (isinstance(node, ast.Call) and _call_name(node.func) == "LinearColorSequence"):
        return None

    kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
    colors_node = kwargs.get("colors")
    step_node = kwargs.get("step")

    if colors_node is None and node.args:
        colors_node = node.args[0]
    if step_node is None and len(node.args) >= 2:
        step_node = node.args[1]

    colors_out: List[str] = []
    if isinstance(colors_node, ast.List):
        for el in colors_node.elts:
            parsed = _parse_color_literal_node(el)
            if isinstance(parsed, str) and parsed.strip():
                colors_out.append(parsed.strip())

    step_h, step_s, step_l = 1.6180339887, 0.0, 0.0
    if isinstance(step_node, ast.Call) and _call_name(step_node.func) == "Color.hsl" and len(step_node.args) >= 3:
        h = _python_value(step_node.args[0])
        s = _python_value(step_node.args[1])
        l = _python_value(step_node.args[2])
        if isinstance(h, (int, float)):
            step_h = float(h)
        if isinstance(s, (int, float)):
            step_s = float(s)
        if isinstance(l, (int, float)):
            step_l = float(l)

    return {
        "class_name": "",
        "colors": ",".join(colors_out),
        "step_h": step_h,
        "step_s": step_s,
        "step_l": step_l,
    }

def _parse_admin_color_expr(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "from_matplotlib_color_sequence" and node.args:
            palette = _python_value(node.args[0])
            return str(palette) if palette else None
    if isinstance(node, ast.Call) and _call_name(node.func) == "RotatingColorSequence" and node.args:
        first = node.args[0]
        if isinstance(first, ast.List):
            out = []
            for el in first.elts:
                parsed = _parse_color_literal_node(el)
                if isinstance(parsed, str):
                    out.append(parsed)
            return ",".join(out) if out else None
    if isinstance(node, ast.Call) and _call_name(node.func) == "LinearColorSequence":
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        colors_node = kwargs.get("colors")
        if colors_node is None and node.args:
            colors_node = node.args[0]
        if isinstance(colors_node, ast.List):
            out = []
            for el in colors_node.elts:
                parsed = _parse_color_literal_node(el)
                if isinstance(parsed, str):
                    out.append(parsed)
            return ",".join(out) if out else None
    return None

def _parse_data_colormap_expr(node: ast.AST) -> Optional[Dict[str, Any]]:
    if isinstance(node, ast.Attribute):
        # e.g. plt.cm.viridis
        if isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name):
            if node.value.value.id == "plt" and node.value.attr == "cm":
                return {"type": node.attr, "colors": "yellow,orange,red"}
    if isinstance(node, ast.Call):
        cname = _call_name(node.func)
        if cname == "LinearSegmentedColormap.from_list":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.List):
                out = []
                for el in node.args[1].elts:
                    val = _python_value(el)
                    if isinstance(val, str) and val.strip():
                        out.append(val.strip())
                if out:
                    return {"type": "LinearSegmented", "colors": ",".join(out)}
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {"type": node.value, "colors": "yellow,orange,red"}
    return None

def _parse_css_rules(css_text: str) -> List[Dict[str, str]]:
    rules = []
    for match in re.finditer(r"([^{}]+)\{([^{}]+)\}", css_text or ""):
        selector = match.group(1).strip()
        style = match.group(2).strip()
        if selector and style:
            rules.append({"selector": selector, "style": style})
    return rules

def _territory_op_from_binop(op_node: ast.AST) -> str:
    if isinstance(op_node, ast.Sub):
        return "difference"
    if isinstance(op_node, ast.BitAnd):
        return "intersection"
    return "union"

def _compress_multi_value_parts(parts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(parts, list) or len(parts) < 2:
        return None
    base_type = parts[0].get("type")
    if base_type not in ("gadm", "predefined"):
        return None
    values = []
    for idx, part in enumerate(parts):
        if not isinstance(part, dict):
            return None
        if part.get("type") != base_type:
            return None
        op = part.get("op", "union")
        if idx > 0 and op != "union":
            return None
        val = part.get("value")
        if not isinstance(val, str) or not val.strip():
            return None
        values.append(val.strip())
    if len(values) < 2:
        return None
    return {"type": base_type, "value": values}

def _parse_territory_operand(node: ast.AST) -> Optional[Dict[str, Any]]:
    if isinstance(node, ast.Call):
        cname = _call_name(node.func)
        if cname == "gadm" and node.args:
            val = _python_value(node.args[0])
            if isinstance(val, str):
                return {"type": "gadm", "value": val}
        elif cname == "polygon" and node.args:
            coords = _python_value(node.args[0])
            if coords is not None:
                return {"type": "polygon", "value": json.dumps(coords)}
    elif isinstance(node, ast.Name):
        return {"type": "predefined", "value": node.id}
    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        # Handle dotted attribute access like `indic.KURU`
        return {"type": "predefined", "value": f"{node.value.id}.{node.attr}"}
    elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.Sub, ast.BitAnd)):
        group_parts = _parse_territory_expr(node)
        compressed = _compress_multi_value_parts(group_parts)
        if compressed:
            return compressed
        return {"type": "group", "value": group_parts}
    return None

def _parse_territory_expr(node: ast.AST) -> List[Dict[str, Any]]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.Sub, ast.BitAnd)):
        parts = _parse_territory_expr(node.left)
        right_part = _parse_territory_operand(node.right)
        if right_part:
            right_part["op"] = "union" if len(parts) == 0 else _territory_op_from_binop(node.op)
            parts.append(right_part)
        return parts
    part = _parse_territory_operand(node)
    if part:
        part["op"] = "union"
        return [part]
    return []

@app.post("/sync/code_to_builder")
def sync_code_to_builder(request: CodeSyncRequest):
    try:
        tree = ast.parse(request.code or "")
    except Exception as e:
        return {"error": f"Python parse failed: {e}"}

    elements: List[Dict[str, Any]] = []
    options: Dict[str, Any] = {"basemaps": []}
    flag_color_rows: List[Dict[str, Any]] = []
    admin_color_rows: List[Dict[str, Any]] = []

    def append_python_layer(stmt: Optional[ast.stmt] = None, code_line: Optional[str] = None):
        line = ""
        if isinstance(code_line, str):
            line = code_line.strip()
        elif stmt is not None:
            try:
                raw = ast.get_source_segment(request.code or "", stmt)
                line = (raw if isinstance(raw, str) and raw.strip() else ast.unparse(stmt)).strip()
            except Exception:
                try:
                    line = ast.unparse(stmt).strip()
                except Exception:
                    line = ""
        if line:
            elements.append({
                "type": "python",
                "label": "Python",
                "value": line,
                "args": {},
            })

    source_code = request.code or ""
    source_lines = source_code.splitlines(keepends=True)
    line_offsets = [0]
    total = 0
    for ln in source_lines:
        total += len(ln)
        line_offsets.append(total)

    def abs_offset(line_no: int, col_no: int) -> int:
        safe_line = max(1, int(line_no or 1))
        safe_col = max(0, int(col_no or 0))
        base = line_offsets[min(safe_line - 1, len(line_offsets) - 1)]
        return base + safe_col

    comment_tokens: List[Dict[str, Any]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source_code).readline):
            if tok.type != tokenize.COMMENT:
                continue
            line_no, col_no = tok.start
            abs_pos = abs_offset(line_no, col_no)
            text = (tok.string or "").strip()
            if text:
                comment_tokens.append({"pos": abs_pos, "line": int(line_no), "text": text})
    except Exception:
        comment_tokens = []

    comment_tokens.sort(key=lambda x: x["pos"])
    comment_idx = 0

    def stmt_pos(stmt: ast.stmt) -> int:
        line_no = int(getattr(stmt, "lineno", 1) or 1)
        col_no = int(getattr(stmt, "col_offset", 0) or 0)
        return abs_offset(line_no, col_no)

    def flush_comments_before(pos: int):
        nonlocal comment_idx
        while comment_idx < len(comment_tokens) and comment_tokens[comment_idx]["pos"] < pos:
            group_start = comment_idx
            group_end = group_start + 1
            last_line = int(comment_tokens[group_start]["line"])
            while (
                group_end < len(comment_tokens)
                and comment_tokens[group_end]["pos"] < pos
                and int(comment_tokens[group_end]["line"]) == last_line + 1
            ):
                last_line = int(comment_tokens[group_end]["line"])
                group_end += 1
            block = "\n".join(str(comment_tokens[i]["text"]) for i in range(group_start, group_end))
            append_python_layer(code_line=block)
            comment_idx = group_end

    for stmt in tree.body:
        flush_comments_before(stmt_pos(stmt))

        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        # Skip xatrahub import statements (assignments like `indic = xatrahub(...)` or bare `xatrahub(...)`)
        if isinstance(stmt, ast.Assign):
            rhs_name = _call_name(stmt.value.func) if isinstance(stmt.value, ast.Call) else None
            if rhs_name == "xatrahub":
                continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            if _call_name(stmt.value.func) == "xatrahub":
                continue
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            append_python_layer(stmt=stmt)
            continue

        call = stmt.value
        name = _call_name(call.func)
        if not (name and name.startswith("xatra.")):
            append_python_layer(stmt=stmt)
            continue
        method = name.split(".", 1)[1]
        kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg}

        if method == "BaseOption":
            if call.args:
                provider = _python_value(call.args[0])
                if isinstance(provider, str):
                    options["basemaps"].append({
                        "url_or_provider": provider,
                        "name": _python_value(kwargs.get("name")) or provider,
                        "default": bool(_python_value(kwargs.get("default"))),
                    })
                else:
                    append_python_layer(stmt=stmt)
            else:
                append_python_layer(stmt=stmt)
            continue

        if method == "TitleBox":
            title: Any = ""
            if call.args:
                title_node = call.args[0]
                title = _builder_value_from_node(source_code, title_node)
            elif "html" in kwargs:
                title = _builder_value_from_node(source_code, kwargs.get("html"))
            tb_args = {}
            if "period" in kwargs:
                tb_args["period"] = _builder_value_from_node(source_code, kwargs.get("period"))
            if isinstance(title, (str, dict)):
                elements.append({
                    "type": "titlebox",
                    "label": "TitleBox",
                    "value": title,
                    "args": tb_args,
                })
            else:
                append_python_layer(stmt=stmt)
            continue

        if method == "zoom":
            if call.args:
                options["zoom"] = _python_value(call.args[0])
            else:
                append_python_layer(stmt=stmt)
            continue

        if method == "focus":
            if len(call.args) >= 2:
                options["focus"] = [_python_value(call.args[0]), _python_value(call.args[1])]
            else:
                append_python_layer(stmt=stmt)
            continue

        if method == "slider":
            simple_slider = True
            for key in ("start", "end", "speed"):
                if key in kwargs and not _is_simple_python_value(kwargs[key]):
                    simple_slider = False
                    break
            if not simple_slider:
                append_python_layer(stmt=stmt)
                continue
            slider = {
                "start": _python_value(kwargs.get("start")),
                "end": _python_value(kwargs.get("end")),
                "speed": _python_value(kwargs.get("speed")),
            }
            options["slider"] = slider
            continue

        if method == "CSS":
            if call.args:
                css_text = _python_value(call.args[0])
                if isinstance(css_text, str):
                    current = options.get("css_rules") or []
                    options["css_rules"] = current + _parse_css_rules(css_text)
                else:
                    append_python_layer(stmt=stmt)
            else:
                append_python_layer(stmt=stmt)
            continue

        if method == "FlagColorSequence":
            if call.args:
                row = _parse_linear_sequence_row_expr(call.args[0])
                if row is None:
                    legacy = _parse_admin_color_expr(call.args[0])
                    if legacy:
                        row = {
                            "class_name": "",
                            "colors": legacy,
                            "step_h": 1.6180339887,
                            "step_s": 0.0,
                            "step_l": 0.0,
                        }
                if row:
                    class_name = _python_value(kwargs.get("class_name"))
                    row["class_name"] = class_name or ""
                    flag_color_rows.append(row)
                else:
                    append_python_layer(stmt=stmt)
            else:
                append_python_layer(stmt=stmt)
            continue

        if method == "AdminColorSequence":
            if call.args:
                row = _parse_linear_sequence_row_expr(call.args[0])
                if row:
                    admin_color_rows = [row]
                else:
                    seq = _parse_admin_color_expr(call.args[0])
                    if seq:
                        admin_color_rows = [{
                            "class_name": "",
                            "colors": seq,
                            "step_h": 1.6180339887,
                            "step_s": 0.0,
                            "step_l": 0.0,
                        }]
                    else:
                        append_python_layer(stmt=stmt)
            else:
                append_python_layer(stmt=stmt)
            continue

        if method == "DataColormap":
            if call.args:
                cmap = _parse_data_colormap_expr(call.args[0])
                if cmap:
                    options["data_colormap"] = cmap
                else:
                    append_python_layer(stmt=stmt)
            else:
                append_python_layer(stmt=stmt)
            continue

        args_dict = {}
        for key, node in kwargs.items():
            if key == "value" and method in ("Flag", "River", "Path"):
                continue
            if key == "position" and method in ("Point", "Text"):
                continue
            if key == "gadm" and method == "Admin":
                continue
            if key == "sources" and method == "AdminRivers":
                continue
            if key == "icon" and method == "Point":
                continue
            args_dict[key] = _builder_value_from_node(source_code, node)

        if method == "Flag":
            if "value" not in kwargs:
                append_python_layer(stmt=stmt)
                continue
            territory_parts: List[Dict[str, Any]] = _parse_territory_expr(kwargs["value"])
            if not territory_parts:
                append_python_layer(stmt=stmt)
                continue
            label = args_dict.pop("label", None)
            args_dict.pop("parent", None)
            elements.append({
                "type": "flag",
                "label": label,
                "value": territory_parts,
                "args": {k: v for k, v in args_dict.items() if k != "value"},
            })
            continue

        if method == "River":
            label = args_dict.pop("label", None)
            source_type = "naturalearth"
            value: Any = ""
            v_node = kwargs.get("value")
            if isinstance(v_node, ast.Call):
                loader = _call_name(v_node.func)
                if loader == "overpass":
                    source_type = "overpass"
                elif loader != "naturalearth":
                    append_python_layer(stmt=stmt)
                    continue
                if v_node.args:
                    value = _builder_value_from_node(source_code, v_node.args[0])
                else:
                    append_python_layer(stmt=stmt)
                    continue
            else:
                append_python_layer(stmt=stmt)
                continue
            river_args = {k: v for k, v in args_dict.items() if k != "value"}
            river_args["source_type"] = source_type
            elements.append({"type": "river", "label": label, "value": value, "args": river_args})
            continue

        if method in ("Point", "Text"):
            pos_node = kwargs.get("position")
            pos = _builder_value_from_node(source_code, pos_node) if pos_node is not None else None
            label = args_dict.pop("label", None)
            if isinstance(pos, list):
                value: Any = json.dumps(pos)
            elif pos is None:
                value = ""
            else:
                value = pos
            if method == "Point":
                icon_node = kwargs.get("icon")
                if isinstance(icon_node, ast.Call):
                    icon_call = _call_name(icon_node.func)
                    if icon_call == "Icon.builtin" and icon_node.args:
                        args_dict["icon"] = _builder_value_from_node(source_code, icon_node.args[0])
                    elif icon_call == "Icon.geometric" and icon_node.args:
                        args_dict["icon"] = {
                            "shape": _builder_value_from_node(source_code, icon_node.args[0]) or "circle",
                            "color": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "color"), ast.Constant(value="#3388ff"))),
                            "size": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "size"), ast.Constant(value=24))),
                        }
                    elif icon_call == "Icon":
                        args_dict["icon"] = {
                            "icon_url": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_url"), ast.Constant(value=""))) or ""
                        }
                    else:
                        append_python_layer(stmt=stmt)
                        continue
                elif icon_node is not None:
                    args_dict["icon"] = _builder_value_from_node(source_code, icon_node)
            elements.append({"type": method.lower(), "label": label, "value": value, "args": args_dict})
            continue

        if method == "Path":
            v_node = kwargs.get("value")
            path_val = _builder_value_from_node(source_code, v_node) if v_node is not None else None
            label = args_dict.pop("label", None)
            if isinstance(path_val, list):
                value: Any = json.dumps(path_val)
            elif path_val is None:
                value = ""
            else:
                value = path_val
            elements.append({"type": "path", "label": label, "value": value, "args": args_dict})
            continue

        if method == "Admin":
            gadm_node = kwargs.get("gadm")
            gadm_code = _builder_value_from_node(source_code, gadm_node) if gadm_node is not None else ""
            elements.append({"type": "admin", "label": None, "value": gadm_code, "args": args_dict})
            continue

        if method == "AdminRivers":
            sources_node = kwargs.get("sources")
            sources = _builder_value_from_node(source_code, sources_node) if sources_node is not None else ["naturalearth"]
            stored_sources = json.dumps(sources) if isinstance(sources, list) else sources
            elements.append({"type": "admin_rivers", "label": "All Rivers", "value": stored_sources, "args": args_dict})
            continue

        if method == "Dataframe":
            elements.append({"type": "dataframe", "label": "Data", "value": "", "args": {}})
            continue

        if method == "Music":
            music_node = kwargs.get("path")
            if music_node is None:
                music_node = kwargs.get("value")
            if music_node is None and call.args:
                music_node = call.args[0]
            music_value = _builder_value_from_node(source_code, music_node) if music_node is not None else ""
            if "timestamps" not in args_dict and len(call.args) >= 2:
                args_dict["timestamps"] = _builder_value_from_node(source_code, call.args[1])
            if "period" not in args_dict and len(call.args) >= 3:
                args_dict["period"] = _builder_value_from_node(source_code, call.args[2])
            args_dict.pop("path", None)
            args_dict.pop("value", None)
            label = args_dict.pop("label", None)
            elements.append({"type": "music", "label": label, "value": music_value if music_value is not None else "", "args": args_dict})
            continue

        append_python_layer(stmt=stmt)

    while comment_idx < len(comment_tokens):
        group_start = comment_idx
        group_end = group_start + 1
        last_line = int(comment_tokens[group_start]["line"])
        while (
            group_end < len(comment_tokens)
            and int(comment_tokens[group_end]["line"]) == last_line + 1
        ):
            last_line = int(comment_tokens[group_end]["line"])
            group_end += 1
        block = "\n".join(str(comment_tokens[i]["text"]) for i in range(group_start, group_end))
        append_python_layer(code_line=block)
        comment_idx = group_end

    if flag_color_rows:
        options["flag_color_sequences"] = flag_color_rows
    if admin_color_rows:
        options["admin_color_sequences"] = admin_color_rows

    return {
        "elements": elements,
        "options": options,
        "predefined_code": request.predefined_code or "",
    }

@app.get("/icons/list")
def list_icons():
    """Return list of built-in icon filenames for Point icon picker."""
    try:
        icons_dir = Path(xatra.__file__).parent / "icons"
        if not icons_dir.exists():
            return []
        return sorted(
            f.name for f in icons_dir.iterdir()
            if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in (".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp")
        )
    except Exception:
        return []

@app.get("/territory_library/names")
def territory_library_names():
    """Return public names from xatra.territory_library for autocomplete in Territory library."""
    try:
        import xatra.territory_library as tl
        return [n for n in dir(tl) if not n.startswith("_")]
    except Exception:
        return []

def _extract_assigned_names(code: str) -> List[str]:
    names: List[str] = []
    if not code or not code.strip():
        return names
    try:
        tree = ast.parse(code)
    except Exception:
        return names
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)
    return names


def _extract_territory_index(code: str) -> List[str]:
    """Extract __TERRITORY_INDEX__ value via AST literal_eval (no exec needed)."""
    if not code or not code.strip():
        return []
    try:
        tree = ast.parse(code)
    except Exception:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__TERRITORY_INDEX__":
                    try:
                        value = ast.literal_eval(node.value)
                        if isinstance(value, (list, tuple)):
                            return [str(x) for x in value if isinstance(x, str)]
                    except Exception:
                        pass
    return []

def _get_territory_catalog(source: str, predefined_code: str, hub_path: Optional[str] = None) -> Dict[str, List[str]]:
    """Return territory names using AST analysis only — no exec() in the main process."""
    import xatra.territory_library as territory_library

    if source == "custom":
        assigned = [n for n in _extract_assigned_names(predefined_code) if n != "__TERRITORY_INDEX__"]
        names: List[str] = []
        seen: set = set()
        for name in assigned:
            if name.startswith("_") or name in seen:
                continue
            seen.add(name)
            names.append(name)
        index_names = _extract_territory_index(predefined_code) if predefined_code else []
        return {
            "names": names,
            "index_names": [n for n in index_names if n in names] if index_names else names,
        }

    if source == "hub" and hub_path:
        try:
            parsed = _parse_xatrahub_path(hub_path)
            loaded = _hub_load_content(parsed["username"], parsed["kind"], parsed["name"], parsed["version"])
            code_text = _extract_python_payload_text(loaded["kind"], loaded.get("content", ""), loaded.get("metadata", {}))
            names = [n for n in _extract_assigned_names(code_text) if n != "__TERRITORY_INDEX__" and not n.startswith("_")]
            idx = _extract_territory_index(code_text)
            return {"names": names, "index_names": [n for n in idx if n in names] if idx else names}
        except Exception:
            return {"names": [], "index_names": []}

    names = [n for n in dir(territory_library) if not n.startswith("_")]
    idx = getattr(territory_library, "__TERRITORY_INDEX__", [])
    index_names = [str(n) for n in idx if isinstance(n, str)] if isinstance(idx, (list, tuple)) else []
    return {
        "names": names,
        "index_names": [n for n in index_names if n in names] if index_names else names,
    }

@app.post("/territory_library/catalog")
def territory_library_catalog(request: TerritoryLibraryRequest):
    try:
        source = (request.source or "builtin").strip().lower()
        catalog = _get_territory_catalog(source, request.predefined_code or "", request.hub_path)
        return catalog
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health():
    return {"status": "ok"}


def _map_vote_count(conn: sqlite3.Connection, artifact_id: int) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM hub_votes WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return int(row["c"] if row else 0)


def _map_view_count(conn: sqlite3.Connection, artifact_id: int) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM hub_map_views WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return int(row["c"] if row else 0)


def _require_write_identity(conn: sqlite3.Connection, request: Request, username: str) -> Optional[sqlite3.Row]:
    target = _normalize_hub_user(username, allow_reserved=True)
    user = _request_user(conn, request)
    if user is not None:
        if user["username"] != target:
            raise HTTPException(status_code=403, detail="Cannot modify another user's artifact")
        return user
    if target != GUEST_USERNAME:
        raise HTTPException(status_code=401, detail="Login required")
    # For guest writes, require the guest cookie to be present so completely anonymous
    # requests (no cookies at all) can't write to guest artifacts.
    guest_id = request.cookies.get(GUEST_COOKIE)
    if not guest_id or not guest_id.strip():
        raise HTTPException(status_code=401, detail="Login required")
    return None


def _transfer_guest_draft(conn: sqlite3.Connection, guest_id: str, user_id: int) -> None:
    """Copy guest draft to user (overwriting any existing user draft), keeping the guest draft intact.
    The guest draft is preserved so that if the user logs out without saving, their work
    is still present the next time they log in as a guest."""
    guest_key = f"guest:{guest_id}"
    user_key = f"user:{user_id}"
    guest_row = conn.execute(
        "SELECT project_json FROM hub_drafts WHERE owner_key = ?", (guest_key,)
    ).fetchone()
    if guest_row is None:
        return
    now = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO hub_drafts(owner_key, project_json, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(owner_key) DO UPDATE SET
            project_json = excluded.project_json,
            updated_at = excluded.updated_at
        """,
        (user_key, guest_row["project_json"], now),
    )
    # Note: caller must conn.commit()


def _create_session_cookie(conn: sqlite3.Connection, row: sqlite3.Row, response: Response) -> Dict[str, Any]:
    """Insert a new session record and set the session cookie. Returns user profile."""
    token = secrets.token_urlsafe(32)
    token_hash = _sha256_text(token)
    now = datetime.now(timezone.utc)
    exp = datetime.fromtimestamp(now.timestamp() + 60 * 60 * 24 * SESSION_TTL_DAYS, tz=timezone.utc).replace(microsecond=0)
    conn.execute(
        "INSERT INTO hub_sessions(user_id, token_hash, created_at, expires_at) VALUES(?, ?, ?, ?)",
        (row["id"], token_hash, _utc_now_iso(), exp.isoformat()),
    )
    conn.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * SESSION_TTL_DAYS,
    )
    return {"user": _user_public_profile(conn, row), "is_authenticated": True}


@app.post("/auth/signup")
def auth_signup(body: AuthSignupRequest, response: Response, http_request: Request):
    ip = (http_request.client.host if http_request.client else "unknown")
    _check_rate_limit(f"signup:{ip}", limit=5, window_seconds=3600)
    username = _normalize_hub_user(body.username)
    password = str(body.password or "")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    conn = _hub_db_conn()
    try:
        exists = conn.execute("SELECT id FROM hub_users WHERE username = ?", (username,)).fetchone()
        if exists is not None:
            raise HTTPException(status_code=409, detail="Username already exists")
        now = _utc_now_iso()
        conn.execute(
            """
            INSERT INTO hub_users(username, password_hash, full_name, bio, is_admin, created_at)
            VALUES(?, ?, ?, '', 0, ?)
            """,
            (username, _hash_password(password), str(body.full_name or "").strip(), now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM hub_users WHERE username = ?", (username,)).fetchone()
        result = _create_session_cookie(conn, row, response)
        guest_id = http_request.cookies.get(GUEST_COOKIE)
        if guest_id and guest_id.strip():
            _transfer_guest_draft(conn, guest_id.strip(), row["id"])
            conn.commit()
        return result
    finally:
        conn.close()


@app.post("/auth/login")
def auth_login(body: AuthLoginRequest, response: Response, http_request: Request):
    ip = (http_request.client.host if http_request.client else "unknown")
    _check_rate_limit(f"login:{ip}", limit=10, window_seconds=300)
    conn = _hub_db_conn()
    try:
        username = _normalize_hub_user(body.username)
        row = conn.execute("SELECT * FROM hub_users WHERE username = ?", (username,)).fetchone()
        if row is None or not _verify_password(str(body.password or ""), row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        result = _create_session_cookie(conn, row, response)
        guest_id = http_request.cookies.get(GUEST_COOKIE)
        if guest_id and guest_id.strip():
            _transfer_guest_draft(conn, guest_id.strip(), row["id"])
            conn.commit()
        return result
    finally:
        conn.close()


@app.post("/auth/logout")
def auth_logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    conn = _hub_db_conn()
    try:
        if token:
            conn.execute("DELETE FROM hub_sessions WHERE token_hash = ?", (_sha256_text(token),))
            conn.commit()
    finally:
        conn.close()
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/auth/me")
def auth_me(request: Request, response: Response):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        guest_id = _ensure_guest_id(request, response=response)
        if user is None:
            return {
                "is_authenticated": False,
                "user": {
                    "username": GUEST_USERNAME,
                    "full_name": "",
                    "bio": "",
                    "maps_count": 0,
                    "views_count": 0,
                },
                "guest_id": guest_id,
            }
        return {
            "is_authenticated": True,
            "user": _user_public_profile(conn, user),
            "guest_id": guest_id,
        }
    finally:
        conn.close()


@app.post("/auth/google")
def auth_google_placeholder():
    return {
        "configured": False,
        "message": "Google OAuth is not configured yet. Add OIDC provider config to enable it.",
    }


@app.put("/auth/me/profile")
def auth_update_profile(request: Request, payload: UserProfileUpdateRequest):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is None:
            raise HTTPException(status_code=401, detail="Login required")
        conn.execute(
            "UPDATE hub_users SET full_name = ?, bio = ? WHERE id = ?",
            (str(payload.full_name or "").strip(), str(payload.bio or "").strip(), user["id"]),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM hub_users WHERE id = ?", (user["id"],)).fetchone()
        return {"user": _user_public_profile(conn, updated)}
    finally:
        conn.close()


@app.put("/auth/me/password")
def auth_update_password(request: Request, payload: PasswordUpdateRequest):
    ip = (request.client.host if request.client else "unknown")
    _check_rate_limit(f"passwd:{ip}", limit=5, window_seconds=300)
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is None:
            raise HTTPException(status_code=401, detail="Login required")
        if not _verify_password(payload.current_password or "", user["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if len(payload.new_password or "") < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        conn.execute("UPDATE hub_users SET password_hash = ? WHERE id = ?", (_hash_password(payload.new_password), user["id"]))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/maps/default-name")
def maps_default_name(request: Request):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        owner = user["username"] if user else GUEST_USERNAME
        # # Reuse the most recently updated unpublished new_map_* artifact if one exists,
        # # rather than always incrementing (which causes proliferation).
        # scratch = conn.execute(
        #     """
        #     SELECT a.name
        #     FROM hub_artifacts a
        #     JOIN hub_users u ON u.id = a.user_id
        #     LEFT JOIN hub_artifact_versions v ON v.artifact_id = a.id
        #     WHERE u.username = ? AND a.kind = 'map'
        #       AND (a.name = 'new_map' OR a.name LIKE 'new_map_%')
        #     GROUP BY a.id
        #     HAVING COUNT(v.id) = 0
        #     ORDER BY a.updated_at DESC
        #     LIMIT 1
        #     """,
        #     (owner,),
        # ).fetchone()
        # if scratch is not None:
        #     return {"username": owner, "name": scratch["name"]}
        return {"username": owner, "name": _next_available_map_name(conn, owner, "new_map")}
    finally:
        conn.close()


@app.get("/maps/resolve-name")
def maps_resolve_name(request: Request, base: str = "new_map"):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        owner = user["username"] if user else GUEST_USERNAME
        cleaned = _normalize_hub_name(base or "new_map")
        return {"username": owner, "name": _next_available_map_name(conn, owner, cleaned)}
    finally:
        conn.close()


@app.get("/maps/{name}")
def maps_get_by_name(name: str, version: str = "alpha", http_request: Request = None):
    """Load a map by name only (no username required; globally unique)."""
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact_by_name(conn, "map", name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Map not found")
        return hub_get_artifact_version(
            username=artifact['username'], kind="map", name=name,
            version=version, http_request=http_request
        )
    finally:
        conn.close()


@app.get("/maps/{username}/{map_name}")
def maps_get(username: str, map_name: str, version: str = "alpha", http_request: Request = None):
    return hub_get_artifact_version(username=username, kind="map", name=map_name, version=version, http_request=http_request)


@app.post("/maps/{username}/{map_name}/view")
def maps_record_view(username: str, map_name: str, request: Request, response: Response):
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact(conn, username, "map", map_name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Map not found")
        user = _request_user(conn, request)
        if user is not None:
            viewer_key = f"user:{user['id']}"
        else:
            viewer_key = f"guest:{_ensure_guest_id(request, response=response)}"
        conn.execute(
            """
            INSERT OR IGNORE INTO hub_map_views(artifact_id, viewer_key, viewed_at)
            VALUES(?, ?, ?)
            """,
            (artifact["id"], viewer_key, _utc_now_iso()),
        )
        conn.commit()
        return {"views": _map_view_count(conn, artifact["id"])}
    finally:
        conn.close()


@app.post("/maps/{username}/{map_name}/vote")
def maps_vote(username: str, map_name: str, request: Request):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is None:
            raise HTTPException(status_code=401, detail="Login required to vote")
        artifact = _hub_get_artifact(conn, username, "map", map_name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Map not found")
        if int(user["id"]) == int(artifact["user_id"]):
            _ensure_owner_vote(conn, artifact["id"], artifact["user_id"])
            conn.commit()
            return {"voted": True, "votes": _map_vote_count(conn, artifact["id"])}
        existing = conn.execute(
            "SELECT id FROM hub_votes WHERE artifact_id = ? AND user_id = ?",
            (artifact["id"], user["id"]),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM hub_votes WHERE id = ?", (existing["id"],))
            voted = False
        else:
            conn.execute(
                "INSERT INTO hub_votes(artifact_id, user_id, created_at) VALUES(?, ?, ?)",
                (artifact["id"], user["id"], _utc_now_iso()),
            )
            voted = True
        conn.commit()
        return {"voted": voted, "votes": _map_vote_count(conn, artifact["id"])}
    finally:
        conn.close()


@app.get("/explore")
def maps_explore(
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 12,
):
    query = str(q or "").strip().lower()
    user_filter = None
    text_terms: List[str] = []
    for token in query.split():
        if token.startswith("user:") and len(token) > 5:
            user_filter = token[5:]
        elif token:
            text_terms.append(token)
    safe_page = max(1, int(page or 1))
    safe_per_page = max(1, min(int(per_page or 12), 30))
    offset = (safe_page - 1) * safe_per_page
    conn = _hub_db_conn()
    try:
        where = ["a.kind = 'map'"]
        params: List[Any] = []
        if user_filter:
            where.append("LOWER(u.username) = ?")
            params.append(user_filter)
        for term in text_terms:
            where.append("(LOWER(a.name) LIKE ? ESCAPE '\\' OR LOWER(a.alpha_metadata) LIKE ? ESCAPE '\\' OR LOWER(u.username) LIKE ? ESCAPE '\\')")
            # Escape LIKE wildcards so user input is treated as literal text
            escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            like = f"%{escaped}%"
            params.extend([like, like, like])
        where_sql = "WHERE " + " AND ".join(where)
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM hub_artifacts a JOIN hub_users u ON u.id = a.user_id {where_sql}",
            tuple(params),
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT a.id, a.name, a.updated_at, a.alpha_metadata, u.username
            FROM hub_artifacts a
            JOIN hub_users u ON u.id = a.user_id
            {where_sql}
            ORDER BY a.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, safe_per_page, offset),
        ).fetchall()
        items = []
        for row in rows:
            meta = _json_parse(row["alpha_metadata"], {})
            items.append({
                "username": row["username"],
                "name": row["name"],
                "slug": f"/{row['name']}",
                "forked_from": meta.get("forked_from"),
                "votes": _map_vote_count(conn, row["id"]),
                "views": _map_view_count(conn, row["id"]),
                "updated_at": row["updated_at"],
                "thumbnail": meta.get("thumbnail") or "/vite.svg",
            })
        return {"items": items, "page": safe_page, "per_page": safe_per_page, "total": int(total or 0)}
    finally:
        conn.close()


@app.get("/users")
def users_list(
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
):
    query = str(q or "").strip().lower()
    safe_page = max(1, int(page or 1))
    safe_per_page = max(1, min(int(per_page or 20), 50))
    offset = (safe_page - 1) * safe_per_page
    conn = _hub_db_conn()
    try:
        where = []
        params: List[Any] = []
        if query:
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            like = f"%{escaped}%"
            where.append("(LOWER(u.username) LIKE ? ESCAPE '\\' OR LOWER(u.full_name) LIKE ? ESCAPE '\\' OR LOWER(u.bio) LIKE ? ESCAPE '\\')")
            params.extend([like, like, like])
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM hub_users u {where_sql}",
            tuple(params),
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT u.*
            FROM hub_users u
            {where_sql}
            ORDER BY u.username ASC
            LIMIT ? OFFSET ?
            """,
            (*params, safe_per_page, offset),
        ).fetchall()
        users = [_user_public_profile(conn, row) for row in rows]
        return {"items": users, "page": safe_page, "per_page": safe_per_page, "total": int(total or 0)}
    finally:
        conn.close()


@app.get("/users/{username}")
def user_profile(username: str, q: Optional[str] = None, page: int = 1, per_page: int = 10):
    uname = _normalize_hub_user(username)
    conn = _hub_db_conn()
    try:
        user = conn.execute("SELECT * FROM hub_users WHERE username = ?", (uname,)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        profile = _user_public_profile(conn, user)
        safe_page = max(1, int(page or 1))
        safe_per_page = max(1, min(int(per_page or 10), 30))
        offset = (safe_page - 1) * safe_per_page
        query = str(q or "").strip().lower()
        where = "WHERE a.user_id = ? AND a.kind = 'map'"
        params: List[Any] = [user["id"]]
        if query:
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            like = f"%{escaped}%"
            where += " AND (LOWER(a.name) LIKE ? ESCAPE '\\' OR LOWER(a.alpha_metadata) LIKE ? ESCAPE '\\')"
            params.extend([like, like])
        total = conn.execute(f"SELECT COUNT(*) AS c FROM hub_artifacts a {where}", tuple(params)).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT a.id, a.name, a.updated_at, a.alpha_metadata
            FROM hub_artifacts a
            {where}
            ORDER BY a.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, safe_per_page, offset),
        ).fetchall()
        maps = []
        for row in rows:
            meta = _json_parse(row["alpha_metadata"], {})
            maps.append({
                "name": row["name"],
                "slug": f"/{row['name']}",
                "votes": _map_vote_count(conn, row["id"]),
                "views": _map_view_count(conn, row["id"]),
                "updated_at": row["updated_at"],
                "thumbnail": meta.get("thumbnail") or "/vite.svg",
            })
        return {"profile": profile, "maps": maps, "page": safe_page, "per_page": safe_per_page, "total": int(total or 0)}
    finally:
        conn.close()


@app.get("/user/{username}")
def user_profile_by_prefix(username: str, q: Optional[str] = None, page: int = 1, per_page: int = 10):
    """User profile accessible at /user/{username} (new canonical URL)."""
    return user_profile(username=username, q=q, page=page, per_page=per_page)


@app.put("/draft/current")
def draft_save(request: Request, response: Response, payload: DraftRequest):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is not None:
            # Logged-in users should not overwrite their transferred unsaved draft
            # while editing normal maps.
            raise HTTPException(status_code=403, detail="Draft edits are guest-only")
        else:
            owner_key = f"guest:{_ensure_guest_id(request, response=response)}"
        now = _utc_now_iso()
        draft_json = json.dumps({
            "map_name": _normalize_hub_name(payload.map_name or "new_map"),
            "project": payload.project or {},
        }, ensure_ascii=False)
        if len(draft_json.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise HTTPException(status_code=413, detail="Content too large (max 10 MB)")
        conn.execute(
            """
            INSERT INTO hub_drafts(owner_key, project_json, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(owner_key) DO UPDATE SET
                project_json = excluded.project_json,
                updated_at = excluded.updated_at
            """,
            (owner_key, draft_json, now),
        )
        conn.commit()
        return {"ok": True, "updated_at": now}
    finally:
        conn.close()


@app.get("/draft/current")
def draft_get(request: Request, response: Response):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is not None:
            owner_key = f"user:{user['id']}"
        else:
            owner_key = f"guest:{_ensure_guest_id(request, response=response)}"
        row = conn.execute("SELECT project_json, updated_at FROM hub_drafts WHERE owner_key = ?", (owner_key,)).fetchone()
        if row is None:
            return {"exists": False}
        return {"exists": True, "updated_at": row["updated_at"], "draft": _json_parse(row["project_json"], {})}
    finally:
        conn.close()


@app.delete("/draft/current")
def draft_delete(request: Request):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is None:
            raise HTTPException(status_code=401, detail="Login required")
        conn.execute(
            "DELETE FROM hub_drafts WHERE owner_key = ?",
            (f"user:{user['id']}",)
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/draft/promote")
def draft_promote(body: DraftPromoteRequest, request: Request):
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is None:
            raise HTTPException(status_code=401, detail="Login required")
        name = _normalize_hub_name(body.name)
        username = user["username"]
        owner_key = f"user:{user['id']}"
        row = conn.execute("SELECT project_json FROM hub_drafts WHERE owner_key = ?", (owner_key,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No draft found")
        existing = _hub_get_artifact_by_name(conn, "map", name)
        if existing is not None:
            raise HTTPException(status_code=409, detail="Map already exists")
        draft = _json_parse(row["project_json"], {})
        project = draft.get("project", {})
        content_obj = {
            "imports_code":    project.get("importsCode", ""),
            "theme_code":      project.get("themeCode", ""),
            "predefined_code": project.get("predefinedCode", ""),
            "map_code":        project.get("code", ""),
            "runtime_code":    project.get("runtimeCode", ""),
            "picker_options":  project.get("pickerOptions", {"entries": [], "adminRivers": False}),
            "project": {
                "elements":       project.get("elements", []),
                "options":        project.get("options", {}),
                "predefinedCode": project.get("predefinedCode", ""),
                "importsCode":    project.get("importsCode", ""),
                "themeCode":      project.get("themeCode", ""),
                "runtimeCode":    project.get("runtimeCode", ""),
            }
        }
        content = json.dumps(content_obj, ensure_ascii=False)
        metadata: Dict[str, Any] = {"updated_at": _utc_now_iso()}
        _hub_upsert_alpha(conn, username, "map", name, content, metadata)
        conn.execute("DELETE FROM hub_drafts WHERE owner_key = ?", (owner_key,))
        conn.commit()
        return {"ok": True, "url": f"/{name}"}
    finally:
        conn.close()


@app.post("/hub/map/create")
def hub_create_map(http_request: Request):
    """Pre-create a new map artifact with an auto-assigned numeric ID as name."""
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, http_request)
        if user is None:
            raise HTTPException(status_code=401, detail="Login required")
        now = _utc_now_iso()
        user_row = _hub_ensure_user(conn, user['username'])
        placeholder = f"_new_{secrets.token_hex(8)}"
        conn.execute(
            "INSERT INTO hub_artifacts(user_id, kind, name, alpha_content, alpha_metadata, created_at, updated_at)"
            " VALUES(?, 'map', ?, '', '{}', ?, ?)",
            (user_row['id'], placeholder, now, now)
        )
        artifact_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
        id_name = str(artifact_id)
        conn.execute("UPDATE hub_artifacts SET name = ? WHERE id = ?", (id_name, artifact_id))
        _ensure_owner_vote(conn, artifact_id, user_row['id'])
        conn.commit()
        return {"username": user['username'], "name": id_name, "id": artifact_id}
    finally:
        conn.close()


@app.put("/hub/{kind}/{name}/alpha")
def hub_save_alpha_by_name(kind: str, name: str, request: HubArtifactWriteRequest, http_request: Request, response: Response):
    """Save alpha by kind+name (no username required; globally unique)."""
    if kind not in HUB_KINDS:
        raise HTTPException(status_code=404, detail="Not found")
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact_by_name(conn, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        _require_write_identity(conn, http_request, artifact['username'])
        content = request.content or ""
        if len(content.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise HTTPException(status_code=413, detail="Content too large (max 10 MB)")
        md = dict(request.metadata or {})
        md["owner"] = artifact['username']
        md["updated_at"] = _utc_now_iso()
        art = _hub_upsert_alpha(conn, artifact['username'], kind, name, content, md)
        conn.commit()
        return _hub_artifact_response(conn, art, request=http_request)
    finally:
        conn.close()


@app.post("/hub/{kind}/{name}/publish")
def hub_publish_by_name(kind: str, name: str, request: HubArtifactWriteRequest, http_request: Request):
    """Publish a version by kind+name (no username required; globally unique)."""
    if kind not in HUB_KINDS:
        raise HTTPException(status_code=404, detail="Not found")
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact_by_name(conn, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        user_row = _require_write_identity(conn, http_request, artifact['username'])
        content = request.content or ""
        if len(content.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise HTTPException(status_code=413, detail="Content too large (max 10 MB)")
        md = dict(request.metadata or {})
        md["owner"] = artifact['username']
        md["updated_at"] = _utc_now_iso()
        latest_row = conn.execute(
            "SELECT content FROM hub_artifact_versions WHERE artifact_id = ? ORDER BY version DESC LIMIT 1",
            (artifact["id"],),
        ).fetchone()
        latest_content = latest_row["content"] if latest_row else ""
        if latest_content == content:
            resp = _hub_artifact_response(conn, artifact, request=http_request)
            resp["published"] = None
            resp["no_changes"] = True
            return resp
        publish_result = _hub_publish_version(conn, artifact['username'], kind, name, content, md)
        art = _hub_get_artifact_by_name(conn, kind, name)
        if art is None:
            raise HTTPException(status_code=500, detail="Artifact missing after publish")
        if kind == "map" and user_row is not None:
            _ensure_owner_vote(conn, art["id"], user_row["id"])
            conn.commit()
        response = _hub_artifact_response(conn, art, request=http_request)
        response["published"] = publish_result
        response["no_changes"] = False
        return response
    finally:
        conn.close()


@app.post("/hub/{kind}/{name}/disassociate")
def hub_disassociate_by_name(kind: str, name: str, http_request: Request):
    """Disassociate by kind+name (no username required)."""
    if kind not in HUB_KINDS:
        raise HTTPException(status_code=404, detail="Not found")
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact_by_name(conn, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        _require_write_identity(conn, http_request, artifact['username'])
        anon_row = conn.execute("SELECT id FROM hub_users WHERE username = ?", (ANONYMOUS_USERNAME,)).fetchone()
        if anon_row is None:
            raise HTTPException(status_code=500, detail="Anonymous user missing")
        artifact_id = artifact["id"]
        new_name = f"{name}_{artifact_id}"
        while conn.execute("SELECT id FROM hub_artifacts WHERE kind = ? AND name = ?", (kind, new_name)).fetchone():
            new_name = f"{new_name}_{artifact_id}"
        conn.execute(
            "UPDATE hub_artifacts SET user_id = ?, name = ?, updated_at = ? WHERE id = ?",
            (anon_row["id"], new_name, _utc_now_iso(), artifact_id),
        )
        conn.commit()
        return {"ok": True, "new_slug": f"/{kind}/{new_name}"}
    finally:
        conn.close()


@app.get("/hub/{kind}/{name}")
def hub_get_artifact_by_kind_name(kind: str, name: str, http_request: Request):
    """Get artifact by kind+name (no username required; globally unique)."""
    if kind not in HUB_KINDS:
        raise HTTPException(status_code=404, detail="Not found")
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact_by_name(conn, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return _hub_artifact_response(conn, artifact, request=http_request)
    finally:
        conn.close()


@app.get("/hub/{kind}/{name}/{version}")
def hub_get_artifact_version_by_name(kind: str, name: str, version: str, http_request: Request):
    """Get a specific version of an artifact by kind+name (globally unique)."""
    if kind not in HUB_KINDS:
        raise HTTPException(status_code=404, detail="Not found")
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact_by_name(conn, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        # Delegate to the existing version handler with resolved username
        return hub_get_artifact_version(
            username=artifact['username'], kind=kind, name=name,
            version=version, http_request=http_request
        )
    finally:
        conn.close()


@app.post("/hub/users/ensure")
def hub_ensure_user(body: HubEnsureUserRequest, http_request: Request, response: Response):
    ip = (http_request.client.host if http_request.client else "unknown")
    _check_rate_limit(f"ensure_user:{ip}", limit=10, window_seconds=3600)
    conn = _hub_db_conn()
    try:
        caller = _request_user(conn, http_request)
        if caller is None and not http_request.cookies.get("xatra_guest"):
            raise HTTPException(status_code=401, detail="Session required")
        user = _hub_ensure_user(conn, body.username)
        conn.commit()
        return {"username": user["username"], "created_at": user["created_at"]}
    finally:
        conn.close()


@app.put("/hub/{username}/{kind}/{name}/alpha")
def hub_save_alpha(username: str, kind: str, name: str, request: HubArtifactWriteRequest, http_request: Request, response: Response):
    conn = _hub_db_conn()
    try:
        _require_write_identity(conn, http_request, username)
        content = request.content or ""
        if len(content.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise HTTPException(status_code=413, detail="Content too large (max 10 MB)")
        # For map metadata, automatically preserve owner and updated_at.
        md = dict(request.metadata or {})
        md["owner"] = _normalize_hub_user(username)
        md["updated_at"] = _utc_now_iso()
        artifact = _hub_upsert_alpha(conn, username, kind, name, content, md)
        conn.commit()
        return _hub_artifact_response(conn, artifact, request=http_request)
    finally:
        conn.close()


@app.post("/hub/{username}/{kind}/{name}/publish")
def hub_publish(username: str, kind: str, name: str, request: HubArtifactWriteRequest, http_request: Request):
    conn = _hub_db_conn()
    try:
        user_row = _require_write_identity(conn, http_request, username)
        content = request.content or ""
        if len(content.encode("utf-8")) > MAX_ARTIFACT_BYTES:
            raise HTTPException(status_code=413, detail="Content too large (max 10 MB)")
        md = dict(request.metadata or {})
        md["owner"] = _normalize_hub_user(username)
        md["updated_at"] = _utc_now_iso()
        current = _hub_get_artifact(conn, username, kind, name)
        if current is not None:
            latest_row = conn.execute(
                "SELECT content FROM hub_artifact_versions WHERE artifact_id = ? ORDER BY version DESC LIMIT 1",
                (current["id"],),
            ).fetchone()
            latest_content = latest_row["content"] if latest_row else ""
            if latest_content == content:
                resp = _hub_artifact_response(conn, current, request=http_request)
                resp["published"] = None
                resp["no_changes"] = True
                return resp
        publish_result = _hub_publish_version(conn, username, kind, name, content, md)
        artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            raise HTTPException(status_code=500, detail="Artifact missing after publish")
        # Auto-like own map on publish (idempotent — only if not already voted)
        if kind == "map" and user_row is not None:
            _ensure_owner_vote(conn, artifact["id"], user_row["id"])
            conn.commit()
        response = _hub_artifact_response(conn, artifact, request=http_request)
        response["published"] = publish_result
        response["no_changes"] = False
        return response
    finally:
        conn.close()


@app.post("/hub/{username}/{kind}/{name}/disassociate")
def hub_disassociate(username: str, kind: str, name: str, http_request: Request):
    """Transfer ownership of an artifact to the anonymous user, removing the author's ownership."""
    conn = _hub_db_conn()
    try:
        _require_write_identity(conn, http_request, username)
        kind = _normalize_hub_kind(kind)
        artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        # Ensure the anonymous user exists.
        anon_row = conn.execute(
            "SELECT id FROM hub_users WHERE username = ?", (ANONYMOUS_USERNAME,)
        ).fetchone()
        if anon_row is None:
            raise HTTPException(status_code=500, detail="Anonymous user missing")
        # Choose a globally unique name (names are globally unique per kind now).
        artifact_id = artifact["id"]
        new_name = f"{name}_{artifact_id}"
        while conn.execute(
            "SELECT id FROM hub_artifacts WHERE kind = ? AND name = ?",
            (kind, new_name),
        ).fetchone():
            new_name = f"{new_name}_{artifact_id}"
        # Update the artifact's owner and name.
        conn.execute(
            "UPDATE hub_artifacts SET user_id = ?, name = ?, updated_at = ? WHERE id = ?",
            (anon_row["id"], new_name, _utc_now_iso(), artifact_id),
        )
        conn.commit()
        return {"ok": True, "new_slug": f"/{kind}/{new_name}"}
    finally:
        conn.close()


@app.get("/hub/{username}/{kind}/{name}")
def hub_get_artifact(username: str, kind: str, name: str, http_request: Request):
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return _hub_artifact_response(conn, artifact, request=http_request)
    finally:
        conn.close()


@app.get("/hub/{username}/{kind}/{name}/{version}")
def hub_get_artifact_version(username: str, kind: str, name: str, version: str, http_request: Request):
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        if str(version).strip().lower() == "alpha":
            if artifact["kind"] == "map":
                _ensure_owner_vote(conn, artifact["id"], artifact["user_id"])
                conn.commit()
            return {
                "username": artifact["username"],
                "kind": _hub_kind_label(artifact["kind"]),
                "name": artifact["name"],
                "version": "alpha",
                "content": artifact["alpha_content"] or "",
                "metadata": _sanitize_artifact_metadata(artifact["kind"], artifact["alpha_metadata"]),
                "updated_at": artifact["updated_at"],
                "slug": f'/{_hub_kind_label(artifact["kind"])}/{artifact["name"]}/alpha',
                "votes": _map_vote_count(conn, artifact["id"]) if artifact["kind"] == "map" else 0,
                "views": _map_view_count(conn, artifact["id"]) if artifact["kind"] == "map" else 0,
                "viewer_voted": _viewer_has_voted(conn, artifact["id"], http_request) if artifact["kind"] == "map" else False,
            }
        if not str(version).isdigit():
            raise HTTPException(status_code=400, detail="version must be 'alpha' or integer")
        row = conn.execute(
            """
            SELECT version, content, metadata, created_at
            FROM hub_artifact_versions
            WHERE artifact_id = ? AND version = ?
            """,
            (artifact["id"], int(version)),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Published version not found")
        return {
            "username": artifact["username"],
            "kind": _hub_kind_label(artifact["kind"]),
            "name": artifact["name"],
            "version": int(row["version"]),
            "content": row["content"] or "",
            "metadata": _sanitize_artifact_metadata(artifact["kind"], row["metadata"]),
            "created_at": row["created_at"],
            "slug": f'/{_hub_kind_label(artifact["kind"])}/{artifact["name"]}/{int(row["version"])}',
            "votes": _map_vote_count(conn, artifact["id"]) if artifact["kind"] == "map" else 0,
            "views": _map_view_count(conn, artifact["id"]) if artifact["kind"] == "map" else 0,
            "viewer_voted": _viewer_has_voted(conn, artifact["id"], http_request) if artifact["kind"] == "map" else False,
        }
    finally:
        conn.close()


@app.get("/hub/registry")
def hub_registry(
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
):
    normalized_kind = None
    if kind is not None and str(kind).strip():
        normalized_kind = _normalize_hub_kind(kind)
    raw_query = str(q or "").strip().lower()
    user_filter = None
    terms: List[str] = []
    for token in raw_query.split():
        if token.startswith("user:") and len(token) > 5:
            user_filter = token[5:]
        elif token:
            terms.append(token)
    safe_limit = max(1, min(int(limit or 50), 200))
    conn = _hub_db_conn()
    try:
        where = []
        params: List[Any] = []
        if normalized_kind:
            where.append("a.kind = ?")
            params.append(normalized_kind)
        if user_filter:
            where.append("LOWER(u.username) = ?")
            params.append(user_filter)
        for term in terms:
            where.append("(LOWER(a.name) LIKE ? ESCAPE '\\' OR LOWER(u.username) LIKE ? ESCAPE '\\' OR LOWER(a.alpha_metadata) LIKE ? ESCAPE '\\')")
            escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            like = f"%{escaped}%"
            params.extend([like, like, like])
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"""
            SELECT
                a.id, a.kind, a.name, a.updated_at,
                u.username,
                COALESCE(MAX(v.version), 0) AS latest_version,
                COUNT(DISTINCT vv.id) AS votes_count,
                COUNT(DISTINCT mv.id) AS views_count
            FROM hub_artifacts a
            JOIN hub_users u ON u.id = a.user_id
            LEFT JOIN hub_artifact_versions v ON v.artifact_id = a.id
            LEFT JOIN hub_votes vv ON vv.artifact_id = a.id
            LEFT JOIN hub_map_views mv ON mv.artifact_id = a.id
            {where_sql}
            GROUP BY a.id, a.kind, a.name, a.updated_at, u.username
            ORDER BY votes_count DESC, views_count DESC, a.updated_at DESC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()
        items = []
        for row in rows:
            kind_label = _hub_kind_label(row["kind"])
            latest = int(row["latest_version"]) if int(row["latest_version"]) > 0 else None
            meta = _json_parse(conn.execute("SELECT alpha_metadata FROM hub_artifacts WHERE id = ?", (row["id"],)).fetchone()["alpha_metadata"], {})
            items.append({
                "username": row["username"],
                "kind": kind_label,
                "name": row["name"],
                "slug": f'/{kind_label}/{row["name"]}',
                "latest_version": latest,
                "updated_at": row["updated_at"],
                "votes": int(row["votes_count"] or 0),
                "views": int(row["views_count"] or 0),
                "thumbnail": meta.get("thumbnail") or "/vite.svg",
            })
        return {"items": items}
    finally:
        conn.close()


@app.get("/registry")
def hub_registry_alias(
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
):
    return hub_registry(kind=kind, q=q, limit=limit)

@app.post("/stop")
def stop_generation(http_request: Request, request: Optional[StopRequest] = Body(default=None)):
    # Require either an authenticated session or a guest cookie to prevent unauthenticated
    # external callers from stopping renders.
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, http_request)
        guest_id = http_request.cookies.get(GUEST_COOKIE)
        if user is None and not (guest_id and guest_id.strip()):
            raise HTTPException(status_code=401, detail="Login required")
    finally:
        conn.close()
    allowed_task_types = {"picker", "territory_library", "code", "builder"}
    requested = request.task_types if request and request.task_types else list(allowed_task_types)
    task_types = [t for t in requested if t in allowed_task_types]
    stopped = []
    with process_lock:
        for task_type in task_types:
            proc = current_processes.get(task_type)
            if proc and proc.is_alive():
                proc.terminate()
                proc.join()
                stopped.append(task_type)
            current_processes[task_type] = None
    return {"status": "stopped" if stopped else "no process running", "stopped_task_types": stopped}


def _parse_xatrahub_path(path: str) -> Dict[str, Any]:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("xatrahub path is empty")
    if raw.startswith("xatrahub("):
        raise ValueError("xatrahub path must be a path string, not xatrahub(...)")
    cleaned = raw.strip().strip('"').strip("'")
    parts = [p for p in cleaned.split("/") if p]
    # New format: /kind/name[/version]  (2-3 parts, kind is first)
    if len(parts) >= 2 and parts[0].lower() in HUB_KINDS:
        kind = _normalize_hub_kind(parts[0])
        name = _normalize_hub_name(parts[1])
        version = "alpha"
        if len(parts) >= 3 and parts[2]:
            version = parts[2].strip()
        return {"username": None, "kind": kind, "name": name, "version": version}
    # Old format: /username/kind/name[/version]  (3-4 parts)
    if len(parts) < 3:
        raise ValueError("xatrahub path must be /{kind}/name[/version] or /username/{kind}/name[/version]")
    username = _normalize_hub_user(parts[0])
    kind = _normalize_hub_kind(parts[1])
    name = _normalize_hub_name(parts[2])
    version = "alpha"
    if len(parts) >= 4 and parts[3]:
        version = parts[3].strip()
    return {"username": username, "kind": kind, "name": name, "version": version}


def _hub_load_content(username: Optional[str], kind: str, name: str, version: str = "alpha") -> Dict[str, Any]:
    conn = _hub_db_conn()
    try:
        if username is None:
            artifact = _hub_get_artifact_by_name(conn, kind, name)
        else:
            artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            path = f"/{kind}/{name}" if username is None else f"/{username}/{kind}/{name}"
            raise ValueError(f"xatrahub artifact not found: {path}")
        if str(version).lower() == "alpha":
            return {
                "username": artifact["username"],
                "kind": _hub_kind_label(artifact["kind"]),
                "name": artifact["name"],
                "version": "alpha",
                "content": artifact["alpha_content"] or "",
                "metadata": _sanitize_artifact_metadata(artifact["kind"], artifact["alpha_metadata"]),
            }
        if not str(version).isdigit():
            raise ValueError("xatrahub version must be integer or alpha")
        row = conn.execute(
            """
            SELECT version, content, metadata
            FROM hub_artifact_versions
            WHERE artifact_id = ? AND version = ?
            """,
            (artifact["id"], int(version)),
        ).fetchone()
        if row is None:
            path = f"/{kind}/{name}" if username is None else f"/{username}/{kind}/{name}"
            raise ValueError(f"xatrahub published version not found: {path}/{version}")
        return {
            "username": artifact["username"],
            "kind": _hub_kind_label(artifact["kind"]),
            "name": artifact["name"],
            "version": int(row["version"]),
            "content": row["content"] or "",
            "metadata": _sanitize_artifact_metadata(artifact["kind"], row["metadata"]),
        }
    finally:
        conn.close()


def _extract_python_payload_text(kind: str, content: str, metadata: Dict[str, Any]) -> str:
    text = content or ""
    parsed = _json_parse(text, None)
    if isinstance(parsed, dict):
        if kind == "lib":
            for key in ("predefined_code", "code", "content"):
                val = parsed.get(key)
                if isinstance(val, str):
                    return val
        if kind == "css":
            for key in ("theme_code", "code", "content"):
                val = parsed.get(key)
                if isinstance(val, str):
                    return val
        if kind == "map":
            parts = []
            for key in ("imports_code", "theme_code", "map_code", "runtime_code", "code"):
                val = parsed.get(key)
                if isinstance(val, str) and val.strip():
                    parts.append(val)
            if parts:
                return "\n\n".join(parts)
        val = parsed.get("code")
        if isinstance(val, str):
            return val
    if isinstance(metadata, dict):
        candidate = metadata.get("code")
        if isinstance(candidate, str):
            return candidate
    return text


def _filter_xatra_code(code: str, filter_only: Optional[List[str]] = None, filter_not: Optional[List[str]] = None) -> str:
    if not code or (not filter_only and not filter_not):
        return code or ""
    only = {str(x).strip() for x in (filter_only or []) if str(x).strip()}
    blocked = {str(x).strip() for x in (filter_not or []) if str(x).strip()}
    try:
        tree = ast.parse(code)
    except Exception:
        return code
    kept: List[str] = []
    for stmt in tree.body:
        segment = _python_expr_from_node(code, stmt) or ""
        if not segment:
            try:
                segment = ast.unparse(stmt)
            except Exception:
                continue
        keep_stmt = True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            name = _call_name(stmt.value.func)
            if name and name.startswith("xatra."):
                method = name.split(".", 1)[1]
                if only and method not in only:
                    keep_stmt = False
                if method in blocked:
                    keep_stmt = False
        if keep_stmt:
            kept.append(segment)
    return "\n".join(kept)

def run_rendering_task(task_type, data, result_queue):
    music_temp_files: List[str] = []

    def parse_color_list(val):
        if not val or not isinstance(val, str) or not val.strip():
            return None
        compact = val.strip()
        if ',' not in compact and compact in color_sequences:
            try:
                return [Color.rgb(*rgb) for rgb in color_sequences[compact]]
            except Exception:
                return None
        out = []
        for token in [c.strip() for c in val.split(',') if c.strip()]:
            try:
                if token.startswith('#'):
                    out.append(Color.hex(token))
                else:
                    out.append(Color.named(token.lower()))
            except Exception:
                continue
        return out if out else None

    def build_linear_sequence_from_row(row):
        if not isinstance(row, dict):
            return None
        try:
            step_h = float(row.get("step_h", 1.6180339887))
        except Exception:
            step_h = 1.6180339887
        try:
            step_s = float(row.get("step_s", 0.0))
        except Exception:
            step_s = 0.0
        try:
            step_l = float(row.get("step_l", 0.0))
        except Exception:
            step_l = 0.0
        colors = parse_color_list(row.get("colors"))
        return LinearColorSequence(colors=colors, step=Color.hsl(step_h, step_s, step_l))

    def apply_basemaps(basemaps):
        if isinstance(basemaps, list) and len(basemaps) > 0:
            for bm in basemaps:
                if isinstance(bm, dict):
                    m.BaseOption(**bm)
                else:
                    m.BaseOption(bm)
            return
        m.BaseOption("Esri.WorldTopoMap", default=True)

    def eval_python_expr_value(value, eval_globals):
        if _is_python_expr_value(value):
            expr = value.get(PYTHON_EXPR_KEY, "").strip()
            if not expr:
                return None
            try:
                return eval(expr, eval_globals)
            except Exception:
                return None
        return value

    def resolve_builder_value(value, eval_globals):
        evaluated = eval_python_expr_value(value, eval_globals)
        if evaluated is not value:
            return evaluated
        if isinstance(value, list):
            return [resolve_builder_value(v, eval_globals) for v in value]
        if isinstance(value, dict):
            if _is_python_expr_value(value):
                return eval_python_expr_value(value, eval_globals)
            return {k: resolve_builder_value(v, eval_globals) for k, v in value.items()}
        return value

    def register_xatrahub(exec_globals):
        def xatrahub(path, filter_only=None, filter_not=None):
            parsed = _parse_xatrahub_path(str(path))
            loaded = _hub_load_content(
                parsed["username"],
                parsed["kind"],
                parsed["name"],
                parsed["version"],
            )
            code_text = _extract_python_payload_text(
                loaded["kind"],
                loaded.get("content", ""),
                loaded.get("metadata", {}) if isinstance(loaded.get("metadata"), dict) else {},
            )
            kind = loaded["kind"]
            only = filter_only if isinstance(filter_only, list) else None
            not_list = filter_not if isinstance(filter_not, list) else None
            if kind in ("map", "css"):
                filtered = _filter_xatra_code(code_text, filter_only=only, filter_not=not_list)
                if filtered.strip():
                    exec(filtered, exec_globals)
                return None
            if kind == "lib":
                lib_globals = {
                    "xatra": xatra,
                    "gadm": xatra.loaders.gadm,
                    "naturalearth": xatra.loaders.naturalearth,
                    "polygon": xatra.loaders.polygon,
                    "overpass": xatra.loaders.overpass,
                    "Icon": Icon,
                    "Color": Color,
                    "ColorSequence": ColorSequence,
                    "LinearColorSequence": LinearColorSequence,
                    "LinearSegmentedColormap": __import__("matplotlib.colors", fromlist=["LinearSegmentedColormap"]).LinearSegmentedColormap,
                    "plt": __import__("matplotlib.pyplot", fromlist=["pyplot"]),
                }
                if "xatrahub" in exec_globals:
                    lib_globals["xatrahub"] = exec_globals["xatrahub"]
                exec(code_text or "", lib_globals)
                names = [
                    name for name in lib_globals.keys()
                    if not name.startswith("_") and name not in {"xatra", "gadm", "naturalearth", "polygon", "overpass", "Icon", "Color", "ColorSequence", "LinearColorSequence", "xatrahub"}
                ]
                payload = {name: lib_globals[name] for name in names}
                return SimpleNamespace(**payload)
            raise ValueError(f"Unsupported xatrahub kind: {kind}")

        exec_globals["xatrahub"] = xatrahub

    def materialize_music_path(music_value):
        if not isinstance(music_value, str):
            return music_value
        raw = music_value.strip()
        if not raw.startswith("data:"):
            return raw
        try:
            import base64
            import mimetypes
            import tempfile
            header, b64data = raw.split(",", 1)
            mime_match = re.match(r"^data:([^;]+);base64$", header)
            mime = mime_match.group(1) if mime_match else "audio/mpeg"
            ext = mimetypes.guess_extension(mime) or ".mp3"
            decoded = base64.b64decode(b64data)
            fd, tmp_path = tempfile.mkstemp(prefix="xatra_music_", suffix=ext)
            with os.fdopen(fd, "wb") as f:
                f.write(decoded)
            music_temp_files.append(tmp_path)
            return tmp_path
        except Exception:
            return raw

    try:
        # Re-import xatra inside the process just in case, though imports are inherited on fork (mostly)
        # But we need fresh map state
        import xatra
        xatra.new_map()
        m = xatra.get_current_map()
        
        if task_type == 'picker':
            apply_basemaps(getattr(data, "basemaps", None))
            for entry in data.entries:
                m.Admin(gadm=entry.country, level=entry.level)
            if data.adminRivers:
                m.AdminRivers()
        elif task_type == 'territory_library':
            apply_basemaps(getattr(data, "basemaps", None))
            import xatra.territory_library as territory_library
            source = (getattr(data, "source", "builtin") or "builtin").strip().lower()
            code = getattr(data, "predefined_code", "") or ""
            hub_path = getattr(data, "hub_path", None)
            catalog = _get_territory_catalog(source, code, hub_path)
            selected_input = getattr(data, "selected_names", None)
            if isinstance(selected_input, list):
                selected_names = [str(n) for n in selected_input if isinstance(n, str)]
            else:
                selected_names = catalog.get("index_names", [])
            selected_names = [n for n in selected_names if n in catalog.get("names", [])]

            if source == "custom":
                exec_globals = {
                    "gadm": xatra.loaders.gadm,
                    "polygon": xatra.loaders.polygon,
                    "naturalearth": xatra.loaders.naturalearth,
                    "overpass": xatra.loaders.overpass,
                }
                for name in dir(territory_library):
                    if not name.startswith("_"):
                        exec_globals[name] = getattr(territory_library, name)
                if code.strip():
                    exec(code, exec_globals)
                for n in selected_names:
                    terr = exec_globals.get(n)
                    if terr is not None:
                        try:
                            m.Flag(label=n, value=terr)
                        except Exception:
                            continue
            elif source == "hub" and hub_path:
                try:
                    parsed = _parse_xatrahub_path(hub_path)
                    loaded = _hub_load_content(parsed["username"], parsed["kind"], parsed["name"], parsed["version"])
                    code_text = _extract_python_payload_text(loaded["kind"], loaded.get("content", ""), loaded.get("metadata", {}))
                    scope = {
                        "gadm": xatra.loaders.gadm,
                        "polygon": xatra.loaders.polygon,
                        "naturalearth": xatra.loaders.naturalearth,
                        "overpass": xatra.loaders.overpass,
                    }
                    exec(code_text or "", scope)
                    for n in selected_names:
                        terr = scope.get(n)
                        if terr is not None:
                            try:
                                m.Flag(label=n, value=terr)
                            except Exception:
                                continue
                except Exception:
                    pass
            else:
                for n in selected_names:
                    terr = getattr(territory_library, n, None)
                    if terr is not None:
                        try:
                            m.Flag(label=n, value=terr)
                        except Exception:
                            continue
                
        elif task_type == 'code':
            exec_globals = {
                "xatra": xatra,
                "gadm": xatra.loaders.gadm,
                "naturalearth": xatra.loaders.naturalearth,
                "polygon": xatra.loaders.polygon,
                "overpass": xatra.loaders.overpass,
                "map": m,
                "Icon": Icon,
                "Color": Color,
                "ColorSequence": ColorSequence,
                "LinearColorSequence": LinearColorSequence,
                "LinearSegmentedColormap": __import__("matplotlib.colors", fromlist=["LinearSegmentedColormap"]).LinearSegmentedColormap,
                "plt": __import__("matplotlib.pyplot", fromlist=["pyplot"]),
            }
            register_xatrahub(exec_globals)
            imports_code = getattr(data, "imports_code", "") or ""
            theme_code = getattr(data, "theme_code", "") or ""
            runtime_code = getattr(data, "runtime_code", "") or ""
            predefined_code = getattr(data, "predefined_code", "") or ""
            if imports_code.strip():
                exec(imports_code, exec_globals)
            if predefined_code.strip():
                import xatra.territory_library as territory_library
                for name in dir(territory_library):
                    if not name.startswith("_"):
                        exec_globals[name] = getattr(territory_library, name)
                exec(predefined_code, exec_globals)
            if theme_code.strip():
                exec(theme_code, exec_globals)
            exec(data.code, exec_globals)
            if runtime_code.strip():
                exec(runtime_code, exec_globals)
            m = xatra.get_current_map() # Refresh in case they used map = xatra.Map()
            
        elif task_type == 'builder':
            # Apply options
            if "basemaps" in data.options:
                for bm in data.options["basemaps"]:
                    if isinstance(bm, dict):
                        m.BaseOption(**bm)
                    else:
                        m.BaseOption(bm)
            
            if "css_rules" in data.options:
                css_str = ""
                for rule in data.options["css_rules"]:
                    selector = rule.get("selector", "")
                    style = rule.get("style", "")
                    if selector and style:
                        css_str += f"{selector} {{ {style} }}\n"
                if css_str:
                    m.CSS(css_str)
            
            if "slider" in data.options:
                sl = data.options["slider"]
                start = sl.get("start")
                end = sl.get("end")
                speed = sl.get("speed")
                if isinstance(start, str) and start.strip():
                     try: start = int(start)
                     except: start = None
                elif isinstance(start, str): start = None
                if isinstance(end, str) and end.strip():
                     try: end = int(end)
                     except: end = None
                elif isinstance(end, str): end = None
                
                if start is not None or end is not None:
                    m.slider(start=start, end=end, speed=speed if speed else 5.0)

            if "zoom" in data.options and data.options["zoom"] is not None:
                 try: m.zoom(int(data.options["zoom"]))
                 except: pass
                 
            if "focus" in data.options and data.options["focus"]:
                 focus = data.options["focus"]
                 if isinstance(focus, list) and len(focus) == 2:
                     try: m.focus(float(focus[0]), float(focus[1]))
                     except: pass

            if "flag_color_sequences" in data.options and isinstance(data.options["flag_color_sequences"], list):
                for row in data.options["flag_color_sequences"]:
                    seq = build_linear_sequence_from_row(row)
                    if not seq:
                        continue
                    class_name = row.get("class_name")
                    if isinstance(class_name, str):
                        class_name = class_name.strip() or None
                    else:
                        class_name = None
                    m.FlagColorSequence(seq, class_name=class_name)
            elif "flag_colors" in data.options:
                m.FlagColorSequence(
                    LinearColorSequence(
                        colors=parse_color_list(data.options["flag_colors"]),
                        step=Color.hsl(1.6180339887, 0.0, 0.0),
                    )
                )
            
            if "admin_colors" in data.options:
                seq = parse_color_list(data.options["admin_colors"])
                if seq:
                    m.AdminColorSequence(LinearColorSequence(colors=seq, step=Color.hsl(1.6180339887, 0.0, 0.0)))
            if "admin_color_sequences" in data.options and isinstance(data.options["admin_color_sequences"], list):
                row = data.options["admin_color_sequences"][0] if data.options["admin_color_sequences"] else None
                if row:
                    seq = build_linear_sequence_from_row(row)
                    if seq:
                        m.AdminColorSequence(seq)
                    
            if "data_colormap" in data.options and data.options["data_colormap"]:
                dc = data.options["data_colormap"]
                if isinstance(dc, dict):
                    cmap_type = str(dc.get("type", "")).strip()
                    if cmap_type == "LinearSegmented":
                        from matplotlib.colors import LinearSegmentedColormap
                        colors_raw = str(dc.get("colors", "yellow,orange,red"))
                        colors = [c.strip() for c in colors_raw.split(",") if c.strip()]
                        if not colors:
                            colors = ["yellow", "orange", "red"]
                        cmap = LinearSegmentedColormap.from_list("custom_cmap", colors)
                        m.DataColormap(cmap)
                    elif cmap_type:
                        _VALID_CMAPS = {
                            "viridis", "plasma", "inferno", "magma", "cividis",
                            "RdYlGn", "RdYlBu", "Spectral",
                            "Greys", "Purples", "Blues", "Greens", "Oranges", "Reds",
                            "YlOrBr", "YlOrRd", "OrRd", "PuRd", "RdPu", "BuPu",
                            "GnBu", "PuBu", "YlGnBu", "PuBuGn", "BuGn", "YlGn",
                            "gray", "bone", "pink", "spring", "summer", "autumn", "winter",
                            "cool", "hot", "afmhot", "gist_heat", "copper",
                            "PiYG", "PRGn", "BrBG", "PuOr", "RdGy", "RdBu",
                            "RdYlBu", "RdYlGn", "Spectral", "coolwarm", "bwr", "seismic",
                            "twilight", "twilight_shifted", "hsv",
                            "ocean", "gist_earth", "terrain", "gist_stern",
                            "gnuplot", "gnuplot2", "CMRmap", "cubehelix", "brg",
                            "rainbow", "jet", "turbo", "nipy_spectral",
                        }
                        if cmap_type in _VALID_CMAPS:
                            import matplotlib.pyplot as plt
                            cmap = getattr(plt.cm, cmap_type, None)
                            if cmap is not None:
                                m.DataColormap(cmap)
                elif isinstance(dc, str):
                    m.DataColormap(dc)

            # Execute predefined territory code so Flag parts of type "predefined" can use them
            predefined_namespace = {}
            if getattr(data, "predefined_code", None) and data.predefined_code.strip():
                try:
                    import xatra.territory_library as territory_library
                    exec_globals = {
                        "gadm": xatra.loaders.gadm,
                        "polygon": xatra.loaders.polygon,
                        "naturalearth": xatra.loaders.naturalearth,
                        "overpass": xatra.loaders.overpass,
                        "xatra": xatra,
                        "Icon": Icon,
                        "Color": Color,
                        "ColorSequence": ColorSequence,
                        "LinearColorSequence": LinearColorSequence,
                        "LinearSegmentedColormap": __import__("matplotlib.colors", fromlist=["LinearSegmentedColormap"]).LinearSegmentedColormap,
                        "plt": __import__("matplotlib.pyplot", fromlist=["pyplot"]),
                    }
                    register_xatrahub(exec_globals)
                    for name in dir(territory_library):
                        if not name.startswith("_"):
                            exec_globals[name] = getattr(territory_library, name)
                    exec(data.predefined_code.strip(), exec_globals)
                    predefined_namespace = {k: v for k, v in exec_globals.items() if k not in ("gadm", "polygon", "naturalearth", "overpass") and not k.startswith("_")}
                except Exception:
                    predefined_namespace = {}

            builder_exec_globals = {
                "xatra": xatra,
                "gadm": xatra.loaders.gadm,
                "polygon": xatra.loaders.polygon,
                "naturalearth": xatra.loaders.naturalearth,
                "overpass": xatra.loaders.overpass,
                "Icon": Icon,
                "Color": Color,
                "ColorSequence": ColorSequence,
                "LinearColorSequence": LinearColorSequence,
                "LinearSegmentedColormap": __import__("matplotlib.colors", fromlist=["LinearSegmentedColormap"]).LinearSegmentedColormap,
                "plt": __import__("matplotlib.pyplot", fromlist=["pyplot"]),
                "map": m,
            }
            if predefined_namespace:
                builder_exec_globals.update(predefined_namespace)
            register_xatrahub(builder_exec_globals)

            imports_code = getattr(data, "imports_code", "") or ""
            theme_code = getattr(data, "theme_code", "") or ""
            runtime_code = getattr(data, "runtime_code", "") or ""
            if imports_code.strip():
                exec(imports_code, builder_exec_globals)
            if theme_code.strip():
                exec(theme_code, builder_exec_globals)

            def _is_empty_builder_arg(value):
                if value is None:
                    return True
                if isinstance(value, str) and value.strip() == "":
                    return True
                if isinstance(value, (list, tuple, set, dict)) and len(value) == 0:
                    return True
                return False

            def _clean_builder_args(arg_dict):
                return {k: v for k, v in (arg_dict or {}).items() if not _is_empty_builder_arg(v)}

            for el in data.elements:
                args = resolve_builder_value(el.args.copy(), builder_exec_globals) if isinstance(el.args, dict) else {}
                resolved_label = resolve_builder_value(el.label, builder_exec_globals)
                if resolved_label not in (None, ""):
                    args["label"] = resolved_label
                args = _clean_builder_args(args)
                    
                if el.type == "flag":
                    args.pop("parent", None)
                    def _eval_part(part):
                        if not isinstance(part, dict):
                            return None
                        ptype = part.get("type", "gadm")
                        val = part.get("value")
                        if ptype == "group":
                            if not isinstance(val, list):
                                return None
                            return _eval_parts(val)
                        if ptype == "gadm":
                            vals = val if isinstance(val, list) else [val]
                            out = None
                            for item in vals:
                                if not item:
                                    continue
                                t = xatra.loaders.gadm(item)
                                out = t if out is None else (out | t)
                            return out
                        if ptype == "polygon":
                            try:
                                coords = json.loads(val) if isinstance(val, str) else val
                                return xatra.loaders.polygon(coords)
                            except Exception:
                                return None
                        if ptype == "predefined":
                            vals = val if isinstance(val, list) else [val]
                            out = None
                            for item in vals:
                                if not item:
                                    continue
                                # Support dotted attribute access like "indic.KURU".
                                # Use builder_exec_globals so hub lib namespaces (added by
                                # imports_code) are also accessible, not just predefined_namespace.
                                parts_list = str(item).split('.')
                                obj = builder_exec_globals.get(parts_list[0])
                                for attr in parts_list[1:]:
                                    if obj is None:
                                        break
                                    obj = getattr(obj, attr, None)
                                t = obj
                                if t is not None:
                                    out = t if out is None else (out | t)
                            return out
                        return None

                    def _eval_parts(parts):
                        territory_obj = None
                        if not isinstance(parts, list):
                            return None
                        for part in parts:
                            op = (part.get("op", "union") if isinstance(part, dict) else "union")
                            part_terr = _eval_part(part)
                            if part_terr is None:
                                continue
                            if territory_obj is None:
                                territory_obj = part_terr
                            else:
                                if op == "difference":
                                    territory_obj = territory_obj - part_terr
                                elif op == "intersection":
                                    territory_obj = territory_obj & part_terr
                                else:
                                    territory_obj = territory_obj | part_terr
                        return territory_obj

                    if isinstance(el.value, str):
                        territory = xatra.loaders.gadm(el.value)
                    elif isinstance(el.value, list):
                        territory = _eval_parts(el.value) if (len(el.value) > 0 and isinstance(el.value[0], dict)) else None
                        if territory is None and el.value and not isinstance(el.value[0], dict):
                            # Fallback: treat bare string list as GADM codes
                            for code in el.value:
                                if not isinstance(code, str):
                                    continue
                                t = xatra.loaders.gadm(code)
                                territory = t if territory is None else (territory | t)
                    else:
                        continue
                    m.Flag(value=territory, **args)
                    
                elif el.type == "river":
                    source_type = args.get("source_type", "naturalearth")
                    if "source_type" in args: del args["source_type"]
                    river_value = resolve_builder_value(el.value, builder_exec_globals)
                    if river_value is not None:
                        if source_type == "overpass":
                            geom = xatra.loaders.overpass(river_value)
                        else:
                            geom = xatra.loaders.naturalearth(river_value)
                        m.River(value=geom, **args)
                        
                elif el.type == "point":
                    pos = resolve_builder_value(el.value, builder_exec_globals)
                    if isinstance(pos, str):
                        try:
                            pos = json.loads(pos)
                        except Exception:
                            pass
                    icon_arg = args.pop("icon", None)
                    if icon_arg is not None and icon_arg != "":
                        try:
                            if isinstance(icon_arg, str):
                                args["icon"] = Icon.builtin(icon_arg)
                            elif isinstance(icon_arg, dict):
                                if "shape" in icon_arg:
                                    args["icon"] = Icon.geometric(
                                        icon_arg.get("shape", "circle"),
                                        color=icon_arg.get("color", "#3388ff"),
                                        size=int(icon_arg.get("size", 24)),
                                        border_color=icon_arg.get("border_color"),
                                        border_width=int(icon_arg.get("border_width", 0)),
                                    )
                                elif "icon_url" in icon_arg or "iconUrl" in icon_arg:
                                    url = icon_arg.get("icon_url") or icon_arg.get("iconUrl")
                                    args["icon"] = Icon(
                                        icon_url=url,
                                        icon_size=tuple(icon_arg.get("icon_size", icon_arg.get("iconSize", (25, 41)))),
                                        icon_anchor=tuple(icon_arg.get("icon_anchor", icon_arg.get("iconAnchor", (12, 41)))),
                                    )
                            else:
                                args["icon"] = icon_arg
                        except Exception:
                            pass
                    m.Point(position=pos, **args)
                    
                elif el.type == "text":
                    pos = resolve_builder_value(el.value, builder_exec_globals)
                    if isinstance(pos, str):
                        try:
                            pos = json.loads(pos)
                        except Exception:
                            pass
                    m.Text(position=pos, **args)
                
                elif el.type == "path":
                    val = resolve_builder_value(el.value, builder_exec_globals)
                    if isinstance(val, str):
                        try:
                            val = json.loads(val)
                        except Exception:
                            pass
                    m.Path(value=val, **args)
                    
                elif el.type == "admin":
                    if "label" in args: del args["label"]
                    m.Admin(gadm=resolve_builder_value(el.value, builder_exec_globals), **args)
                
                elif el.type == "admin_rivers":
                    if "label" in args: del args["label"]
                    sources = resolve_builder_value(el.value, builder_exec_globals)
                    if isinstance(sources, str):
                        try:
                            sources = json.loads(sources)
                        except Exception:
                            sources = [sources]
                    m.AdminRivers(sources=sources, **args)

                elif el.type == "dataframe":
                    import pandas as pd
                    import io
                    val = resolve_builder_value(el.value, builder_exec_globals)
                    if isinstance(val, str):
                        # Always treat the value as CSV content (never as a file path)
                        # to prevent path traversal attacks.
                        df = pd.read_csv(io.StringIO(val))
                        if "label" in args: del args["label"]
                        if args.get("data_column") in (None, ""): args.pop("data_column", None)
                        if args.get("year_columns") in (None, [], ""): args.pop("year_columns", None)
                        m.Dataframe(df, **args)
                    elif val is not None:
                        if "label" in args: del args["label"]
                        if args.get("data_column") in (None, ""): args.pop("data_column", None)
                        if args.get("year_columns") in (None, [], ""): args.pop("year_columns", None)
                        m.Dataframe(val, **args)
                elif el.type == "titlebox":
                    if "label" in args:
                        del args["label"]
                    title_val = resolve_builder_value(el.value, builder_exec_globals)
                    html = title_val if isinstance(title_val, str) else str(title_val or "")
                    m.TitleBox(html, **args)
                elif el.type == "music":
                    music_val = resolve_builder_value(el.value, builder_exec_globals)
                    if "label" in args:
                        del args["label"]
                    if "filename" in args:
                        del args["filename"]
                    music_path = materialize_music_path(music_val)
                    if music_path not in (None, ""):
                        m.Music(path=music_path, **args)
                elif el.type == "python":
                    code_line = el.value if isinstance(el.value, str) else str(el.value or "")
                    if code_line.strip():
                        exec(code_line, builder_exec_globals)

            if runtime_code.strip():
                exec(runtime_code, builder_exec_globals)

        m.TitleBox("<i>made with <a href='https://github.com/srajma/xatra'>xatra</a></i>")
        payload = m._export_json()
        html = export_html_string(payload)
        result = {"html": html, "payload": payload}
        if task_type == 'territory_library':
            source = (getattr(data, "source", "builtin") or "builtin").strip().lower()
            code = getattr(data, "predefined_code", "") or ""
            hub_path = getattr(data, "hub_path", None)
            catalog = _get_territory_catalog(source, code, hub_path)
            result["available_names"] = catalog.get("names", [])
            result["index_names"] = catalog.get("index_names", [])
        result_queue.put(result)
        
    except Exception as e:
        print(f"[xatra] Rendering error:\n{traceback.format_exc()}", file=sys.stderr)
        result_queue.put({"error": str(e)})
    finally:
        for tmp_path in music_temp_files:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def run_in_process(task_type, data):
    cache_key = None
    try:
        payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        cache_key = f"{task_type}:{json.dumps(payload, sort_keys=True, default=str)}"
    except Exception:
        cache_key = None

    if cache_key:
        with render_cache_lock:
            cached = render_cache.get(cache_key)
            if cached is not None:
                # Maintain LRU order
                render_cache.move_to_end(cache_key)
                return cached

    queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=run_rendering_task, args=(task_type, data, queue))

    # Kill any previous process and register+start the new one atomically inside the lock
    # to prevent a race window where another thread could see a registered-but-not-started
    # process and incorrectly terminate it.
    with process_lock:
        previous = current_processes.get(task_type)
        if previous and previous.is_alive():
            previous.terminate()
            previous.join()
        current_processes[task_type] = p
        p.start()
    
    result = {"error": "Rendering process timed out or crashed"}
    try:
        # Get result from queue with a timeout (60s)
        # IMPORTANT: Read from queue BEFORE join() to avoid deadlocks with large data
        result = queue.get(timeout=60)
    except Exception as e:
        result = {"error": f"Rendering failed: {str(e)}"}
    
    p.join(timeout=5)
    if p.is_alive():
        p.terminate()
        p.join()
        
    with process_lock:
        current_processes[task_type] = None

    if cache_key and isinstance(result, dict) and "error" not in result:
        with render_cache_lock:
            render_cache[cache_key] = result
            render_cache.move_to_end(cache_key)
            while len(render_cache) > RENDER_CACHE_MAX_ENTRIES:
                render_cache.popitem(last=False)

    return result

@app.post("/render/picker")
def render_picker(request: PickerRequest):
    result = run_in_process('picker', request)
    if "error" in result:
        return result
    return result

@app.post("/render/territory-library")
def render_territory_library(request: TerritoryLibraryRequest):
    result = run_in_process('territory_library', request)
    if "error" in result:
        return result
    return result

@app.post("/render/code")
def render_code(request: CodeRequest):
    result = run_in_process('code', request)
    if "error" in result:
        return result
    return result

@app.post("/render/builder")
def render_builder(request: BuilderRequest):
    result = run_in_process('builder', request)
    if "error" in result:
        return result
    return result


@app.get("/{username}/{kind}/{name}/{version}")
def public_hub_artifact_version(username: str, kind: str, name: str, version: str, http_request: Request):
    return hub_get_artifact_version(username=username, kind=kind, name=name, version=version, http_request=http_request)


@app.get("/{username}/{kind}/{name}")
def public_hub_artifact_alpha(username: str, kind: str, name: str, http_request: Request):
    return hub_get_artifact_version(username=username, kind=kind, name=name, version="alpha", http_request=http_request)

if __name__ == "__main__":
    import uvicorn
    # Use spawn for multiprocessing compatibility
    multiprocessing.set_start_method('spawn')
    uvicorn.run(app, host="0.0.0.0", port=8088)
