"""
Network Configuration Backup & Compare Tool
Main script
"""

import sys
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config_manager import ConfigManager
from src.models import DeviceConfig, BackupResult
from src.device_handler import NetworkDeviceHandler
from src.backup_manager import BackupManager
from src.comparison_engine import ComparisonEngine
from typing import List

class NetworkBackupTool:
    """Main application class"""

    def __init__(self, config_dir: str = "config"):
        # Initialize components
        self.config_manager = ConfigManager(config_dir)
        self.device_handler = NetworkDeviceHandler(self.config_manager)

        self.backup_manager = BackupManager(self.config_manager.backup_config)

        self.comparison_engine = ComparisonEngine(
            self.config_manager.comparison_config,
            self.backup_manager.backup_dir,
            self.backup_manager.reports_dir
        )

        # Results storage
        self.results: List[BackupResult] = []

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration"""
        log_file = self.backup_manager.logs_dir / f'backup_{datetime.now().strftime("%Y%m%d")}.log'

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def backup_device(self, device: DeviceConfig) -> BackupResult:
        """Backup a single device"""
        result = BackupResult(device=device, success=False)

        logging.info(f"Starting backup for {device.host} ({device.device_type})")

        # Connect to device
        connection = self.device_handler.connect(device)
        if not connection:
            result.error = "Connection failed"
            return result

        try:
            # Get hostname
            hostname = self.device_handler.get_hostname(connection, device)
            result.hostname = hostname

            # Get configuration
            config = self.device_handler.get_configuration(connection, device)
            if not config:
                result.error = "Failed to get configuration"
                return result

            result.config = config

            # Clean configuration
            clean_config = self.device_handler.cleanup_config(config, device.device_type)

            # Save configuration
            backup_path = self.backup_manager.save_config(hostname, clean_config)
            if not backup_path:
                result.error = "Failed to save configuration"
                return result

            result.backup_path = str(backup_path)

            # Find and compare with previous backup
            old_backup = self.backup_manager.find_latest_backup(hostname)
            if old_backup and old_backup != backup_path:  # Make sure it's not the same file
                try:
                    diff = self.comparison_engine.compare_files(
                        old_backup, backup_path, device.device_type
                    )

                    # Save diff if there are significant changes
                    if diff and self.comparison_engine.has_significant_changes(diff):
                        self.comparison_engine.generate_diff_report(
                            diff, hostname, old_backup, backup_path
                        )

                except Exception as e:
                    logging.warning(f"Error comparing configurations for {hostname}: {e}")

            result.success = True
            logging.info(f"Backup completed for {hostname}")

        except Exception as e:
            result.error = str(e)
            logging.error(f"Error backing up {device.host}: {e}")

        finally:
            # Always disconnect
            self.device_handler.disconnect(device.host)

        return result

    def backup_devices_parallel(self, devices: List[DeviceConfig], max_workers: int = None):
        """Backup multiple devices in parallel"""
        if max_workers is None:
            max_workers = self.config_manager.backup_config['max_workers']

        logging.info(f"Starting parallel backup of {len(devices)} devices (workers: {max_workers})")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all backup tasks
            future_to_device = {
                executor.submit(self.backup_device, device): device
                for device in devices
            }

            # Process results as they complete
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    result = future.result()
                    self.results.append(result)
                except Exception as e:
                    logging.error(f"Exception processing {device.host}: {e}")
                    self.results.append(BackupResult(
                        device=device, success=False, error=str(e)
                    ))

    def backup_devices_sequential(self, devices: List[DeviceConfig]):
        """Backup multiple devices sequentially"""
        logging.info(f"Starting sequential backup of {len(devices)} devices")

        for device in devices:
            result = self.backup_device(device)
            self.results.append(result)

    def generate_summary_report(self) -> dict:
        """Generate summary report"""
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful

        summary = {
            "timestamp": datetime.now().isoformat(),
            "tool_version": "2.0",
            "total_devices": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "backup_count": self.backup_manager.backup_count,
            "results": []
        }

        for result in self.results:
            result_dict = {
                "host": result.device.host,
                "hostname": result.hostname,
                "device_type": result.device.device_type,
                "success": result.success,
                "backup_path": result.backup_path,
                "error": result.error,
                "timestamp": result.timestamp.isoformat() if result.timestamp else None
            }
            summary["results"].append(result_dict)

        # Save summary
        self.backup_manager.save_summary_report(summary)

        return summary

    def print_summary(self, summary: dict):
        """Print summary to console"""
        print("\n" + "="*60)
        print("NETWORK BACKUP TOOL - SUMMARY REPORT")
        print("="*60)
        print(f"Timestamp:      {summary['timestamp']}")
        print(f"Total devices:  {summary['total_devices']}")
        print(f"Successful:     {summary['successful']}")
        print(f"Failed:         {summary['failed']}")
        print(f"Success rate:   {summary['success_rate']:.1f}%")
        print(f"Total backups:  {summary['backup_count']}")

        if summary['failed'] > 0:
            print("\nFAILED DEVICES:")
            for result in summary['results']:
                if not result['success']:
                    print(f"  - {result['host']}: {result['error']}")

        print("\nSUCCESSFUL DEVICES:")
        for result in summary['results']:
            if result['success']:
                print(f"  - {result['hostname']} ({result['device_type']})")

        print("="*60)
        print(f"\nBackups saved in:  {self.backup_manager.backup_dir}")
        print(f"Reports saved in:  {self.backup_manager.reports_dir}")
        print(f"Logs saved in:     {self.backup_manager.logs_dir}")

    def run(self, parallel: bool = None):
        """Main execution method"""
        print("Network Configuration Backup & Compare Tool")
        print("="*60)

        # Load devices
        devices = self.config_manager.load_devices()
        if not devices:
            logging.error("No devices to process")
            return

        print(f"Loaded {len(devices)} devices from configuration")

        # Determine mode
        if parallel is None:
            parallel = self.config_manager.backup_config['parallel_mode']

        # Perform backup
        if parallel:
            max_workers = self.config_manager.backup_config['max_workers']
            self.backup_devices_parallel(devices, max_workers)
        else:
            self.backup_devices_sequential(devices)

        # Cleanup old backups
        self.backup_manager.cleanup_old_backups()

        # Disconnect all connections
        self.device_handler.disconnect_all()

        # Generate summary
        summary = self.generate_summary_report()
        self.print_summary(summary)


def main():
    """Command line entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Network Configuration Backup & Compare Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config', '-c',
        default='config',
        help='Configuration directory (default: config)'
    )

    parser.add_argument(
        '--sequential', '-s',
        action='store_true',
        help='Run backups sequentially (default: parallel)'
    )

    parser.add_argument(
        '--parallel', '-p',
        action='store_true',
        help='Run backups in parallel (default from config)'
    )

    parser.add_argument(
        '--workers', '-w',
        type=int,
        help='Number of parallel workers (overrides config)'
    )

    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Test configuration without actual backup'
    )

    parser.add_argument(
        '--validate', '-V',
        action='store_true',
        help='Validate configuration files only'
    )

    args = parser.parse_args()

    try:
        # Run validation if requested
        if args.validate:
            from validate_config import validate_configuration
            success = validate_configuration(args.config)
            sys.exit(0 if success else 1)

        # Initialize tool
        tool = NetworkBackupTool(args.config)

        # Test mode
        if args.test:
            print("Test mode - Checking configuration...")

            devices = tool.config_manager.load_devices()
            print(f"\nFound {len(devices)} devices:")
            for i, device in enumerate(devices, 1):
                print(f"  {i}. {device.host} ({device.device_type})")

            print(f"\nBackup directory: {tool.backup_manager.backup_dir}")
            print(f"Reports directory: {tool.backup_manager.reports_dir}")
            print(f"Max backups per device: {tool.config_manager.backup_config['max_backups']}")
            return

        # Determine parallel mode
        parallel = None
        if args.sequential:
            parallel = False
        elif args.parallel:
            parallel = True

        # Override workers if specified
        if args.workers:
            tool.config_manager.backup_config['max_workers'] = args.workers

        # Run backup
        tool.run(parallel=parallel)

    except KeyboardInterrupt:
        print("\n\nBackup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()