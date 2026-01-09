#!/usr/bin/env python3
"""
Детектор типа и производителя сетевых устройств
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from connectors.ssh_client import SSHClient
from connectors.telnet_client import TelnetClient
from models.device import Protocol, DeviceCredentials

logger = logging.getLogger(__name__)


class DeviceDetector:
    """Детектор типа и производителя сетевых устройств"""

    # Шаблоны для определения производителя
    VENDOR_PATTERNS = {
        'Cisco': [
            r'cisco',
            r'ios',
            r'ios\s+xe',
            r'ios\s+xr',
            r'nexus',
            r'asa',
            r'cat[0-9]+',
            r'ws-[c|s]',
            r'c[0-9]+',
            r'asr[0-9]+',
            r'isr[0-9]+'
        ],
        'Juniper': [
            r'juniper',
            r'junos',
            r'srx',
            r'ex[0-9]+',
            r'mx[0-9]+',
            r'ptx[0-9]+',
            r'qfx[0-9]+'
        ],
        'HP/HPE/Aruba': [
            r'procurve',
            r'aruba',
            r'hp',
            r'comware',
            r'1910',
            r'2920',
            r'3800',
            r'5400',
            r'8200'
        ],
        'MikroTik': [
            r'mikrotik',
            r'routeros',
            r'ccr',
            r'rb',
            r'hex',
            r'hap'
        ],
        'Arista': [
            r'arista',
            r'eos',
            r'dcs'
        ],
        'Palo Alto': [
            r'palo',
            r'pan-os',
            r'pa-[0-9]+'
        ],
        'Fortinet': [
            r'fortinet',
            r'fortios',
            r'fortigate'
        ],
        'Ubiquiti': [
            r'ubiquiti',
            r'edgerouter',
            r'edgeswitch',
            r'unifi'
        ],
        'Linux': [
            r'linux',
            r'ubuntu',
            r'debian',
            r'centos',
            r'red\s+hat',
            r'fedora'
        ],
        'Huawei': [
            r'huawei',
            r'vrp',
            r'ce[0-9]+',
            r'ne[0-9]+'
        ],
        'Dell': [
            r'dell',
            r'powerconnect',
            r'force10',
            r'n[0-9]+'
        ],
        'Extreme': [
            r'extreme',
            r'exos'
        ],
        'Brocade': [
            r'brocade',
            r'vdx',
            r'netiron',
            r'fastiron'
        ],
        'Nokia': [
            r'nokia',
            r'sr\s+os',
            r'alu'
        ]
    }

    # Соответствие vendor -> device_type для Netmiko
    VENDOR_TO_DEVICE_TYPE = {
        'Cisco': {
            'ios': 'cisco_ios',
            'ios-xe': 'cisco_xe',
            'ios-xr': 'cisco_xr',
            'nx-os': 'cisco_nxos',
            'asa': 'cisco_asa',
            's300': 'cisco_s300',
            'wlc': 'cisco_wlc',
            'ios-telnet': 'cisco_ios_telnet',
            'xe-telnet': 'cisco_xe_telnet'
        },
        'Juniper': {
            'junos': 'juniper',
            'junos-telnet': 'juniper_telnet',
            'screenos': 'juniper_screenos'
        },
        'HP/HPE/Aruba': {
            'procurve': 'hp_procurve',
            'comware': 'hp_comware',
            'aruba': 'aruba_osswitch',
            'procurve-telnet': 'hp_procurve_telnet'
        },
        'MikroTik': {
            'routeros': 'mikrotik_routeros',
            'routeros-telnet': 'mikrotik_routeros_telnet'
        },
        'Arista': {
            'eos': 'arista_eos',
            'eos-telnet': 'arista_eos_telnet'
        },
        'Palo Alto': {
            'pan-os': 'paloalto_panos',
            'pan-os-telnet': 'paloalto_panos_telnet'
        },
        'Fortinet': {
            'fortios': 'fortinet',
            'fortios-telnet': 'fortinet_telnet'
        },
        'Ubiquiti': {
            'edge': 'ubiquiti_edge',
            'edgeswitch': 'ubiquiti_edgeswitch'
        },
        'Linux': {
            'linux': 'linux',
            'linux-telnet': 'linux_telnet'
        },
        'Huawei': {
            'vrp': 'huawei',
            'vrp-telnet': 'huawei_telnet'
        },
        'Dell': {
            'powerconnect': 'dell_powerconnect',
            'force10': 'dell_force10',
            'os6': 'dell_os6',
            'os10': 'dell_os10'
        }
    }

    # Команды для обнаружения устройств
    DISCOVERY_COMMANDS = [
        'show version',
        'show ver',
        'version',
        'display version',
        'cat /etc/os-release',
        'uname -a',
        '/system resource print',
        'get system status',
        'show system',
        'show inventory'
    ]

    def __init__(self):
        self.cache = {}

    def detect_vendor(self, output: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Определение производителя и модели по выводу команды

        Args:
            output: Вывод команды с устройства

        Returns:
            Кортеж (производитель, модель)
        """
        output_lower = output.lower()

        # Проверяем кэш
        cache_key = hash(output[:500])
        if cache_key in self.cache:
            return self.cache[cache_key]

        vendor = None
        model = None

        # Ищем производителя
        for vendor_name, patterns in self.VENDOR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, output_lower):
                    vendor = vendor_name

                    # Пробуем определить модель
                    model = self._extract_model(output, vendor_name)

                    # Сохраняем в кэш
                    self.cache[cache_key] = (vendor, model)
                    return vendor, model

        # Если производитель не найден, пробуем по ключевым словам
        if 'cisco' in output_lower:
            vendor = 'Cisco'
        elif 'juniper' in output_lower:
            vendor = 'Juniper'
        elif 'mikrotik' in output_lower:
            vendor = 'MikroTik'
        elif 'linux' in output_lower:
            vendor = 'Linux'

        if vendor:
            model = self._extract_model(output, vendor)
            self.cache[cache_key] = (vendor, model)

        return vendor, model

    def _extract_model(self, output: str, vendor: str) -> Optional[str]:
        """Извлечение модели устройства из вывода"""
        if vendor == 'Cisco':
            patterns = [
                r'[Cc]isco\s+(\S+)\s+\(',
                r'[Mm]odel\s*\.*:\s*(\S+)',
                r'[Pp]latform:\s*(\S+)',
                r'[Cc][Ss][Rr]?([0-9]+)',
                r'[Cc]atalyst\s+([0-9]+)'
            ]
        elif vendor == 'Juniper':
            patterns = [
                r'[Mm]odel:\s*(\S+)',
                r'[Mm]odel\s+number:\s*(\S+)',
                r'([SM]X|EX|QFX|PTX)[0-9]+'
            ]
        elif vendor == 'MikroTik':
            patterns = [
                r'platform:\s*(\S+)',
                r'[Cc][Cc][Rr]([0-9]+)',
                r'[Rr][Bb]([0-9]+)'
            ]
        elif vendor == 'Linux':
            patterns = [
                r'[Mm]odel\s*\.*:\s*(\S+)',
                r'[Pp]roduct\s+name:\s*(\S+)'
            ]
        else:
            patterns = [
                r'[Mm]odel\s*\.*:\s*(\S+)',
                r'[Pp]latform:\s*(\S+)',
                r'[Pp]roduct\s+name:\s*(\S+)'
            ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def extract_version(self, output: str) -> Optional[str]:
        """Извлечение версии ОС из вывода"""
        version_patterns = [
            r'[Vv]ersion\s+(\S+)',
            r'[Ii][Oo][Ss]\s+[Vv]ersion\s+(\S+)',
            r'[Jj]UNOS\s+(\S+)',
            r'[Vv]ERSION\s*=\s*"([^"]+)"',
            r'[Rr]elease\s+(\S+)',
            r'[Ss]oftware\s+[Vv]ersion\s+(\S+)'
        ]

        for pattern in version_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def extract_serial(self, output: str) -> Optional[str]:
        """Извлечение серийного номера из вывода"""
        serial_patterns = [
            r'[Ss]erial\s+[Nn]umber\s*\.*:\s*(\S+)',
            r'[Ss]erial\s*#\s*\.*:\s*(\S+)',
            r'[Ss][Nn]\s*:\s*(\S+)',
            r'[Ss]ystem\s+[Ss]erial\s+[Nn]umber\s*\.*:\s*(\S+)'
        ]

        for pattern in serial_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def determine_device_type(self, vendor: str, output: str) -> Optional[str]:
        """
        Определение device_type для Netmiko

        Args:
            vendor: Производитель устройства
            output: Вывод команды с устройства

        Returns:
            device_type для Netmiko
        """
        if not vendor:
            return None

        output_lower = output.lower()

        # Для Cisco определяем точный тип
        if vendor == 'Cisco':
            if 'asa' in output_lower:
                return 'cisco_asa'
            elif 'nexus' in output_lower or 'nx-os' in output_lower:
                return 'cisco_nxos'
            elif 'ios-xe' in output_lower:
                return 'cisco_xe'
            elif 'ios-xr' in output_lower:
                return 'cisco_xr'
            else:
                return 'cisco_ios'

        # Для других вендоров берем из словаря
        elif vendor in self.VENDOR_TO_DEVICE_TYPE:
            # Пробуем определить подтип по ключевым словам
            for subtype in self.VENDOR_TO_DEVICE_TYPE[vendor]:
                if subtype.replace('-', ' ') in output_lower:
                    return self.VENDOR_TO_DEVICE_TYPE[vendor][subtype]

            # Возвращаем первый доступный тип
            return list(self.VENDOR_TO_DEVICE_TYPE[vendor].values())[0]

        return None

    def analyze_output(self, output: str) -> Dict[str, Any]:
        """
        Полный анализ вывода устройства

        Args:
            output: Вывод команды с устройства

        Returns:
            Словарь с информацией об устройстве
        """
        result = {
            'raw_output': output[:1000],
            'vendor': None,
            'model': None,
            'os_version': None,
            'serial_number': None,
            'device_type': None
        }

        if not output or len(output.strip()) < 10:
            return result

        # Определяем производителя и модель
        vendor, model = self.detect_vendor(output)
        result['vendor'] = vendor
        result['model'] = model

        # Извлекаем версию ОС
        result['os_version'] = self.extract_version(output)

        # Извлекаем серийный номер
        result['serial_number'] = self.extract_serial(output)

        # Определяем device_type
        if vendor:
            result['device_type'] = self.determine_device_type(vendor, output)

        return result

    def discover_via_ssh(self, ip: str, credentials: DeviceCredentials) -> Optional[Dict[str, Any]]:
        """
        Обнаружение устройства через SSH

        Args:
            ip: IP адрес устройства
            credentials: Учетные данные

        Returns:
            Словарь с информацией об устройстве или None
        """
        try:
            with SSHClient() as ssh_client:
                success, error = ssh_client.connect(ip, credentials)

                if not success:
                    logger.debug(f"Не удалось подключиться по SSH к {ip}: {error}")
                    return None

                # Пробуем разные команды для обнаружения
                for command in self.DISCOVERY_COMMANDS:
                    success, output = ssh_client.execute_command(command, timeout=5)

                    if success and output and len(output.strip()) > 10:
                        device_info = self.analyze_output(output)

                        # Пробуем получить hostname
                        hostname_success, hostname_output = ssh_client.execute_command('hostname', timeout=3)
                        if hostname_success and hostname_output:
                            device_info['hostname'] = hostname_output.strip()
                        else:
                            device_info['hostname'] = ip

                        return device_info

                return None

        except Exception as e:
            logger.debug(f"Ошибка при SSH обнаружении {ip}: {e}")
            return None

    def discover_via_telnet(self, ip: str, credentials: DeviceCredentials) -> Optional[Dict[str, Any]]:
        """
        Обнаружение устройства через Telnet

        Args:
            ip: IP адрес устройства
            credentials: Учетные данные

        Returns:
            Словарь с информацией об устройстве или None
        """
        try:
            with TelnetClient() as telnet_client:
                success, error = telnet_client.connect(ip, credentials)

                if not success:
                    logger.debug(f"Не удалось подключиться по Telnet к {ip}: {error}")
                    return None

                # Пробуем разные команды для обнаружения
                for command in self.DISCOVERY_COMMANDS:
                    success, output = telnet_client.send_command(command, timeout=5)

                    if success and output and len(output.strip()) > 10:
                        device_info = self.analyze_output(output)

                        # Пробуем получить hostname
                        hostname_success, hostname_output = telnet_client.send_command('hostname', timeout=3)
                        if hostname_success and hostname_output:
                            device_info['hostname'] = hostname_output.strip()
                        else:
                            device_info['hostname'] = ip

                        return device_info

                return None

        except Exception as e:
            logger.debug(f"Ошибка при Telnet обнаружении {ip}: {e}")
            return None