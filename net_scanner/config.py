"""
Модуль конфигурации и моделей данных
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum
import logging


class ReportFormat(Enum):
    """Формат отчета"""
    TEXT = "text"
    JSON = "json"
    CSV = "csv"


class PingResult(Enum):
    """Результат проверки ping"""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    ERROR = "error"


@dataclass
class ScannerConfig:
    """Конфигурация сканера с валидацией"""

    # Основные пути
    input_file: str = "ips.txt"
    output_file: str = "report.txt"
    log_file: str = "scanner.log"

    # Параметры ping
    timeout: float = 2.0
    ping_count: int = 1
    ping_duration: int = 60
    ping_interval: float = 1.0

    # Параметры производительности
    concurrent_limit: int = 100
    max_retries: int = 3

    # Настройки фильтрации
    exclude_self: bool = True
    validate_ips: bool = True

    # Настройки вывода
    report_format: ReportFormat = ReportFormat.TEXT
    log_level: str = "INFO"
    show_progress: bool = True
    progress_update_interval: int = 10  # Процентов

    # Дополнительные настройки
    save_raw_results: bool = False
    raw_results_file: str = "raw_results.json"

    def __post_init__(self):
        """Валидация значений после инициализации"""
        self._validate_values()

    def _validate_values(self):
        """Проверка корректности значений"""
        if self.timeout <= 0:
            raise ValueError("timeout должен быть положительным числом")
        if self.ping_count <= 0:
            raise ValueError("ping_count должен быть положительным числом")
        if self.ping_duration <= 0:
            raise ValueError("ping_duration должен быть положительным числом")
        if self.concurrent_limit <= 0:
            raise ValueError("concurrent_limit должен быть положительным числом")
        if self.max_retries <= 0:
            raise ValueError("max_retries должен быть положительным числом")
        if self.ping_interval <= 0:
            raise ValueError("ping_interval должен быть положительным числом")

        # Проверка log_level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"log_level должен быть одним из: {valid_log_levels}")

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScannerConfig":
        """Создание из словаря"""
        # Преобразуем строковый формат в Enum
        if "report_format" in data and isinstance(data["report_format"], str):
            try:
                data["report_format"] = ReportFormat(data["report_format"].lower())
            except ValueError:
                data["report_format"] = ReportFormat.TEXT

        return cls(**data)


class ConfigLoader:
    """Загрузчик конфигурации"""

    CONFIG_FILES = [
        "scanner_config.json",
        "config/scanner.json",
        "config.json"
    ]

    DEFAULT_CONFIG = {
        "input_file": "ips.txt",
        "output_file": "report.txt",
        "log_file": "scanner.log",
        "timeout": 2.0,
        "ping_count": 1,
        "ping_duration": 60,
        "ping_interval": 1.0,
        "concurrent_limit": 100,
        "max_retries": 3,
        "exclude_self": True,
        "validate_ips": True,
        "report_format": "text",
        "log_level": "INFO",
        "show_progress": True,
        "progress_update_interval": 10,
        "save_raw_results": False,
        "raw_results_file": "raw_results.json"
    }

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> ScannerConfig:
        """
        Загрузка конфигурации

        Args:
            config_path: Путь к файлу конфигурации (опционально)

        Returns:
            Объект конфигурации
        """
        config_dict = cls.DEFAULT_CONFIG.copy()

        # Ищем файл конфигурации
        found_config = cls._find_config_file(config_path)

        if found_config:
            try:
                user_config = cls._load_config_file(found_config)
                config_dict.update(user_config)
                logging.info(f"Загружена конфигурация из {found_config}")
            except Exception as e:
                logging.warning(f"Ошибка загрузки конфигурации: {e}")
                logging.info("Используются значения по умолчанию")
        else:
            logging.info("Конфигурационный файл не найден, используются значения по умолчанию")
            logging.info("Создан файл конфигурации по умолчанию: scanner_config.json")
            cls._save_default_config()

        return ScannerConfig.from_dict(config_dict)

    @classmethod
    def _find_config_file(cls, config_path: Optional[str] = None) -> Optional[Path]:
        """Поиск файла конфигурации"""
        if config_path:
            path = Path(config_path)
            if path.exists():
                return path
            return None

        for config_file in cls.CONFIG_FILES:
            path = Path(config_file)
            if path.exists():
                return path

        return None

    @staticmethod
    def _load_config_file(filepath: Path) -> Dict[str, Any]:
        """Загрузка конфигурации из файла"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def _save_default_config(cls):
        """Сохранение конфигурации по умолчанию"""
        default_path = Path("scanner_config.json")
        with open(default_path, 'w', encoding='utf-8') as f:
            json.dump(cls.DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)


@dataclass
class ScanResult:
    """Результат сканирования одного хоста"""
    ip: str
    is_alive: bool
    avg_latency: Optional[float] = None
    latencies: List[float] = field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    last_error: Optional[str] = None


@dataclass
class ScanSummary:
    """Сводка по сканированию"""
    total_hosts: int = 0
    alive_hosts: int = 0
    dead_hosts: int = 0
    scan_duration: float = 0.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def alive_percent(self) -> float:
        """Процент доступных хостов"""
        if self.total_hosts == 0:
            return 0.0
        return (self.alive_hosts / self.total_hosts) * 100

    @property
    def dead_percent(self) -> float:
        """Процент недоступных хостов"""
        if self.total_hosts == 0:
            return 0.0
        return (self.dead_hosts / self.total_hosts) * 100