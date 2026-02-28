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
import urllib.request
import urllib.error
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
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict, Union, Tuple

import xatra
from xatra.loaders import gadm, naturalearth, polygon, GADM_DIR
from xatra.render import export_html_string
from xatra.colorseq import Color, ColorSequence, LinearColorSequence, color_sequences
from xatra.icon import Icon

# Track one rendering process per (actor, task_type) so users cannot cancel each other.
current_processes: Dict[str, Optional[multiprocessing.Process]] = {}
process_lock = threading.Lock()
render_cache_lock = threading.Lock()
RENDER_CACHE_MAX_ENTRIES = 24
render_cache = OrderedDict()
_bootstrap_icon_cache_lock = threading.Lock()
_bootstrap_icon_cache: Dict[str, List[str]] = {}

# Simple in-memory rate limiter (IP-keyed, sliding window)
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()
MAX_PY_INPUT_CHARS = 200_000
MAX_PY_AST_NODES = 50_000
MAX_PY_AST_DEPTH = 160

def _check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
    label: str = "Too many requests. Please try again later.",
) -> None:
    """Raise HTTP 429 if this key has exceeded `limit` requests in `window_seconds`."""
    now = time.time()
    cutoff = now - window_seconds
    with _rate_limit_lock:
        timestamps = _rate_limit_store[key]
        timestamps[:] = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= limit:
            oldest = min(timestamps) if timestamps else now
            retry_after = max(1, int((oldest + window_seconds) - now))
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limited",
                    "message": label,
                    "retry_after_seconds": retry_after,
                    "limit": limit,
                    "window_seconds": window_seconds,
                },
                headers={"Retry-After": str(retry_after)},
            )
        timestamps.append(now)


def _enforce_python_input_limits(code: str, label: str) -> None:
    text = str(code or "")
    if len(text) > MAX_PY_INPUT_CHARS:
        raise HTTPException(status_code=413, detail=f"{label} too large")
    if not text.strip():
        return
    try:
        tree = ast.parse(text)
    except Exception:
        return
    node_count = 0
    max_depth = 0
    stack: List[Tuple[ast.AST, int]] = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        node_count += 1
        if depth > max_depth:
            max_depth = depth
        if node_count > MAX_PY_AST_NODES:
            raise HTTPException(status_code=413, detail=f"{label} too complex (too many AST nodes)")
        if max_depth > MAX_PY_AST_DEPTH:
            raise HTTPException(status_code=413, detail=f"{label} too complex (AST depth limit exceeded)")
        for child in ast.iter_child_nodes(node):
            stack.append((child, depth + 1))

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
EXTRA_CORS_ORIGINS = [
    str(x).strip()
    for x in str(os.environ.get("XATRA_EXTRA_CORS_ORIGINS", "")).split(",")
    if str(x).strip()
]
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
    "theme",
    "thm",
    "default",
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
COOKIE_SECURE_ENV = os.environ.get("XATRA_COOKIE_SECURE")


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _parse_bool_env(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _secure_cookie_flag(request: Optional[Request] = None) -> bool:
    if COOKIE_SECURE_ENV is not None:
        return _parse_bool_env(COOKIE_SECURE_ENV, default=False)
    if request is None:
        return False
    forwarded = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if forwarded:
        return forwarded == "https"
    try:
        return str(request.url.scheme).lower() == "https"
    except Exception:
        return False


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
    return cleaned

def _is_user_trusted(user_row: Optional[sqlite3.Row]) -> bool:
    if user_row is None:
        return False
    try:
        if int(user_row["is_admin"] or 0) == 1:
            return True
    except Exception:
        pass
    try:
        return int(user_row["is_trusted"] or 0) == 1
    except Exception:
        return False


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), 600000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def _xatra_lib_dir() -> Path:
    """Return the path to the xatra_lib/ directory."""
    return Path(__file__).resolve().parent / "xatra_lib"


def _is_xatrahub_line(line: str, require_assignment: bool = False) -> bool:
    """Return True if the line is a xatrahub import statement."""
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        return False
    if require_assignment:
        return bool(re.match(r'^\w+\s*=\s*xatrahub\s*\(', stripped))
    return bool(re.match(r'^(?:\w+\s*=\s*)?xatrahub\s*\(', stripped))


_THEME_CALL_NAMES = frozenset({"CSS", "BaseOption", "FlagColorSequence", "AdminColorSequence", "DataColormap", "zoom", "focus", "slider"})


def _is_xatrahub_node(node: ast.stmt) -> bool:
    """True if node is xatrahub(...) or x = xatrahub(...)."""
    if isinstance(node, ast.Expr):
        call = node.value
        return isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "xatrahub"
    if isinstance(node, ast.Assign):
        return isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "xatrahub"
    return False


def _is_theme_call_node(node: ast.stmt) -> bool:
    """True if node is xatra.CSS/BaseOption/FlagColorSequence/AdminColorSequence/DataColormap(...)."""
    if not isinstance(node, ast.Expr):
        return False
    call = node.value
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "xatra"
        and func.attr in _THEME_CALL_NAMES
    )


def _parse_xatra_lib_map_file(content: str) -> Dict[str, str]:
    """
    Parse a map/ file into sections:
    - imports_code: xatrahub(...) or abc = xatrahub(...) calls (top-level, outside # <lib>)
    - predefined_code: content between # <lib> and # </lib> delimiters
    - map_code: remaining top-level statements
    - theme_code: xatra.CSS/BaseOption/FlagColorSequence/AdminColorSequence/DataColormap calls
                  (from top-level only)
    - runtime_code: non-xatrahub, non-theme body of if __name__ == '__main__': (indent stripped)
    - runtime_imports_code: xatrahub calls inside if __name__ body (indent stripped)
    - runtime_theme_code: theme calls inside if __name__ body (NOT merged with main theme_code)
    """
    lines = content.splitlines(keepends=True)

    # --- Step 1: find # <lib> ... # </lib> line ranges (1-indexed, inclusive) ---
    lib_line_set: set = set()  # set of 1-indexed line numbers inside lib blocks
    predefined_lines: List[str] = []
    lib_start: Optional[int] = None
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped == "# <lib>":
            lib_start = i
            lib_line_set.add(i)
        elif stripped == "# </lib>" and lib_start is not None:
            lib_line_set.add(i)
            for j in range(lib_start + 1, i):
                predefined_lines.append(lines[j - 1])
            lib_start = None
        elif lib_start is not None:
            lib_line_set.add(i)

    # --- Step 2: use AST to find if __name__ == "__main__": block ---
    main_lineno: Optional[int] = None
    try:
        tree = ast.parse(content)
        for node in tree.body:
            if (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == "__main__"
            ):
                main_lineno = node.lineno
                break
    except SyntaxError:
        pass

    if main_lineno is not None:
        before_lines = lines[: main_lineno - 1]
        raw_body_lines = lines[main_lineno:]
    else:
        before_lines = lines
        raw_body_lines = []

    # --- Step 3: classify top-level statements using AST ---
    imports_segs: List[str] = []
    map_segs: List[str] = []
    theme_segs: List[str] = []

    before_content = "".join(before_lines)
    try:
        before_tree = ast.parse(before_content)
        for node in before_tree.body:
            if node.lineno in lib_line_set:
                continue  # handled as predefined_code
            seg = ast.get_source_segment(before_content, node) or ast.unparse(node)
            seg = seg.rstrip("\n") + "\n"
            if _is_xatrahub_node(node):
                imports_segs.append(seg)
            elif _is_theme_call_node(node):
                theme_segs.append(seg)
            else:
                map_segs.append(seg)
    except SyntaxError:
        # Fallback: line-by-line (no theme separation on syntax error)
        for line in before_lines:
            if _is_xatrahub_line(line):
                imports_segs.append(line)
            elif line.strip() not in ("# <lib>", "# </lib>") and not any(line is lines[j - 1] for j in lib_line_set):
                map_segs.append(line)

    # --- Step 4: classify if __name__ body using AST ---
    runtime_imports_segs: List[str] = []
    runtime_theme_segs: List[str] = []
    runtime_segs: List[str] = []
    body_lines: List[str] = []
    for line in raw_body_lines:
        if line.startswith("    "):
            body_lines.append(line[4:])
        elif line.startswith("\t"):
            body_lines.append(line[1:])
        else:
            body_lines.append(line)

    body_content = "".join(body_lines)
    try:
        body_tree = ast.parse(body_content)
        for node in body_tree.body:
            seg = ast.get_source_segment(body_content, node) or ast.unparse(node)
            seg = seg.rstrip("\n") + "\n"
            if _is_xatrahub_node(node):
                runtime_imports_segs.append(seg)
            elif _is_theme_call_node(node):
                runtime_theme_segs.append(seg)  # kept separate from main theme_code
            else:
                runtime_segs.append(seg)
    except SyntaxError:
        runtime_segs = body_lines

    def _clean(lst: List[str]) -> str:
        s = "".join(lst).strip()
        return s + "\n" if s else ""

    return {
        "imports_code": _clean(imports_segs),
        "predefined_code": _clean(predefined_lines),
        "map_code": _clean(map_segs),
        "theme_code": _clean(theme_segs),
        "runtime_code": _clean(runtime_segs),
        "runtime_imports_code": _clean(runtime_imports_segs),
        "runtime_theme_code": _clean(runtime_theme_segs),
    }


def _parse_xatra_lib_lib_file(content: str) -> Dict[str, str]:
    """
    Parse a lib/ file into:
    - imports_code: abc = xatrahub(...) lines
    - predefined_code: everything else
    """
    imports_lines: List[str] = []
    other_lines: List[str] = []
    for line in content.splitlines(keepends=True):
        if _is_xatrahub_line(line, require_assignment=True):
            imports_lines.append(line)
        else:
            other_lines.append(line)

    def _clean(lst: List[str]) -> str:
        s = "".join(lst).strip()
        return s + "\n" if s else ""

    return {
        "imports_code": _clean(imports_lines),
        "predefined_code": _clean(other_lines),
    }


