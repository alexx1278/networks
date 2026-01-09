"""
Сканер портов для обнаружения сетевых устройств
"""

import socket
import concurrent.futures
import logging
from typing import List, Tuple, Dict, Any
import ipaddress

logger = logging.getLogger(__name__)


class PortScanner:
    """Сканер портов для обнаружения открытых портов"""

    def __init__(self, timeout: int = 3, max_workers: int = 50):
        self.timeout = timeout
        self.max_workers = max_workers

    def scan_single_port(self, ip: str, port: int) -> Tuple[int, bool]:
        """
        Сканирование одного порта

        Args:
            ip: IP адрес
            port: Порт для сканирования

        Returns:
            Кортеж (порт, открыт ли)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()

            is_open = (result == 0)
            return port, is_open

        except Exception as e:
            logger.debug(f"Ошибка при сканировании порта {port} на {ip}: {e}")
            return port, False

    def scan_ports(self, ip: str, ports: List[int]) -> List[int]:
        """
        Сканирование списка портов

        Args:
            ip: IP адрес
            ports: Список портов для сканирования

        Returns:
            Список открытых портов
        """
        logger.debug(f"Сканирование портов на {ip}: {ports}")

        open_ports = []

        # Используем ThreadPoolExecutor для многопоточного сканирования
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Создаем задачи для сканирования портов
            future_to_port = {
                executor.submit(self.scan_single_port, ip, port): port
                for port in ports
            }

            # Обрабатываем результаты
            for future in concurrent.futures.as_completed(future_to_port):
                port = future_to_port[future]
                try:
                    port, is_open = future.result(timeout=self.timeout + 1)
                    if is_open:
                        open_ports.append(port)
                except Exception as e:
                    logger.debug(f"Ошибка при обработке результата порта {port}: {e}")

        logger.debug(f"Открытые порты на {ip}: {open_ports}")
        return open_ports

    def scan_common_ports(self, ip: str) -> List[int]:
        """
        Сканирование наиболее распространенных портов

        Args:
            ip: IP адрес

        Returns:
            Список открытых портов
        """
        common_ports = [
            21,    # FTP
            22,    # SSH
            23,    # Telnet
            25,    # SMTP
            53,    # DNS
            80,    # HTTP
            110,   # POP3
            111,   # RPC
            135,   # MS RPC
            139,   # NetBIOS
            143,   # IMAP
            443,   # HTTPS
            445,   # SMB
            993,   # IMAPS
            995,   # POP3S
            1723,  # PPTP
            3306,  # MySQL
            3389,  # RDP
            5432,  # PostgreSQL
            5900,  # VNC
            8080,  # HTTP Alt
        ]

        return self.scan_ports(ip, common_ports)

    def quick_scan(self, ip: str) -> bool:
        """
        Быстрая проверка доступности устройства

        Args:
            ip: IP адрес

        Returns:
            True если устройство отвечает
        """
        # Проверяем основные порты управления
        management_ports = [22, 23, 80, 443, 2222]
        open_ports = self.scan_ports(ip, management_ports)

        return len(open_ports) > 0

    def scan_ip_range(self, ip_range: str, ports: List[int]) -> Dict[str, List[int]]:
        """
        Сканирование диапазона IP адресов

        Args:
            ip_range: Диапазон IP (например, "192.168.1.0/24" или "192.168.1.1-192.168.1.10")
            ports: Список портов для сканирования

        Returns:
            Словарь {IP: список открытых портов}
        """
        result = {}

        # Парсим диапазон IP
        ip_list = self._parse_ip_range(ip_range)
        if not ip_list:
            logger.error(f"Неверный формат диапазона IP: {ip_range}")
            return result

        logger.info(f"Сканирование диапазона {ip_range} ({len(ip_list)} IP)")

        # Сканируем каждый IP
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ip = {
                executor.submit(self.scan_ports, ip, ports): ip
                for ip in ip_list
            }

            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    open_ports = future.result(timeout=self.timeout * len(ports) + 5)
                    if open_ports:
                        result[ip] = open_ports
                        logger.debug(f"На {ip} открыты порты: {open_ports}")
                except Exception as e:
                    logger.debug(f"Ошибка при сканировании {ip}: {e}")

        return result

    def _parse_ip_range(self, ip_range: str) -> List[str]:
        """Парсинг диапазона IP адресов"""
        ip_list = []

        try:
            # Проверяем формат CIDR
            if '/' in ip_range:
                network = ipaddress.ip_network(ip_range, strict=False)
                for ip in network.hosts():
                    ip_list.append(str(ip))

            # Проверяем формат диапазона
            elif '-' in ip_range:
                start_ip, end_ip = ip_range.split('-')
                start = ipaddress.ip_address(start_ip.strip())
                end = ipaddress.ip_address(end_ip.strip())

                current = start
                while current <= end:
                    ip_list.append(str(current))
                    current = current + 1

            # Одиночный IP
            else:
                ipaddress.ip_address(ip_range)
                ip_list.append(ip_range)

        except ValueError as e:
            logger.error(f"Ошибка парсинга IP диапазона {ip_range}: {e}")
            return []

        return ip_list