"""
Data models for Network Backup Tool
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class DeviceConfig:
    """Device connection configuration"""
    host: str
    device_type: str
    username: str
    password: str
    port: int = 22
    secret: str = ""
    timeout: int = 30
    use_keys: bool = False
    key_file: str = ""
    transport: str = "ssh"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceConfig':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class BackupResult:
    """Result of backup operation"""
    device: DeviceConfig
    success: bool
    hostname: str = ""
    config: str = ""
    error: str = ""
    backup_path: str = ""
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class CommandMapping:
    """Command mappings for device types"""
    hostname_cmd: str
    config_cmd: str
    hostname_pattern: str
    post_login_cmd: str = ""
    pre_logout_cmd: str = ""
    enable_password: bool = False
    disable_paging: bool = True