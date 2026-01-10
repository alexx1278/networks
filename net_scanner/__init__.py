"""
Асинхронный сканер IP-адресов
"""

__version__ = "1.0.0"
__author__ = "IP Scanner Team"

from .config import ScannerConfig, PingResult
from .scanner import AsyncPingScanner
from .reporter import ReportGenerator