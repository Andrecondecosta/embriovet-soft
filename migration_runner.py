import os
from pathlib import Path


def run_migrations(conn, migrations_dir="/app/migrations"):
    migrations_path = Path(migrations_dir)
    if not migrations_path.exists():
        return

    cur = conn.cursor()

    # advisory lock para evitar concorrência
    cur.execute("SELECT pg_advisory_lock(987654321);")

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ DEFAULT now()
    );
    """
    )
    conn.commit()

    cur.execute("SELECT version FROM schema_migrations;")
    applied = {row[0] for row in cur.fetchall()}

    files = sorted([p for p in migrations_path.glob("*.sql")])

    try:
        for f in files:
            version = f.name
            if version in applied:
                continue

            sql = f.read_text(encoding="utf-8").strip()
            if not sql:
                cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (version,))
                conn.commit()
                continue

            try:
                cur.execute("BEGIN;")
                cur.execute(sql)
                cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (version,))
                cur.execute("COMMIT;")
                conn.commit()
            except Exception:
                cur.execute("ROLLBACK;")
                conn.rollback()
                raise
    finally:
        try:
            cur.execute("SELECT pg_advisory_unlock(987654321);")
        except Exception:
            pass
        cur.close()