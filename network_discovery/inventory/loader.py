"""
Загрузка данных для Network Discovery
"""

import yaml
import json
import ipaddress
import logging
from typing import List, Dict, Any
from models.device import DeviceCredentials

logger = logging.getLogger(__name__)


class DataLoader:
    """Класс для загрузки данных из файлов"""

    @staticmethod
    def load_ip_list(file_path: str) -> List[str]:
        """
        Загрузка списка IP адресов из файла

        Args:
            file_path: Путь к файлу с IP адресами

        Returns:
            Список IP адресов
        """
        ips = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_number, line in enumerate(f, 1):
                    line = line.strip()

                    # Пропускаем комментарии и пустые строки
                    if not line or line.startswith('#'):
                        continue

                    try:
                        # Обрабатываем CIDR нотацию
                        if '/' in line:
                            network = ipaddress.ip_network(line, strict=False)
                            for ip in network.hosts():
                                ips.append(str(ip))

                        # Обрабатываем диапазоны
                        elif '-' in line:
                            start_ip, end_ip = line.split('-')
                            start = ipaddress.ip_address(start_ip.strip())
                            end = ipaddress.ip_address(end_ip.strip())

                            current = start
                            while current <= end:
                                ips.append(str(current))
                                current = current + 1

                        # Одиночный IP
                        else:
                            ipaddress.ip_address(line)
                            ips.append(line)

                    except ValueError as e:
                        logger.warning(f"Строка {line_number}: Неверный формат IP '{line}': {e}")

        except FileNotFoundError:
            logger.error(f"Файл не найден: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка при чтении файла {file_path}: {e}")

        # Удаляем дубликаты
        unique_ips = list(set(ips))
        logger.info(f"Загружено {len(unique_ips)} уникальных IP адресов из {file_path}")

        return unique_ips

    @staticmethod
    def load_credentials(file_path: str) -> List[DeviceCredentials]:
        """
        Загрузка учетных данных из файла

        Args:
            file_path: Путь к файлу с учетными данными

        Returns:
            Список объектов DeviceCredentials
        """
        credentials = []

        # Стандартные учетные данные
        default_credentials = [
            DeviceCredentials(username='admin', password='admin', enable_password='admin'),
            DeviceCredentials(username='cisco', password='cisco', enable_password='cisco'),
            DeviceCredentials(username='admin', password='password', enable_password='password'),
            DeviceCredentials(username='root', password='password'),
            DeviceCredentials(username='ubnt', password='ubnt'),
            DeviceCredentials(username='mikrotik', password=''),
            DeviceCredentials(username='operator', password='operator'),
            DeviceCredentials(username='user', password='user'),
            DeviceCredentials(username='administrator', password='administrator'),
        ]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Пробуем разные форматы
                data = None

                # Пробуем YAML
                try:
                    data = yaml.safe_load(content)
                except yaml.YAMLError:
                    pass

                # Пробуем JSON
                if data is None:
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        pass

                # Обрабатываем данные
                if data is not None:
                    credentials = DataLoader._parse_credentials(data)
                else:
                    # Текстовый формат
                    credentials = DataLoader._parse_text_credentials(content)

        except FileNotFoundError:
            logger.warning(f"Файл учетных данных не найден: {file_path}. Используются значения по умолчанию.")
            credentials = default_credentials
        except Exception as e:
            logger.error(f"Ошибка при загрузке учетных данных: {e}. Используются значения по умолчанию.")
            credentials = default_credentials

        # Если нет учетных данных, используем стандартные
        if not credentials:
            logger.warning("Нет загруженных учетных данных, используются значения по умолчанию.")
            credentials = default_credentials

        logger.info(f"Загружено {len(credentials)} наборов учетных данных")
        return credentials

    @staticmethod
    def _parse_credentials(data: Any) -> List[DeviceCredentials]:
        """Парсинг учетных данных из структурированных данных"""
        credentials = []

        if isinstance(data, dict):
            # Формат: {username: password} или {username: {password: ..., enable_password: ...}}
            for username, password_data in data.items():
                if isinstance(password_data, dict):
                    creds = DeviceCredentials(
                        username=username,
                        password=password_data.get('password', ''),
                        enable_password=password_data.get('enable_password'),
                        ssh_port=password_data.get('ssh_port', 22),
                        telnet_port=password_data.get('telnet_port', 23),
                        description=password_data.get('description', '')
                    )
                else:
                    creds = DeviceCredentials(
                        username=username,
                        password=str(password_data)
                    )
                credentials.append(creds)

        elif isinstance(data, list):
            # Формат: список словарей
            for item in data:
                if isinstance(item, dict):
                    creds = DeviceCredentials(
                        username=item.get('username', ''),
                        password=item.get('password', ''),
                        enable_password=item.get('enable_password'),
                        ssh_port=item.get('ssh_port', 22),
                        telnet_port=item.get('telnet_port', 23),
                        description=item.get('description', '')
                    )
                    credentials.append(creds)
                elif isinstance(item, str) and ':' in item:
                    # Формат: "username:password"
                    parts = item.split(':')
                    if len(parts) >= 2:
                        creds = DeviceCredentials(
                            username=parts[0].strip(),
                            password=parts[1].strip(),
                            enable_password=parts[2].strip() if len(parts) > 2 else None
                        )
                        credentials.append(creds)

        return credentials

    @staticmethod
    def _parse_text_credentials(content: str) -> List[DeviceCredentials]:
        """Парсинг учетных данных из текстового файла"""
        credentials = []

        for line in content.split('\n'):
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            # Формат: username:password[:enable_password]
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    creds = DeviceCredentials(
                        username=parts[0].strip(),
                        password=parts[1].strip(),
                        enable_password=parts[2].strip() if len(parts) > 2 else None
                    )
                    credentials.append(creds)

        return credentials

    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        """
        Загрузка конфигурации из YAML файла

        Args:
            file_path: Путь к файлу конфигурации

        Returns:
            Словарь с конфигурацией
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config or {}

        except FileNotFoundError:
            logger.warning(f"Файл конфигурации не найден: {file_path}")
            return {}
        except Exception as e:
            logger.error(f"Ошибка при загрузке конфигурации: {e}")
            return {}