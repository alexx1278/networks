"""
Клиент для Telnet подключений
"""

import telnetlib
import socket
import time
import logging
import threading
from typing import Optional, Tuple
from models.device import DeviceCredentials

logger = logging.getLogger(__name__)


class TelnetClient:
    """Клиент для Telnet подключений к сетевым устройствам"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.connection = None
        self.buffer_size = 4096

    def connect(self, host: str, credentials: DeviceCredentials) -> Tuple[bool, Optional[str]]:
        """
        Установка Telnet подключения

        Args:
            host: Хост для подключения
            credentials: Учетные данные

        Returns:
            Кортеж (успех, сообщение об ошибке)
        """
        try:
            logger.debug(f"Попытка Telnet подключения к {host}:{credentials.telnet_port}")

            # Создаем подключение
            self.connection = telnetlib.Telnet(host, credentials.telnet_port, credentials.telnet_timeout)

            # Ждем приглашения для логина
            login_prompt = self._read_until([b"Username:", b"login:", b"User:"], timeout=5)

            if login_prompt:
                self.connection.write(credentials.username.encode('ascii') + b"\n")
            else:
                # Некоторые устройства сразу просят логин
                self.connection.write(credentials.username.encode('ascii') + b"\n")
                time.sleep(0.5)

            # Ждем запроса пароля
            password_prompt = self._read_until([b"Password:", b"password:"], timeout=5)

            if password_prompt:
                self.connection.write(credentials.password.encode('ascii') + b"\n")
            else:
                # Может быть сразу после логина
                self.connection.write(credentials.password.encode('ascii') + b"\n")
                time.sleep(0.5)

            # Ждем приглашения командной строки
            time.sleep(1)
            output = self._read_output(timeout=3)

            # Проверяем успешность подключения
            if any(marker in output for marker in ['#', '>', '$', '%']):
                logger.debug(f"Telnet подключение к {host} успешно")
                return True, None
            else:
                error_msg = f"Не удалось войти на {host} через Telnet"
                logger.debug(error_msg)
                return False, error_msg

        except ConnectionRefusedError:
            error_msg = f"Telnet порт {credentials.telnet_port} закрыт на {host}"
            logger.debug(error_msg)
            return False, error_msg

        except socket.timeout:
            error_msg = f"Таймаут Telnet подключения к {host}"
            logger.debug(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Ошибка Telnet подключения к {host}: {e}"
            logger.debug(error_msg)
            return False, error_msg

    def _read_until(self, patterns: list, timeout: int = 5) -> Optional[bytes]:
        """Чтение до обнаружения одного из шаблонов"""
        if not self.connection:
            return None

        try:
            result = self.connection.expect(patterns, timeout=timeout)
            if result[0] != -1:
                return result[2]  # Возвращаем прочитанные данные
        except Exception:
            pass

        return None

    def _read_output(self, timeout: int = 2) -> str:
        """Чтение вывода из Telnet сессии"""
        if not self.connection:
            return ""

        try:
            output = self.connection.read_very_eager().decode('utf-8', errors='ignore')
            return output
        except:
            return ""

    def send_command(self, command: str, wait_for_prompt: bool = True,
                     timeout: int = 5) -> Tuple[bool, Optional[str]]:
        """
        Отправка команды по Telnet

        Args:
            command: Команда для отправки
            wait_for_prompt: Ждать ли приглашения командной строки
            timeout: Таймаут ожидания

        Returns:
            Кортеж (успех, результат выполнения)
        """
        if not self.connection:
            return False, "Нет активного подключения"

        try:
            # Отправляем команду
            self.connection.write(command.encode('ascii') + b"\n")

            # Ждем ответа
            time.sleep(1)
            output = self._read_output(timeout=1)

            # Если нужно ждать приглашения
            if wait_for_prompt:
                start_time = time.time()
                while time.time() - start_time < timeout:
                    if any(marker in output for marker in ['#', '>', '$', '%']):
                        break
                    time.sleep(0.5)
                    output += self._read_output(timeout=0.5)

            # Очищаем вывод от эхо-команды
            lines = output.split('\n')
            cleaned_lines = []
            for line in lines:
                if command not in line and line.strip():
                    cleaned_lines.append(line)

            result = '\n'.join(cleaned_lines)
            return True, result

        except Exception as e:
            error_msg = f"Ошибка отправки Telnet команды: {e}"
            logger.debug(error_msg)
            return False, error_msg

    def disconnect(self):
        """Закрытие Telnet соединения"""
        if self.connection:
            try:
                # Отправляем команду выхода
                self.connection.write(b"exit\n")
                time.sleep(0.5)
                self.connection.close()
                self.connection = None
                logger.debug("Telnet соединение закрыто")
            except Exception as e:
                logger.debug(f"Ошибка при закрытии Telnet соединения: {e}")

    def __enter__(self):
        """Контекстный менеджер"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход"""
        self.disconnect()


class TelnetConnectionManager:
    """Менеджер Telnet подключений"""

    def __init__(self):
        self.connections = {}
        self.lock = threading.Lock()

    def get_connection(self, host: str, credentials: DeviceCredentials) -> Optional[TelnetClient]:
        """Получение Telnet подключения"""
        key = f"{host}:{credentials.telnet_port}:{credentials.username}"

        with self.lock:
            if key in self.connections:
                return self.connections[key]

            client = TelnetClient()
            success, error = client.connect(host, credentials)

            if success:
                self.connections[key] = client
                return client
            else:
                client.disconnect()
                return None

    def close_all(self):
        """Закрытие всех подключений"""
        with self.lock:
            for key, client in self.connections.items():
                try:
                    client.disconnect()
                except:
                    pass
            self.connections.clear()