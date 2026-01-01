"""
Configuration Manager
"""
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any
from .models import DeviceConfig


class ConfigManager:
    """Manages configuration files and settings"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.default_config_path = self.config_dir / "default.yaml"
        self.devices_path = self.config_dir / "devices.json"
        self.commands_path = self.config_dir / "device_commands.yaml"

        # Default configuration
        self.default_config = {
            "global": {
                "username": "admin",
                "password": "",
                "port": 22,
                "timeout": 30,
                "use_keys": False,
                "key_file": "~/.ssh/id_rsa",
                "transport": "ssh"
            },
            "backup": {
                "backup_dir": "backups",
                "reports_dir": "reports",
                "logs_dir": "logs",
                "max_backups": 30,
                "max_workers": 5,
                "parallel_mode": True
            },
            "comparison": {
                "context_lines": 3,
                "ignore_patterns": {
                    "common": [
                        r"^! Time:.*",
                        r"^! Last configuration change.*",
                        r"^! NVRAM config last updated.*",
                        r"^Building configuration.*",
                        r"^Current configuration :.*",
                        r"^## Last commit:.*",
                        r"^## .*",
                        r"^# .*"
                    ]
                }
            }
        }

        # Load configurations
        self.config = self._load_config()
        self.commands = self._load_commands()

    def _load_config(self) -> Dict[str, Any]:
        """Load main configuration"""
        try:
            if self.default_config_path.exists():
                with open(self.default_config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f) or {}
                    # Deep merge with defaults
                    return self._deep_merge(self.default_config, user_config)
        except Exception as e:
            logging.error(f"Error loading config: {e}")

        return self.default_config

    def _load_commands(self) -> Dict[str, Dict[str, Any]]:
        """Load command mappings"""
        try:
            if self.commands_path.exists():
                with open(self.commands_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            logging.error(f"Error loading commands: {e}")

        # Return default commands if file not found
        return self._get_default_commands()

    def _get_default_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get default command mappings"""
        return {
            "cisco_ios": {
                "hostname_cmd": "show running-config | include hostname",
                "config_cmd": "show running-config",
                "hostname_pattern": r"hostname\s+(\S+)",
                "enable_password": True,
                "disable_paging": True
            },
            "cisco_nxos": {
                "hostname_cmd": "show running-config | include hostname",
                "config_cmd": "show running-config",
                "hostname_pattern": r"hostname\s+(\S+)",
                "disable_paging": True
            },
            "juniper_junos": {
                "hostname_cmd": "show configuration system host-name",
                "config_cmd": "show configuration | display set",
                "hostname_pattern": r"host-name\s+(\S+);",
                "disable_paging": True
            },
            "huawei": {
                "hostname_cmd": "display current-configuration | include sysname",
                "config_cmd": "display current-configuration",
                "hostname_pattern": r"sysname\s+(\S+)",
                "disable_paging": "screen-length 0 temporary"
            },
            "arista_eos": {
                "hostname_cmd": "show running-config | include hostname",
                "config_cmd": "show running-config",
                "hostname_pattern": r"hostname\s+(\S+)",
                "disable_paging": True
            }
        }

    def load_devices(self) -> List[DeviceConfig]:
        """Load devices from JSON file"""
        devices = []

        if not self.devices_path.exists():
            logging.error(f"Devices file not found: {self.devices_path}")
            self._create_sample_devices()
            return []

        try:
            with open(self.devices_path, 'r', encoding='utf-8') as f:
                devices_data = json.load(f)

            if not isinstance(devices_data, list):
                logging.error("Devices file must contain a JSON array")
                return []

            for device_data in devices_data:
                # Apply global defaults for missing values
                device_cfg = {
                    'host': device_data.get('host', ''),
                    'device_type': device_data.get('device_type', 'cisco_ios'),
                    'username': device_data.get('username', self.config['global']['username']),
                    'password': device_data.get('password', self.config['global']['password']),
                    'port': device_data.get('port', self.config['global']['port']),
                    'secret': device_data.get('secret', ''),
                    'timeout': device_data.get('timeout', self.config['global']['timeout']),
                    'use_keys': device_data.get('use_keys', self.config['global']['use_keys']),
                    'key_file': device_data.get('key_file', self.config['global'].get('key_file', '')),
                    'transport': device_data.get('transport', self.config['global']['transport'])
                }

                if device_cfg['host']:  # Skip empty devices
                    devices.append(DeviceConfig(**device_cfg))

            logging.info(f"Loaded {len(devices)} devices from {self.devices_path}")
            return devices

        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in devices file: {e}")
        except Exception as e:
            logging.error(f"Error loading devices: {e}")

        return []

    def get_device_commands(self, device_type: str) -> Dict[str, Any]:
        """Get commands for specific device type"""
        return self.commands.get(device_type, self.commands.get('cisco_ios', {}))

    def get_ignore_patterns(self, device_type: str) -> List[str]:
        """Get ignore patterns for device type"""
        patterns = self.config['comparison']['ignore_patterns'].get('common', [])

        # Add device-specific patterns if any
        device_patterns = self.config['comparison']['ignore_patterns'].get(device_type, [])
        patterns.extend(device_patterns)

        return patterns

    def save_devices(self, devices: List[DeviceConfig]):
        """Save devices to JSON file"""
        try:
            devices_data = [device.to_dict() for device in devices]

            with open(self.devices_path, 'w', encoding='utf-8') as f:
                json.dump(devices_data, f, indent=2, ensure_ascii=False)

            logging.info(f"Saved {len(devices)} devices to {self.devices_path}")
            return True

        except Exception as e:
            logging.error(f"Error saving devices: {e}")
            return False

    def _create_sample_devices(self):
        """Create sample devices JSON file"""
        sample_devices = [
            {
                "host": "192.168.1.1",
                "device_type": "cisco_ios",
                "username": "admin",
                "password": "cisco123",
                "secret": "enable123",
                "description": "Core Switch"
            },
            {
                "host": "192.168.1.2",
                "device_type": "juniper_junos",
                "username": "admin",
                "password": "Juniper!",
                "description": "Edge Router"
            }
        ]

        try:
            self.devices_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.devices_path, 'w', encoding='utf-8') as f:
                json.dump(sample_devices, f, indent=2, ensure_ascii=False)
            logging.info(f"Created sample devices file: {self.devices_path}")
        except Exception as e:
            logging.error(f"Failed to create devices file: {e}")

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @property
    def backup_config(self) -> Dict[str, Any]:
        """Get backup configuration"""
        return self.config['backup']

    @property
    def comparison_config(self) -> Dict[str, Any]:
        """Get comparison configuration"""
        return self.config['comparison']