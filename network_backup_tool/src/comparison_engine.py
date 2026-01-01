"""
Comparison Engine
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from difflib import unified_diff
import logging


class ComparisonEngine:
    """Handles configuration comparison and diff generation"""

    def __init__(self, config: dict, backup_dir: Path, reports_dir: Path):
        self.config = config
        self.backup_dir = backup_dir
        self.reports_dir = reports_dir
        self.context_lines = config.get('context_lines', 3)

    def compare_configs(self, old_config: str, new_config: str,
                        device_type: str = "cisco_ios") -> List[str]:
        """Compare two configurations and return diff lines"""
        if not old_config or not new_config:
            return []

        # Split into lines
        old_lines = old_config.split('\n')
        new_lines = new_config.split('\n')

        # Generate unified diff
        diff = list(unified_diff(
            old_lines,
            new_lines,
            fromfile='Old Config',
            tofile='New Config',
            lineterm='',
            n=self.context_lines
        ))

        return diff

    def compare_files(self, old_file: Path, new_file: Path,
                      device_type: str = "cisco_ios") -> Optional[List[str]]:
        """Compare two configuration files"""
        try:
            with open(old_file, 'r', encoding='utf-8') as f:
                old_config = f.read()

            with open(new_file, 'r', encoding='utf-8') as f:
                new_config = f.read()

            return self.compare_configs(old_config, new_config, device_type)

        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")
        except Exception as e:
            logging.error(f"Error comparing files: {e}")

        return None

    def generate_diff_report(self, diff_lines: List[str],
                             hostname: str,
                             old_file: Optional[Path] = None,
                             new_file: Optional[Path] = None) -> Optional[Path]:
        """Generate and save diff report"""
        if not diff_lines:
            return None

        # Add header information
        report_lines = []
        report_lines.append(f"Configuration Change Report")
        report_lines.append(f"Device: {hostname}")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if old_file and new_file:
            report_lines.append(f"Old Config: {old_file.name}")
            report_lines.append(f"New Config: {new_file.name}")

        report_lines.append("=" * 60)
        report_lines.append("")

        # Add diff lines
        report_lines.extend(diff_lines)

        # Count changes
        added = sum(1 for line in diff_lines if line.startswith('+')
                    and not line.startswith('+++'))
        removed = sum(1 for line in diff_lines if line.startswith('-')
                      and not line.startswith('---'))

        report_lines.append("")
        report_lines.append("=" * 60)
        report_lines.append(f"Summary: +{added} lines added, -{removed} lines removed")

        # Save report
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_hostname = self._sanitize_filename(hostname)
        filename = f"CHANGES_{safe_hostname}_{timestamp}.diff"
        filepath = self.reports_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n'.join(report_lines))

            logging.info(f"Diff report saved: {filepath}")
            logging.info(f"Changes: +{added} lines, -{removed} lines")
            return filepath

        except Exception as e:
            logging.error(f"Error saving diff report: {e}")
            return None

    def has_significant_changes(self, diff_lines: List[str]) -> bool:
        """Check if diff contains significant changes (not just timestamps)"""
        if not diff_lines:
            return False

        # Patterns that indicate insignificant changes
        insignificant_patterns = [
            r'^--- Old Config$',
            r'^\+\+\+ New Config$',
            r'^@@ .+ @@$',
            r'^! Time:',
            r'^! Last configuration change',
            r'^! NVRAM config last updated',
            r'^## Last commit:',
        ]

        significant_lines = 0

        for line in diff_lines:
            if line.startswith('+') and not line.startswith('+++'):
                # Check if this is an insignificant addition
                if not any(re.match(pattern, line[1:].strip()) for pattern in insignificant_patterns):
                    significant_lines += 1
            elif line.startswith('-') and not line.startswith('---'):
                # Check if this is an insignificant deletion
                if not any(re.match(pattern, line[1:].strip()) for pattern in insignificant_patterns):
                    significant_lines += 1

        return significant_lines > 0

    def get_change_statistics(self, diff_lines: List[str]) -> Tuple[int, int]:
        """Get statistics about changes"""
        added = sum(1 for line in diff_lines if line.startswith('+')
                    and not line.startswith('+++'))
        removed = sum(1 for line in diff_lines if line.startswith('-')
                      and not line.startswith('---'))

        return added, removed

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename"""
        return re.sub(r'[<>:"/\\|?*]', '_', filename)