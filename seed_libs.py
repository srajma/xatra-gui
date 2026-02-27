#!/usr/bin/env python3
"""
Seed hub artifacts from xatra_lib/ directory.

Creates map artifacts for each file in xatra_lib/map/ and creates both lib
and map artifacts for each file in xatra_lib/lib/. The Custom Theme section of
every created artifact is pre-filled with xatra_lib/default_theme.py contents.

Usage:
    uv run seed_libs.py            # skip existing artifacts
    uv run seed_libs.py --force    # overwrite existing alpha content
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import (
    _hub_db_conn,
    _seed_xatra_lib_artifacts,
    _utc_now_iso,
    ADMIN_USERNAME,
    sync_code_to_builder,
)


def main():
    parser = argparse.ArgumentParser(description="Seed xatra_lib artifacts into the hub database.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing alpha content")
    args = parser.parse_args()

    conn = _hub_db_conn()
    try:
        user_row = conn.execute("SELECT id FROM hub_users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        if user_row is None:
            print(f"[seed_libs] Admin user '{ADMIN_USERNAME}' not found in database. Run the server first to initialise it.", file=sys.stderr)
            sys.exit(1)
        now = _utc_now_iso()
        _seed_xatra_lib_artifacts(conn, user_row["id"], now, force=args.force, code_to_builder_fn=sync_code_to_builder)
        conn.commit()
        print("[seed_libs] Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
