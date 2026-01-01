"""
Configuration Validator for Network Backup Tool
"""

import sys
import json
import yaml
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple


def setup_logging():
    """Setup logging for validator"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def validate_yaml_file(filepath: Path) -> Tuple[bool, str, Any]:
    """Validate YAML file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)

        if content is None:
            return False, "File is empty", None

        return True, "Valid YAML", content

    except yaml.YAMLError as e:
        return False, f"YAML syntax error: {e}", None
    except Exception as e:
        return False, f"Error reading file: {e}", None


def validate_json_file(filepath: Path) -> Tuple[bool, str, Any]:
    """Validate JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = json.load(f)

        return True, "Valid JSON", content

    except json.JSONDecodeError as e:
        return False, f"JSON syntax error: {e}", None
    except Exception as e:
        return False, f"Error reading file: {e}", None


def validate_regex_patterns(patterns: List[str]) -> List[str]:
    """Validate regex patterns"""
    errors = []

    for i, pattern in enumerate(patterns):
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append(f"Pattern {i+1} '{pattern}': {e}")

    return errors


def validate_device_commands(commands: Dict[str, Any]) -> List[str]:
    """Validate device commands configuration"""
    errors = []
    required_fields = ['hostname_cmd', 'config_cmd', 'hostname_pattern']

    for device_type, config in commands.items():
        if not isinstance(config, dict):
            errors.append(f"Device type '{device_type}': Configuration must be a dictionary")
            continue

        # Check required fields
        for field in required_fields:
            if field not in config:
                errors.append(f"Device type '{device_type}': Missing required field '{field}'")

        # Validate hostname pattern if present
        if 'hostname_pattern' in config:
            try:
                re.compile(config['hostname_pattern'])
            except re.error as e:
                errors.append(f"Device type '{device_type}': Invalid hostname pattern: {e}")

    return errors


def validate_devices(devices: List[Dict[str, Any]]) -> List[str]:
    """Validate devices configuration"""
    errors = []
    required_fields = ['host', 'device_type']

    if not isinstance(devices, list):
        return ["Devices must be a JSON array"]

    for i, device in enumerate(devices):
        if not isinstance(device, dict):
            errors.append(f"Device {i+1}: Must be a dictionary")
            continue

        # Check required fields
        for field in required_fields:
            if field not in device:
                errors.append(f"Device {i+1}: Missing required field '{field}'")

        # Validate host
        if 'host' in device and not device['host']:
            errors.append(f"Device {i+1}: Host cannot be empty")

        # Validate device_type
        if 'device_type' in device and not device['device_type']:
            errors.append(f"Device {i+1}: Device type cannot be empty")

        # Validate port
        if 'port' in device:
            try:
                port = int(device['port'])
                if not 1 <= port <= 65535:
                    errors.append(f"Device {i+1}: Port must be between 1 and 65535")
            except (ValueError, TypeError):
                errors.append(f"Device {i+1}: Port must be a number")

    return errors


def validate_default_config(config: Dict[str, Any]) -> List[str]:
    """Validate default configuration"""
    errors = []

    # Check required sections
    required_sections = ['global', 'backup', 'comparison']
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section '{section}'")

    # Validate global section
    if 'global' in config:
        global_config = config['global']
        if not isinstance(global_config, dict):
            errors.append("Global section must be a dictionary")
        else:
            # Check port
            if 'port' in global_config:
                try:
                    port = int(global_config['port'])
                    if not 1 <= port <= 65535:
                        errors.append("Global port must be between 1 and 65535")
                except (ValueError, TypeError):
                    errors.append("Global port must be a number")

    # Validate backup section
    if 'backup' in config and isinstance(config['backup'], dict):
        backup_config = config['backup']

        # Check max_backups
        if 'max_backups' in backup_config:
            try:
                max_backups = int(backup_config['max_backups'])
                if max_backups < 1:
                    errors.append("max_backups must be at least 1")
            except (ValueError, TypeError):
                errors.append("max_backups must be a number")

        # Check max_workers
        if 'max_workers' in backup_config:
            try:
                max_workers = int(backup_config['max_workers'])
                if max_workers < 1:
                    errors.append("max_workers must be at least 1")
            except (ValueError, TypeError):
                errors.append("max_workers must be a number")

    # Validate comparison section
    if 'comparison' in config and isinstance(config['comparison'], dict):
        comparison_config = config['comparison']

        # Check context_lines
        if 'context_lines' in comparison_config:
            try:
                context_lines = int(comparison_config['context_lines'])
                if context_lines < 0:
                    errors.append("context_lines cannot be negative")
            except (ValueError, TypeError):
                errors.append("context_lines must be a number")

        # Validate ignore patterns
        if 'ignore_patterns' in comparison_config:
            ignore_patterns = comparison_config['ignore_patterns']
            if not isinstance(ignore_patterns, dict):
                errors.append("ignore_patterns must be a dictionary")
            else:
                # Check common patterns
                if 'common' in ignore_patterns:
                    if not isinstance(ignore_patterns['common'], list):
                        errors.append("ignore_patterns.common must be a list")
                    else:
                        pattern_errors = validate_regex_patterns(ignore_patterns['common'])
                        if pattern_errors:
                            errors.extend([f"Common pattern error: {e}" for e in pattern_errors])

    return errors


def validate_directory_structure(config_dir: Path) -> List[str]:
    """Validate that required directories exist"""
    errors = []

    # Check if config directory exists
    if not config_dir.exists():
        errors.append(f"Configuration directory not found: {config_dir}")
        return errors

    # Check required files
    required_files = [
        ('default.yaml', 'Default configuration file'),
        ('device_commands.yaml', 'Device commands file'),
        ('devices.json', 'Devices configuration file'),
    ]

    for filename, description in required_files:
        filepath = config_dir / filename
        if not filepath.exists():
            errors.append(f"{description} not found: {filepath}")

    return errors


def validate_configuration(config_dir: str = "config") -> bool:
    """Main validation function"""
    config_dir_path = Path(config_dir)
    all_valid = True

    print(f"Validating configuration in: {config_dir_path.absolute()}")
    print("-" * 60)

    # Validate directory structure
    dir_errors = validate_directory_structure(config_dir_path)
    if dir_errors:
        for error in dir_errors:
            logging.error(error)
            all_valid = False

        if not all_valid:
            print("\nPlease create missing files or check the configuration directory.")
            return False

    # Validate default.yaml
    default_yaml_path = config_dir_path / "default.yaml"
    if default_yaml_path.exists():
        valid, message, config = validate_yaml_file(default_yaml_path)
        if valid:
            logging.info(f"✓ default.yaml: {message}")

            # Validate configuration content
            config_errors = validate_default_config(config)
            if config_errors:
                for error in config_errors:
                    logging.error(f"  Configuration error: {error}")
                all_valid = False
            else:
                logging.info("  ✓ Configuration structure is valid")
        else:
            logging.error(f"✗ default.yaml: {message}")
            all_valid = False
    else:
        logging.error(f"✗ default.yaml: File not found")
        all_valid = False

    # Validate device_commands.yaml
    commands_path = config_dir_path / "device_commands.yaml"
    if commands_path.exists():
        valid, message, commands = validate_yaml_file(commands_path)
        if valid:
            logging.info(f"✓ device_commands.yaml: {message}")

            # Validate commands content
            if isinstance(commands, dict):
                command_errors = validate_device_commands(commands)
                if command_errors:
                    for error in command_errors:
                        logging.error(f"  Command error: {error}")
                    all_valid = False
                else:
                    device_types = list(commands.keys())
                    logging.info(f"  ✓ Found {len(device_types)} device types: {', '.join(device_types)}")
            else:
                logging.error("  Commands must be a dictionary")
                all_valid = False
        else:
            logging.error(f"✗ device_commands.yaml: {message}")
            all_valid = False
    else:
        logging.error(f"✗ device_commands.yaml: File not found")
        all_valid = False

    # Validate devices.json
    devices_path = config_dir_path / "devices.json"
    if devices_path.exists():
        valid, message, devices = validate_json_file(devices_path)
        if valid:
            logging.info(f"✓ devices.json: {message}")

            # Validate devices content
            device_errors = validate_devices(devices)
            if device_errors:
                for error in device_errors:
                    logging.error(f"  Device error: {error}")
                all_valid = False
            else:
                logging.info(f"  ✓ Found {len(devices)} valid devices")

                # Count by device type
                device_types = {}
                for device in devices:
                    dev_type = device.get('device_type', 'unknown')
                    device_types[dev_type] = device_types.get(dev_type, 0) + 1

                if device_types:
                    type_summary = ', '.join([f"{k}: {v}" for k, v in device_types.items()])
                    logging.info(f"  Device types: {type_summary}")
        else:
            logging.error(f"✗ devices.json: {message}")
            all_valid = False
    else:
        logging.error(f"✗ devices.json: File not found")
        all_valid = False

    # Final summary
    print("-" * 60)
    if all_valid:
        print("✅ All configuration files are valid and ready to use!")

        # Check if device types in devices.json are defined in device_commands.yaml
        if commands_path.exists() and devices_path.exists():
            valid_commands = validate_yaml_file(commands_path)
            valid_devices = validate_json_file(devices_path)

            if valid_commands[0] and valid_devices[0]:
                commands_data = valid_commands[2]
                devices_data = valid_devices[2]

                if isinstance(commands_data, dict) and isinstance(devices_data, list):
                    defined_types = set(commands_data.keys())
                    used_types = set()

                    for device in devices_data:
                        if isinstance(device, dict) and 'device_type' in device:
                            used_types.add(device['device_type'])

                    undefined_types = used_types - defined_types
                    if undefined_types:
                        print(f"⚠️  Warning: The following device types are used but not defined in device_commands.yaml:")
                        for dev_type in undefined_types:
                            print(f"    - {dev_type}")
                        print("  Consider adding them to device_commands.yaml")
    else:
        print("❌ Configuration validation failed. Please fix the errors above.")

    return all_valid


def create_sample_config(config_dir: str = "config"):
    """Create sample configuration files"""
    config_dir_path = Path(config_dir)
    config_dir_path.mkdir(parents=True, exist_ok=True)

    # Sample default.yaml
    default_yaml = """# Network Backup Tool - Default Configuration

