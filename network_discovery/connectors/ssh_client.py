""""
Клиент для SSH подключений
"""

import paramiko
import socket
import logging
import threading
from typing import Optional, Tuple
from models.device import DeviceCredentials

logger = logging.getLogger(__name__)


class SSHClient:
    """Клиент для SSH подключений к сетевым устройствам"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.connection = None

    def connect(self, host: str, credentials: DeviceCredentials) -> Tuple[bool, Optional[str]]:
        """
        Установка SSH подключения

        Args:
            host: Хост для подключения
            credentials: Учетные данные

        Returns:
            Кортеж (успех, сообщение об ошибке)
        """
        try:
            logger.debug(f"Попытка SSH подключения к {host}:{credentials.ssh_port}")

            # Создаем клиент
            self.connection = paramiko.SSHClient()
            self.connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Устанавливаем соединение
            self.connection.connect(
                hostname=host,
                port=credentials.ssh_port,
                username=credentials.username,
                password=credentials.password,
                timeout=credentials.ssh_timeout,
                look_for_keys=False,
                allow_agent=False,
                banner_timeout=30
            )

            logger.debug(f"SSH подключение к {host} успешно")
            return True, None

        except paramiko.AuthenticationException:
            error_msg = f"Ошибка аутентификации SSH к {host}"
            logger.debug(error_msg)
            return False, error_msg

        except paramiko.SSHException as e:
            error_msg = f"SSH ошибка к {host}: {e}"
            logger.debug(error_msg)
            return False, error_msg

        except socket.timeout:
            error_msg = f"Таймаут SSH подключения к {host}"
            logger.debug(error_msg)
            return False, error_msg

        except socket.error as e:
            error_msg = f"Сетевая ошибка SSH к {host}: {e}"
            logger.debug(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Неизвестная ошибка SSH к {host}: {e}"
            logger.debug(error_msg)
            return False, error_msg

    def execute_command(self, command: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
        """
        Выполнение команды через SSH

        Args:
            command: Команда для выполнения
            timeout: Таймаут выполнения

        Returns:
            Кортеж (успех, результат выполнения)
        """
        if not self.connection:
            return False, "Нет активного подключения"

        try:
            stdin, stdout, stderr = self.connection.exec_command(command, timeout=timeout)
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')

            if error and 'Invalid input' not in error and 'Incomplete command' not in error:
                logger.debug(f"SSH команда ошибка: {error[:100]}")

            return True, output

        except Exception as e:
            error_msg = f"Ошибка выполнения SSH команды: {e}"
            logger.debug(error_msg)
            return False, error_msg

    def disconnect(self):
        """Закрытие SSH соединения"""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                logger.debug("SSH соединение закрыто")
            except Exception as e:
                logger.debug(f"Ошибка при закрытии SSH соединения: {e}")

    def __enter__(self):
        """Контекстный менеджер"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход"""
        self.disconnect()


class SSHConnectionManager:
    """Менеджер SSH подключений"""

    def __init__(self):
        self.connections = {}
        self.lock = threading.Lock()

    def get_connection(self, host: str, credentials: DeviceCredentials) -> Optional[SSHClient]:
        """Получение SSH подключения (создает новое или возвращает существующее)"""
        key = f"{host}:{credentials.ssh_port}:{credentials.username}"

        with self.lock:
            if key in self.connections:
                return self.connections[key]

            client = SSHClient()
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