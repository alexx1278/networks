"""
Сохранение инвентаря сетевых устройств
"""

import yaml
import json
import csv
from datetime import datetime
from typing import Dict
from models.device import DiscoveredDevice
import logging

logger = logging.getLogger(__name__)


class InventorySaver:
    """Класс для сохранения инвентаря в различных форматах"""

    @staticmethod
    def save_yaml(devices: Dict[str, DiscoveredDevice], filename: str) -> str:
        """
        Сохранение инвентаря в YAML формате

        Args:
            devices: Словарь устройств
            filename: Имя файла

        Returns:
            Путь к сохраненному файлу
        """
        inventory = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_devices': len(devices),
                'generator': 'NetworkDiscovery v2.0'
            },
            'devices': {ip: device.to_dict() for ip, device in devices.items()}
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                yaml.dump(inventory, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            logger.info(f"Инвентарь сохранен в YAML: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Ошибка при сохранении YAML: {e}")
            raise

    @staticmethod
    def save_json(devices: Dict[str, DiscoveredDevice], filename: str) -> str:
        """
        Сохранение инвентаря в JSON формате

        Args:
            devices: Словарь устройств
            filename: Имя файла

        Returns:
            Путь к сохраненному файлу
        """
        inventory = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_devices': len(devices),
                'generator': 'NetworkDiscovery v2.0'
            },
            'devices': {ip: device.to_dict() for ip, device in devices.items()}
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(inventory, f, indent=2, ensure_ascii=False)

            logger.info(f"Инвентарь сохранен в JSON: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Ошибка при сохранении JSON: {e}")
            raise

    @staticmethod
    def save_csv(devices: Dict[str, DiscoveredDevice], filename: str) -> str:
        """
        Сохранение инвентаря в CSV формате

        Args:
            devices: Словарь устройств
            filename: Имя файла

        Returns:
            Путь к сохраненному файлу
        """
        fieldnames = [
            'ip_address', 'hostname', 'device_type', 'vendor', 'model',
            'os_version', 'serial_number', 'protocol', 'username',
            'ssh_port', 'telnet_port', 'status', 'last_seen'
        ]

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for device in devices.values():
                    row = {
                        'ip_address': device.ip_address,
                        'hostname': device.hostname or '',
                        'device_type': device.device_type or '',
                        'vendor': device.vendor or '',
                        'model': device.model or '',
                        'os_version': device.os_version or '',
                        'serial_number': device.serial_number or '',
                        'protocol': device.protocol,
                        'username': device.username or '',
                        'ssh_port': device.ssh_port,
                        'telnet_port': device.telnet_port,
                        'status': device.status,
                        'last_seen': device.last_seen
                    }
                    writer.writerow(row)

            logger.info(f"Инвентарь сохранен в CSV: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Ошибка при сохранении CSV: {e}")
            raise

    @staticmethod
    def save_netmiko_inventory(devices: Dict[str, DiscoveredDevice], filename: str) -> str:
        """
        Сохранение инвентаря в формате для Netmiko

        Args:
            devices: Словарь устройств
            filename: Имя файла

        Returns:
            Путь к сохраненному файлу
        """
        netmiko_inventory = {
            'ssh_devices': [],
            'telnet_devices': [],
            'all_devices': []
        }

        for device in devices.values():
            config = device.to_netmiko_config()
            config['name'] = device.hostname or device.ip_address

            # Добавляем в общий список
            netmiko_inventory['all_devices'].append(config)

            # Добавляем в соответствующий список по протоколу
            if device.protocol == 'ssh':
                netmiko_inventory['ssh_devices'].append(config)
            elif device.protocol == 'telnet':
                netmiko_inventory['telnet_devices'].append(config)

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                yaml.dump(netmiko_inventory, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Инвентарь Netmiko сохранен: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Ошибка при сохранении инвентаря Netmiko: {e}")
            raise

    @staticmethod
    def save_ansible_inventory(devices: Dict[str, DiscoveredDevice], filename: str) -> str:
        """
        Сохранение инвентаря в формате для Ansible

        Args:
            devices: Словарь устройств
            filename: Имя файла

        Returns:
            Путь к сохраненному файлу
        """
        ansible_inventory = {
            'all': {
                'hosts': {},
                'children': {}
            }
        }

        for device in devices.values():
            hostname = device.hostname or device.ip_address

            # Добавляем хост
            ansible_inventory['all']['hosts'][hostname] = {
                'ansible_host': device.ip_address,
                'ansible_user': device.username,
                'ansible_ssh_pass': device.password,
                'ansible_become_pass': device.enable_password,
                'ansible_network_os': device.device_type,
                'ansible_port': device.ssh_port if device.protocol == 'ssh' else device.telnet_port,
                'device_vendor': device.vendor,
                'device_model': device.model,
                'device_os_version': device.os_version,
                'device_protocol': device.protocol
            }

            # Создаем группы по производителю
            if device.vendor:
                vendor_group = device.vendor.lower().replace('/', '_').replace(' ', '_')
                if vendor_group not in ansible_inventory['all']['children']:
                    ansible_inventory['all']['children'][vendor_group] = {'hosts': {}}
                ansible_inventory['all']['children'][vendor_group]['hosts'][hostname] = {}

            # Создаем группы по типу устройства
            if device.device_type:
                type_group = device.device_type.lower().replace('_', '-')
                if type_group not in ansible_inventory['all']['children']:
                    ansible_inventory['all']['children'][type_group] = {'hosts': {}}
                ansible_inventory['all']['children'][type_group]['hosts'][hostname] = {}

            # Создаем группы по протоколу
            if device.protocol:
                protocol_group = f"{device.protocol}_devices"
                if protocol_group not in ansible_inventory['all']['children']:
                    ansible_inventory['all']['children'][protocol_group] = {'hosts': {}}
                ansible_inventory['all']['children'][protocol_group]['hosts'][hostname] = {}

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                yaml.dump(ansible_inventory, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Инвентарь Ansible сохранен: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Ошибка при сохранении инвентаря Ansible: {e}")
            raise

    @staticmethod
    def save_report(devices: Dict[str, DiscoveredDevice], filename: str) -> str:
        """
        Сохранение текстового отчета

        Args:
            devices: Словарь устройств
            filename: Имя файла

        Returns:
            Путь к сохраненному файлу
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Отчет об обнаружении сетевых устройств\n")
                f.write(f"Сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Всего устройств: {len(devices)}\n")
                f.write("=" * 100 + "\n\n")

                # Статистика
                vendors = {}
                device_types = {}
                protocols = {'ssh': 0, 'telnet': 0}

                for device in devices.values():
                    vendor = device.vendor or 'Неизвестно'
                    device_type = device.device_type or 'unknown'
                    protocol = device.protocol or 'unknown'

                    vendors[vendor] = vendors.get(vendor, 0) + 1
                    device_types[device_type] = device_types.get(device_type, 0) + 1

                    if protocol in protocols:
                        protocols[protocol] += 1

                f.write("СТАТИСТИКА:\n")
                f.write("-" * 50 + "\n")
                f.write("Производители:\n")
                for vendor, count in sorted(vendors.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {vendor}: {count}\n")

                f.write("\nТипы устройств:\n")
                for dev_type, count in sorted(device_types.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {dev_type}: {count}\n")

                f.write("\nПротоколы подключения:\n")
                f.write(f"  SSH: {protocols['ssh']}\n")
                f.write(f"  Telnet: {protocols['telnet']}\n")

                f.write("\n" + "=" * 100 + "\n")
                f.write("ДЕТАЛЬНЫЙ СПИСОК УСТРОЙСТВ:\n")
                f.write("=" * 100 + "\n\n")

                for ip, device in devices.items():
                    f.write(f"IP: {ip}\n")
                    f.write(f"  Hostname: {device.hostname}\n")
                    f.write(f"  Тип: {device.device_type}\n")
                    f.write(f"  Производитель: {device.vendor}\n")
                    f.write(f"  Модель: {device.model}\n")
                    f.write(f"  Версия ОС: {device.os_version}\n")
                    f.write(f"  Протокол: {device.protocol}\n")
                    f.write(f"  Пользователь: {device.username}\n")
                    f.write(f"  Порт SSH: {device.ssh_port}\n")
                    f.write(f"  Порт Telnet: {device.telnet_port}\n")
                    f.write(f"  Статус: {device.status}\n")
                    f.write("-" * 50 + "\n")

            logger.info(f"Текстовый отчет сохранен: {filename}")
            return filename

        except Exception as e:
            logger.error(f"Ошибка при сохранении отчета: {e}")
            raise