global:
  username: "admin"
  password: ""  # Leave empty to prompt or use key-based auth
  port: 22
  timeout: 30
  use_keys: false
  key_file: "~/.ssh/id_rsa"
  transport: "ssh"

backup:
  backup_dir: "backups"
  reports_dir: "reports"
  logs_dir: "logs"
  max_backups: 30
  max_workers: 5
  parallel_mode: true

comparison:
  context_lines: 3
  ignore_patterns:
    common:
      - "^! Time:.*"
      - "^! Last configuration change.*"
      - "^! NVRAM config last updated.*"
      - "^Building configuration.*"
      - "^Current configuration :.*"
      - "^## Last commit:.*"
      - "^## .*"
      - "^# .*"
      - "^\\s*$"
    
    cisco_ios:
      - "^! Configuration register.*"
    
    juniper_junos:
      - "^##.*"
"""

    # Sample device_commands.yaml
    device_commands_yaml = """# Device Command Mappings
# Each device type should have the following commands:
# - hostname_cmd: Command to get device hostname
# - config_cmd: Command to get configuration
# - hostname_pattern: Regex pattern to extract hostname from output
# - disable_paging: Command to disable paging (true/false or command string)
# - enable_password: Whether enable password is required (true/false)

cisco_ios:
  hostname_cmd: "show running-config | include hostname"
  config_cmd: "show running-config"
  hostname_pattern: "hostname\\s+(\\S+)"
  disable_paging: true
  enable_password: true

