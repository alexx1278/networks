"""
Модуль асинхронного сканера
"""

import asyncio
import platform
import re
import time
from typing import List, Dict, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor
import logging

from config import ScannerConfig, PingResult, ScanResult, ScanSummary
from ip_parser import IPParser


class ProgressTracker:
    """Трекер прогресса сканирования"""

    def __init__(self, total: int, show_progress: bool = True):
        self.total = total
        self.completed = 0
        self.show_progress = show_progress
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 1.0  # Обновлять не чаще чем раз в секунду

    def update(self, count: int = 1):
        """Обновить прогресс"""
        self.completed += count
        current_time = time.time()

        if self.show_progress and current_time - self.last_update >= self.update_interval:
            self._display()
            self.last_update = current_time

    def _display(self):
        """Отобразить прогресс"""
        elapsed = time.time() - self.start_time
        percent = (self.completed / self.total * 100) if self.total > 0 else 0

        if elapsed > 0:
            ips_per_sec = self.completed / elapsed
            remaining = (self.total - self.completed) / ips_per_sec if ips_per_sec > 0 else 0

            print(f"\rПрогресс: {self.completed}/{self.total} ({percent:.1f}%) | "
                  f"Скорость: {ips_per_sec:.1f} IP/сек | "
                  f"Осталось: {remaining:.0f} сек", end="", flush=True)

    def finish(self):
        """Завершить отображение прогресса"""
        if self.show_progress:
            elapsed = time.time() - self.start_time
            print(f"\nСканирование завершено за {elapsed:.1f} секунд")

    def get_stats(self) -> Dict:
        """Получить статистику"""
        elapsed = time.time() - self.start_time
        ips_per_sec = self.completed / elapsed if elapsed > 0 else 0

        return {
            "total": self.total,
            "completed": self.completed,
            "elapsed_seconds": elapsed,
            "ips_per_second": ips_per_sec,
            "percent": (self.completed / self.total * 100) if self.total > 0 else 0
        }


