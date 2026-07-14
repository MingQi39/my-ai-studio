"""Format sandbox file mtimes for display (container clocks are UTC)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


def format_file_mtime(mtime: float | int) -> str:
    """Convert Unix epoch (UTC) to Asia/Shanghai display string."""
    return datetime.fromtimestamp(mtime, tz=DISPLAY_TZ).strftime("%b %d %H:%M")


def parse_ls_line(line: str) -> dict | None:
    """Parse one `ls -la --time-style=+%s` line into an entry dict."""
    parts = line.split(maxsplit=6)
    if len(parts) < 7:
        return None
    try:
        mtime = int(parts[5])
    except ValueError:
        return None
    return {
        "permissions": parts[0],
        "links": parts[1],
        "owner": parts[2],
        "group": parts[3],
        "size": parts[4],
        "mtime": mtime,
        "name": parts[6],
    }
