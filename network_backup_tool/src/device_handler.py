"""
Network Device Handler
"""
import re
import socket
import logging
from typing import Optional, Any
from .models import DeviceConfig
from .config_manager import ConfigManager

try:
    from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
    from netmiko.ssh_exception import SSHException
except ImportError:
    print("Error: Netmiko not installed")
    raise


class NetworkDeviceHandler:
    """Handles connection and interaction with network devices"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.connections = {}

    def connect(self, device: DeviceConfig) -> Optional[Any]:
        """Establish SSH connection to device"""
        try:
            # Get device-specific commands
            commands = self.config_manager.get_device_commands(device.device_type)

            # Prepare connection parameters
            connection_params = {
                'device_type': device.device_type,
                'host': device.host,
                'username': device.username,
                'password': device.password,
                'port': device.port,
                'secret': device.secret,
                'timeout': device.timeout,
                'verbose': False,
                'global_delay_factor': 1,
            }

            # Add key-based authentication if requested
            if device.use_keys and device.key_file:
                from pathlib import Path
                key_file = Path(device.key_file).expanduser()
                if key_file.exists():
                    connection_params['use_keys'] = True
                    connection_params['key_file'] = str(key_file)

            # Establish connection
            connection = ConnectHandler(**connection_params)

            # Disable paging if configured
            if commands.get('disable_paging'):
                if isinstance(commands['disable_paging'], bool):
                    connection.disable_paging()
                elif isinstance(commands['disable_paging'], str):
                    connection.send_command(commands['disable_paging'])

            # Run post-login command if configured
            if commands.get('post_login_cmd'):
                connection.send_command(commands['post_login_cmd'])

            # Enter enable mode if needed
            if commands.get('enable_password', False) and device.secret:
                connection.enable()

            logging.info(f"Connected to {device.host} ({device.device_type})")
            self.connections[device.host] = connection
            return connection

        except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
            logging.error(f"Authentication/Timeout error for {device.host}: {e}")
            return None
        except (SSHException, socket.timeout, socket.error) as e:
            logging.error(f"Connection error for {device.host}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error connecting to {device.host}: {e}")
            return None

    def get_hostname(self, connection: Any, device: DeviceConfig) -> str:
        """Get device hostname"""
        commands = self.config_manager.get_device_commands(device.device_type)
        hostname_cmd = commands.get('hostname_cmd', '')
        hostname_pattern = commands.get('hostname_pattern', r'(\S+)')

        if not hostname_cmd:
            return device.host

        try:
            output = connection.send_command(hostname_cmd, strip_prompt=False)
            output = self._clean_output(output)

            # Extract hostname using pattern
            match = re.search(hostname_pattern, output, re.IGNORECASE)
            if match:
                hostname = match.group(1).strip()
                hostname = hostname.strip('"\'')
                return hostname

            # Fallback: try to get from prompt
            if hasattr(connection, 'base_prompt'):
                hostname = connection.base_prompt.strip('#> ')
                if hostname:
                    return hostname

            logging.warning(f"Could not extract hostname from {device.host}, using host")
            return device.host

        except Exception as e:
            logging.error(f"Error getting hostname from {device.host}: {e}")
            return device.host

    def get_configuration(self, connection: Any, device: DeviceConfig) -> str:
        """Get device configuration"""
        commands = self.config_manager.get_device_commands(device.device_type)
        config_cmd = commands.get('config_cmd', 'show running-config')

        try:
            # Send command with appropriate delay
            output = connection.send_command(
                config_cmd,
                delay_factor=2,
                max_loops=5000,
                strip_prompt=False
            )

            output = self._clean_output(output)

            # Remove command echo if present
            lines = output.split('\n')
            if lines and config_cmd in lines[0]:
                lines = lines[1:]

            return '\n'.join(lines).strip()

        except Exception as e:
            logging.error(f"Error getting configuration from {device.host}: {e}")
            return ""

    def cleanup_config(self, config: str, device_type: str) -> str:
        """Clean configuration from dynamic/non-essential lines"""
        patterns = self.config_manager.get_ignore_patterns(device_type)
        lines = config.split('\n')
        cleaned_lines = []

        for line in lines:
            skip = False
            line_stripped = line.strip()

            for pattern in patterns:
                try:
                    if re.match(pattern, line_stripped):
                        skip = True
                        break
                except re.error:
                    logging.warning(f"Invalid regex pattern: {pattern}")
                    continue

            if not skip and line_stripped:
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _clean_output(self, output: str) -> str:
        """Clean ANSI escape sequences and extra whitespace"""
        # Remove ANSI escape codes
        output = self.ansi_escape.sub('', output)

        # Remove carriage returns
        output = output.replace('\r', '')

        # Normalize line endings
        lines = output.split('\n')
        cleaned_lines = []

        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()
            if line:  # Keep non-empty lines
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def disconnect(self, device_host: str):
        """Close SSH connection"""
        try:
            if device_host in self.connections:
                connection = self.connections.pop(device_host)
                if connection:
                    # Run pre-logout command if configured
                    try:
                        if hasattr(connection, 'device_type'):
                            commands = self.config_manager.get_device_commands(connection.device_type)
                            if commands.get('pre_logout_cmd'):
                                connection.send_command(commands['pre_logout_cmd'])
                    except Exception:
                        pass

                    connection.disconnect()
        except Exception as e:
            logging.warning(f"Error disconnecting from {device_host}: {e}")

    def disconnect_all(self):
        """Close all connections"""
        for device_host in list(self.connections.keys()):
            self.disconnect(device_host)