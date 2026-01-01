"""
Backup Manager
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging


class BackupManager:
    """Manages backup operations and file storage"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backup_dir = Path(config['backup_dir'])
        self.reports_dir = Path(config['reports_dir'])
        self.logs_dir = Path(config['logs_dir'])
        self.max_backups = config['max_backups']

        # Create directories
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def get_backup_filename(self, hostname: str) -> str:
        """Generate backup filename with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_hostname = self._sanitize_filename(hostname)
        return f"{safe_hostname}_{timestamp}.conf"

    def get_backup_path(self, hostname: str) -> Path:
        """Get full backup path"""
        filename = self.get_backup_filename(hostname)
        return self.backup_dir / filename

    def save_config(self, hostname: str, config: str) -> Optional[Path]:
        """Save configuration to file"""
        filepath = self.get_backup_path(hostname)

        try:
            with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
                f.write(config)

            logging.info(f"Saved configuration: {filepath}")
            return filepath

        except Exception as e:
            logging.error(f"Error saving configuration to {filepath}: {e}")
            return None

    def find_latest_backup(self, hostname: str) -> Optional[Path]:
        """Find the most recent backup for a device"""
        safe_hostname = self._sanitize_filename(hostname)
        pattern = f"{safe_hostname}_*.conf"

        try:
            backups = list(self.backup_dir.glob(pattern))
            if not backups:
                return None

            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x.stat().st_ctime, reverse=True)
            return backups[0]

        except Exception as e:
            logging.error(f"Error finding backups for {hostname}: {e}")
            return None

    def get_device_backups(self, hostname: str) -> List[Path]:
        """Get all backups for a device, sorted by date (newest first)"""
        safe_hostname = self._sanitize_filename(hostname)
        pattern = f"{safe_hostname}_*.conf"

        try:
            backups = list(self.backup_dir.glob(pattern))
            backups.sort(key=lambda x: x.stat().st_ctime, reverse=True)
            return backups
        except Exception:
            return []

    def cleanup_old_backups(self, max_backups: Optional[int] = None):
        """Remove old backup files keeping only max_backups per device"""
        if max_backups is None:
            max_backups = self.max_backups

        # Get all backups and group by device
        all_backups = list(self.backup_dir.glob("*.conf"))
        backups_by_device: Dict[str, List[Path]] = {}

        for backup_file in all_backups:
            # Extract device name from filename
            match = re.match(r'([^_]+)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.conf', backup_file.name)
            if match:
                device = match.group(1)
                if device not in backups_by_device:
                    backups_by_device[device] = []
                backups_by_device[device].append(backup_file)

        # Keep only max_backups per device
        removed_count = 0
        for device, backups in backups_by_device.items():
            if len(backups) > max_backups:
                # Sort by creation time (oldest first)
                backups.sort(key=lambda x: x.stat().st_ctime)

                # Remove oldest backups
                for backup in backups[:-max_backups]:
                    try:
                        backup.unlink()
                        removed_count += 1
                        logging.debug(f"Removed old backup: {backup}")
                    except Exception as e:
                        logging.error(f"Error removing backup {backup}: {e}")

        if removed_count > 0:
            logging.info(f"Cleaned up {removed_count} old backup files")

    def save_summary_report(self, summary_data: Dict[str, Any]) -> Optional[Path]:
        """Save summary report to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"summary_{timestamp}.json"
        filepath = self.reports_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, default=str, ensure_ascii=False)

            logging.info(f"Summary report saved: {filepath}")
            return filepath

        except Exception as e:
            logging.error(f"Error saving summary report: {e}")
            return None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to remove unsafe characters"""
        # Replace unsafe characters with underscore
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename)
        # Remove leading/trailing spaces and dots
        safe_name = safe_name.strip(' .')
        # Limit length
        return safe_name[:100]

    @property
    def backup_count(self) -> int:
        """Count of backup files"""
        try:
            return len(list(self.backup_dir.glob("*.conf")))
        except Exception:
            return 0