#!/usr/bin/env python3
"""Merge travel formal plans from local backend DB into Docker backend DB."""

from __future__ import annotations

import base64
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DB = ROOT / "backend" / "myai_studio.db"
DOCKER_CONTAINER = "my-ai-studio-backend-1"


def main() -> int:
    if not LOCAL_DB.exists():
        print(f"Local database not found: {LOCAL_DB}", file=sys.stderr)
        return 1

    local = sqlite3.connect(LOCAL_DB)
    rows = local.execute(
        "SELECT id, description FROM sessions "
        "WHERE description LIKE '%travel_formal_plan%'"
    ).fetchall()
    local.close()

    if not rows:
        print("No formal travel plans found in local database.")
        return 0

    merged = 0
    skipped = 0
    for session_id, description in rows:
        payload = base64.b64encode(description.encode("utf-8")).decode("ascii")
        script = f"""
import base64
import sqlite3

session_id = {session_id!r}
description = base64.b64decode({payload!r}).decode("utf-8")
conn = sqlite3.connect("/app/data/myai_studio.db")
row = conn.execute("SELECT description FROM sessions WHERE id=?", (session_id,)).fetchone()
if not row:
    print("skip-missing")
elif row[0] and "travel_formal_plan" in row[0]:
    print("skip-existing")
else:
    conn.execute("UPDATE sessions SET description=? WHERE id=?", (description, session_id))
    conn.commit()
    print("merged")
conn.close()
"""
        result = subprocess.run(
            ["docker", "exec", "-i", DOCKER_CONTAINER, "python3"],
            input=script.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            print(result.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
            return result.returncode

        status = result.stdout.decode("utf-8", errors="replace").strip().splitlines()[-1]
        if status == "merged":
            merged += 1
            print(f"merged {session_id}")
        else:
            skipped += 1
            print(f"{status} {session_id}")

    print(f"Done. merged={merged}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
