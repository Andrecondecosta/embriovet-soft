import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
    if not files:
        logger.info("No migrations found")
        return

    try:
        for f in files:
            version = f.name
            if version in applied:
                logger.info(f"Migration already applied: {version}")
                continue

            sql = f.read_text(encoding="utf-8").strip()
            if not sql:
                cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (version,))
                conn.commit()
                continue

            try:
                logger.info(f"Applying migration {version}")
                cur.execute("BEGIN;")
                cur.execute(sql)
                cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (version,))
                cur.execute("COMMIT;")
                conn.commit()
            except Exception:
                cur.execute("ROLLBACK;")
                conn.rollback()
                raise
        logger.info("Migrations finished")
    finally:
        try:
            cur.execute("SELECT pg_advisory_unlock(987654321);")
        except Exception:
            pass
        cur.close()