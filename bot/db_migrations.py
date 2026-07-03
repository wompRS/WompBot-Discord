"""
Lightweight forward-migration runner for WompBot.

Applies `bot/migrations/*.sql` files that have not yet been recorded in the
`schema_migrations` table, in filename order. Every migration file uses idempotent
DDL (CREATE TABLE/INDEX ... IF NOT EXISTS), so re-running an already-applied
migration is a no-op. That makes this safe on BOTH a fresh database and an existing
populated one, and it fixes the long-standing gap where migrations only ran on a
fresh Postgres initdb volume (so tables like iracing_participation_history never
appeared on upgraded or restored deployments).

To add a migration: drop an ordered, idempotent `NN_name.sql` into bot/migrations/.
It applies automatically on the next bot start.
"""
import os
import logging

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def run_migrations(db, migrations_dir: str = MIGRATIONS_DIR) -> None:
    """Apply any pending migrations. Never raises — a single failing migration is
    logged and skipped (it retries next start) so it can't block bot startup."""
    try:
        files = sorted(f for f in os.listdir(migrations_dir) if f.endswith(".sql"))
    except FileNotFoundError:
        logger.info("No migrations directory at %s; skipping migrations", migrations_dir)
        return

    # Ensure the tracking table exists and read what's already applied.
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename   TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute("SELECT filename FROM schema_migrations")
                applied = {row[0] for row in cur.fetchall()}
    except Exception as e:
        logger.error("Could not initialize schema_migrations table: %s", e, exc_info=True)
        return

    pending = [f for f in files if f not in applied]
    if not pending:
        logger.info("Database migrations up to date (%d applied)", len(applied))
        return

    logger.info("Applying %d pending migration(s): %s", len(pending), ", ".join(pending))
    for filename in pending:
        path = os.path.join(migrations_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                sql = fh.read()
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
                        (filename,),
                    )
            logger.info("Applied migration: %s", filename)
        except Exception as e:
            # Do not record it (so it retries next start) and do not block startup.
            logger.error("Migration %s failed (will retry next start): %s", filename, e, exc_info=True)
