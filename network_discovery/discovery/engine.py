"""
Движок обнаружения сетевых устройств
"""

import concurrent.futures
import threading
import time
import logging
from typing import Dict, List, Optional, Any
from models.device import DiscoveredDevice, DeviceCredentials, DeviceFactory
from connectors.protocol_detector import ProtocolDetector
from discovery.device_detector import DeviceDetector

logger = logging.getLogger(__name__)


class NetworkDiscoveryEngine:
    """Основной класс для обнаружения сетевых устройств"""

    def __init__(self, max_workers: int = 10, timeout: int = 5):
        """
        Инициализация Network Discovery

        Args:
            max_workers: Максимальное количество потоков
            timeout: Таймаут подключения
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self.discovered_devices: Dict[str, DiscoveredDevice] = {}
        self.lock = threading.Lock()
        self.protocol_detector = ProtocolDetector(timeout=timeout)
        self.device_detector = DeviceDetector()

    def discover_single_device(self, ip: str, credentials_list: List[DeviceCredentials]) -> Optional[DiscoveredDevice]:
        """
        Обнаружение одного устройства

        Args:
            ip: IP адрес устройства
            credentials_list: Список учетных данных для перебора

        Returns:
            Обнаруженное устройство или None
        """
        logger.info(f"Обнаружение устройства: {ip}")

        # Определяем доступные протоколы
        protocol_info = self.protocol_detector.detect_all_protocols(ip)

        if not protocol_info.get('has_management', False):
            logger.warning(f"Устройство {ip} не имеет доступных протоколов управления")
            return None

        # Пробуем SSH (приоритет)
        if protocol_info.get('ssh', False):
            for creds in credentials_list:
                logger.debug(f"Пробуем SSH подключение с {creds.username} на {ip}")

                device_info = self.device_detector.discover_via_ssh(ip, creds)

                if device_info:
                    # Создаем объект устройства
                    device = DeviceFactory.from_ssh_discovery(
                        ip=ip,
                        device_type=device_info.get('device_type'),
                        vendor=device_info.get('vendor'),
                        credentials=creds,
                        hostname=device_info.get('hostname'),
                        model=device_info.get('model'),
                        os_version=device_info.get('os_version'),
                        serial_number=device_info.get('serial_number'),
                        capabilities=self._get_capabilities(protocol_info)
                    )

                    logger.info(f"Успешно обнаружено {ip} через SSH как {device.device_type}")
                    return device

        # Пробуем Telnet
        if protocol_info.get('telnet', False):
            for creds in credentials_list:
                logger.debug(f"Пробуем Telnet подключение с {creds.username} на {ip}")

                device_info = self.device_detector.discover_via_telnet(ip, creds)

                if device_info:
                    # Создаем объект устройства
                    device = DeviceFactory.from_telnet_discovery(
                        ip=ip,
                        device_type=device_info.get('device_type'),
                        vendor=device_info.get('vendor'),
                        credentials=creds,
                        hostname=device_info.get('hostname'),
                        model=device_info.get('model'),
                        os_version=device_info.get('os_version'),
                        serial_number=device_info.get('serial_number'),
                        capabilities=self._get_capabilities(protocol_info)
                    )

                    logger.info(f"Успешно обнаружено {ip} через Telnet как {device.device_type}")
                    return device

        logger.warning(f"Не удалось обнаружить устройство {ip} с предоставленными учетными данными")
        return None

    def _get_capabilities(self, protocol_info: Dict[str, Any]) -> List[str]:
        """Получение списка возможностей устройства"""
        capabilities = []

        # Протоколы управления
        if protocol_info.get('ssh', False):
            capabilities.append('ssh')
        if protocol_info.get('telnet', False):
            capabilities.append('telnet')

        # Веб-интерфейсы
        if protocol_info.get('http', False):
            capabilities.append('http')
        if protocol_info.get('https', False):
            capabilities.append('https')

        # Сетевые протоколы
        if protocol_info.get('snmp', False):
            capabilities.append('snmp')
        if protocol_info.get('netconf', False):
            capabilities.append('netconf')
        if protocol_info.get('ftp', False):
            capabilities.append('ftp')
        if protocol_info.get('tftp', False):
            capabilities.append('tftp')

        return capabilities

    def discover_devices(self, ip_list: List[str], credentials_list: List[DeviceCredentials]) -> Dict[str, DiscoveredDevice]:
        """
        Обнаружение множества устройств

        Args:
            ip_list: Список IP адресов
            credentials_list: Список учетных данных

        Returns:
            Словарь обнаруженных устройств
        """
        logger.info(f"Начало обнаружения {len(ip_list)} устройств с {self.max_workers} потоками")

        total_devices = len(ip_list)
        discovered_count = 0
        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Создаем задачи для каждого IP
            future_to_ip = {
                executor.submit(self.discover_single_device, ip, credentials_list): ip
                for ip in ip_list
            }

            # Обрабатываем результаты
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    device = future.result(timeout=60)

                    if device:
                        with self.lock:
                            self.discovered_devices[ip] = device
                            discovered_count += 1

                        # Выводим прогресс
                        elapsed_time = time.time() - start_time
                        avg_time = elapsed_time / discovered_count if discovered_count > 0 else 0
                        remaining = total_devices - discovered_count
                        estimated_remaining = avg_time * remaining if avg_time > 0 else 0

                        logger.info(
                            f"Прогресс: {discovered_count}/{total_devices} "
                            f"({(discovered_count/total_devices*100):.1f}%) "
                            f"Время: {elapsed_time:.1f}с "
                            f"Осталось: ~{estimated_remaining:.1f}с"
                        )

                except Exception as e:
                    logger.error(f"Ошибка обнаружения устройства {ip}: {e}")

        elapsed_time = time.time() - start_time
        logger.info(f"Обнаружение завершено за {elapsed_time:.2f} секунд")
        logger.info(f"Найдено {len(self.discovered_devices)} устройств")

        return self.discovered_devices

    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики по обнаруженным устройствам"""
        stats = {
            'total_devices': len(self.discovered_devices),
            'vendors': {},
            'device_types': {},
            'protocols': {'ssh': 0, 'telnet': 0},
            'status': {'active': 0, 'unknown': 0}
        }

        for device in self.discovered_devices.values():
            # Производители
            vendor = device.vendor or 'Неизвестно'
            stats['vendors'][vendor] = stats['vendors'].get(vendor, 0) + 1

            # Типы устройств
            device_type = device.device_type or 'unknown'
            stats['device_types'][device_type] = stats['device_types'].get(device_type, 0) + 1

            # Протоколы
            protocol = device.protocol
            if protocol in stats['protocols']:
                stats['protocols'][protocol] += 1

            # Статус
            status = device.status
            stats['status'][status] = stats['status'].get(status, 0) + 1

        return stats

    def get_devices_by_vendor(self, vendor: str) -> List[DiscoveredDevice]:
        """
        Получение устройств по производителю

        Args:
            vendor: Производитель устройства

        Returns:
            Список устройств
        """
        return [
            device for device in self.discovered_devices.values()
            if device.vendor and device.vendor.lower() == vendor.lower()
        ]

    def get_devices_by_type(self, device_type: str) -> List[DiscoveredDevice]:
        """
        Получение устройств по типу

        Args:
            device_type: Тип устройства

        Returns:
            Список устройств
        """
        return [
            device for device in self.discovered_devices.values()
            if device.device_type and device.device_type.lower() == device_type.lower()
        ]

    def clear(self):
        """Очистка обнаруженных устройств"""
        self.discovered_devices.clear()
        logger.info("Обнаруженные устройства очищены")