import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run_migrations(conn, migrations_dir="migrations"):
    migrations_path = Path(migrations_dir)
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

    files = sorted(migrations_path.glob("*.sql")) if migrations_path.exists() else []

    try:
        if not files:
            logger.info(f"No migrations found in {migrations_dir}")
            return
        for f in files:
            version = f.name
            if version in applied:
                logger.info(f"Migration already applied: {version}")
                continue

            raw_sql = f.read_text(encoding="utf-8")
            sql = raw_sql.strip()
            logger.info(f"Applying migration {version}")

            if not sql:
                logger.info(f"Empty migration file: {version}")
                cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (version,))
                conn.commit()
                continue

            lines = [
                line for line in sql.splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            if not lines:
                logger.info(f"Empty migration file: {version}")
                cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (version,))
                conn.commit()
                continue

            cur.execute(raw_sql)
            cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (version,))
            conn.commit()

        logger.info("Migrations finished")

    finally:
        cur.execute("SELECT pg_advisory_unlock(987654321);")
        conn.commit()
        cur.close()