"""
Вспомогательные утилиты
"""

import sys
import logging
from typing import Optional
from pathlib import Path

from config import ScannerConfig


def setup_logging(config: ScannerConfig):
    """
    Настройка логирования

    Args:
        config: Конфигурация сканера
    """
    # Уровень логирования
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Формат сообщений
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Очищаем существующие обработчики
    logging.getLogger().handlers.clear()

    # Создаем форматтер
    formatter = logging.Formatter(log_format, date_format)

    # Файловый обработчик
    file_handler = logging.FileHandler(config.log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Отключаем логирование для некоторых библиотек
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def print_banner():
    """Печать баннера при запуске"""
    banner = """
    ╔══════════════════════════════════════════════════════╗
    ║          АСИНХРОННЫЙ СКАНЕР IP-АДРЕСОВ              ║
    ║          Проверка доступности и времени отклика     ║
    ╚══════════════════════════════════════════════════════╝
    """
    print(banner)


def print_summary(config: ScannerConfig, ip_count: int):
    """
    Печать сводки перед началом сканирования

    Args:
        config: Конфигурация сканера
        ip_count: Количество IP-адресов для сканирования
    """
    print(f"\n{'='*60}")
    print("НАСТРОЙКИ СКАНИРОВАНИЯ:")
    print(f"  Файл с IP-адресами: {config.input_file}")
    print(f"  Количество адресов: {ip_count}")
    print(f"  Файл отчета: {config.output_file}")
    print(f"  Формат отчета: {config.report_format.value}")
    print(f"  Таймаут ping: {config.timeout} сек")
    print(f"  Длительность измерения: {config.ping_duration} сек")
    print(f"  Одновременных запросов: {config.concurrent_limit}")
    print(f"  Максимум попыток: {config.max_retries}")
    print(f"  Показывать прогресс: {'Да' if config.show_progress else 'Нет'}")
    print(f"{'='*60}\n")


def validate_environment() -> bool:
    """
    Проверка окружения

    Returns:
        True если окружение корректно
    """
    import platform
    import subprocess

    try:
        system = platform.system().lower()

        if system == 'windows':
            # Проверяем ping на Windows
            result = subprocess.run(
                ['ping', '/?'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2
            )
        else:
            # Проверяем ping на Linux/macOS
            result = subprocess.run(
                ['ping', '-V'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2
            )

        if result.returncode not in [0, 1]:  # Некоторые системы возвращают 1 для справки
            print("Ошибка: Команда 'ping' недоступна")
            return False

        return True

    except FileNotFoundError:
        print("Ошибка: Команда 'ping' не найдена")
        print("Убедитесь, что ping установлен в системе")
        return False
    except Exception as e:
        print(f"Ошибка проверки окружения: {e}")
        return False


def get_input_file() -> Optional[Path]:
    """
    Получение файла с IP-адресами

    Returns:
        Путь к файлу или None если не найден
    """
    # Стандартные имена файлов
    possible_files = [
        "ips.txt",
        "ip_list.txt",
        "addresses.txt",
        "hosts.txt"
    ]

    for filename in possible_files:
        path = Path(filename)
        if path.exists():
            return path

    return None