"""
Модуль для генерации отчетов
"""

import csv
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

from config import ScannerConfig, ReportFormat


class ReportGenerator:
    """Генератор отчетов"""

    def __init__(self, config: ScannerConfig):
        self.config = config

    def generate(self, scan_data: Dict) -> str:
        """
        Генерация отчета

        Args:
            scan_data: Данные сканирования

        Returns:
            Строка с отчетом
        """
        format_methods = {
            ReportFormat.TEXT: self._generate_text,
            ReportFormat.JSON: self._generate_json,
            ReportFormat.CSV: self._generate_csv,
        }

        method = format_methods.get(self.config.report_format, self._generate_text)
        return method(scan_data)

    def _generate_text(self, scan_data: Dict) -> str:
        """Генерация текстового отчета"""
        summary = scan_data.get("summary", {})
        latencies = scan_data.get("latencies", {})

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_lines = [
            "=" * 70,
            "ОТЧЕТ О СКАНИРОВАНИИ СЕТИ",
            f"Дата и время: {timestamp}",
            "=" * 70,
            "",
            "ОБЩАЯ СТАТИСТИКА:",
            f"  Всего хостов: {summary.get('total', 0)}",
            f"  Доступно: {summary.get('alive', 0)} ({summary.get('alive_percent', 0):.1f}%)",
            f"  Недоступно: {summary.get('dead', 0)} ({summary.get('dead_percent', 0):.1f}%)",
            f"  Средняя латентность: {summary.get('avg_latency_ms', 0):.2f} мс",
            f"  Время сканирования: {summary.get('scan_duration_seconds', 0):.1f} сек",
            "",
            ]

        # Доступные хосты с латентностью
        if latencies:
            report_lines.extend([
                "ДОСТУПНЫЕ ХОСТЫ (время отклика):",
                "-" * 50,
                ])

            # Сортируем по IP
            sorted_ips = sorted(latencies.items(), key=lambda x: self._ip_sort_key(x[0]))

            for ip, latency in sorted_ips:
                report_lines.append(f"  {ip:<40} {latency:>6.2f} мс")

        # Недоступные хосты
        dead_hosts = scan_data.get("dead_hosts", [])
        if dead_hosts:
            report_lines.extend([
                "",
                "НЕДОСТУПНЫЕ ХОСТЫ:",
                "-" * 50,
                ])

            sorted_dead = sorted(dead_hosts, key=self._ip_sort_key)
            for ip in sorted_dead:
                report_lines.append(f"  {ip}")
        else:
            report_lines.append("Нет недоступных хостов")

        report_lines.extend([
            "",
            "=" * 70,
            f"Отчет сгенерирован: {timestamp}",
            "=" * 70,
            ])

        return "\n".join(report_lines)

    def _generate_json(self, scan_data: Dict) -> str:
        """Генерация JSON отчета"""
        # Добавляем метаинформацию
        full_report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "config": self.config.to_dict(),
                "scanner_version": "1.0.0"
            },
            "scan_results": scan_data
        }

        return json.dumps(full_report, indent=2, ensure_ascii=False)

    def _generate_csv(self, scan_data: Dict) -> str:
        """Генерация CSV отчета"""
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Заголовок
        writer.writerow(["IP Address", "Status", "Latency (ms)", "Timestamp"])

        timestamp = datetime.now().isoformat()

        # Доступные хосты
        latencies = scan_data.get("latencies", {})
        for ip, latency in sorted(latencies.items(), key=lambda x: self._ip_sort_key(x[0])):
            writer.writerow([ip, "available", f"{latency:.2f}", timestamp])

        # Недоступные хосты
        dead_hosts = scan_data.get("dead_hosts", [])
        for ip in sorted(dead_hosts, key=self._ip_sort_key):
            writer.writerow([ip, "unavailable", "", timestamp])

        return output.getvalue()

    def _ip_sort_key(self, ip_str: str) -> tuple:
        """
        Ключ для сортировки IP-адресов

        Args:
            ip_str: Строка с IP-адресом

        Returns:
            Кортеж для сортировки
        """
        try:
            import ipaddress
            ip = ipaddress.ip_address(ip_str)
            # Сначала IPv4, потом IPv6
            return (0, ip) if ip.version == 4 else (1, ip)
        except ValueError:
            # Невалидные адреса в конце
            return (2, ip_str)

    def save_report(self, report: str, filepath: Optional[str] = None) -> bool:
        """
        Сохранение отчета в файл

        Args:
            report: Текст отчета
            filepath: Путь к файлу (опционально)

        Returns:
            True если успешно
        """
        try:
            if filepath is None:
                filepath = self.config.output_file

            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(report)

            logging.info(f"Отчет сохранен в файл: {filepath}")
            return True

        except Exception as e:
            logging.error(f"Ошибка сохранения отчета: {e}")
            return False

    def save_raw_results(self, results: Dict, filepath: Optional[str] = None) -> bool:
        """
        Сохранение сырых результатов

        Args:
            results: Сырые результаты сканирования
            filepath: Путь к файлу (опционально)

        Returns:
            True если успешно
        """
        if not self.config.save_raw_results:
            return False

        try:
            if filepath is None:
                filepath = self.config.raw_results_file

            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logging.info(f"Сырые результаты сохранены в файл: {filepath}")
            return True

        except Exception as e:
            logging.error(f"Ошибка сохранения сырых результатов: {e}")
            return False