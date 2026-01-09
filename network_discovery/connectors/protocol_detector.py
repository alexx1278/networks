#!/usr/bin/env python3
"""
Детектор протоколов для сетевых устройств
"""

import socket
import concurrent.futures
import logging
from typing import Dict, Any
from discovery.port_scanner import PortScanner

logger = logging.getLogger(__name__)


class ProtocolDetector:
    """Детектор доступных протоколов на устройстве"""

    # Стандартные порты для протоколов
    PROTOCOL_PORTS = {
        'ssh': [22, 2222, 22222],
        'telnet': [23, 2323],
        'snmp': [161],
        'http': [80, 8080],
        'https': [443, 8443],
        'netconf': [830],
        'ftp': [21],
        'tftp': [69],
        'syslog': [514],
        'radius': [1812, 1813],
        'tacacs': [49],
        'dns': [53],
        'ntp': [123],
        'ldap': [389, 636],
        'kerberos': [88]
    }

    def __init__(self, timeout: int = 3, max_workers: int = 10):
        self.timeout = timeout
        self.max_workers = max_workers
        self.port_scanner = PortScanner(timeout=timeout)

    def detect_all_protocols(self, ip: str) -> Dict[str, Any]:
        """
        Обнаружение всех доступных протоколов на устройстве

        Args:
            ip: IP адрес устройства

        Returns:
            Словарь с информацией о доступных протоколах
        """
        logger.debug(f"Обнаружение протоколов на {ip}")

        # Собираем все порты для сканирования
        all_ports = []
        for ports in self.PROTOCOL_PORTS.values():
            all_ports.extend(ports)

        # Сканируем порты
        open_ports = self.port_scanner.scan_ports(ip, all_ports)

        # Определяем какие протоколы доступны
        protocol_info = {'open_ports': open_ports}

        for protocol, ports in self.PROTOCOL_PORTS.items():
            # Проверяем, открыт ли хотя бы один порт для протокола
            is_open = any(port in open_ports for port in ports)
            protocol_info[protocol] = is_open

            # Если протокол доступен, определяем точный порт
            if is_open:
                for port in ports:
                    if port in open_ports:
                        protocol_info[f'{protocol}_port'] = port
                        break

        # Дополнительная информация
        protocol_info['has_management'] = protocol_info.get('ssh', False) or protocol_info.get('telnet', False)
        protocol_info['has_web'] = protocol_info.get('http', False) or protocol_info.get('https', False)

        logger.debug(f"Результат обнаружения протоколов на {ip}: {protocol_info}")
        return protocol_info

    def detect_management_protocols(self, ip: str) -> Dict[str, bool]:
        """
        Обнаружение только протоколов управления

        Args:
            ip: IP адрес устройства

        Returns:
            Словарь с доступными протоколами управления
        """
        management_ports = []
        management_protocols = ['ssh', 'telnet', 'http', 'https']

        for protocol in management_protocols:
            management_ports.extend(self.PROTOCOL_PORTS.get(protocol, []))

        open_ports = self.port_scanner.scan_ports(ip, management_ports)

        result = {}
        for protocol in management_protocols:
            ports = self.PROTOCOL_PORTS.get(protocol, [])
            result[protocol] = any(port in open_ports for port in ports)

        return result

    def check_specific_protocol(self, ip: str, protocol: str, port: int = None) -> bool:
        """
        Проверка конкретного протокола

        Args:
            ip: IP адрес устройства
            protocol: Протокол для проверки
            port: Конкретный порт (если None - проверяются все порты протокола)

        Returns:
            True если протокол доступен
        """
        if protocol not in self.PROTOCOL_PORTS:
            logger.warning(f"Неизвестный протокол: {protocol}")
            return False

        if port:
            ports_to_check = [port]
        else:
            ports_to_check = self.PROTOCOL_PORTS[protocol]

        open_ports = self.port_scanner.scan_ports(ip, ports_to_check)
        return len(open_ports) > 0

    def get_recommended_protocol(self, ip: str) -> Dict[str, Any]:
        """
        Получение рекомендуемого протокола для подключения

        Args:
            ip: IP адрес устройства

        Returns:
            Словарь с рекомендуемым протоколом и портом
        """
        protocol_info = self.detect_all_protocols(ip)

        # Приоритет протоколов (от высшего к низшему)
        protocol_priority = [
            ('ssh', 22),
            ('ssh', 2222),
            ('telnet', 23),
            ('https', 443),
            ('http', 80)
        ]

        for protocol, default_port in protocol_priority:
            ports = self.PROTOCOL_PORTS.get(protocol, [default_port])

            # Проверяем стандартный порт
            if protocol_info.get(protocol, False) and default_port in protocol_info.get('open_ports', []):
                return {
                    'protocol': protocol,
                    'port': default_port,
                    'secure': protocol in ['ssh', 'https']
                }

            # Проверяем альтернативные порты
            for port in ports:
                if port in protocol_info.get('open_ports', []):
                    return {
                        'protocol': protocol,
                        'port': port,
                        'secure': protocol in ['ssh', 'https']
                    }

        # Если не найдено подходящих протоколов
        return {
            'protocol': None,
            'port': None,
            'secure': False
        }