"""
Database backup manager for WompBot

Handles automatic PostgreSQL backups with rotation and per-guild support.
Backups are stored outside the repository to protect personal data.
"""
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages PostgreSQL database backups"""

    def __init__(self, backup_dir: str = "/backups"):
        """
        Initialize backup manager

        Args:
            backup_dir: Directory to store backups (outside repository)
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Database connection info
        self.db_host = os.getenv('DB_HOST', 'postgres')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME', 'discord_bot')
        self.db_user = os.getenv('DB_USER', 'botuser')
        self.db_password = os.getenv('DB_PASSWORD')

        # Backup settings
        self.max_backups = int(os.getenv('MAX_BACKUPS', '30'))  # Keep last 30 backups
        self.backup_interval = timedelta(hours=int(os.getenv('BACKUP_INTERVAL_HOURS', '6')))  # Backup every 6 hours

        logger.info(f"Backup manager initialized: dir={backup_dir}, max_backups={self.max_backups}")

    def create_backup(self, guild_id: Optional[int] = None) -> Optional[Path]:
        """
        Create a database backup

        Args:
            guild_id: If provided, backup only this guild's schema.
                     If None, backup entire database.

        Returns:
            Path to backup file, or None if backup failed
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

        if guild_id:
            # Per-guild backup (backup specific schema)
            backup_file = self.backup_dir / f"guild_{guild_id}_{timestamp}.sql"
            schema_name = f"guild_{guild_id}"
            logger.info(f"Creating backup for guild {guild_id} (schema={schema_name})")
        else:
            # Full database backup
            backup_file = self.backup_dir / f"full_{timestamp}.sql"
            schema_name = None
            logger.info("Creating full database backup")

        try:
            # Build pg_dump command
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password

            cmd = [
                'pg_dump',
                '-h', self.db_host,
                '-p', self.db_port,
                '-U', self.db_user,
                '-d', self.db_name,
                '--no-password',
                '--format=plain',
                '--encoding=UTF8',
            ]

            # Add schema filter if backing up specific guild
            if schema_name:
                cmd.extend(['--schema', schema_name])

            # Add output file
            cmd.extend(['-f', str(backup_file)])

            # Execute pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                logger.info(f"✓ Backup created: {backup_file.name} ({size_mb:.2f} MB)")
                return backup_file
            else:
                logger.error(f"✗ Backup failed: {result.stderr}")
                if backup_file.exists():
                    backup_file.unlink()  # Clean up failed backup
                return None

        except subprocess.TimeoutExpired:
            logger.error("✗ Backup timed out after 5 minutes")
            if backup_file.exists():
                backup_file.unlink()
            return None
        except Exception as e:
            logger.error(f"✗ Backup error: {e}", exc_info=True)
            if backup_file.exists():
                backup_file.unlink()
            return None

    def restore_backup(self, backup_file: Path, guild_id: Optional[int] = None) -> bool:
        """
        Restore a database backup

        Args:
            backup_file: Path to backup file
            guild_id: If provided, restore to specific guild schema

        Returns:
            True if restore succeeded, False otherwise
        """
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False

        logger.warning(f"Restoring backup: {backup_file}")

        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password

            cmd = [
                'psql',
                '-h', self.db_host,
                '-p', self.db_port,
                '-U', self.db_user,
                '-d', self.db_name,
                '-f', str(backup_file)
            ]

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode == 0:
                logger.info(f"✓ Backup restored successfully")
                return True
            else:
                logger.error(f"✗ Restore failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"✗ Restore error: {e}", exc_info=True)
            return False

    def cleanup_old_backups(self, guild_id: Optional[int] = None):
        """
        Remove old backups, keeping only the most recent ones

        Args:
            guild_id: If provided, clean up backups for specific guild
        """
        pattern = f"guild_{guild_id}_*.sql" if guild_id else "*.sql"
        backups = sorted(self.backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

        if len(backups) > self.max_backups:
            old_backups = backups[self.max_backups:]
            for backup in old_backups:
                try:
                    size_mb = backup.stat().st_size / (1024 * 1024)
                    backup.unlink()
                    logger.info(f"Removed old backup: {backup.name} ({size_mb:.2f} MB)")
                except Exception as e:
                    logger.error(f"Failed to remove old backup {backup.name}: {e}")

    def list_backups(self, guild_id: Optional[int] = None) -> List[tuple]:
        """
        List available backups

        Args:
            guild_id: If provided, list backups for specific guild

        Returns:
            List of (filepath, size_mb, timestamp) tuples
        """
        pattern = f"guild_{guild_id}_*.sql" if guild_id else "*.sql"
        backups = []

        for backup_file in self.backup_dir.glob(pattern):
            size_mb = backup_file.stat().st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc)
            backups.append((backup_file, size_mb, mtime))

        return sorted(backups, key=lambda x: x[2], reverse=True)

    def auto_backup(self, guild_id: Optional[int] = None) -> Optional[Path]:
        """
        Perform automatic backup if interval has passed

        Args:
            guild_id: If provided, backup specific guild

        Returns:
            Path to backup file if created, None otherwise
        """
        # Check if we need a backup
        pattern = f"guild_{guild_id}_*.sql" if guild_id else "full_*.sql"
        recent_backups = sorted(
            self.backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if recent_backups:
            last_backup_time = datetime.fromtimestamp(
                recent_backups[0].stat().st_mtime,
                tz=timezone.utc
            )
            time_since_backup = datetime.now(timezone.utc) - last_backup_time

            if time_since_backup < self.backup_interval:
                logger.debug(f"Skipping backup, last backup was {time_since_backup} ago")
                return None

        # Create backup
        backup_file = self.create_backup(guild_id)

        # Cleanup old backups
        if backup_file:
            self.cleanup_old_backups(guild_id)

        return backup_file