class AsyncPingScanner:
    """Асинхронный сканер IP-адресов"""

    def __init__(self, config: ScannerConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.concurrent_limit)
        self.results: Dict[str, ScanResult] = {}
        self.summary = ScanSummary()
        self._progress: Optional[ProgressTracker] = None

        # Проверяем доступность ping
        self._check_ping_available()

    def _check_ping_available(self):
        """Проверка доступности команды ping"""
        system = platform.system().lower()

        # Просто логируем, проверка будет при первом вызове ping
        if system == 'windows':
            logging.debug("ОС: Windows, будет использоваться команда ping")
        else:
            logging.debug("ОС: Linux/macOS, будет использоваться команда ping")

    def _build_ping_command(self, ip: str) -> List[str]:
        """Построение команды ping"""
        system = platform.system().lower()

        if system == 'windows':
            return [
                'ping', '-n', str(self.config.ping_count),
                '-w', str(int(self.config.timeout * 1000)),
                ip
            ]
        else:
            return [
                'ping', '-c', str(self.config.ping_count),
                '-W', str(int(self.config.timeout)),
                ip
            ]

    def _extract_latency(self, output: str) -> Optional[float]:
        """Извлечение времени отклика из вывода ping"""
        patterns = [
            r'time[=<>](\d+\.?\d*)\s*ms',  # Стандартный формат
            r'время[=<>](\d+\.?\d*)\s*мс',  # Русская локализация
            r'(\d+\.?\d*)\s*ms',  # Просто число с ms
        ]

        for pattern in patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                try:
                    # Берем последнее значение (самое актуальное)
                    return float(matches[-1])
                except (ValueError, IndexError):
                    continue

        return None

    async def _execute_ping(self, ip: str) -> Tuple[PingResult, Optional[float]]:
        """
        Выполнение ping для одного IP

        Returns:
            Кортеж (результат, время отклика)
        """
        async with self.semaphore:
            cmd = self._build_ping_command(ip)

            for attempt in range(self.config.max_retries):
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(),
                            timeout=self.config.timeout + 1
                        )

                        output = stdout.decode('utf-8', errors='ignore')

                        if process.returncode == 0:
                            latency = self._extract_latency(output)
                            return PingResult.SUCCESS, latency
                        else:
                            if attempt < self.config.max_retries - 1:
                                await asyncio.sleep(0.1 * (attempt + 1))
                                continue
                            return PingResult.UNREACHABLE, None

                    except asyncio.TimeoutError:
                        try:
                            process.kill()
                            await process.wait()
                        except:
                            pass

                        if attempt < self.config.max_retries - 1:
                            continue
                        return PingResult.TIMEOUT, None

                except Exception as e:
                    logging.debug(f"Ошибка при ping {ip}: {e}")
                    if attempt < self.config.max_retries - 1:
                        continue
                    return PingResult.ERROR, None

            return PingResult.ERROR, None

    async def _measure_latency(self, ip: str) -> Optional[float]:
        """
        Измерение средней латентности для одного хоста

        Returns:
            Среднее время отклика или None
        """
        latencies = []
        start_time = time.time()

        logging.debug(f"Начато измерение латентности для {ip}")

        while time.time() - start_time < self.config.ping_duration:
            try:
                result, latency = await self._execute_ping(ip)

                if result == PingResult.SUCCESS and latency is not None:
                    latencies.append(latency)

                # Ждем указанный интервал
                elapsed = time.time() - start_time
                if elapsed < self.config.ping_duration:
                    await asyncio.sleep(self.config.ping_interval)

            except Exception as e:
                logging.debug(f"Ошибка при измерении {ip}: {e}")
                await asyncio.sleep(0.1)

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            logging.debug(f"Измерение завершено для {ip}: {len(latencies)} пингов, "
                          f"среднее: {avg_latency:.2f} мс")
            return round(avg_latency, 2)

        logging.debug(f"Не удалось измерить латентность для {ip}")
        return None

    async def scan_hosts(self, ip_list: List[str]) -> Dict[str, ScanResult]:
        """
        Основное сканирование хостов

        Args:
            ip_list: Список IP-адресов для сканирования

        Returns:
            Словарь с результатами сканирования
        """
        self.summary.start_time = time.time()
        self.summary.total_hosts = len(ip_list)

        logging.info(f"Начинаем сканирование {len(ip_list)} хостов...")

        # Инициализируем прогресс
        self._progress = ProgressTracker(
            total=len(ip_list),
            show_progress=self.config.show_progress
        )

        print(f"\n{'='*60}")
        print(f"СКАНИРОВАНИЕ СЕТИ")
        print(f"Количество хостов: {len(ip_list)}")
        print(f"Одновременных запросов: {self.config.concurrent_limit}")
        print(f"Таймаут: {self.config.timeout} сек")
        print(f"{'='*60}\n")

        # Шаг 1: Проверка доступности
        print("ШАГ 1: Проверка доступности хостов...")
        alive_hosts = await self._check_availability(ip_list)

        # Шаг 2: Измерение латентности
        print("\nШАГ 2: Измерение времени отклика...")
        await self._measure_latencies(alive_hosts)

        # Завершаем сканирование
        self.summary.end_time = time.time()
        self.summary.scan_duration = self.summary.end_time - self.summary.start_time
        self.summary.alive_hosts = len(alive_hosts)
        self.summary.dead_hosts = self.summary.total_hosts - self.summary.alive_hosts

        if self._progress:
            self._progress.finish()

        logging.info(f"Сканирование завершено за {self.summary.scan_duration:.1f} секунд")
        logging.info(f"Результаты: {self.summary.alive_hosts} доступно, "
                     f"{self.summary.dead_hosts} недоступно")

        return self.results

    async def _check_availability(self, ip_list: List[str]) -> List[str]:
        """Проверка доступности хостов"""
        alive_hosts = []

        # Создаем задачи для всех хостов
        tasks = []
        for ip in ip_list:
            task = self._check_single_host(ip)
            tasks.append(task)

        # Запускаем все задачи
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обрабатываем результаты
        for ip, result in zip(ip_list, results):
            if isinstance(result, Exception):
                logging.error(f"Ошибка при сканировании {ip}: {result}")
                self.results[ip] = ScanResult(ip=ip, is_alive=False, last_error=str(result))
            else:
                is_alive, latency = result
                self.results[ip] = ScanResult(
                    ip=ip,
                    is_alive=is_alive,
                    avg_latency=latency if is_alive else None
                )
                if is_alive:
                    alive_hosts.append(ip)

                # Обновляем прогресс
                if self._progress:
                    self._progress.update()

        return alive_hosts

    async def _check_single_host(self, ip: str) -> Tuple[bool, Optional[float]]:
        """Проверка одного хоста"""
        result, latency = await self._execute_ping(ip)
        return (result == PingResult.SUCCESS), latency

    async def _measure_latencies(self, alive_hosts: List[str]):
        """Измерение латентности для доступных хостов"""
        if not alive_hosts:
            print("Нет доступных хостов для измерения латентности")
            return

        print(f"Измерение латентности для {len(alive_hosts)} хостов "
              f"(длительность: {self.config.ping_duration} сек)...")

        # Создаем задачи для измерения латентности
        tasks = []
        for ip in alive_hosts:
            task = self._measure_latency(ip)
            tasks.append(task)

        # Запускаем измерения
        latencies = await asyncio.gather(*tasks, return_exceptions=True)

        # Обновляем результаты
        for ip, latency in zip(alive_hosts, latencies):
            if isinstance(latency, Exception):
                logging.error(f"Ошибка измерения латентности для {ip}: {latency}")
                self.results[ip].last_error = str(latency)
            elif latency is not None:
                self.results[ip].avg_latency = latency

    def get_summary(self) -> Dict:
        """Получить сводку по сканированию"""
        alive_ips = [ip for ip, result in self.results.items() if result.is_alive]
        dead_ips = [ip for ip, result in self.results.items() if not result.is_alive]

        # Средняя латентность для доступных хостов
        avg_latencies = []
        for ip in alive_ips:
            if self.results[ip].avg_latency:
                avg_latencies.append(self.results[ip].avg_latency)

        avg_latency = sum(avg_latencies) / len(avg_latencies) if avg_latencies else 0

        return {
            "summary": {
                "total": self.summary.total_hosts,
                "alive": self.summary.alive_hosts,
                "dead": self.summary.dead_hosts,
                "alive_percent": self.summary.alive_percent,
                "dead_percent": self.summary.dead_percent,
                "avg_latency_ms": round(avg_latency, 2),
                "scan_duration_seconds": round(self.summary.scan_duration, 2)
            },
            "alive_hosts": alive_ips,
            "dead_hosts": dead_ips,
            "latencies": {
                ip: self.results[ip].avg_latency
                for ip in alive_ips
                if self.results[ip].avg_latency is not None
            }
        }