def _seed_xatra_lib_artifacts(
    conn: "sqlite3.Connection",
    user_id: int,
    now: str,
    force: bool = False,
    code_to_builder_fn=None,
    parse_theme_fn=None,
) -> None:
    """
    Seeds hub artifacts from xatra_lib/ directory.

    - xatra_lib/map/*.py  → creates kind='map' artifacts
    - xatra_lib/lib/*.py  → creates kind='lib' artifact + sibling kind='map' artifact
    - xatra_lib/default_theme.py → used as theme_code for all created artifacts

    If force=False, skips artifacts that already exist (but still fills in empty project.elements
    and project.options).
    If force=True, overwrites the alpha_content of existing artifacts.
    code_to_builder_fn: optional callable(CodeSyncRequest) → dict; used to parse map_code into
    project.elements. When None, elements are left empty.
    parse_theme_fn: optional callable(theme_code: str) → dict; used to parse theme_code into
    project.options (basemaps, css_rules, etc.). When None, options are left as {}.
    Caller is responsible for committing the transaction.
    """
    xatra_lib_dir = _xatra_lib_dir()
    if not xatra_lib_dir.exists():
        print("[xatra] xatra_lib/ not found; skipping artifact seeding.", file=sys.stderr)
        return

    default_theme_path = xatra_lib_dir / "default_theme.py"
    theme_code = default_theme_path.read_text(encoding="utf-8") if default_theme_path.exists() else ""

    def _parse_builder_state(code: str, predefined_code: str) -> Dict[str, Any]:
        """Parse code into builder state dict with elements and options. Returns {} on failure."""
        if code_to_builder_fn is None or not code.strip():
            return {}
        try:
            result = code_to_builder_fn(CodeSyncRequest(code=code, predefined_code=predefined_code))
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _parse_elements(map_code: str, predefined_code: str) -> list:
        return _parse_builder_state(map_code, predefined_code).get("elements", [])

    def _upsert(kind: str, name: str, alpha_content: str, alpha_metadata: Optional[Dict[str, Any]] = None) -> None:
        meta_json = json.dumps(alpha_metadata or {}, ensure_ascii=False)
        existing = conn.execute(
            "SELECT id, alpha_content, alpha_metadata FROM hub_artifacts WHERE kind = ? AND name = ?", (kind, name)
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO hub_artifacts(user_id, kind, name, alpha_content, alpha_metadata, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, kind, name, alpha_content, meta_json, now, now),
            )
            print(f"[xatra] Seeded {kind} artifact '{name}'")
        elif force:
            update_args = [alpha_content, now]
            update_sql = "UPDATE hub_artifacts SET alpha_content = ?, updated_at = ?"
            if alpha_metadata is not None:
                update_sql += ", alpha_metadata = ?"
                update_args.append(meta_json)
            update_sql += " WHERE id = ?"
            update_args.append(existing["id"])
            conn.execute(update_sql, update_args)
            print(f"[xatra] Reseeded {kind} artifact '{name}' (--force)")
        elif kind == "map" and (code_to_builder_fn is not None or parse_theme_fn is not None):
            # Populate project.elements / project.options if currently empty, without overwriting
            # other content. Also backfill display_type if alpha_metadata was provided.
            try:
                existing_content = _json_parse(existing["alpha_content"], {})
                desired_content = _json_parse(alpha_content, {})
                existing_meta = _json_parse(existing["alpha_metadata"], {})
                proj = existing_content.get("project", {}) if isinstance(existing_content, dict) else {}
                content_changed = False
                meta_changed = False
                if not proj.get("elements") and code_to_builder_fn is not None:
                    mc = existing_content.get("map_code", "") if isinstance(existing_content, dict) else ""
                    pc = existing_content.get("predefined_code", "") if isinstance(existing_content, dict) else ""
                    elements = _parse_elements(mc, pc)
                    if elements:
                        if not isinstance(existing_content, dict):
                            existing_content = {}
                        existing_content.setdefault("project", {})["elements"] = elements
                        content_changed = True
                        print(f"[xatra] Populated builder elements for map '{name}'")
                if parse_theme_fn is not None and not proj.get("options") and isinstance(existing_content, dict):
                    tc = existing_content.get("theme_code", "")
                    new_options = parse_theme_fn(tc) if tc else {}
                    if new_options:
                        existing_content.setdefault("project", {})["options"] = new_options
                        content_changed = True
                        print(f"[xatra] Populated builder options for map '{name}'")
                if isinstance(existing_content, dict) and isinstance(desired_content, dict):
                    proj2 = existing_content.get("project", {})
                    # Backfill runtime_imports_code if the existing row has it as empty string
                    # (old rows from before runtime_imports_code was returned by the parser)
                    desired_ric = desired_content.get("runtime_imports_code", "")
                    if desired_ric and desired_ric.strip() and not existing_content.get("runtime_imports_code", "").strip():
                        existing_content["runtime_imports_code"] = desired_ric
                        existing_content.setdefault("project", {})["runtimeImportsCode"] = desired_ric
                        content_changed = True
                        print(f"[xatra] Backfilled runtime_imports_code for map '{name}'")
                    # Backfill runtime_theme_code if missing
                    desired_rtc = desired_content.get("runtime_theme_code", "")
                    if desired_rtc and desired_rtc.strip() and not existing_content.get("runtime_theme_code", "").strip():
                        existing_content["runtime_theme_code"] = desired_rtc
                        existing_content.setdefault("project", {})["runtimeThemeCode"] = desired_rtc
                        content_changed = True
                        print(f"[xatra] Backfilled runtime_theme_code for map '{name}'")
                if code_to_builder_fn is not None and isinstance(existing_content, dict):
                    proj2 = existing_content.get("project", {})
                    if proj2.get("runtimeElements") is None or proj2.get("runtimeOptions") is None:
                        rc = existing_content.get("runtime_code", "")
                        ric = existing_content.get("runtime_imports_code", "")
                        rtc = existing_content.get("runtime_theme_code", "")
                        # For runtimeOptions, parse from runtime_theme_code (if present) rather than runtime_code
                        if parse_theme_fn and rtc and rtc.strip():
                            new_runtime_options = parse_theme_fn(rtc)
                            existing_content.setdefault("project", {})["runtimeOptions"] = new_runtime_options
                            content_changed = True
                        elif rc and rc.strip():
                            runtime_state = _parse_builder_state(rc, "")
                            if runtime_state:
                                existing_content.setdefault("project", {})["runtimeElements"] = runtime_state.get("elements", [])
                                existing_content.setdefault("project", {})["runtimeOptions"] = runtime_state.get("options", {})
                                content_changed = True
                        if content_changed:
                            print(f"[xatra] Populated runtime builder state for map '{name}'")
                # Backfill territory-library predefined code/index for old seeded rows that were
                # created before __TERRITORY_INDEX__ support.
                if isinstance(existing_content, dict) and isinstance(desired_content, dict):
                    existing_predef = existing_content.get("predefined_code", "")
                    desired_predef = desired_content.get("predefined_code", "")
                    existing_map_code = existing_content.get("map_code", "")
                    existing_runtime_code = existing_content.get("runtime_code", "")
                    is_seed_like_library_map = (
                        isinstance(existing_map_code, str)
                        and not existing_map_code.strip()
                        and isinstance(existing_runtime_code, str)
                        and not existing_runtime_code.strip()
                        and isinstance(existing_meta, dict)
                        and str(existing_meta.get("display_type", "")).strip().lower() == "territory_library"
                    )
                    if (
                        is_seed_like_library_map
                        and isinstance(existing_predef, str)
                        and isinstance(desired_predef, str)
                    ):
                        existing_idx = _extract_territory_index(existing_predef)
                        desired_idx = _extract_territory_index(desired_predef)
                        if (not existing_idx) and desired_idx:
                            existing_content["predefined_code"] = desired_predef
                            existing_content.setdefault("project", {})["predefinedCode"] = desired_predef
                            content_changed = True
                            print(f"[xatra] Backfilled __TERRITORY_INDEX__ for map '{name}'")
                if alpha_metadata is not None:
                    for k, v in alpha_metadata.items():
                        if existing_meta.get(k) != v:
                            existing_meta[k] = v
                            meta_changed = True
                if content_changed or meta_changed:
                    conn.execute(
                        "UPDATE hub_artifacts SET alpha_content = ?, alpha_metadata = ?, updated_at = ? WHERE id = ?",
                        (json.dumps(existing_content, ensure_ascii=False), json.dumps(existing_meta, ensure_ascii=False), now, existing["id"]),
                    )
            except Exception as e:
                print(f"[xatra] Warning: failed to populate elements for '{name}': {e}", file=sys.stderr)

    def _build_map_content(
        imports_code: str,
        predefined_code: str,
        map_code: str,
        runtime_code: str,
        file_theme_code: str = "",
        runtime_imports_code: str = "",
        runtime_theme_code: str = "",
    ) -> str:
        # Combine default_theme.py with any map-specific theme calls (CSS etc.)
        combined_theme = theme_code
        if file_theme_code.strip():
            combined_theme = (theme_code.rstrip("\n") + "\n\n" + file_theme_code.strip() + "\n").lstrip("\n")
        elements = _parse_elements(map_code, predefined_code)
        options = parse_theme_fn(combined_theme) if parse_theme_fn else {}
        runtime_state = _parse_builder_state(runtime_code, "")
        runtime_elements = runtime_state.get("elements", [])
        runtime_options = parse_theme_fn(runtime_theme_code) if (parse_theme_fn and runtime_theme_code.strip()) else {}
        return json.dumps({
            "imports_code": imports_code,
            "theme_code": combined_theme,
            "predefined_code": predefined_code,
            "map_code": map_code,
            "runtime_code": runtime_code,
            "runtime_imports_code": runtime_imports_code,
            "runtime_theme_code": runtime_theme_code,
            "runtime_predefined_code": "",
            "project": {
                "elements": elements,
                "options": options,
                "runtimeElements": runtime_elements,
                "runtimeOptions": runtime_options,
                "importsCode": imports_code,
                "themeCode": combined_theme,
                "predefinedCode": predefined_code,
                "runtimeCode": runtime_code,
                "runtimeImportsCode": runtime_imports_code,
                "runtimeThemeCode": runtime_theme_code,
                "runtimePredefinedCode": "",
            },
        }, ensure_ascii=False)

    # Process map/ files
    map_dir = xatra_lib_dir / "map"
    if map_dir.exists():
        for py_file in sorted(map_dir.glob("*.py")):
            name = py_file.stem
            try:
                parsed = _parse_xatra_lib_map_file(py_file.read_text(encoding="utf-8"))
                _upsert("map", name, _build_map_content(
                    imports_code=parsed["imports_code"],
                    predefined_code=parsed["predefined_code"],
                    map_code=parsed["map_code"],
                    runtime_code=parsed["runtime_code"],
                    file_theme_code=parsed.get("theme_code", ""),
                    runtime_imports_code=parsed.get("runtime_imports_code", ""),
                    runtime_theme_code=parsed.get("runtime_theme_code", ""),
                ))
            except Exception as e:
                print(f"[xatra] Warning: failed to seed map '{name}': {e}", file=sys.stderr)

    # Process lib/ files — create both a lib artifact and a sibling map artifact
    lib_dir = xatra_lib_dir / "lib"
    if lib_dir.exists():
        for py_file in sorted(lib_dir.glob("*.py")):
            name = py_file.stem
            try:
                parsed = _parse_xatra_lib_lib_file(py_file.read_text(encoding="utf-8"))
                _upsert("lib", name, json.dumps({"predefined_code": parsed["predefined_code"]}, ensure_ascii=False))
                _upsert("map", name, _build_map_content(
                    imports_code=parsed["imports_code"],
                    predefined_code=parsed["predefined_code"],
                    map_code="",
                    runtime_code="",
                ), alpha_metadata={"display_type": "territory_library"})
            except Exception as e:
                print(f"[xatra] Warning: failed to seed lib '{name}': {e}", file=sys.stderr)


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
                is_trusted INTEGER NOT NULL DEFAULT 0,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hub_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES hub_users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                featured INTEGER NOT NULL DEFAULT 0,
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
        if "is_trusted" not in existing_cols:
            conn.execute("ALTER TABLE hub_users ADD COLUMN is_trusted INTEGER NOT NULL DEFAULT 0")
        artifact_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(hub_artifacts)").fetchall()
        }
        if "featured" not in artifact_cols:
            conn.execute("ALTER TABLE hub_artifacts ADD COLUMN featured INTEGER NOT NULL DEFAULT 0")

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
        conn.execute(
            "UPDATE hub_users SET is_trusted = 1 WHERE username = ?",
            (ADMIN_USERNAME,),
        )
        if result.rowcount > 0:
            print(f"[xatra] Admin account '{ADMIN_USERNAME}' created. Password: {admin_password}")
            print("[xatra] Set XATRA_ADMIN_PASSWORD env var to configure this at startup, or change it after first login.")
        # Seed hub artifacts from xatra_lib/ directory.
        user_row = conn.execute("SELECT id FROM hub_users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        if user_row is not None:
            _seed_xatra_lib_artifacts(conn, user_row["id"], now, force=False)
        # (Historical migration: once stripped description from map metadata; now a no-op since descriptions are supported again.)
        map_rows = conn.execute(
            "SELECT id, alpha_metadata FROM hub_artifacts WHERE kind = 'map'"
        ).fetchall()
        for row in map_rows:
            original = _json_text(_json_parse(row["alpha_metadata"], {}))
            sanitized = _json_text(_sanitize_artifact_metadata("map", row["alpha_metadata"]))
            if sanitized != original:
                conn.execute(
                    "UPDATE hub_artifacts SET alpha_metadata = ? WHERE id = ?",
                    (sanitized, row["id"]),
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
            original = _json_text(_json_parse(row["metadata"], {}))
            sanitized = _json_text(_sanitize_artifact_metadata("map", row["metadata"]))
            if sanitized != original:
                conn.execute(
                    "UPDATE hub_artifact_versions SET metadata = ? WHERE id = ?",
                    (sanitized, row["id"]),
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
            a.id, a.user_id, a.kind, a.name, a.featured, a.alpha_content, a.alpha_metadata, a.created_at, a.updated_at,
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
            a.id, a.user_id, a.kind, a.name, a.featured, a.alpha_content, a.alpha_metadata, a.created_at, a.updated_at,
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
    for key in ('imports_code', 'runtime_imports_code', 'map_code', 'predefined_code', 'runtime_code', 'theme_code'):
        if isinstance(parsed.get(key), str):
            nv = _update_xatrahub_paths_in_code(parsed[key], rename_map)
            if nv != parsed[key]:
                parsed[key] = nv
                modified = True
    project = parsed.get('project')
    if isinstance(project, dict):
        for key in ('importsCode', 'runtimeImportsCode', 'predefinedCode', 'themeCode', 'runtimeCode'):
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
            featured INTEGER NOT NULL DEFAULT 0,
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
            "INSERT INTO hub_artifacts_new(id, user_id, kind, name, featured, alpha_content, alpha_metadata, created_at, updated_at)"
            " VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                art['id'],
                art['user_id'],
                art['kind'],
                new_name,
                int(art["featured"] or 0) if "featured" in art.keys() else 0,
                new_content,
                art['alpha_metadata'],
                art['created_at'],
                art['updated_at'],
            )
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
                for key in ('importsCode', 'runtimeImportsCode', 'predefinedCode', 'themeCode', 'runtimeCode', 'code'):
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
                    print(f"[xatra] Warning: failed to read GADM file {f}: {e}", file=sys.stderr)
        
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
    except Exception as e:
        print(f"[xatra] Warning: failed to load cached GADM index: {e}", file=sys.stderr)
        threading.Thread(target=build_gadm_index).start()
else:
    threading.Thread(target=build_gadm_index).start()

app = FastAPI()
_init_hub_db()

DEFAULT_CORS_ORIGINS = [
    f"http://localhost:{FRONTEND_PORT}",
    f"http://127.0.0.1:{FRONTEND_PORT}",
    f"http://0.0.0.0:{FRONTEND_PORT}",
    f"http://localhost:{FRONTEND_PREVIEW_PORT}",
    f"http://127.0.0.1:{FRONTEND_PREVIEW_PORT}",
    f"http://0.0.0.0:{FRONTEND_PREVIEW_PORT}",
]
ALLOWED_CORS_ORIGINS = list(dict.fromkeys(DEFAULT_CORS_ORIGINS + EXTRA_CORS_ORIGINS))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
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

    with _gadm_lock:
        index_snapshot = list(GADM_INDEX)
    for item in index_snapshot:
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
    with _gadm_lock:
        country_snapshot = list(COUNTRY_SEARCH_INDEX)
    if not q:
        return country_snapshot[:20]
    q = q.lower().strip()
    results = []

    for item in country_snapshot:
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
    with _gadm_lock:
        levels = COUNTRY_LEVELS_INDEX.get(country_code, [0, 1, 2, 3, 4])
    return list(levels)

class CodeRequest(BaseModel):
    code: str
    predefined_code: Optional[str] = None
    imports_code: Optional[str] = None
    runtime_imports_code: Optional[str] = None
    theme_code: Optional[str] = None
    runtime_code: Optional[str] = None
    runtime_theme_code: Optional[str] = None
    runtime_predefined_code: Optional[str] = None
    trusted_user: bool = False

class CodeSyncRequest(BaseModel):
    code: str
    predefined_code: Optional[str] = None

class MapElement(BaseModel):
    type: str
    label: Optional[Any] = None
    value: Any = None
    args: Dict[str, Any] = {}

class BuilderRequest(BaseModel):
    elements: List[MapElement]
    options: Dict[str, Any] = {}
    predefined_code: Optional[str] = None
    imports_code: Optional[str] = None
    runtime_imports_code: Optional[str] = None
    theme_code: Optional[str] = None
    runtime_code: Optional[str] = None
    runtime_theme_code: Optional[str] = None
    runtime_predefined_code: Optional[str] = None
    runtime_elements: Optional[List[MapElement]] = None
    runtime_options: Optional[Dict[str, Any]] = None
    trusted_user: bool = False

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


class HubArtifactWriteRequest(BaseModel):
    content: str = ""
    metadata: Dict[str, Any] = {}


class HubArtifactRenameRequest(BaseModel):
    new_name: str


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

class UserTrustUpdateRequest(BaseModel):
    trusted: bool

class MapFeaturedUpdateRequest(BaseModel):
    featured: bool


def _hub_kind_label(kind: str) -> str:
    if kind == "map":
        return "map"
    if kind == "lib":
        return "lib"
    return "css"


def _require_admin_user(conn: sqlite3.Connection, request: Request) -> sqlite3.Row:
    user = _request_user(conn, request)
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    try:
        if int(user["is_admin"] or 0) != 1:
            raise HTTPException(status_code=403, detail="Admin required")
    except Exception:
        raise HTTPException(status_code=403, detail="Admin required")
    return user


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
        "featured": bool(int(artifact["featured"] or 0)) if artifact["kind"] == "map" else False,
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
        "is_admin": bool(int(user_row["is_admin"] or 0)) if "is_admin" in user_row.keys() else False,
        "is_trusted": _is_user_trusted(user_row),
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
            secure=_secure_cookie_flag(request),
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

def _compress_multi_value_parts(parts: List[Dict[str, Any]], allow_list_values: bool = False) -> Optional[Dict[str, Any]]:
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
        if isinstance(val, str):
            if not val.strip():
                return None
            values.append(val.strip())
        elif isinstance(val, list):
            if not allow_list_values:
                return None
            nested = []
            for item in val:
                if not isinstance(item, str) or not item.strip():
                    return None
                nested.append(item.strip())
            if not nested:
                return None
            values.extend(nested)
        else:
            return None
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
        if len(group_parts) == 1 and isinstance(group_parts[0], dict):
            return group_parts[0]
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
        if isinstance(node.op, ast.BitOr) and len(parts) >= 3:
            compressed_all = _compress_multi_value_parts(parts, allow_list_values=True)
            if compressed_all:
                parts = [compressed_all]
        return parts
    part = _parse_territory_operand(node)
    if part:
        part["op"] = "union"
        return [part]
    return []

@app.post("/sync/code_to_builder")
def sync_code_to_builder(request: CodeSyncRequest):
    _enforce_python_input_limits(request.code or "", "code")
    _enforce_python_input_limits(request.predefined_code or "", "predefined_code")
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
                        args_dict["icon"] = {
                            "type": "builtin",
                            "name": _builder_value_from_node(source_code, icon_node.args[0]) or "",
                            "icon_size": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_size"), ast.Constant(value=None))),
                            "icon_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_anchor"), ast.Constant(value=None))),
                            "popup_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "popup_anchor"), ast.Constant(value=None))),
                        }
                    elif icon_call == "Icon.bootstrap" and icon_node.args:
                        args_dict["icon"] = {
                            "type": "bootstrap",
                            "name": _builder_value_from_node(source_code, icon_node.args[0]) or "",
                            "version": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "version"), ast.Constant(value="1.11.3"))),
                            "base_url": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "base_url"), ast.Constant(value=""))) or "",
                            "icon_size": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_size"), ast.Constant(value=24))),
                            "icon_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_anchor"), ast.Constant(value=None))),
                            "popup_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "popup_anchor"), ast.Constant(value=None))),
                        }
                    elif icon_call == "Icon.geometric" and icon_node.args:
                        args_dict["icon"] = {
                            "type": "geometric",
                            "shape": _builder_value_from_node(source_code, icon_node.args[0]) or "circle",
                            "color": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "color"), ast.Constant(value="#3388ff"))),
                            "size": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "size"), ast.Constant(value=24))),
                            "border_color": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "border_color"), ast.Constant(value=None))),
                            "border_width": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "border_width"), ast.Constant(value=0))),
                            "icon_size": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_size"), ast.Constant(value=None))),
                            "icon_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_anchor"), ast.Constant(value=None))),
                            "popup_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "popup_anchor"), ast.Constant(value=None))),
                        }
                    elif icon_call == "Icon":
                        args_dict["icon"] = {
                            "type": "url",
                            "icon_url": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_url"), ast.Constant(value=""))) or "",
                            "shadow_url": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "shadow_url"), ast.Constant(value=None))),
                            "icon_size": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_size"), ast.Constant(value=None))),
                            "icon_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "icon_anchor"), ast.Constant(value=None))),
                            "popup_anchor": _builder_value_from_node(source_code, next((kw.value for kw in icon_node.keywords if kw.arg == "popup_anchor"), ast.Constant(value=None))),
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


