from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple


MIGRATION_RE = re.compile(r"^(\d{3})_.*\.sql$")


def _list_migration_files(migrations_dir: str) -> List[Tuple[str, str, Path]]:
    base = Path(migrations_dir)
    if not base.exists():
        return []
    items: List[Tuple[str, str, Path]] = []
    for p in base.iterdir():
        if not p.is_file():
            continue
        m = MIGRATION_RE.match(p.name)
        if not m:
            continue
        order = m.group(1)
        migration_id = p.name
        items.append((order, migration_id, p))
    items.sort(key=lambda t: (int(t[0]), t[1]))
    return items


def _ensure_schema_migrations(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    # Backward/forward compatibility:
    # - Old deployments can have schema_migrations without filename.
    # - We add filename lazily and keep it nullable so legacy rows remain valid.
    cur.execute("ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS filename TEXT;")


def _already_applied(cur) -> set[str]:
    cur.execute("SELECT version, filename FROM schema_migrations;")
    rows = cur.fetchall()
    applied: set[str] = set()
    for version, filename in rows:
        if version:
            applied.add(version)
        if filename:
            applied.add(filename)
    return applied


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

        for _order, migration_id, path in files:
            if migration_id in applied:
                summary["skipped"].append(path.name)
                continue

            sql = path.read_text(encoding="utf-8").strip()

            if sql:
                cur.execute(sql)

            cur.execute(
                "INSERT INTO schema_migrations(version, filename) VALUES (%s, %s);",
                (migration_id, path.name),
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