cisco_nxos:
  hostname_cmd: "show running-config | include hostname"
  config_cmd: "show running-config"
  hostname_pattern: "hostname\\s+(\\S+)"
  disable_paging: true

juniper_junos:
  hostname_cmd: "show configuration system host-name"
  config_cmd: "show configuration | display set"
  hostname_pattern: "host-name\\s+(\\S+);"
  disable_paging: true

huawei_vrp:
  hostname_cmd: "display current-configuration | include sysname"
  config_cmd: "display current-configuration"
  hostname_pattern: "sysname\\s+(\\S+)"
  disable_paging: "screen-length 0 temporary"

arista_eos:
  hostname_cmd: "show running-config | include hostname"
  config_cmd: "show running-config"
  hostname_pattern: "hostname\\s+(\\S+)"
  disable_paging: true

mikrotik_routeros:
  hostname_cmd: "/system identity print"
  config_cmd: "/export compact"
  hostname_pattern: "name:\\s+(\\S+)"
  disable_paging: true
"""

    # Sample devices.json
    devices_json = [
        {
            "host": "192.168.1.1",
            "device_type": "cisco_ios",
            "username": "admin",
            "password": "cisco123",
            "secret": "enable123",
            "port": 22,
            "timeout": 30,
            "description": "Core Switch 1"
        },
        {
            "host": "192.168.1.2",
            "device_type": "juniper_junos",
            "username": "admin",
            "password": "Juniper!",
            "port": 22,
            "timeout": 30,
            "description": "Edge Router"
        },
        {
            "host": "10.0.0.1",
            "device_type": "huawei_vrp",
            "username": "admin",
            "password": "Huawei@123",
            "port": 22,
            "description": "Access Switch"
        }
    ]

    try:
        # Write default.yaml
        with open(config_dir_path / "default.yaml", 'w', encoding='utf-8') as f:
            f.write(default_yaml)
        print(f"Created: {config_dir_path / 'default.yaml'}")

        # Write device_commands.yaml
        with open(config_dir_path / "device_commands.yaml", 'w', encoding='utf-8') as f:
            f.write(device_commands_yaml)
        print(f"Created: {config_dir_path / 'device_commands.yaml'}")

        # Write devices.json
        with open(config_dir_path / "devices.json", 'w', encoding='utf-8') as f:
            json.dump(devices_json, f, indent=2, ensure_ascii=False)
        print(f"Created: {config_dir_path / 'devices.json'}")

        print("\n✅ Sample configuration files created successfully!")
        print("Please edit these files with your actual device information.")

    except Exception as e:
        print(f"Error creating sample files: {e}")


def main():
    """Command line entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Configuration Validator for Network Backup Tool"
    )

    parser.add_argument(
        '--config-dir', '-c',
        default='config',
        help='Configuration directory (default: config)'
    )

    parser.add_argument(
        '--create-samples', '-s',
        action='store_true',
        help='Create sample configuration files'
    )

    parser.add_argument(
        '--fix', '-f',
        action='store_true',
        help='Try to fix common configuration issues'
    )

    args = parser.parse_args()

    setup_logging()

    if args.create_samples:
        create_sample_config(args.config_dir)
        return

    success = validate_configuration(args.config_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
