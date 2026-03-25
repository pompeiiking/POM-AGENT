from __future__ import annotations

import re


def build_fts_match_query(raw: str) -> str | None:
    parts = [p for p in re.split(r"\W+", raw.strip()) if p]
    if not parts:
        return None
    out: list[str] = []
    for p in parts[:16]:
        safe = p.replace('"', " ").strip()
        if not safe:
            continue
        out.append('"' + safe + '"')
    if not out:
        return None
    return " OR ".join(out)