def _fetch_bootstrap_icons(version: str = "1.11.3") -> List[str]:
    """Fetch Bootstrap icon names from jsDelivr's package index."""
    with _bootstrap_icon_cache_lock:
        cached = _bootstrap_icon_cache.get(version)
        if cached is not None:
            return cached

    url = f"https://data.jsdelivr.com/v1/package/npm/bootstrap-icons@{version}/flat"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        names: List[str] = []
        for entry in payload.get("files", []):
            name = str(entry.get("name") or "")
            if not name.startswith("/icons/") or not name.endswith(".svg"):
                continue
            stem = name[len("/icons/"):-len(".svg")]
            if stem:
                names.append(stem)
        names = sorted(set(names))
    except Exception:
        names = []

    with _bootstrap_icon_cache_lock:
        _bootstrap_icon_cache[version] = names
    return names


@app.get("/icons/bootstrap")
def list_bootstrap_icons(q: str = "", offset: int = 0, limit: int = 80, version: str = "1.11.3"):
    """Search Bootstrap icon names with pagination for the Point icon picker."""
    all_icons = _fetch_bootstrap_icons(version=version)
    query = (q or "").strip().lower()
    if query:
        filtered = [name for name in all_icons if query in name.lower()]
    else:
        filtered = all_icons

    safe_offset = max(0, int(offset or 0))
    safe_limit = max(1, min(200, int(limit or 80)))
    items = filtered[safe_offset : safe_offset + safe_limit]
    return {
        "items": items,
        "offset": safe_offset,
        "limit": safe_limit,
        "total": len(filtered),
        "has_more": safe_offset + safe_limit < len(filtered),
        "version": version,
    }



@app.get("/icons/file/{filename}")
def icon_file(filename: str):
    """Serve a built-in icon asset for UI previews."""
    icons_dir = Path(xatra.__file__).parent / "icons"
    safe_name = Path(filename).name
    target = (icons_dir / safe_name)
    if not icons_dir.exists() or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Icon not found")
    return FileResponse(str(target))

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


