"""
Настройка логирования для проекта
"""

import logging
import sys
from datetime import datetime
import os


def setup_logger(name: str = __name__, log_level: int = logging.INFO) -> logging.Logger:
    """
    Настройка логгера с выводом в консоль и файл

    Args:
        name: Имя логгера
        log_level: Уровень логирования

    Returns:
        Настроенный логгер
    """
    # Создаем директорию для логов если её нет
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Формат логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Очищаем существующие обработчики
    logger.handlers.clear()

    # Форматтер
    formatter = logging.Formatter(log_format, date_format)

    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # Обработчик для файла
    log_filename = f"{log_dir}/network_discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)

    # Отключаем логирование от других библиотек если не в DEBUG режиме
    if log_level > logging.DEBUG:
        logging.getLogger('paramiko').setLevel(logging.WARNING)
        logging.getLogger('telnetlib').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)

    return logger