"""
Модели данных для проекта Network Discovery
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class Protocol(Enum):
    """Перечисление поддерживаемых протоколов"""
    SSH = "ssh"
    TELNET = "telnet"
    UNKNOWN = "unknown"


@dataclass
class DeviceCredentials:
    """Класс для хранения учетных данных устройства"""
    username: str
    password: str
    enable_password: Optional[str] = None
    ssh_port: int = 22
    telnet_port: int = 23
    ssh_timeout: int = 10
    telnet_timeout: int = 10
    description: str = ""

    def __post_init__(self):
        """Проверка валидности данных после инициализации"""
        if not self.username:
            raise ValueError("Имя пользователя не может быть пустым")
        if self.ssh_port <= 0 or self.ssh_port > 65535:
            raise ValueError(f"Неверный SSH порт: {self.ssh_port}")
        if self.telnet_port <= 0 or self.telnet_port > 65535:
            raise ValueError(f"Неверный Telnet порт: {self.telnet_port}")

    def for_ssh(self) -> Dict:
        """Возвращает параметры для SSH подключения"""
        return {
            'username': self.username,
            'password': self.password,
            'port': self.ssh_port,
            'timeout': self.ssh_timeout
        }

    def for_telnet(self) -> Dict:
        """Возвращает параметры для Telnet подключения"""
        return {
            'username': self.username,
            'password': self.password,
            'port': self.telnet_port,
            'timeout': self.telnet_timeout
        }

    def to_dict(self) -> Dict:
        """Конвертация в словарь"""
        return asdict(self)


@dataclass
class DiscoveredDevice:
    """Класс для хранения информации об обнаруженном устройстве"""
    ip_address: str
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    serial_number: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enable_password: Optional[str] = None
    ssh_port: int = 22
    telnet_port: int = 23
    snmp_community: Optional[str] = None
    protocol: str = "unknown"
    capabilities: List[str] = field(default_factory=list)
    status: str = "unknown"
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Проверка валидности данных после инициализации"""
        # Проверяем IP адрес
        import ipaddress
        try:
            ipaddress.ip_address(self.ip_address)
        except ValueError:
            raise ValueError(f"Неверный IP адрес: {self.ip_address}")

    def to_dict(self) -> Dict:
        """Конвертация в словарь"""
        return asdict(self)

    def to_netmiko_config(self) -> Dict:
        """Конвертация в конфигурацию для Netmiko"""
        # Маппинг device_type для Telnet
        telnet_mapping = {
            'cisco_ios': 'cisco_ios_telnet',
            'cisco_xe': 'cisco_xe_telnet',
            'cisco_xr': 'cisco_xr_telnet',
            'cisco_nxos': 'cisco_nxos_telnet',
            'cisco_asa': 'cisco_asa_telnet',
            'juniper': 'juniper_telnet',
            'arista_eos': 'arista_eos_telnet',
            'hp_procurve': 'hp_procurve_telnet',
            'hp_comware': 'hp_comware_telnet',
            'mikrotik_routeros': 'mikrotik_routeros_telnet',
            'linux': 'linux_telnet',
        }

        # Определяем device_type
        if self.protocol == "telnet" and self.device_type:
            if not self.device_type.endswith('_telnet'):
                device_type = telnet_mapping.get(self.device_type, f"{self.device_type}_telnet")
            else:
                device_type = self.device_type
        else:
            device_type = self.device_type or 'autodetect'

        # Формируем конфигурацию
        config = {
            'device_type': device_type,
            'host': self.ip_address,
            'username': self.username,
            'password': self.password,
            'port': self.ssh_port if self.protocol == 'ssh' else self.telnet_port,
            'timeout': 10,
            'global_delay_factor': 2,
        }

        if self.enable_password:
            config['secret'] = self.enable_password

        # Добавляем метаданные
        if self.vendor:
            config['vendor'] = self.vendor
        if self.model:
            config['model'] = self.model
        if self.os_version:
            config['os_version'] = self.os_version
        if self.hostname:
            config['name'] = self.hostname

        return config

    def get_connection_info(self) -> Dict:
        """Возвращает информацию для подключения"""
        return {
            'ip': self.ip_address,
            'hostname': self.hostname,
            'protocol': self.protocol,
            'port': self.ssh_port if self.protocol == 'ssh' else self.telnet_port,
            'username': self.username,
            'device_type': self.device_type,
            'vendor': self.vendor
        }


class DeviceFactory:
    """Фабрика для создания объектов устройств"""

    @staticmethod
    def from_ssh_discovery(ip: str, device_type: str, vendor: str,
                           credentials: DeviceCredentials, **kwargs) -> DiscoveredDevice:
        """Создание устройства из SSH обнаружения"""
        return DiscoveredDevice(
            ip_address=ip,
            device_type=device_type,
            vendor=vendor,
            username=credentials.username,
            password=credentials.password,
            enable_password=credentials.enable_password,
            ssh_port=credentials.ssh_port,
            protocol="ssh",
            status="active",
            **kwargs
        )

    @staticmethod
    def from_telnet_discovery(ip: str, device_type: str, vendor: str,
                              credentials: DeviceCredentials, **kwargs) -> DiscoveredDevice:
        """Создание устройства из Telnet обнаружения"""
        return DiscoveredDevice(
            ip_address=ip,
            device_type=device_type,
            vendor=vendor,
            username=credentials.username,
            password=credentials.password,
            enable_password=credentials.enable_password,
            telnet_port=credentials.telnet_port,
            protocol="telnet",
            status="active",
            **kwargs
        )