def _dedupe_str_list(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: set = set()
    for raw in values or []:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


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
                            return _dedupe_str_list([str(x) for x in value if isinstance(x, str)])
                    except Exception:
                        pass
    return []

def _get_territory_catalog(source: str, predefined_code: str, hub_path: Optional[str] = None) -> Dict[str, List[str]]:
    """Return territory names using AST analysis only — no exec() in the main process."""
    import xatra.territory_library as territory_library

    if source == "custom":
        struct = _extract_territory_library_struct(predefined_code or "")
        names = [entry.get("name") for entry in struct.get("territories", []) if isinstance(entry, dict) and isinstance(entry.get("name"), str)]
        index_names = struct.get("index_names", [])
        return {
            "names": names,
            "index_names": [n for n in index_names if n in names] if index_names else names,
        }

    if source == "hub" and hub_path:
        try:
            parsed = _parse_xatrahub_path(hub_path)
            loaded = _hub_load_content(parsed["username"], parsed["kind"], parsed["name"], parsed["version"])
            struct = _extract_territory_library_struct(loaded.get("content", "") or "")
            names = _dedupe_str_list([
                entry.get("name")
                for entry in struct.get("territories", [])
                if isinstance(entry, dict) and isinstance(entry.get("name"), str)
            ])
            idx = _dedupe_str_list(struct.get("index_names", []))
            return {"names": names, "index_names": [n for n in idx if n in names] if idx else names}
        except Exception:
            return {"names": [], "index_names": []}

    names = _dedupe_str_list([n for n in dir(territory_library) if not n.startswith("_")])
    idx = getattr(territory_library, "__TERRITORY_INDEX__", [])
    index_names = _dedupe_str_list([str(n) for n in idx if isinstance(n, str)] if isinstance(idx, (list, tuple)) else [])
    return {
        "names": names,
        "index_names": [n for n in index_names if n in names] if index_names else names,
    }

def _parse_territory_library_code_to_struct(code: str) -> Dict[str, Any]:
    territories: List[Dict[str, Any]] = []
    index_names: List[str] = []
    if not isinstance(code, str) or not code.strip():
        return {"territories": territories, "index_names": index_names}
    try:
        tree = ast.parse(code)
    except Exception:
        return {"territories": territories, "index_names": index_names}
    seen: set = set()
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        name = stmt.targets[0].id
        if name == "__TERRITORY_INDEX__":
            try:
                value = ast.literal_eval(stmt.value)
                if isinstance(value, (list, tuple)):
                    index_names = _dedupe_str_list([str(v) for v in value if isinstance(v, str)])
            except Exception:
                pass
            continue
        if not name or name.startswith("_") or name in seen:
            continue
        parts = _parse_territory_expr(stmt.value)
        if not parts:
            continue
        seen.add(name)
        territories.append({"name": name, "parts": parts})
    valid_names = {entry["name"] for entry in territories if isinstance(entry, dict) and isinstance(entry.get("name"), str)}
    return {
        "territories": territories,
        "index_names": [n for n in index_names if n in valid_names] if index_names else [entry["name"] for entry in territories],
    }


def _extract_territory_library_struct(content: str) -> Dict[str, Any]:
    parsed = _json_parse(content, None)
    if isinstance(parsed, dict):
        territories_raw = parsed.get("territories")
        if isinstance(territories_raw, list):
            territories: List[Dict[str, Any]] = []
            for item in territories_raw:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                parts = item.get("parts")
                if not isinstance(name, str) or not name or name.startswith("_") or not isinstance(parts, list):
                    continue
                territories.append({"name": name, "parts": parts})
            names = [t["name"] for t in territories]
            idx_raw = parsed.get("index_names")
            if isinstance(idx_raw, list):
                idx = _dedupe_str_list([str(x) for x in idx_raw if isinstance(x, str)])
                index_names = [n for n in idx if n in set(names)] if idx else names
            else:
                index_names = names
            return {"territories": territories, "index_names": index_names}
        for key in ("predefined_code", "code", "content"):
            val = parsed.get(key)
            if isinstance(val, str):
                return _parse_territory_library_code_to_struct(val)
    return _parse_territory_library_code_to_struct(content or "")


def _territory_value_expr(part_type: str, value: Any) -> Optional[str]:
    if part_type == "gadm":
        vals = value if isinstance(value, list) else [value]
        terms = [f"gadm({json.dumps(str(v))})" for v in vals if isinstance(v, str) and str(v).strip()]
        return " | ".join(terms) if terms else None
    if part_type == "predefined":
        vals = value if isinstance(value, list) else [value]
        terms = [str(v).strip() for v in vals if isinstance(v, str) and str(v).strip()]
        return " | ".join(terms) if terms else None
    if part_type == "polygon":
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = value
        else:
            parsed = value
        return f"polygon({json.dumps(parsed, ensure_ascii=False)})"
    if part_type == "group" and isinstance(value, list):
        inner = _territory_parts_to_expr(value)
        if inner:
            return f"({inner})"
    return None


def _territory_parts_to_expr(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    expr = ""
    first = True
    for part in parts:
        if not isinstance(part, dict):
            continue
        term = _territory_value_expr(str(part.get("type", "")), part.get("value"))
        if not term:
            continue
        if first:
            expr = term
            first = False
            continue
        op = str(part.get("op", "union"))
        token = "|" if op == "union" else ("-" if op == "difference" else "&")
        expr = f"{expr} {token} {term}"
    return expr


def _territory_library_struct_to_code(struct: Dict[str, Any]) -> str:
    lines: List[str] = []
    territories = struct.get("territories") if isinstance(struct, dict) else None
    if isinstance(territories, list):
        for entry in territories:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name or name.startswith("_"):
                continue
            expr = _territory_parts_to_expr(entry.get("parts"))
            if not expr:
                continue
            lines.append(f"{name} = {expr}")
    idx_raw = struct.get("index_names") if isinstance(struct, dict) else None
    if isinstance(idx_raw, list):
        idx = _dedupe_str_list([str(v) for v in idx_raw if isinstance(v, str)])
        lines.append(f"__TERRITORY_INDEX__ = {json.dumps(idx, ensure_ascii=False)}")
    return ("\n".join(lines) + "\n") if lines else ""


def _parse_theme_code_to_options(theme_code: str) -> Dict[str, Any]:
    options: Dict[str, Any] = {"basemaps": []}
    flag_rows: List[Dict[str, Any]] = []
    admin_rows: List[Dict[str, Any]] = []
    if not isinstance(theme_code, str) or not theme_code.strip():
        return options
    try:
        tree = ast.parse(theme_code)
    except Exception:
        return options
    for stmt in tree.body:
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        name = _call_name(call.func)
        if not (name and name.startswith("xatra.")):
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
            continue
        if method == "CSS":
            if call.args:
                css_text = _python_value(call.args[0])
                if isinstance(css_text, str):
                    current = options.get("css_rules") or []
                    options["css_rules"] = current + _parse_css_rules(css_text)
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
                    flag_rows.append(row)
            continue
        if method == "AdminColorSequence":
            if call.args:
                row = _parse_linear_sequence_row_expr(call.args[0])
                if row:
                    admin_rows = [row]
                else:
                    legacy = _parse_admin_color_expr(call.args[0])
                    if legacy:
                        admin_rows = [{
                            "class_name": "",
                            "colors": legacy,
                            "step_h": 1.6180339887,
                            "step_s": 0.0,
                            "step_l": 0.0,
                        }]
            continue
        if method == "DataColormap":
            if call.args:
                cmap = _parse_data_colormap_expr(call.args[0])
                if cmap:
                    options["data_colormap"] = cmap
            continue
        if method == "zoom":
            if call.args:
                zoom_val = _python_value(call.args[0])
                if zoom_val is not None:
                    try:
                        options["zoom"] = int(zoom_val)
                    except (TypeError, ValueError):
                        pass
            continue
        if method == "focus":
            if len(call.args) >= 2:
                lat = _python_value(call.args[0])
                lng = _python_value(call.args[1])
                if lat is not None and lng is not None:
                    try:
                        options["focus"] = [float(lat), float(lng)]
                    except (TypeError, ValueError):
                        pass
            continue
        if method == "slider":
            start_val = _python_value(kwargs["start"]) if kwargs.get("start") else None
            end_val = _python_value(kwargs["end"]) if kwargs.get("end") else None
            speed_val = _python_value(kwargs["speed"]) if kwargs.get("speed") else None
            if call.args:
                if len(call.args) >= 1:
                    start_val = _python_value(call.args[0])
                if len(call.args) >= 2:
                    end_val = _python_value(call.args[1])
            options["slider"] = {"start": start_val, "end": end_val, "speed": speed_val}
            continue
    if flag_rows:
        options["flag_color_sequences"] = flag_rows
    if admin_rows:
        options["admin_color_sequences"] = admin_rows
    return options


def _normalize_theme_options_struct(options: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(options, dict):
        return {"basemaps": []}
    out: Dict[str, Any] = {"basemaps": []}
    basemaps = options.get("basemaps")
    if isinstance(basemaps, list):
        out["basemaps"] = [bm for bm in basemaps if isinstance(bm, (dict, str))]
    for key in ("css_rules", "flag_color_sequences", "admin_color_sequences"):
        val = options.get(key)
        if isinstance(val, list):
            out[key] = [item for item in val if isinstance(item, dict)]
    dc = options.get("data_colormap")
    if isinstance(dc, dict):
        out["data_colormap"] = dict(dc)
    return out


def _extract_theme_options_struct(content: str) -> Dict[str, Any]:
    parsed = _json_parse(content, None)
    if isinstance(parsed, dict):
        opts = parsed.get("theme_options")
        if isinstance(opts, dict):
            return _normalize_theme_options_struct(opts)
        for key in ("theme_code", "code", "content"):
            val = parsed.get(key)
            if isinstance(val, str):
                return _parse_theme_code_to_options(val)
    return _parse_theme_code_to_options(content or "")


def _normalize_lib_content_for_storage(content: str) -> str:
    parsed = _json_parse(content, None)
    payload = dict(parsed) if isinstance(parsed, dict) else {}
    struct = _extract_territory_library_struct(content or "")
    payload["schema"] = "territory_library_v1"
    payload["territories"] = struct.get("territories", [])
    payload["index_names"] = struct.get("index_names", [])
    payload["predefined_code"] = _territory_library_struct_to_code(struct)
    return json.dumps(payload, ensure_ascii=False)


def _normalize_css_content_for_storage(content: str) -> str:
    parsed = _json_parse(content, None)
    payload = dict(parsed) if isinstance(parsed, dict) else {}
    if isinstance(parsed, dict):
        original_code = parsed.get("theme_code")
        if not isinstance(original_code, str):
            original_code = parsed.get("code") if isinstance(parsed.get("code"), str) else ""
    else:
        original_code = content or ""
    opts = _extract_theme_options_struct(content or "")
    payload["schema"] = "theme_v1"
    payload["theme_options"] = _normalize_theme_options_struct(opts)
    payload["theme_code"] = original_code if isinstance(original_code, str) else ""
    return json.dumps(payload, ensure_ascii=False)


def _strip_python_wrappers_for_storage(value: Any) -> Any:
    if isinstance(value, dict):
        if len(value) == 1 and isinstance(value.get(PYTHON_EXPR_KEY), str):
            return str(value.get(PYTHON_EXPR_KEY) or "")
        return {k: _strip_python_wrappers_for_storage(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_python_wrappers_for_storage(v) for v in value]
    return value


def _sanitize_untrusted_map_elements(elements: Any) -> List[Any]:
    out: List[Any] = []
    if not isinstance(elements, list):
        return out
    for item in elements:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", "")).strip().lower()
        if item_type == "python":
            continue
        copied = dict(item)
        copied["label"] = _strip_python_wrappers_for_storage(copied.get("label"))
        copied["value"] = _strip_python_wrappers_for_storage(copied.get("value"))
        copied["args"] = _strip_python_wrappers_for_storage(copied.get("args") if isinstance(copied.get("args"), dict) else {})
        out.append(copied)
    return out


def _sanitize_untrusted_map_content_for_storage(content: str) -> str:
    parsed = _json_parse(content or "", None)
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Non-trusted map content must be a JSON object")

    payload = dict(parsed)
    for key in ("imports_code", "runtime_imports_code", "theme_code", "predefined_code", "map_code", "code", "runtime_code"):
        if key in payload:
            payload[key] = ""

    payload["runtime_elements"] = _sanitize_untrusted_map_elements(payload.get("runtime_elements", []))
    runtime_options = payload.get("runtime_options", {})
    payload["runtime_options"] = _strip_python_wrappers_for_storage(runtime_options if isinstance(runtime_options, dict) else {})
    picker_options = payload.get("picker_options", {})
    payload["picker_options"] = _strip_python_wrappers_for_storage(picker_options if isinstance(picker_options, dict) else {})

    project = payload.get("project", {})
    project_dict = dict(project) if isinstance(project, dict) else {}
    project_dict["elements"] = _sanitize_untrusted_map_elements(project_dict.get("elements", []))
    project_dict["runtimeElements"] = _sanitize_untrusted_map_elements(project_dict.get("runtimeElements", []))
    project_dict["options"] = _strip_python_wrappers_for_storage(project_dict.get("options", {}) if isinstance(project_dict.get("options"), dict) else {})
    project_dict["runtimeOptions"] = _strip_python_wrappers_for_storage(project_dict.get("runtimeOptions", {}) if isinstance(project_dict.get("runtimeOptions"), dict) else {})
    for key in ("importsCode", "runtimeImportsCode", "themeCode", "predefinedCode", "code", "runtimeCode"):
        if key in project_dict:
            project_dict[key] = ""
    payload["project"] = project_dict

    return json.dumps(payload, ensure_ascii=False)


def _sanitize_untrusted_project_for_draft(project: Any) -> Dict[str, Any]:
    data = dict(project) if isinstance(project, dict) else {}
    data["elements"] = _sanitize_untrusted_map_elements(data.get("elements", []))
    data["runtimeElements"] = _sanitize_untrusted_map_elements(data.get("runtimeElements", []))
    data["options"] = _strip_python_wrappers_for_storage(data.get("options", {}) if isinstance(data.get("options"), dict) else {})
    data["runtimeOptions"] = _strip_python_wrappers_for_storage(data.get("runtimeOptions", {}) if isinstance(data.get("runtimeOptions"), dict) else {})
    for key in ("importsCode", "runtimeImportsCode", "themeCode", "predefinedCode", "code", "runtimeCode"):
        if key in data:
            data[key] = ""
    return data


def _normalize_artifact_content_for_storage(kind: str, content: str, trusted_user: bool = True) -> str:
    normalized_kind = _normalize_hub_kind(kind)
    raw = content or ""
    if normalized_kind == "lib":
        return _normalize_lib_content_for_storage(raw)
    if normalized_kind == "css":
        return _normalize_css_content_for_storage(raw)
    if normalized_kind == "map" and not trusted_user:
        return _sanitize_untrusted_map_content_for_storage(raw)
    return raw

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


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Return empty 204 to silence browser favicon requests (frontend serves its own favicon)
    return Response(status_code=204)


def _map_vote_count(conn: sqlite3.Connection, artifact_id: int) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM hub_votes WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return int(row["c"] if row else 0)


def _map_view_count(conn: sqlite3.Connection, artifact_id: int) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM hub_map_views WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return int(row["c"] if row else 0)


def _normalize_map_sort(sort: Optional[str]) -> str:
    key = str(sort or "").strip().lower()
    return key if key in {"default", "votes", "views", "recency"} else "default"


def _map_sort_order_sql(sort: str) -> str:
    if sort == "votes":
        return "COALESCE(vv.votes_count, 0) DESC, COALESCE(mv.views_count, 0) DESC, a.updated_at DESC"
    if sort == "views":
        return "COALESCE(mv.views_count, 0) DESC, COALESCE(vv.votes_count, 0) DESC, a.updated_at DESC"
    if sort == "recency":
        return "a.updated_at DESC, COALESCE(vv.votes_count, 0) DESC, COALESCE(mv.views_count, 0) DESC"
    return "a.featured DESC, COALESCE(vv.votes_count, 0) DESC, COALESCE(mv.views_count, 0) DESC, a.updated_at DESC"


def _require_write_identity(conn: sqlite3.Connection, request: Request, username: str) -> Optional[sqlite3.Row]:
    target = _normalize_hub_user(username, allow_reserved=True)
    user = _request_user(conn, request)
    if user is not None:
        if user["username"] != target:
            raise HTTPException(status_code=403, detail="Cannot modify another user's artifact")
        return user
    raise HTTPException(status_code=401, detail="Login required")


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


def _create_session_cookie(conn: sqlite3.Connection, row: sqlite3.Row, response: Response, request: Request) -> Dict[str, Any]:
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
        secure=_secure_cookie_flag(request),
        max_age=60 * 60 * 24 * SESSION_TTL_DAYS,
    )
    return {"user": _user_public_profile(conn, row), "is_authenticated": True}


@app.post("/auth/signup")
def auth_signup(body: AuthSignupRequest, response: Response, http_request: Request):
    ip = (http_request.client.host if http_request.client else "unknown")
    _check_rate_limit(
        f"signup:{ip}",
        limit=5,
        window_seconds=3600,
        label="Too many signup attempts from this IP.",
    )
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
        result = _create_session_cookie(conn, row, response, http_request)
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
    _check_rate_limit(
        f"login:{ip}",
        limit=20,
        window_seconds=600,
        label="Too many login attempts. Please wait before trying again.",
    )
    conn = _hub_db_conn()
    try:
        username = _normalize_hub_user(body.username)
        row = conn.execute("SELECT * FROM hub_users WHERE username = ?", (username,)).fetchone()
        if row is None or not _verify_password(str(body.password or ""), row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        result = _create_session_cookie(conn, row, response, http_request)
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
                    "is_admin": False,
                    "maps_count": 0,
                    "views_count": 0,
                    "is_trusted": False,
                },
                "guest_id": guest_id,
            }
        profile = _user_public_profile(conn, user)
        profile["is_trusted"] = _is_user_trusted(user)
        return {
            "is_authenticated": True,
            "user": profile,
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
    _check_rate_limit(
        f"passwd:{ip}",
        limit=6,
        window_seconds=1800,
        label="Too many password change attempts.",
    )
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


@app.put("/auth/users/{username}/trusted")
def auth_set_user_trusted(username: str, payload: UserTrustUpdateRequest, request: Request):
    conn = _hub_db_conn()
    try:
        _require_admin_user(conn, request)
        target = _normalize_hub_user(username)
        row = conn.execute("SELECT * FROM hub_users WHERE username = ?", (target,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        trusted = bool(payload.trusted)
        if int(row["is_admin"] or 0) == 1:
            trusted = True
        conn.execute(
            "UPDATE hub_users SET is_trusted = ? WHERE id = ?",
            (1 if trusted else 0, row["id"]),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM hub_users WHERE id = ?", (row["id"],)).fetchone()
        return {"ok": True, "user": _user_public_profile(conn, updated)}
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


@app.put("/maps/{map_name}/featured")
def maps_set_featured(map_name: str, payload: MapFeaturedUpdateRequest, request: Request):
    conn = _hub_db_conn()
    try:
        _require_admin_user(conn, request)
        artifact = _hub_get_artifact_by_name(conn, "map", map_name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Map not found")
        featured = 1 if bool(payload.featured) else 0
        conn.execute(
            "UPDATE hub_artifacts SET featured = ? WHERE id = ?",
            (featured, artifact["id"]),
        )
        conn.commit()
        return {"ok": True, "name": artifact["name"], "featured": bool(featured)}
    finally:
        conn.close()


@app.get("/explore")
def maps_explore(
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 12,
    sort: Optional[str] = "default",
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
    sort_key = _normalize_map_sort(sort)
    order_sql = _map_sort_order_sql(sort_key)
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
            SELECT
                a.id,
                a.name,
                a.updated_at,
                a.alpha_metadata,
                a.featured,
                u.username,
                u.is_admin,
                COALESCE(vv.votes_count, 0) AS votes_count,
                COALESCE(mv.views_count, 0) AS views_count
            FROM hub_artifacts a
            JOIN hub_users u ON u.id = a.user_id
            LEFT JOIN (
                SELECT artifact_id, COUNT(*) AS votes_count
                FROM hub_votes
                GROUP BY artifact_id
            ) vv ON vv.artifact_id = a.id
            LEFT JOIN (
                SELECT artifact_id, COUNT(*) AS views_count
                FROM hub_map_views
                GROUP BY artifact_id
            ) mv ON mv.artifact_id = a.id
            {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            (*params, safe_per_page, offset),
        ).fetchall()
        items = []
        for row in rows:
            meta = _json_parse(row["alpha_metadata"], {})
            items.append({
                "username": row["username"],
                "is_admin": bool(int(row["is_admin"] or 0)),
                "name": row["name"],
                "slug": f"/{row['name']}",
                "forked_from": meta.get("forked_from"),
                "votes": int(row["votes_count"] or 0),
                "views": int(row["views_count"] or 0),
                "featured": bool(int(row["featured"] or 0)),
                "updated_at": row["updated_at"],
                "thumbnail": meta.get("thumbnail") or "/vite.svg",
            })
        return {"items": items, "page": safe_page, "per_page": safe_per_page, "total": int(total or 0), "sort": sort_key}
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
            SELECT
                u.username,
                u.full_name,
                u.bio,
                u.is_admin,
                u.is_trusted,
                u.created_at,
                COALESCE(mc.maps_count, 0) AS maps_count,
                COALESCE(vc.views_count, 0) AS views_count
            FROM hub_users u
            LEFT JOIN (
                SELECT user_id, COUNT(*) AS maps_count
                FROM hub_artifacts
                WHERE kind = 'map'
                GROUP BY user_id
            ) mc ON mc.user_id = u.id
            LEFT JOIN (
                SELECT a.user_id, COUNT(*) AS views_count
                FROM hub_map_views mv
                JOIN hub_artifacts a ON a.id = mv.artifact_id
                WHERE a.kind = 'map'
                GROUP BY a.user_id
            ) vc ON vc.user_id = u.id
            {where_sql}
            ORDER BY u.username ASC
            LIMIT ? OFFSET ?
            """,
            (*params, safe_per_page, offset),
        ).fetchall()
        users = [{
            "username": row["username"],
            "full_name": row["full_name"] or "",
            "bio": row["bio"] or "",
            "is_admin": bool(int(row["is_admin"] or 0)),
            "is_trusted": bool(int(row["is_trusted"] or 0)) or bool(int(row["is_admin"] or 0)),
            "maps_count": int(row["maps_count"] or 0),
            "views_count": int(row["views_count"] or 0),
            "created_at": row["created_at"],
        } for row in rows]
        return {"items": users, "page": safe_page, "per_page": safe_per_page, "total": int(total or 0)}
    finally:
        conn.close()


@app.get("/users/{username}")
def user_profile(username: str, q: Optional[str] = None, page: int = 1, per_page: int = 10, sort: Optional[str] = "default"):
    uname = _normalize_hub_user(username)
    conn = _hub_db_conn()
    try:
        user = conn.execute("SELECT * FROM hub_users WHERE username = ?", (uname,)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        profile = _user_public_profile(conn, user)
        safe_page = max(1, int(page or 1))
        safe_per_page = max(1, min(int(per_page or 10), 30))
        sort_key = _normalize_map_sort(sort)
        order_sql = _map_sort_order_sql(sort_key)
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
            SELECT
                a.id,
                a.name,
                a.updated_at,
                a.alpha_metadata,
                a.featured,
                COALESCE(vv.votes_count, 0) AS votes_count,
                COALESCE(mv.views_count, 0) AS views_count
            FROM hub_artifacts a
            LEFT JOIN (
                SELECT artifact_id, COUNT(*) AS votes_count
                FROM hub_votes
                GROUP BY artifact_id
            ) vv ON vv.artifact_id = a.id
            LEFT JOIN (
                SELECT artifact_id, COUNT(*) AS views_count
                FROM hub_map_views
                GROUP BY artifact_id
            ) mv ON mv.artifact_id = a.id
            {where}
            ORDER BY {order_sql}
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
                "votes": int(row["votes_count"] or 0),
                "views": int(row["views_count"] or 0),
                "featured": bool(int(row["featured"] or 0)),
                "updated_at": row["updated_at"],
                "thumbnail": meta.get("thumbnail") or "/vite.svg",
            })
        return {"profile": profile, "maps": maps, "page": safe_page, "per_page": safe_per_page, "total": int(total or 0), "sort": sort_key}
    finally:
        conn.close()


@app.get("/user/{username}")
def user_profile_by_prefix(username: str, q: Optional[str] = None, page: int = 1, per_page: int = 10, sort: Optional[str] = "default"):
    """User profile accessible at /user/{username} (new canonical URL)."""
    return user_profile(username=username, q=q, page=page, per_page=per_page, sort=sort)


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
        safe_project = _sanitize_untrusted_project_for_draft(payload.project or {})
        draft_json = json.dumps({
            "map_name": _normalize_hub_name(payload.map_name or "new_map"),
            "project": safe_project,
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
        _check_rate_limit(
            f"draft_promote:user:{int(user['id'])}",
            limit=20,
            window_seconds=3600,
            label="Too many map create actions. Please wait before creating more maps.",
        )
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
        trusted_user = _is_user_trusted(user)
        content_obj = {
            "imports_code":    project.get("importsCode", ""),
            "runtime_imports_code": project.get("runtimeImportsCode", ""),
            "theme_code":      project.get("themeCode", ""),
            "predefined_code": project.get("predefinedCode", ""),
            "map_code":        project.get("code", ""),
            "runtime_code":    project.get("runtimeCode", ""),
            "runtime_elements": project.get("runtimeElements", []),
            "runtime_options":  project.get("runtimeOptions", {}),
            "picker_options":  project.get("pickerOptions", {"entries": [], "adminRivers": False}),
            "project": {
                "elements":       project.get("elements", []),
                "options":        project.get("options", {}),
                "runtimeElements": project.get("runtimeElements", []),
                "runtimeOptions":  project.get("runtimeOptions", {}),
                "predefinedCode": project.get("predefinedCode", ""),
                "importsCode":    project.get("importsCode", ""),
                "runtimeImportsCode": project.get("runtimeImportsCode", ""),
                "themeCode":      project.get("themeCode", ""),
                "runtimeCode":    project.get("runtimeCode", ""),
            }
        }
        content = _normalize_artifact_content_for_storage("map", json.dumps(content_obj, ensure_ascii=False), trusted_user=trusted_user)
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
        _check_rate_limit(
            f"hub_create_map:user:{int(user['id'])}",
            limit=30,
            window_seconds=3600,
            label="Map creation rate limit reached. Please wait before creating more maps.",
        )
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
        user_row = _require_write_identity(conn, http_request, artifact['username'])
        content = _normalize_artifact_content_for_storage(kind, request.content or "", trusted_user=_is_user_trusted(user_row))
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
        if user_row is not None:
            _check_rate_limit(
                f"publish:user:{int(user_row['id'])}:{kind}",
                limit=60,
                window_seconds=3600,
                label="Publish rate limit reached. Please wait before publishing again.",
            )
        content = _normalize_artifact_content_for_storage(kind, request.content or "", trusted_user=_is_user_trusted(user_row))
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


@app.patch("/hub/{username}/{kind}/{name}/rename")
def hub_rename_artifact(username: str, kind: str, name: str, request: HubArtifactRenameRequest, http_request: Request):
    """Rename an artifact in-place. Only allowed when there are no published versions."""
    conn = _hub_db_conn()
    try:
        _require_write_identity(conn, http_request, username)
        kind = _normalize_hub_kind(kind)
        artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        version_count = conn.execute(
            "SELECT COUNT(*) AS c FROM hub_artifact_versions WHERE artifact_id = ?",
            (artifact["id"],),
        ).fetchone()["c"]
        if version_count > 0:
            raise HTTPException(status_code=409, detail="Cannot rename: artifact has published versions")
        new_name = _normalize_hub_name(request.new_name)
        if kind == "map" and new_name in HUB_RESERVED_USERNAMES:
            raise HTTPException(status_code=400, detail=f"Map name '{new_name}' is reserved")
        existing = conn.execute(
            "SELECT id FROM hub_artifacts WHERE kind = ? AND name = ? AND id != ?",
            (kind, new_name, artifact["id"]),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"A {kind} named '{new_name}' already exists")
        conn.execute(
            "UPDATE hub_artifacts SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, _utc_now_iso(), artifact["id"]),
        )
        conn.commit()
        return {"name": new_name, "renamed": True}
    finally:
        conn.close()


@app.put("/hub/{username}/{kind}/{name}/alpha")
def hub_save_alpha(username: str, kind: str, name: str, request: HubArtifactWriteRequest, http_request: Request, response: Response):
    conn = _hub_db_conn()
    try:
        user_row = _require_write_identity(conn, http_request, username)
        content = _normalize_artifact_content_for_storage(kind, request.content or "", trusted_user=_is_user_trusted(user_row))
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
        if user_row is not None:
            _check_rate_limit(
                f"publish:user:{int(user_row['id'])}:{kind}",
                limit=60,
                window_seconds=3600,
                label="Publish rate limit reached. Please wait before publishing again.",
            )
        content = _normalize_artifact_content_for_storage(kind, request.content or "", trusted_user=_is_user_trusted(user_row))
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


@app.get("/hub/{username}/{kind}/{name}/info")
def hub_artifact_info(username: str, kind: str, name: str, forks_limit: int = 5, importers_limit: int = 5):
    conn = _hub_db_conn()
    try:
        artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        meta = _artifact_metadata_dict(artifact["alpha_metadata"])
        kind_label = _hub_kind_label(artifact["kind"])
        # Forks: maps where forked_from metadata contains this artifact's slug
        slug = f"/{artifact['name']}"
        safe_forks_limit = max(1, min(int(forks_limit), 50))
        fork_rows = conn.execute(
            """
            SELECT a.name, u.username, a.alpha_metadata, a.updated_at
            FROM hub_artifacts a
            JOIN hub_users u ON u.id = a.user_id
            WHERE a.kind = 'map'
              AND a.alpha_metadata LIKE ?
            ORDER BY a.updated_at DESC
            LIMIT ?
            """,
            (f'%"forked_from":"{slug}"%', safe_forks_limit + 1),
        ).fetchall()
        forks_has_more = len(fork_rows) > safe_forks_limit
        forks = []
        for row in fork_rows[:safe_forks_limit]:
            fork_meta = _json_parse(row["alpha_metadata"], {})
            forks.append({
                "username": row["username"],
                "name": row["name"],
                "slug": f"/{row['name']}",
                "thumbnail": fork_meta.get("thumbnail") or "/vite.svg",
                "updated_at": row["updated_at"],
            })
        # Importers: artifacts whose alpha_content references this artifact
        safe_imp_limit = max(1, min(int(importers_limit), 50))
        import_search = f"%/{kind_label}/{artifact['name']}/%"
        imp_rows = conn.execute(
            """
            SELECT a.name, a.kind, u.username, a.updated_at
            FROM hub_artifacts a
            JOIN hub_users u ON u.id = a.user_id
            WHERE a.id != ?
              AND a.alpha_content LIKE ?
            ORDER BY a.updated_at DESC
            LIMIT ?
            """,
            (artifact["id"], import_search, safe_imp_limit + 1),
        ).fetchall()
        importers_has_more = len(imp_rows) > safe_imp_limit
        importers = []
        for row in imp_rows[:safe_imp_limit]:
            importers.append({
                "username": row["username"],
                "kind": _hub_kind_label(row["kind"]),
                "name": row["name"],
                "slug": f"/{_hub_kind_label(row['kind'])}/{row['name']}",
                "updated_at": row["updated_at"],
            })
        # Timeline
        versions_rows = conn.execute(
            "SELECT version, created_at FROM hub_artifact_versions WHERE artifact_id = ? ORDER BY version ASC",
            (artifact["id"],),
        ).fetchall()
        timeline = {
            "created_at": artifact["created_at"],
            "updated_at": artifact["updated_at"],
            "versions": [{"version": int(r["version"]), "created_at": r["created_at"]} for r in versions_rows],
        }
        return {
            "description": meta.get("description") or "",
            "display_type": meta.get("display_type") or "map",
            "forks": forks,
            "forks_has_more": forks_has_more,
            "importers": importers,
            "importers_has_more": importers_has_more,
            "timeline": timeline,
        }
    finally:
        conn.close()


@app.put("/hub/{username}/{kind}/{name}/meta")
async def hub_update_artifact_meta(username: str, kind: str, name: str, http_request: Request):
    body = await http_request.json()
    conn = _hub_db_conn()
    try:
        _require_write_identity(conn, http_request, username)
        artifact = _hub_get_artifact(conn, username, kind, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        existing_meta = _artifact_metadata_dict(artifact["alpha_metadata"])
        if "description" in body:
            existing_meta["description"] = str(body["description"] or "")
        if "display_type" in body:
            dt = str(body.get("display_type") or "map")
            if dt not in ("map", "territory_library", "theme"):
                raise HTTPException(status_code=400, detail="display_type must be 'map', 'territory_library', or 'theme'")
            existing_meta["display_type"] = dt
        conn.execute(
            "UPDATE hub_artifacts SET alpha_metadata = ?, updated_at = ? WHERE id = ?",
            (json.dumps(existing_meta, ensure_ascii=False), _utc_now_iso(), artifact["id"]),
        )
        conn.commit()
        return {"ok": True, "description": existing_meta.get("description", ""), "display_type": existing_meta.get("display_type", "map")}
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
                "featured": bool(int(artifact["featured"] or 0)) if artifact["kind"] == "map" else False,
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
            "featured": bool(int(artifact["featured"] or 0)) if artifact["kind"] == "map" else False,
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
                a.id, a.kind, a.name, a.updated_at, a.alpha_metadata,
                u.username, u.is_admin,
                COALESCE(MAX(v.version), 0) AS latest_version,
                COUNT(DISTINCT vv.id) AS votes_count,
                COUNT(DISTINCT mv.id) AS views_count
            FROM hub_artifacts a
            JOIN hub_users u ON u.id = a.user_id
            LEFT JOIN hub_artifact_versions v ON v.artifact_id = a.id
            LEFT JOIN hub_votes vv ON vv.artifact_id = a.id
            LEFT JOIN hub_map_views mv ON mv.artifact_id = a.id
            {where_sql}
            GROUP BY a.id, a.kind, a.name, a.updated_at, u.username, u.is_admin
            ORDER BY votes_count DESC, views_count DESC, a.updated_at DESC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()
        items = []
        for row in rows:
            kind_label = _hub_kind_label(row["kind"])
            latest = int(row["latest_version"]) if int(row["latest_version"]) > 0 else None
            meta = _json_parse(row["alpha_metadata"], {})
            items.append({
                "username": row["username"],
                "is_admin": bool(int(row["is_admin"] or 0)),
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
        actor_key = f"user:{int(user['id'])}" if user is not None else f"guest:{guest_id.strip()}"
    finally:
        conn.close()
    allowed_task_types = {"picker", "territory_library", "code", "builder"}
    requested = request.task_types if request and request.task_types else list(allowed_task_types)
    task_types = [t for t in requested if t in allowed_task_types]
    stopped = []
    to_join: List[multiprocessing.Process] = []
    with process_lock:
        for task_type in task_types:
            slot_key = f"{actor_key}:{task_type}"
            proc = current_processes.get(slot_key)
            if proc and proc.is_alive():
                proc.terminate()
                stopped.append(task_type)
                to_join.append(proc)
            if current_processes.get(slot_key) is proc:
                current_processes.pop(slot_key, None)
    for proc in to_join:
        _terminate_process(proc, timeout=3.0)
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
            for key in ("imports_code", "runtime_imports_code", "theme_code", "map_code", "code"):
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

def _parse_imports_code_calls(imports_code: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(imports_code, str) or not imports_code.strip():
        return out
    try:
        tree = ast.parse(imports_code)
    except Exception:
        return out
    for stmt in tree.body:
        alias: Optional[str] = None
        call: Optional[ast.Call] = None
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            alias = stmt.targets[0].id
            if isinstance(stmt.value, ast.Call):
                call = stmt.value
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
        if call is None:
            continue
        if _call_name(call.func) != "xatrahub":
            continue
        if not call.args:
            continue
        path_val = _python_value(call.args[0])
        if not isinstance(path_val, str) or not path_val.strip():
            continue
        kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg}
        filter_only_val = _python_value(kwargs.get("filter_only")) if "filter_only" in kwargs else None
        filter_not_val = _python_value(kwargs.get("filter_not")) if "filter_not" in kwargs else None
        filter_only = [str(x) for x in filter_only_val] if isinstance(filter_only_val, list) else None
        filter_not = [str(x) for x in filter_not_val] if isinstance(filter_not_val, list) else None
        out.append({
            "alias": alias if isinstance(alias, str) and alias.strip() else None,
            "path": path_val.strip(),
            "filter_only": filter_only,
            "filter_not": filter_not,
        })
    return out


def _strip_python_wrappers(value: Any) -> Any:
    if isinstance(value, dict):
        if len(value) == 1 and isinstance(value.get(PYTHON_EXPR_KEY), str):
            return str(value.get(PYTHON_EXPR_KEY) or "")
        return {k: _strip_python_wrappers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_python_wrappers(v) for v in value]
    return value


def _sanitize_untrusted_point_icon(icon: Any) -> Any:
    """Disallow URL/custom icons in untrusted builder payloads."""
    if isinstance(icon, dict):
        icon_type = str(icon.get("type", "")).strip().lower()
        if icon_type == "url" or "icon_url" in icon or "iconUrl" in icon:
            return None
    return icon


def _sanitize_untrusted_builder_payload(elements: Any, options: Any) -> Tuple[List[Any], Dict[str, Any]]:
    safe_elements: List[Any] = []
    if isinstance(elements, list):
        for item in elements:
            if isinstance(item, dict):
                item_type = str(item.get("type", "")).strip().lower()
                if item_type == "python":
                    continue
                copied = dict(item)
                copied["value"] = _strip_python_wrappers(copied.get("value"))
                copied["args"] = _strip_python_wrappers(copied.get("args") if isinstance(copied.get("args"), dict) else {})
                if isinstance(copied.get("args"), dict) and item_type == "point":
                    copied["args"]["icon"] = _sanitize_untrusted_point_icon(copied["args"].get("icon"))
                copied["label"] = _strip_python_wrappers(copied.get("label"))
                safe_elements.append(copied)
            else:
                item_type = str(getattr(item, "type", "")).strip().lower()
                if item_type == "python":
                    continue
                copied = {
                    "type": getattr(item, "type", ""),
                    "label": _strip_python_wrappers(getattr(item, "label", None)),
                    "value": _strip_python_wrappers(getattr(item, "value", None)),
                    "args": _strip_python_wrappers(getattr(item, "args", {}) if isinstance(getattr(item, "args", {}), dict) else {}),
                }
                if isinstance(copied.get("args"), dict) and item_type == "point":
                    copied["args"]["icon"] = _sanitize_untrusted_point_icon(copied["args"].get("icon"))
                safe_elements.append(copied)
    safe_options = _strip_python_wrappers(options if isinstance(options, dict) else {})
    if not isinstance(safe_options, dict):
        safe_options = {}
    return safe_elements, safe_options

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

    def resolve_dotted_name(scope: Dict[str, Any], name: str):
        parts = [p for p in str(name or "").split(".") if p]
        if not parts:
            return None
        obj = scope.get(parts[0])
        for attr in parts[1:]:
            if obj is None:
                return None
            obj = getattr(obj, attr, None)
        return obj

    def eval_territory_parts(parts: Any, resolver):
        if not isinstance(parts, list):
            return None
        out = None
        for part in parts:
            if not isinstance(part, dict):
                continue
            ptype = str(part.get("type", ""))
            value = part.get("value")
            piece = None
            if ptype == "group":
                piece = eval_territory_parts(value, resolver)
            elif ptype == "gadm":
                vals = value if isinstance(value, list) else [value]
                for item in vals:
                    if not isinstance(item, str) or not item.strip():
                        continue
                    terr = xatra.loaders.gadm(item.strip())
                    piece = terr if piece is None else (piece | terr)
            elif ptype == "polygon":
                try:
                    coords = json.loads(value) if isinstance(value, str) else value
                    piece = xatra.loaders.polygon(coords)
                except Exception:
                    piece = None
            elif ptype == "predefined":
                vals = value if isinstance(value, list) else [value]
                for item in vals:
                    if not isinstance(item, str) or not item.strip():
                        continue
                    terr = resolver(item.strip())
                    if terr is not None:
                        piece = terr if piece is None else (piece | terr)
            if piece is None:
                continue
            op = str(part.get("op", "union"))
            if out is None:
                out = piece
            elif op == "difference":
                out = out - piece
            elif op == "intersection":
                out = out & piece
            else:
                out = out | piece
        return out

    def materialize_library_namespace(struct: Dict[str, Any], external_scope: Dict[str, Any], include_builtin: bool = False):
        definitions: Dict[str, List[Dict[str, Any]]] = {}
        territories = struct.get("territories") if isinstance(struct, dict) else None
        if isinstance(territories, list):
            for entry in territories:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                parts = entry.get("parts")
                if not isinstance(name, str) or not name or name.startswith("_") or not isinstance(parts, list):
                    continue
                definitions[name] = parts
        cache: Dict[str, Any] = {}
        visiting: set = set()

        def _resolver(token: str):
            if "." in token:
                return resolve_dotted_name(external_scope, token)
            if token in cache:
                return cache[token]
            if token in visiting:
                return None
            parts = definitions.get(token)
            if isinstance(parts, list):
                visiting.add(token)
                try:
                    terr = eval_territory_parts(parts, _resolver)
                    cache[token] = terr
                    return terr
                finally:
                    visiting.discard(token)
            obj = external_scope.get(token)
            if obj is not None:
                return obj
            if include_builtin:
                try:
                    import xatra.territory_library as territory_library
                    return getattr(territory_library, token, None)
                except Exception:
                    return None
            return None

        for name in definitions.keys():
            _resolver(name)
        payload = {k: v for k, v in cache.items() if v is not None}
        return SimpleNamespace(**payload), payload

    def filter_theme_options(options: Dict[str, Any], filter_only: Optional[List[str]], filter_not: Optional[List[str]]) -> Dict[str, Any]:
        if not filter_only and not filter_not:
            return _normalize_theme_options_struct(options or {})
        only = {str(x).strip() for x in (filter_only or []) if str(x).strip()}
        blocked = {str(x).strip() for x in (filter_not or []) if str(x).strip()}
        key_map = {
            "BaseOption": "basemaps",
            "CSS": "css_rules",
            "FlagColorSequence": "flag_color_sequences",
            "AdminColorSequence": "admin_color_sequences",
            "DataColormap": "data_colormap",
        }
        filtered: Dict[str, Any] = {"basemaps": []}
        for method, key in key_map.items():
            if only and method not in only:
                continue
            if method in blocked:
                continue
            if key in options:
                filtered[key] = options[key]
        return _normalize_theme_options_struct(filtered)

    def apply_theme_options(options: Dict[str, Any]):
        opts = _normalize_theme_options_struct(options or {})
        basemaps = opts.get("basemaps")
        if isinstance(basemaps, list):
            for bm in basemaps:
                if isinstance(bm, dict):
                    m.BaseOption(**bm)
                else:
                    m.BaseOption(bm)
        css_rules = opts.get("css_rules")
        if isinstance(css_rules, list):
            css_str = ""
            for rule in css_rules:
                if not isinstance(rule, dict):
                    continue
                selector = rule.get("selector", "")
                style = rule.get("style", "")
                if selector and style:
                    css_str += f"{selector} {{ {style} }}\n"
            if css_str:
                m.CSS(css_str)
        flag_rows = opts.get("flag_color_sequences")
        if isinstance(flag_rows, list):
            for row in flag_rows:
                seq = build_linear_sequence_from_row(row)
                if not seq:
                    continue
                class_name = row.get("class_name")
                if isinstance(class_name, str):
                    class_name = class_name.strip() or None
                else:
                    class_name = None
                m.FlagColorSequence(seq, class_name=class_name)
        admin_rows = opts.get("admin_color_sequences")
        if isinstance(admin_rows, list) and admin_rows:
            row = admin_rows[0]
            seq = build_linear_sequence_from_row(row)
            if seq:
                m.AdminColorSequence(seq)
        dc = opts.get("data_colormap")
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
                import matplotlib.pyplot as plt
                cmap = getattr(plt.cm, cmap_type, None)
                if cmap is not None:
                    m.DataColormap(cmap)
        elif isinstance(dc, str):
            m.DataColormap(dc)

    def apply_scalar_options(options: Dict[str, Any]):
        if not isinstance(options, dict):
            return
        if "zoom" in options and options["zoom"] is not None:
            try:
                m.zoom(int(options["zoom"]))
            except Exception as e:
                print(f"[xatra] Warning: invalid zoom value in imported options: {e}", file=sys.stderr)
        if "focus" in options and options["focus"]:
            focus = options["focus"]
            if isinstance(focus, list) and len(focus) == 2:
                try:
                    m.focus(float(focus[0]), float(focus[1]))
                except Exception as e:
                    print(f"[xatra] Warning: invalid focus value in imported options: {e}", file=sys.stderr)
        if "slider" in options and isinstance(options["slider"], dict):
            sl = options["slider"]
            start = sl.get("start")
            end = sl.get("end")
            speed = sl.get("speed")
            if isinstance(start, str) and start.strip():
                try: start = int(start)
                except: start = None
            elif isinstance(start, str):
                start = None
            if isinstance(end, str) and end.strip():
                try: end = int(end)
                except: end = None
            elif isinstance(end, str):
                end = None
            if start is not None or end is not None:
                m.slider(start=start, end=end, speed=speed if speed else 5.0)

    def _import_method_allowed(method: str, filter_only: Optional[List[str]], filter_not: Optional[List[str]]) -> bool:
        only = {str(x).strip() for x in (filter_only or []) if str(x).strip()}
        blocked = {str(x).strip() for x in (filter_not or []) if str(x).strip()}
        if only and method not in only:
            return False
        if method in blocked:
            return False
        return True

    def _filter_imported_options(options: Dict[str, Any], filter_only: Optional[List[str]], filter_not: Optional[List[str]]) -> Dict[str, Any]:
        if not isinstance(options, dict):
            return {}
        out: Dict[str, Any] = {}
        option_method_map = {
            "basemaps": "BaseOption",
            "css_rules": "CSS",
            "flag_color_sequences": "FlagColorSequence",
            "admin_color_sequences": "AdminColorSequence",
            "data_colormap": "DataColormap",
            "zoom": "zoom",
            "focus": "focus",
            "slider": "slider",
        }
        for key, method in option_method_map.items():
            if key in options and _import_method_allowed(method, filter_only, filter_not):
                out[key] = options[key]
        return out

    def _filter_imported_elements(elements: List[Any], filter_only: Optional[List[str]], filter_not: Optional[List[str]]) -> List[Any]:
        if not isinstance(elements, list):
            return []
        type_method_map = {
            "flag": "Flag",
            "river": "River",
            "path": "Path",
            "point": "Point",
            "text": "Text",
            "admin": "Admin",
            "admin_rivers": "AdminRivers",
            "dataframe": "Dataframe",
            "titlebox": "TitleBox",
            "music": "Music",
            "python": "Python",
        }
        out: List[Any] = []
        for el in elements:
            if isinstance(el, dict):
                el_type = str(el.get("type", "")).strip().lower()
            else:
                el_type = str(getattr(el, "type", "")).strip().lower()
            method = type_method_map.get(el_type)
            if not method:
                continue
            if _import_method_allowed(method, filter_only, filter_not):
                out.append(el)
        return out

    def _parse_imported_map_payload(content_text: str) -> Dict[str, Any]:
        parsed = _json_parse(content_text or "", None)
        if isinstance(parsed, dict):
            imports_code = parsed.get("imports_code")
            if not isinstance(imports_code, str):
                imports_code = ""
            project = parsed.get("project")
            if isinstance(project, dict) and isinstance(project.get("elements"), list):
                return {
                    "imports_code": imports_code,
                    "elements": project.get("elements", []),
                    "options": project.get("options", {}) if isinstance(project.get("options"), dict) else {},
                }
            map_code = parsed.get("map_code") if isinstance(parsed.get("map_code"), str) else ""
            theme_code = parsed.get("theme_code") if isinstance(parsed.get("theme_code"), str) else ""
            combined = "\n\n".join([x for x in [theme_code, map_code] if isinstance(x, str) and x.strip()])
            if combined.strip():
                parsed_builder = parse_code_segment_to_builder_payload(combined, parsed.get("predefined_code") if isinstance(parsed.get("predefined_code"), str) else "")
                return {
                    "imports_code": imports_code,
                    "elements": parsed_builder.get("elements", []),
                    "options": parsed_builder.get("options", {}),
                }
        return {"imports_code": "", "elements": [], "options": {}}

    pending_import_elements: List[Any] = []
    import_resolution_ctx: Dict[str, Any] = {
        "active_stack": [],
        "active_set": set(),
    }

    def _import_key_from_loaded(loaded: Dict[str, Any]) -> Tuple[Optional[str], str, str, str]:
        username = loaded.get("username")
        if isinstance(username, str):
            username = username.strip().lower() or None
        else:
            username = None
        kind = str(loaded.get("kind") or "").strip().lower()
        name = str(loaded.get("name") or "").strip().lower()
        version = str(loaded.get("version") if loaded.get("version") is not None else "alpha").strip().lower() or "alpha"
        return (username, kind, name, version)

    def _import_key_label(key: Tuple[Optional[str], str, str, str]) -> str:
        username, kind, name, version = key
        if username:
            return f"/{username}/{kind}/{name}/{version}"
        return f"/{kind}/{name}/{version}"

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
            key = _import_key_from_loaded(loaded)
            if key in import_resolution_ctx["active_set"]:
                chain = import_resolution_ctx["active_stack"] + [key]
                chain_str = " -> ".join(_import_key_label(k) for k in chain)
                print(
                    f"[xatra] Warning: circular xatrahub import detected; skipping {_import_key_label(key)} ({chain_str})",
                    file=sys.stderr,
                )
                return None
            import_resolution_ctx["active_stack"].append(key)
            import_resolution_ctx["active_set"].add(key)
            try:
                kind = loaded["kind"]
                only = filter_only if isinstance(filter_only, list) else None
                not_list = filter_not if isinstance(filter_not, list) else None
                if kind == "map":
                    payload = _parse_imported_map_payload(loaded.get("content", "") or "")
                    imports_code = payload.get("imports_code", "")
                    if isinstance(imports_code, str) and imports_code.strip():
                        apply_imports_code_parsed(imports_code, exec_globals)
                    filtered_options = _filter_imported_options(
                        payload.get("options", {}) if isinstance(payload.get("options"), dict) else {},
                        only,
                        not_list,
                    )
                    if filtered_options:
                        apply_scalar_options(filtered_options)
                        apply_theme_options(_normalize_theme_options_struct(filtered_options))
                    filtered_elements = _filter_imported_elements(
                        payload.get("elements", []) if isinstance(payload.get("elements"), list) else [],
                        only,
                        not_list,
                    )
                    if filtered_elements:
                        pending_import_elements.extend(filtered_elements)
                    return None
                if kind == "css":
                    theme_opts = _extract_theme_options_struct(loaded.get("content", "") or "")
                    apply_theme_options(filter_theme_options(theme_opts, only, not_list))
                    return None
                if kind == "lib":
                    linked_map_filter_not = [
                        "BaseOption", "CSS", "FlagColorSequence", "AdminColorSequence", "DataColormap",
                        "zoom", "focus", "slider",
                        "Flag", "River", "Path", "Point", "Text",
                        "Admin", "AdminRivers", "Dataframe", "TitleBox", "Music", "Python",
                    ]
                    linked_name = str(loaded.get("name") or "").strip()
                    linked_version = str(loaded.get("version") if loaded.get("version") is not None else "alpha").strip() or "alpha"
                    if linked_name:
                        try:
                            # Pull recursive imports from the sibling map without importing its runtime-visible layers/options.
                            exec_globals["xatrahub"](
                                f"/map/{linked_name}/{linked_version}",
                                filter_not=linked_map_filter_not,
                            )
                        except Exception:
                            pass
                    struct = _extract_territory_library_struct(loaded.get("content", "") or "")
                    ns, _ = materialize_library_namespace(struct, exec_globals, include_builtin=True)
                    return ns
                raise ValueError(f"Unsupported xatrahub kind: {kind}")
            finally:
                import_resolution_ctx["active_set"].discard(key)
                if import_resolution_ctx["active_stack"] and import_resolution_ctx["active_stack"][-1] == key:
                    import_resolution_ctx["active_stack"].pop()
                else:
                    import_resolution_ctx["active_stack"] = [
                        k for k in import_resolution_ctx["active_stack"] if k != key
                    ]

        exec_globals["xatrahub"] = xatrahub

    def apply_imports_code_parsed(imports_code: str, exec_globals: Dict[str, Any]):
        if not isinstance(imports_code, str) or not imports_code.strip():
            return
        imports = _parse_imports_code_calls(imports_code)
        for item in imports:
            path = item.get("path")
            if not isinstance(path, str) or not path.strip():
                continue
            loaded = exec_globals["xatrahub"](
                path,
                filter_only=item.get("filter_only"),
                filter_not=item.get("filter_not"),
            )
            alias = item.get("alias")
            if isinstance(alias, str) and alias.strip() and loaded is not None:
                exec_globals[alias.strip()] = loaded

    def parse_code_segment_to_builder_payload(segment: str, predefined_code: str = "") -> Dict[str, Any]:
        parsed = sync_code_to_builder(CodeSyncRequest(code=segment or "", predefined_code=predefined_code or ""))
        if isinstance(parsed, dict) and parsed.get("error"):
            raise ValueError(str(parsed.get("error")))
        elements = parsed.get("elements", []) if isinstance(parsed, dict) else []
        options = parsed.get("options", {}) if isinstance(parsed, dict) else {}
        return {
            "elements": elements if isinstance(elements, list) else [],
            "options": options if isinstance(options, dict) else {"basemaps": []},
        }

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
        effective_task_type = task_type
        trusted_user = bool(getattr(data, "trusted_user", False))

        if task_type == "code":
            imports_code = getattr(data, "imports_code", "") or ""
            theme_code = getattr(data, "theme_code", "") or ""
            runtime_imports_code = getattr(data, "runtime_imports_code", "") or ""
            runtime_code = getattr(data, "runtime_code", "") or ""
            runtime_theme_code = getattr(data, "runtime_theme_code", "") or ""
            runtime_predefined_code = getattr(data, "runtime_predefined_code", "") or ""
            predefined_code = getattr(data, "predefined_code", "") or ""
            combined_predefined = "\n\n".join([x for x in [predefined_code, runtime_predefined_code] if x.strip()])
            main_payload = parse_code_segment_to_builder_payload(getattr(data, "code", "") or "", predefined_code)
            runtime_segment = "\n\n".join([
                x for x in [runtime_imports_code, runtime_theme_code, runtime_code] if isinstance(x, str) and x.strip()
            ])
            runtime_payload = parse_code_segment_to_builder_payload(runtime_segment, combined_predefined)
            data = SimpleNamespace(
                elements=main_payload.get("elements", []),
                options=main_payload.get("options", {}),
                predefined_code=predefined_code,
                imports_code=imports_code,
                runtime_imports_code=runtime_imports_code,
                theme_code=theme_code,
                runtime_code="",
                runtime_theme_code=runtime_theme_code,
                runtime_predefined_code=runtime_predefined_code,
                runtime_elements=runtime_payload.get("elements", []),
                runtime_options=runtime_payload.get("options", {}),
                trusted_user=trusted_user,
            )
            effective_task_type = "builder"
        
        if effective_task_type == 'picker':
            apply_basemaps(getattr(data, "basemaps", None))
            valid_entries: List[Tuple[str, int]] = []
            for entry in (getattr(data, "entries", None) or []):
                country = str(getattr(entry, "country", "") or "").strip()
                if not country:
                    continue
                try:
                    level = int(getattr(entry, "level", 1))
                except Exception:
                    level = 1
                valid_entries.append((country, level))
            if not valid_entries:
                # Keep picker previews stable even with malformed/blank picker state.
                valid_entries = [
                    ("IND", 2),
                    ("PAK", 3),
                    ("BGD", 2),
                    ("NPL", 3),
                    ("BTN", 1),
                    ("LKA", 1),
                    ("AFG", 2),
                ]
            for country, level in valid_entries:
                try:
                    m.Admin(gadm=country, level=level)
                except Exception as e:
                    print(f"[xatra] Warning: picker Admin({country}, level={level}) failed: {e}", file=sys.stderr)
            if data.adminRivers and valid_entries:
                m.AdminRivers()
        elif effective_task_type == 'territory_library':
            apply_basemaps(getattr(data, "basemaps", None))
            import xatra.territory_library as territory_library
            source = (getattr(data, "source", "builtin") or "builtin").strip().lower()
            code = getattr(data, "predefined_code", "") or ""
            hub_path = getattr(data, "hub_path", None)
            catalog = _get_territory_catalog(source, code, hub_path)
            selected_input = getattr(data, "selected_names", None)
            if isinstance(selected_input, list):
                selected_names = _dedupe_str_list([str(n) for n in selected_input if isinstance(n, str)])
            else:
                selected_names = catalog.get("index_names", [])
            selected_names = _dedupe_str_list([n for n in selected_names if n in catalog.get("names", [])])

            if source == "custom":
                exec_globals = {}
                for name in dir(territory_library):
                    if not name.startswith("_"):
                        exec_globals[name] = getattr(territory_library, name)
                struct = _extract_territory_library_struct(code)
                _, custom_map = materialize_library_namespace(struct, exec_globals, include_builtin=True)
                for n in selected_names:
                    terr = custom_map.get(n)
                    if terr is not None:
                        try:
                            m.Flag(label=n, value=terr)
                        except Exception:
                            continue
            elif source == "hub" and hub_path:
                try:
                    parsed = _parse_xatrahub_path(hub_path)
                    loaded = _hub_load_content(parsed["username"], parsed["kind"], parsed["name"], parsed["version"])
                    scope = {}
                    for name in dir(territory_library):
                        if not name.startswith("_"):
                            scope[name] = getattr(territory_library, name)
                    struct = _extract_territory_library_struct(loaded.get("content", "") or "")
                    _, hub_map = materialize_library_namespace(struct, scope, include_builtin=True)
                    for n in selected_names:
                        terr = hub_map.get(n)
                        if terr is not None:
                            try:
                                m.Flag(label=n, value=terr)
                            except Exception:
                                continue
                except Exception:
                    print("[xatra] Warning: failed to load territory library preview from hub path.", file=sys.stderr)
            else:
                for n in selected_names:
                    terr = getattr(territory_library, n, None)
                    if terr is not None:
                        try:
                            m.Flag(label=n, value=terr)
                        except Exception:
                            continue
                
        elif effective_task_type == 'builder':
            if not trusted_user:
                safe_main_elements, safe_main_options = _sanitize_untrusted_builder_payload(
                    getattr(data, "elements", []),
                    getattr(data, "options", {}),
                )
                safe_runtime_elements, safe_runtime_options = _sanitize_untrusted_builder_payload(
                    getattr(data, "runtime_elements", []),
                    getattr(data, "runtime_options", {}),
                )
                setattr(data, "elements", safe_main_elements)
                setattr(data, "options", safe_main_options)
                setattr(data, "runtime_elements", safe_runtime_elements)
                setattr(data, "runtime_options", safe_runtime_options)
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
                 except Exception as e:
                     print(f"[xatra] Warning: invalid zoom value in builder options: {e}", file=sys.stderr)
                 
            if "focus" in data.options and data.options["focus"]:
                 focus = data.options["focus"]
                 if isinstance(focus, list) and len(focus) == 2:
                     try: m.focus(float(focus[0]), float(focus[1]))
                     except Exception as e:
                         print(f"[xatra] Warning: invalid focus value in builder options: {e}", file=sys.stderr)

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

            predefined_namespace = {}
            predefined_code = getattr(data, "predefined_code", "") or ""
            predefined_struct = _extract_territory_library_struct(predefined_code)

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
            register_xatrahub(builder_exec_globals)

            imports_code = getattr(data, "imports_code", "") or ""
            runtime_imports_code = getattr(data, "runtime_imports_code", "") or ""
            theme_code = getattr(data, "theme_code", "") or ""
            runtime_code = getattr(data, "runtime_code", "") or ""
            runtime_theme_code = getattr(data, "runtime_theme_code", "") or ""
            runtime_predefined_code = getattr(data, "runtime_predefined_code", "") or ""
            runtime_imports_effective = "\n\n".join([
                x for x in [runtime_imports_code, runtime_code] if isinstance(x, str) and x.strip()
            ])
            runtime_elements = getattr(data, "runtime_elements", None)
            runtime_options = getattr(data, "runtime_options", None)
            if not isinstance(runtime_elements, list) or not isinstance(runtime_options, dict):
                runtime_for_parse = "\n\n".join([
                    x for x in [runtime_imports_code, runtime_theme_code, runtime_code] if isinstance(x, str) and x.strip()
                ])
                combined_runtime_predef = "\n\n".join([x for x in [predefined_code, runtime_predefined_code] if x.strip()])
                parsed_runtime = parse_code_segment_to_builder_payload(runtime_for_parse, combined_runtime_predef)
                runtime_elements = parsed_runtime.get("elements", [])
                runtime_options = parsed_runtime.get("options", {})
            apply_imports_code_parsed(imports_code, builder_exec_globals)
            if predefined_struct.get("territories"):
                _, predefined_namespace = materialize_library_namespace(predefined_struct, builder_exec_globals, include_builtin=True)
                if predefined_namespace:
                    builder_exec_globals.update(predefined_namespace)
            # Also materialize runtime_predefined_code into exec globals if provided
            if runtime_predefined_code.strip():
                runtime_predef_struct = _extract_territory_library_struct(runtime_predefined_code)
                if runtime_predef_struct.get("territories"):
                    try:
                        _, runtime_predef_ns = materialize_library_namespace(runtime_predef_struct, builder_exec_globals, include_builtin=True)
                        if runtime_predef_ns:
                            builder_exec_globals.update(runtime_predef_ns)
                    except Exception:
                        pass
            # Apply theme_code only as a fallback: if data.options already has theme settings
            # (basemaps, css_rules, etc.), those were already applied above and theme_code would
            # cause duplication. Only apply theme_code when options has no theme content.
            _opts = getattr(data, "options", {}) or {}
            _options_has_theme = bool(
                _opts.get("basemaps") or _opts.get("css_rules") or
                _opts.get("flag_color_sequences") or _opts.get("admin_color_sequences") or
                _opts.get("data_colormap")
            )
            if theme_code.strip() and not _options_has_theme:
                apply_theme_options(_parse_theme_code_to_options(theme_code))
            if isinstance(runtime_options, dict):
                if "zoom" in runtime_options and runtime_options["zoom"] is not None:
                    try:
                        m.zoom(int(runtime_options["zoom"]))
                    except Exception as e:
                        print(f"[xatra] Warning: invalid runtime zoom value: {e}", file=sys.stderr)
                if "focus" in runtime_options and runtime_options["focus"]:
                    focus = runtime_options["focus"]
                    if isinstance(focus, list) and len(focus) == 2:
                        try:
                            m.focus(float(focus[0]), float(focus[1]))
                        except Exception as e:
                            print(f"[xatra] Warning: invalid runtime focus value: {e}", file=sys.stderr)
                if "slider" in runtime_options:
                    sl = runtime_options["slider"]
                    if isinstance(sl, dict):
                        start = sl.get("start")
                        end = sl.get("end")
                        speed = sl.get("speed")
                        if isinstance(start, str) and start.strip():
                            try: start = int(start)
                            except: start = None
                        elif isinstance(start, str):
                            start = None
                        if isinstance(end, str) and end.strip():
                            try: end = int(end)
                            except: end = None
                        elif isinstance(end, str):
                            end = None
                        if start is not None or end is not None:
                            m.slider(start=start, end=end, speed=speed if speed else 5.0)
                apply_theme_options(_normalize_theme_options_struct(runtime_options))
            # Apply runtime_theme_code as fallback if runtime_options has no theme content
            _runtime_options_has_theme = bool(
                runtime_options.get("basemaps") or runtime_options.get("css_rules") or
                runtime_options.get("flag_color_sequences") or runtime_options.get("admin_color_sequences") or
                runtime_options.get("data_colormap")
            ) if isinstance(runtime_options, dict) else False
            if runtime_theme_code.strip() and not _runtime_options_has_theme:
                apply_theme_options(_parse_theme_code_to_options(runtime_theme_code))

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

            def _apply_builder_elements(elements_list: Any):
                if not isinstance(elements_list, list):
                    return
                for el in elements_list:
                    if isinstance(el, dict):
                        el_type = el.get("type")
                        el_label = el.get("label")
                        el_value = el.get("value")
                        el_args = el.get("args")
                    else:
                        el_type = getattr(el, "type", None)
                        el_label = getattr(el, "label", None)
                        el_value = getattr(el, "value", None)
                        el_args = getattr(el, "args", None)
                    if not isinstance(el_type, str) or not el_type:
                        continue
                    args = resolve_builder_value(dict(el_args), builder_exec_globals) if isinstance(el_args, dict) else {}
                    resolved_label = resolve_builder_value(el_label, builder_exec_globals)
                    if resolved_label not in (None, ""):
                        args["label"] = resolved_label
                    args = _clean_builder_args(args)

                    if el_type == "flag":
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

                        if isinstance(el_value, str):
                            territory = xatra.loaders.gadm(el_value)
                        elif isinstance(el_value, list):
                            territory = _eval_parts(el_value) if (len(el_value) > 0 and isinstance(el_value[0], dict)) else None
                            if territory is None and el_value and not isinstance(el_value[0], dict):
                                for code in el_value:
                                    if not isinstance(code, str):
                                        continue
                                    t = xatra.loaders.gadm(code)
                                    territory = t if territory is None else (territory | t)
                        else:
                            continue
                        m.Flag(value=territory, **args)

                    elif el_type == "river":
                        source_type = args.get("source_type", "naturalearth")
                        if "source_type" in args:
                            del args["source_type"]
                        river_value = resolve_builder_value(el_value, builder_exec_globals)
                        if river_value is not None:
                            if source_type == "overpass":
                                geom = xatra.loaders.overpass(river_value)
                            else:
                                geom = xatra.loaders.naturalearth(river_value)
                            m.River(value=geom, **args)

                    elif el_type == "point":
                        pos = resolve_builder_value(el_value, builder_exec_globals)
                        if isinstance(pos, str):
                            pos = _json_parse(pos, pos)
                        icon_arg = args.pop("icon", None)
                        if icon_arg is not None and icon_arg != "":
                            try:
                                if isinstance(icon_arg, str):
                                    # Backward compatibility: legacy string icon means builtin marker filename
                                    args["icon"] = Icon.builtin(icon_arg)
                                elif isinstance(icon_arg, dict):
                                    icon_type = str(icon_arg.get("type") or "").strip().lower()
                                    if icon_type == "builtin" or (not icon_type and "name" in icon_arg and "shape" not in icon_arg and "icon_url" not in icon_arg and "iconUrl" not in icon_arg):
                                        name = icon_arg.get("name") or ""
                                        if name:
                                            icon_kwargs = {}
                                            if icon_arg.get("icon_size") is not None:
                                                icon_kwargs["icon_size"] = icon_arg.get("icon_size")
                                            if icon_arg.get("icon_anchor") is not None:
                                                icon_kwargs["icon_anchor"] = icon_arg.get("icon_anchor")
                                            if icon_arg.get("popup_anchor") is not None:
                                                icon_kwargs["popup_anchor"] = icon_arg.get("popup_anchor")
                                            args["icon"] = Icon.builtin(name, **icon_kwargs)
                                    elif icon_type == "bootstrap":
                                        name = icon_arg.get("name") or ""
                                        if name:
                                            bootstrap_kwargs = {}
                                            if icon_arg.get("version"):
                                                bootstrap_kwargs["version"] = icon_arg.get("version")
                                            if icon_arg.get("base_url"):
                                                bootstrap_kwargs["base_url"] = icon_arg.get("base_url")
                                            if icon_arg.get("icon_size") is not None:
                                                bootstrap_kwargs["icon_size"] = icon_arg.get("icon_size")
                                            if icon_arg.get("icon_anchor") is not None:
                                                bootstrap_kwargs["icon_anchor"] = icon_arg.get("icon_anchor")
                                            if icon_arg.get("popup_anchor") is not None:
                                                bootstrap_kwargs["popup_anchor"] = icon_arg.get("popup_anchor")
                                            args["icon"] = Icon.bootstrap(name, **bootstrap_kwargs)
                                    elif icon_type == "geometric" or "shape" in icon_arg:
                                        geo_kwargs = {
                                            "color": icon_arg.get("color", "#3388ff"),
                                            "size": int(icon_arg.get("size", 24)),
                                            "border_color": icon_arg.get("border_color"),
                                            "border_width": int(icon_arg.get("border_width", 0)),
                                        }
                                        if icon_arg.get("icon_size") is not None:
                                            geo_kwargs["icon_size"] = icon_arg.get("icon_size")
                                        if icon_arg.get("icon_anchor") is not None:
                                            geo_kwargs["icon_anchor"] = icon_arg.get("icon_anchor")
                                        if icon_arg.get("popup_anchor") is not None:
                                            geo_kwargs["popup_anchor"] = icon_arg.get("popup_anchor")
                                        args["icon"] = Icon.geometric(icon_arg.get("shape", "circle"), **geo_kwargs)
                                    elif icon_type == "url" or "icon_url" in icon_arg or "iconUrl" in icon_arg:
                                        url = icon_arg.get("icon_url") or icon_arg.get("iconUrl")
                                        icon_kwargs = {"icon_url": url}
                                        if icon_arg.get("shadow_url") is not None:
                                            icon_kwargs["shadow_url"] = icon_arg.get("shadow_url")
                                        if icon_arg.get("icon_size") is not None:
                                            icon_kwargs["icon_size"] = tuple(icon_arg.get("icon_size"))
                                        elif icon_arg.get("iconSize") is not None:
                                            icon_kwargs["icon_size"] = tuple(icon_arg.get("iconSize"))
                                        if icon_arg.get("icon_anchor") is not None:
                                            icon_kwargs["icon_anchor"] = tuple(icon_arg.get("icon_anchor"))
                                        elif icon_arg.get("iconAnchor") is not None:
                                            icon_kwargs["icon_anchor"] = tuple(icon_arg.get("iconAnchor"))
                                        if icon_arg.get("popup_anchor") is not None:
                                            icon_kwargs["popup_anchor"] = tuple(icon_arg.get("popup_anchor"))
                                        args["icon"] = Icon(**icon_kwargs)
                                else:
                                    args["icon"] = icon_arg
                            except Exception:
                                pass
                        m.Point(position=pos, **args)

                    elif el_type == "text":
                        pos = resolve_builder_value(el_value, builder_exec_globals)
                        if isinstance(pos, str):
                            try:
                                pos = json.loads(pos)
                            except Exception:
                                pass
                        m.Text(position=pos, **args)

                    elif el_type == "path":
                        val = resolve_builder_value(el_value, builder_exec_globals)
                        if isinstance(val, str):
                            try:
                                val = json.loads(val)
                            except Exception:
                                pass
                        m.Path(value=val, **args)

                    elif el_type == "admin":
                        if "label" in args:
                            del args["label"]
                        m.Admin(gadm=resolve_builder_value(el_value, builder_exec_globals), **args)

                    elif el_type == "admin_rivers":
                        if "label" in args:
                            del args["label"]
                        sources = resolve_builder_value(el_value, builder_exec_globals)
                        if isinstance(sources, str):
                            try:
                                sources = json.loads(sources)
                            except Exception:
                                sources = [sources]
                        m.AdminRivers(sources=sources, **args)

                    elif el_type == "dataframe":
                        import pandas as pd
                        import io
                        val = resolve_builder_value(el_value, builder_exec_globals)
                        if isinstance(val, str):
                            df = pd.read_csv(io.StringIO(val))
                            if "label" in args:
                                del args["label"]
                            if args.get("data_column") in (None, ""):
                                args.pop("data_column", None)
                            if args.get("year_columns") in (None, [], ""):
                                args.pop("year_columns", None)
                            m.Dataframe(df, **args)
                        elif val is not None:
                            if "label" in args:
                                del args["label"]
                            if args.get("data_column") in (None, ""):
                                args.pop("data_column", None)
                            if args.get("year_columns") in (None, [], ""):
                                args.pop("year_columns", None)
                            m.Dataframe(val, **args)
                    elif el_type == "titlebox":
                        if "label" in args:
                            del args["label"]
                        title_val = resolve_builder_value(el_value, builder_exec_globals)
                        html = title_val if isinstance(title_val, str) else str(title_val or "")
                        m.TitleBox(html, **args)
                    elif el_type == "music":
                        music_val = resolve_builder_value(el_value, builder_exec_globals)
                        if "label" in args:
                            del args["label"]
                        if "filename" in args:
                            del args["filename"]
                        music_path = materialize_music_path(music_val)
                        if music_path not in (None, ""):
                            m.Music(path=music_path, **args)
                    elif el_type == "python":
                        code_line = el_value if isinstance(el_value, str) else str(el_value or "")
                        if code_line.strip():
                            exec(code_line, builder_exec_globals)

            def _flush_pending_import_elements():
                nonlocal pending_import_elements
                if pending_import_elements:
                    _apply_builder_elements(pending_import_elements)
                    pending_import_elements = []

            _flush_pending_import_elements()
            _apply_builder_elements(data.elements)
            if runtime_imports_effective.strip():
                apply_imports_code_parsed(runtime_imports_effective, builder_exec_globals)
            _flush_pending_import_elements()
            _apply_builder_elements(runtime_elements)

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

def _request_actor_key(request: Request) -> Tuple[str, str]:
    ip = (request.client.host if request.client else "unknown")
    conn = _hub_db_conn()
    try:
        user = _request_user(conn, request)
        if user is not None:
            actor = f"user:{int(user['id'])}"
            return actor, actor
        guest_id = request.cookies.get(GUEST_COOKIE)
        if guest_id and guest_id.strip():
            actor = f"guest:{guest_id.strip()}"
            return actor, actor
        # Fallback: isolate unauthenticated/no-cookie render jobs by IP.
        actor = f"ip:{ip}"
        return actor, actor
    finally:
        conn.close()


def _terminate_process(proc: Optional[multiprocessing.Process], timeout: float = 3.0) -> None:
    if proc is None:
        return
    try:
        alive = proc.is_alive()
    except Exception:
        return
    if alive:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.join(timeout=timeout)
    except Exception:
        pass
    try:
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
    except Exception:
        pass


def _hub_render_dependency_epoch() -> str:
    conn = _hub_db_conn()
    try:
        row = conn.execute(
            """
            SELECT
                COALESCE((SELECT MAX(updated_at) FROM hub_artifacts), '') AS artifact_epoch,
                COALESCE((SELECT MAX(created_at) FROM hub_artifact_versions), '') AS version_epoch
            """
        ).fetchone()
        return f"{row['artifact_epoch']}|{row['version_epoch']}"
    finally:
        conn.close()


def _enforce_render_rate_limit(task_type: str, actor_key: str) -> None:
    # Picker is cheap and often frequent; code/builder renders are heavier.
    limits = {
        "picker": (180, 60),
        "territory_library": (90, 60),
        "code": (60, 60),
        "builder": (60, 60),
    }
    limit, window = limits.get(task_type, (20, 60))
    _check_rate_limit(
        f"render:{task_type}:{actor_key}",
        limit=limit,
        window_seconds=window,
        label=f"Render rate limit reached for '{task_type}' previews.",
    )


def run_in_process(task_type, data, actor_key: str):
    cache_key = None
    try:
        payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        cache_key = f"{task_type}:{json.dumps(payload, sort_keys=True, default=str)}:hub={_hub_render_dependency_epoch()}"
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
    slot_key = f"{actor_key}:{task_type}"
    previous_to_join: Optional[multiprocessing.Process] = None

    # Kill any previous process and register+start the new one atomically inside the lock
    # to prevent a race window where another thread could see a registered-but-not-started
    # process and incorrectly terminate it.
    with process_lock:
        previous = current_processes.get(slot_key)
        if previous and previous.is_alive():
            previous.terminate()
            previous_to_join = previous
        current_processes[slot_key] = p
        p.start()
    if previous_to_join is not None:
        _terminate_process(previous_to_join, timeout=3.0)
    
    result = {"error": "Rendering process timed out or crashed"}
    try:
        # Get result from queue with a timeout (60s)
        # IMPORTANT: Read from queue BEFORE join() to avoid deadlocks with large data
        result = queue.get(timeout=60)
    except Exception as e:
        result = {"error": f"Rendering failed: {str(e)}"}
    
    _terminate_process(p, timeout=5.0)
        
    with process_lock:
        if current_processes.get(slot_key) is p:
            current_processes.pop(slot_key, None)

    if cache_key and isinstance(result, dict) and "error" not in result:
        with render_cache_lock:
            render_cache[cache_key] = result
            render_cache.move_to_end(cache_key)
            while len(render_cache) > RENDER_CACHE_MAX_ENTRIES:
                render_cache.popitem(last=False)

    return result

@app.post("/render/picker")
def render_picker(request: PickerRequest, http_request: Request):
    actor_key, rate_key = _request_actor_key(http_request)
    _enforce_render_rate_limit("picker", rate_key)
    result = run_in_process('picker', request, actor_key)
    if "error" in result:
        return result
    return result

@app.post("/render/territory-library")
def render_territory_library(request: TerritoryLibraryRequest, http_request: Request):
    _enforce_python_input_limits(request.predefined_code or "", "predefined_code")
    actor_key, rate_key = _request_actor_key(http_request)
    _enforce_render_rate_limit("territory_library", rate_key)
    result = run_in_process('territory_library', request, actor_key)
    if "error" in result:
        return result
    return result

@app.post("/render/code")
def render_code(request: CodeRequest, http_request: Request):
    _enforce_python_input_limits(request.code or "", "code")
    _enforce_python_input_limits(request.predefined_code or "", "predefined_code")
    _enforce_python_input_limits(request.imports_code or "", "imports_code")
    _enforce_python_input_limits(request.runtime_imports_code or "", "runtime_imports_code")
    _enforce_python_input_limits(request.theme_code or "", "theme_code")
    _enforce_python_input_limits(request.runtime_code or "", "runtime_code")
    _enforce_python_input_limits(request.runtime_theme_code or "", "runtime_theme_code")
    _enforce_python_input_limits(request.runtime_predefined_code or "", "runtime_predefined_code")
    conn = _hub_db_conn()
    try:
        request.trusted_user = _is_user_trusted(_request_user(conn, http_request))
    finally:
        conn.close()
    actor_key, rate_key = _request_actor_key(http_request)
    _enforce_render_rate_limit("code", rate_key)
    result = run_in_process('code', request, actor_key)
    if "error" in result:
        return result
    return result

@app.post("/render/builder")
def render_builder(request: BuilderRequest, http_request: Request):
    _enforce_python_input_limits(request.predefined_code or "", "predefined_code")
    _enforce_python_input_limits(request.imports_code or "", "imports_code")
    _enforce_python_input_limits(request.runtime_imports_code or "", "runtime_imports_code")
    _enforce_python_input_limits(request.theme_code or "", "theme_code")
    _enforce_python_input_limits(request.runtime_code or "", "runtime_code")
    _enforce_python_input_limits(request.runtime_theme_code or "", "runtime_theme_code")
    _enforce_python_input_limits(request.runtime_predefined_code or "", "runtime_predefined_code")
    conn = _hub_db_conn()
    try:
        request.trusted_user = _is_user_trusted(_request_user(conn, http_request))
    finally:
        conn.close()
    actor_key, rate_key = _request_actor_key(http_request)
    _enforce_render_rate_limit("builder", rate_key)
    result = run_in_process('builder', request, actor_key)
    if "error" in result:
        return result
    return result


@app.get("/{username}/{kind}/{name}/{version}")
def public_hub_artifact_version(username: str, kind: str, name: str, version: str, http_request: Request):
    return hub_get_artifact_version(username=username, kind=kind, name=name, version=version, http_request=http_request)


@app.get("/{username}/{kind}/{name}")
def public_hub_artifact_alpha(username: str, kind: str, name: str, http_request: Request):
    return hub_get_artifact_version(username=username, kind=kind, name=name, version="alpha", http_request=http_request)

@app.on_event("startup")
def _startup_populate_builder_elements():
    """Populate project.elements and project.options for seeded artifacts that are missing them."""
    try:
        conn = _hub_db_conn()
        try:
            user_row = conn.execute("SELECT id FROM hub_users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
            if user_row is not None:
                _seed_xatra_lib_artifacts(
                    conn,
                    user_row["id"],
                    _utc_now_iso(),
                    force=False,
                    code_to_builder_fn=sync_code_to_builder,
                    parse_theme_fn=_parse_theme_code_to_options,
                )
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[xatra] Warning: startup element seeding failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    import uvicorn
    # Use spawn for multiprocessing compatibility
    multiprocessing.set_start_method('spawn')
    uvicorn.run(
        app,
        host=os.environ.get("XATRA_BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("XATRA_BACKEND_PORT", "8088")),
    )
