"""
Модуль для парсинга IP-адресов из различных форматов
"""

import ipaddress
import re
import logging
from typing import Set, List, Dict


class IPParser:
    """Парсер IP-адресов"""

    @staticmethod
    def parse_line(line: str, line_num: int = 1) -> Set[str]:
        """
        Парсинг одной строки с IP-адресами

        Args:
            line: Строка для парсинга
            line_num: Номер строки (для логирования)

        Returns:
            Множество IP-адресов
        """
        line = line.strip()
        ip_set = set()

        # Пропускаем пустые строки и комментарии
        if not line or line.startswith('#'):
            return ip_set

        # Удаляем возможные пробелы вокруг /
        line = re.sub(r'\s*/\s*', '/', line)
        line = re.sub(r'\s*-\s*', '-', line)

        # Проверяем на корректность CIDR маски
        if '/' in line:
            parts = line.split('/')
            if len(parts) == 2:
                address, mask = parts[0].strip(), parts[1].strip()

                # Проверяем, является ли маска числом
                if mask.isdigit():
                    mask_int = int(mask)

                    # Проверяем диапазон для IPv4
                    if '.' in address and mask_int > 32:
                        logging.error(f"Строка {line_num}: Некорректная маска CIDR /{mask} для IPv4. "
                                      f"Допустимый диапазон: 0-32")
                        return ip_set

                    # Проверяем диапазон для IPv6
                    if ':' in address and mask_int > 128:
                        logging.error(f"Строка {line_num}: Некорректная маска CIDR /{mask} для IPv6. "
                                      f"Допустимый диапазон: 0-128")
                        return ip_set

        try:
            # Пробуем распарсить как отдельный IP
            ip = ipaddress.ip_address(line)
            ip_set.add(str(ip))
            return ip_set
        except ValueError:
            pass

        # Пробуем распарсить как CIDR
        if '/' in line:
            try:
                network = ipaddress.ip_network(line, strict=False)

                # Проверяем размер сети для больших диапазонов
                if network.num_addresses > 65536:  # /16 или больше
                    logging.warning(f"Строка {line_num}: Большой диапазон CIDR '{line}' "
                                    f"({network.num_addresses} адресов). "
                                    f"Добавлены только первый и последний адреса")
                    ip_set.add(str(network[1]))  # Первый хост
                    ip_set.add(str(network[-2]))  # Последний хост
                else:
                    for ip in network.hosts():
                        ip_set.add(str(ip))
                return ip_set
            except ValueError as e:
                logging.error(f"Строка {line_num}: Ошибка парсинга CIDR '{line}': {e}")
                return ip_set

        # Пробуем распарсить как диапазон (формат: start-end)
        if '-' in line and line.count('-') == 1:
            try:
                start_str, end_str = line.split('-')
                start_ip = ipaddress.ip_address(start_str.strip())
                end_ip = ipaddress.ip_address(end_str.strip())

                # Проверяем, что оба адреса одной версии
                if type(start_ip) != type(end_ip):
                    logging.error(f"Строка {line_num}: Несовместимые версии IP в диапазоне: "
                                  f"{start_str} и {end_str}")
                    return ip_set

                # Для IPv4
                if isinstance(start_ip, ipaddress.IPv4Address):
                    start_int = int(start_ip)
                    end_int = int(end_ip)

                    # Проверяем, что начальный адрес <= конечному
                    if start_int > end_int:
                        logging.error(f"Строка {line_num}: Начальный адрес больше конечного в диапазоне: "
                                      f"{start_str}-{end_str}")
                        return ip_set

                    # Ограничиваем размер диапазона
                    range_size = end_int - start_int + 1
                    if range_size > 1000:
                        logging.warning(f"Строка {line_num}: Большой диапазон '{line}' "
                                        f"({range_size} адресов). "
                                        f"Добавлены только первый и последний адреса")
                        ip_set.add(str(start_ip))
                        ip_set.add(str(end_ip))
                    else:
                        for ip_int in range(start_int, end_int + 1):
                            ip_set.add(str(ipaddress.IPv4Address(ip_int)))
                # Для IPv6 - только начальный и конечный
                elif isinstance(start_ip, ipaddress.IPv6Address):
                    ip_set.add(str(start_ip))
                    ip_set.add(str(end_ip))

                return ip_set
            except ValueError as e:
                logging.error(f"Строка {line_num}: Ошибка парсинга диапазона '{line}': {e}")
                return ip_set

        # Пробуем распарсить как список через запятую
        if ',' in line:
            parts = line.split(',')
            for part in parts:
                part = part.strip()
                if part:
                    result = IPParser.parse_line(part, line_num)
                    ip_set.update(result)
            return ip_set

        # Пробуем распарсить как подсеть с маской в десятичном виде (192.168.1.0/255.255.255.0)
        if '/' in line and '.' in line.split('/')[1]:
            try:
                # Преобразуем маску в префикс CIDR
                address, mask = line.split('/')
                mask_parts = mask.split('.')

                if len(mask_parts) == 4:
                    # Преобразуем маску в префикс
                    prefix = sum(bin(int(x)).count('1') for x in mask_parts)
                    cidr_line = f"{address}/{prefix}"

                    # Парсим как CIDR
                    network = ipaddress.ip_network(cidr_line, strict=False)

                    if network.num_addresses > 65536:
                        logging.warning(f"Строка {line_num}: Большая сеть '{line}'. "
                                        f"Добавлены только первый и последний адреса")
                        ip_set.add(str(network[1]))
                        ip_set.add(str(network[-2]))
                    else:
                        for ip in network.hosts():
                            ip_set.add(str(ip))
                    return ip_set
            except (ValueError, AttributeError) as e:
                logging.error(f"Строка {line_num}: Ошибка парсинга подсети '{line}': {e}")
                return ip_set

        logging.warning(f"Строка {line_num}: Не удалось распарсить '{line}'")
        return ip_set

    @classmethod
    def parse_file(cls, filepath: str) -> Set[str]:
        """
        Парсинг файла с IP-адресами

        Args:
            filepath: Путь к файлу

        Returns:
            Множество уникальных IP-адресов
        """
        ip_set = set()
        successful_lines = 0
        total_lines = 0

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    total_lines += 1
                    try:
                        ips = cls.parse_line(line, line_num)
                        if ips:
                            ip_set.update(ips)
                            successful_lines += 1
                    except Exception as e:
                        logging.error(f"Ошибка парсинга строки {line_num}: {e}")

            logging.info(f"Обработано строк: {successful_lines}/{total_lines}")
            logging.info(f"Из файла {filepath} получено {len(ip_set)} уникальных IP-адресов")

            if len(ip_set) == 0:
                logging.warning("Не найдено корректных IP-адресов. Проверьте формат файла.")
                logging.info("Пример корректного формата:")
                logging.info("  8.8.8.8")
                logging.info("  192.168.1.0/24")
                logging.info("  10.0.0.1-10.0.0.10")

            return ip_set

        except FileNotFoundError:
            logging.error(f"Файл не найден: {filepath}")
            # Создаем пример файла
            cls._create_example_file(filepath)
            raise
        except Exception as e:
            logging.error(f"Ошибка чтения файла {filepath}: {e}")
            raise

    @staticmethod
    def _create_example_file(filepath: str):
        """Создание примера файла с IP-адресами"""
        example_content = """# Пример файла с IP-адресами
# Форматы, которые поддерживаются:

# Отдельные адреса
8.8.8.8
8.8.4.4

# Диапазон CIDR (маска от 0 до 32 для IPv4)
192.168.1.0/24
10.0.0.0/30

# Простой диапазон
192.168.1.1-192.168.1.10

# Подсеть с маской в десятичном виде
192.168.2.0/255.255.255.0

# Комментарии начинаются с #
# Пустые строки игнорируются

# Неправильные примеры (не будут обработаны):
# 192.168.1.0/254  <- маска больше 32
# 10.0.0.20-10.0.0.10  <- начальный адрес больше конечного
"""

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(example_content)
            logging.info(f"Создан пример файла: {filepath}")
            logging.info("Отредактируйте его и добавьте свои IP-адреса")
        except Exception as e:
            logging.error(f"Не удалось создать пример файла: {e}")

    @classmethod
    def filter_local_ips(cls, ip_set: Set[str]) -> Set[str]:
        """
        Фильтрация локальных IP-адресов

        Args:
            ip_set: Множество IP-адресов

        Returns:
            Отфильтрованное множество
        """
        local_patterns = [
            r'^127\.',  # localhost
            r'^169\.254\.',  # link-local
            r'^10\.',  # private
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',  # private
            r'^192\.168\.',  # private
            r'^::1$',  # IPv6 localhost
            r'^fe80::',  # IPv6 link-local
            r'^fc00::',  # IPv6 private
            r'^fd00::',  # IPv6 private
        ]

        filtered_ips = set()
        local_ips = set()

        for ip in ip_set:
            is_local = False
            for pattern in local_patterns:
                if re.match(pattern, ip):
                    is_local = True
                    break

            if is_local:
                local_ips.add(ip)
            else:
                filtered_ips.add(ip)

        removed_count = len(local_ips)
        if removed_count > 0:
            logging.info(f"Удалено {removed_count} локальных IP-адресов")
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                for ip in sorted(local_ips):
                    logging.debug(f"  Удален локальный адрес: {ip}")

        return filtered_ips

    @classmethod
    def validate_ip(cls, ip_str: str) -> bool:
        """
        Валидация IP-адреса

        Args:
            ip_str: Строка с IP-адресом

        Returns:
            True если адрес валидный
        """
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False

    @classmethod
    def sort_ips(cls, ip_list: List[str]) -> List[str]:
        """
        Сортировка IP-адресов

        Args:
            ip_list: Список IP-адресов

        Returns:
            Отсортированный список
        """
        def ip_key(ip_str: str):
            try:
                ip = ipaddress.ip_address(ip_str)
                # Сначала IPv4, потом IPv6
                return (0, ip) if ip.version == 4 else (1, ip)
            except ValueError:
                # Невалидные адреса в конце
                return (2, ip_str)

        return sorted(ip_list, key=ip_key)

    @classmethod
    def validate_file(cls, filepath: str) -> Dict[str, any]:
        """
        Валидация файла с IP-адресами

        Args:
            filepath: Путь к файлу

        Returns:
            Словарь с результатами валидации
        """
        results = {
            'valid': True,
            'total_lines': 0,
            'successful_lines': 0,
            'error_lines': [],
            'ip_count': 0,
            'errors': []
        }

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    results['total_lines'] += 1
                    line = line.strip()

                    if not line or line.startswith('#'):
                        continue

                    try:
                        ips = cls.parse_line(line, line_num)
                        if ips:
                            results['successful_lines'] += 1
                            results['ip_count'] += len(ips)
                        else:
                            results['error_lines'].append(line_num)
                    except Exception as e:
                        results['error_lines'].append(line_num)
                        results['errors'].append(f"Строка {line_num}: {e}")

            if results['ip_count'] == 0:
                results['valid'] = False
                results['errors'].append("Не найдено корректных IP-адресов")

            return results

        except FileNotFoundError:
            results['valid'] = False
            results['errors'].append(f"Файл не найден: {filepath}")
            return results
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"Ошибка чтения файла: {e}")
            return results