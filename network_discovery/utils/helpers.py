"""
Вспомогательные функции для Network Discovery
"""

import sys
import os
import platform
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def validate_ip_address(ip: str) -> bool:
    """
    Валидация IP адреса

    Args:
        ip: IP адрес для проверки

    Returns:
        True если IP валиден
    """
    try:
        import ipaddress
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_port(port: int) -> bool:
    """
    Валидация номера порта

    Args:
        port: Номер порта

    Returns:
        True если порт валиден
    """
    return 1 <= port <= 65535


def get_system_info() -> Dict[str, str]:
    """
    Получение информации о системе

    Returns:
        Словарь с информацией о системе
    """
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'system': platform.system(),
        'release': platform.release(),
        'machine': platform.machine(),
        'processor': platform.processor()
    }


def calculate_progress(current: int, total: int) -> Dict[str, Any]:
    """
    Расчет прогресса выполнения

    Args:
        current: Текущий прогресс
        total: Общее количество

    Returns:
        Словарь с информацией о прогрессе
    """
    if total == 0:
        return {
            'current': 0,
            'total': 0,
            'percentage': 0,
            'remaining': 0
        }

    percentage = (current / total) * 100

    return {
        'current': current,
        'total': total,
        'percentage': round(percentage, 1),
        'remaining': total - current
    }


def format_bytes(size: int) -> str:
    """
    Форматирование размера в байтах в читаемый вид

    Args:
        size: Размер в байтах

    Returns:
        Отформатированная строка
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def check_dependencies() -> List[str]:
    """
    Проверка необходимых зависимостей

    Returns:
        Список отсутствующих зависимостей
    """
    missing = []

    required_packages = [
        ('paramiko', 'paramiko'),
        ('yaml', 'pyyaml'),
        ('concurrent', 'concurrent.futures'),
        ('ipaddress', 'ipaddress'),
        ('socket', 'socket'),
        ('telnetlib', 'telnetlib'),
    ]

    for import_name, package_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package_name)

    return missing


def setup_environment():
    """Настройка окружения для работы скрипта"""
    # Создаем необходимые директории
    directories = ['logs', 'inventory', 'reports', 'config']

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    # Настраиваем кодировку
    if platform.system() == 'Windows':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def print_banner():
    """Вывод баннера приложения"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                  NETWORK DEVICE DISCOVERY                    ║
║                    Version 2.0 (Modular)                     ║
║            SSH & Telnet Network Inventory Builder            ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def get_color_codes() -> Dict[str, str]:
    """
    Получение кодов цветов для терминала

    Returns:
        Словарь с кодами цветов
    """
    colors = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'white': '\033[37m'
    }

    # Проверяем поддержку цветов
    if platform.system() == 'Windows':
        try:
            import colorama
            colorama.init()
            return colors
        except ImportError:
            # Без colorama цвета не работают на Windows
            return {k: '' for k in colors.keys()}

    return colors