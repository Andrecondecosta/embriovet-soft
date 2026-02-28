from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple


MIGRATION_RE = re.compile(r"^(\d{3})_.*\.sql$")


def _list_migration_files(migrations_dir: str) -> List[Tuple[str, Path]]:
    base = Path(migrations_dir)
    if not base.exists():
        return []
    items: List[Tuple[str, Path]] = []
    for p in base.iterdir():
        if not p.is_file():
            continue
        m = MIGRATION_RE.match(p.name)
        if not m:
            continue
        version = m.group(1)
        items.append((version, p))
    items.sort(key=lambda t: int(t[0]))
    return items


def _ensure_schema_migrations(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


def _already_applied(cur) -> set[str]:
    cur.execute("SELECT version FROM schema_migrations;")
    rows = cur.fetchall()
    return {r[0] for r in rows}


def _acquire_lock(cur) -> None:
    cur.execute("SELECT pg_advisory_lock(987654321);")


def _release_lock(cur) -> None:
    cur.execute("SELECT pg_advisory_unlock(987654321);")


def apply_migrations(conn, migrations_dir: str) -> dict:
    summary = {"applied": [], "skipped": [], "errors": []}

    files = _list_migration_files(migrations_dir)
    if not files:
        summary["skipped"].append(f"(no migrations found in {migrations_dir})")
        return summary

    cur = conn.cursor()
    try:
        _acquire_lock(cur)
        _ensure_schema_migrations(cur)
        applied = _already_applied(cur)

        for version, path in files:
            if version in applied:
                summary["skipped"].append(path.name)
                continue

            sql = path.read_text(encoding="utf-8").strip()

            if sql:
                cur.execute(sql)

            cur.execute(
                "INSERT INTO schema_migrations(version, filename) VALUES (%s, %s);",
                (version, path.name),
            )

            summary["applied"].append(path.name)

        conn.commit()
        return summary

    except Exception as e:
        conn.rollback()
        summary["errors"].append(str(e))
        raise

    finally:
        try:
            _release_lock(cur)
        except Exception:
            pass
        cur.close()