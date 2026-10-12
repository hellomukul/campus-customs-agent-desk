"""Append-only audit trail at output/audit_trail.json.

Every entry is appended to the existing file. The trail is never truncated,
rewritten or cleared: `append` reads what is there, adds to the end, and writes
the whole list back through a temporary file so an interrupted write cannot
leave a half-file behind. If the file is ever found corrupt it is moved aside
with a timestamped `.corrupt-*` name rather than deleted.

Entry kinds
    run_start       a top-level request to the team
    agent_start     an agent run begins
    step            one agent-loop step: model text, an MCP tool call, or a
                    tool result, with arguments and return value
    delegation      one agent hands work to another
    delegation_refused   a hand-off blocked by the depth / budget / repeat rules
    agent_end       an agent run finishes, with its structured report
    error           anything that raised
    run_end         the top-level request finishes, with usage totals
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TRAIL_PATH = HERE.parent / "output" / "audit_trail.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load(path: Path) -> list[dict[str, Any]]:
    """Read the existing trail. Never returns a fresh list over live data."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Preserve whatever is there instead of overwriting it.
        backup = path.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json")
        path.rename(backup)
        print(f"[audit] existing trail was not valid JSON; kept it at {backup.name}")
        return []
    if isinstance(data, list):
        return data
    # An older shape, e.g. {"entries": [...]}: keep it as the first element.
    return [data]


def append(entry: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Append one entry to the trail and return it (with seq and timestamp)."""
    path = path or TRAIL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    trail = _load(path)
    stamped = {"seq": len(trail) + 1, "at": _now(), **entry}
    trail.append(stamped)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(trail, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return stamped


def entry_count(path: Path | None = None) -> int:
    return len(_load(path or TRAIL_PATH))
