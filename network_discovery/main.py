"""
Точка входа для Network Device Discovery
"""

import argparse
import sys
import time
import os
from datetime import datetime
from config.logger import setup_logger
from utils.helpers import (
    setup_environment, print_banner, check_dependencies,
    get_system_info, get_color_codes
)
from inventory.loader import DataLoader
from inventory.saver import InventorySaver
from discovery import NetworkDiscovery


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Network Device Discovery and Inventory Builder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py -i ips.txt -c credentials.yaml
  python main.py -i 192.168.1.0/24 -c creds.json --workers 20
  python main.py -i ips.txt -c creds.yaml --format json --generate-all
  python main.py (запуск в интерактивном режиме)
        """
    )

    parser.add_argument(
        '--ip-list', '-i',
        help='Файл со списком IP адресов или IP диапазон (CIDR)'
    )

    parser.add_argument(
        '--credentials', '-c',
        help='Файл с учетными данными (YAML/JSON/TXT)'
    )

    parser.add_argument(
        '--output', '-o',
        default='inventory/inventory.yaml',
        help='Выходной файл инвентаря (по умолчанию: inventory/inventory.yaml)'
    )

    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=10,
        help='Количество одновременных потоков (по умолчанию: 10)'
    )

    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=5,
        help='Таймаут подключения в секундах (по умолчанию: 5)'
    )

    parser.add_argument(
        '--format', '-f',
        choices=['yaml', 'json', 'csv', 'all'],
        default='yaml',
        help='Формат вывода (по умолчанию: yaml)'
    )

    parser.add_argument(
        '--generate-netmiko',
        action='store_true',
        help='Сгенерировать инвентарь для Netmiko'
    )

    parser.add_argument(
        '--generate-ansible',
        action='store_true',
        help='Сгенерировать инвентарь для Ansible'
    )

    parser.add_argument(
        '--generate-report',
        action='store_true',
        help='Сгенерировать текстовый отчет'
    )

    parser.add_argument(
        '--generate-all',
        action='store_true',
        help='Сгенерировать все форматы инвентаря'
    )

    parser.add_argument(
        '--protocol', '-p',
        choices=['both', 'ssh', 'telnet'],
        default='both',
        help='Протокол для сканирования (по умолчанию: both)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод (DEBUG уровень)'
    )

    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='Проверить зависимости и выйти'
    )

    parser.add_argument(
        '--interactive', '-I',
        action='store_true',
        help='Запуск в интерактивном режиме'
    )

    return parser.parse_args()


def check_requirements():
    """Проверка системных требований"""
    # Проверяем Python версию
    if sys.version_info < (3, 7):
        print("Требуется Python 3.7 или выше")
        sys.exit(1)

    # Проверяем зависимости
    missing_deps = check_dependencies()
    if missing_deps:
        print("Отсутствуют следующие зависимости:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nУстановите зависимости командой:")
        print("pip install paramiko pyyaml")
        sys.exit(1)


def interactive_mode():
    """Интерактивный режим работы"""
    colors = get_color_codes()

    print(f"\n{colors['cyan']}{'='*60}{colors['reset']}")
    print(f"{colors['bold']}ИНТЕРАКТИВНЫЙ РЕЖИМ NETWORK DISCOVERY{colors['reset']}")
    print(f"{colors['cyan']}{'='*60}{colors['reset']}\n")

    # 1. Выбор IP адресов
    print(f"{colors['yellow']}1. ВЫБОР IP АДРЕСОВ:{colors['reset']}")
    print("   Выберите способ указания IP адресов:")
    print("   1. Файл со списком IP адресов: ./examples/ip_list.txt")
    print("   2. Диапазон IP (CIDR, например: 192.168.1.0/24)")
    print("   3. Диапазон IP (например: 192.168.1.1-192.168.1.10)")
    print("   4. Одиночный IP адрес")

    ip_choice = input("\n   Ваш выбор [1-4]: ").strip()

    ip_list_input = ""
    if ip_choice == '1':
        ip_file = './examples/ip_list.txt'
        if os.path.exists(ip_file):
            ip_list_input = ip_file
        else:
            print(f"   {colors['red']}Файл не найден!{colors['reset']}")
            return None
    elif ip_choice == '2':
        ip_list_input = input("   Введите CIDR диапазон (например, 192.168.1.0/24): ").strip()
    elif ip_choice == '3':
        ip_list_input = input("   Введите диапазон IP (например, 192.168.1.1-192.168.1.10): ").strip()
    elif ip_choice == '4':
        ip_list_input = input("   Введите IP адрес: ").strip()
    else:
        print(f"   {colors['red']}Неверный выбор!{colors['reset']}")
        return None

    # 2. Выбор учетных данных
    print(f"\n{colors['yellow']}2. УЧЕТНЫЕ ДАННЫЕ:{colors['reset']}")
    print("   Выберите способ указания учетных данных:")
    print("   1. Файл с учетными данными (YAML/JSON/TXT)")
    print("   2. Использовать стандартные учетные данные")

    cred_choice = input("\n   Ваш выбор [1-2]: ").strip()

    credentials_input = ""
    if cred_choice == '1':
        cred_file = input("   Введите путь к файлу с учетными данными: ").strip()
        if os.path.exists(cred_file):
            credentials_input = cred_file
        else:
            print(f"   {colors['red']}Файл не найден!{colors['reset']}")
            return None
    elif cred_choice == '2':
        # Используем стандартные учетные данные
        default_creds_file = os.path.join(os.path.dirname(__file__), 'examples', 'credentials.yaml')
        if os.path.exists(default_creds_file):
            credentials_input = default_creds_file
            print(f"   Используются стандартные учетные данные из: {default_creds_file}")
        else:
            # Создаем временный файл со стандартными учетными данными
            import tempfile
            temp_creds = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
            temp_creds.write("""# Стандартные учетные данные
admin: admin
cisco: cisco
root: password
mikrotik: ""
ubnt: ubnt
operator: operator
user: user
administrator: administrator
""")
            temp_creds.close()
            credentials_input = temp_creds.name
            print(f"   Создан временный файл со стандартными учетными данными")
    else:
        print(f"   {colors['red']}Неверный выбор!{colors['reset']}")
        return None

    # 3. Дополнительные параметры
    print(f"\n{colors['yellow']}3. ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ:{colors['reset']}")

    # Количество потоков
    workers_input = input(f"   Количество потоков [по умолчанию: 10]: ").strip()
    workers = int(workers_input) if workers_input else 10

    # Таймаут
    timeout_input = input(f"   Таймаут подключения (секунд) [по умолчанию: 5]: ").strip()
    timeout = int(timeout_input) if timeout_input else 5

    # Формат вывода
    print("\n   Формат вывода результатов:")
    print("   1. YAML (рекомендуется)")
    print("   2. JSON")
    print("   3. CSV")
    print("   4. Все форматы")
    format_choice = input("\n   Ваш выбор [1-4]: ").strip()
    format_map = {'1': 'yaml', '2': 'json', '3': 'csv', '4': 'all'}
    format_output = format_map.get(format_choice, 'yaml')

    # Дополнительные форматы
    print("\n   Дополнительные форматы вывода:")
    generate_netmiko = input("   Генерировать инвентарь для Netmiko? [y/N]: ").strip().lower() == 'y'
    generate_ansible = input("   Генерировать инвентарь для Ansible? [y/N]: ").strip().lower() == 'y'
    generate_report = input("   Генерировать текстовый отчет? [y/N]: ").strip().lower() == 'y'

    # Протокол
    print("\n   Протокол для сканирования:")
    print("   1. SSH и Telnet (оба)")
    print("   2. Только SSH")
    print("   3. Только Telnet")
    protocol_choice = input("\n   Ваш выбор [1-3]: ").strip()
    protocol_map = {'1': 'both', '2': 'ssh', '3': 'telnet'}
    protocol_output = protocol_map.get(protocol_choice, 'both')

    # Подробный вывод
    verbose_output = input("\n   Подробный вывод (verbose mode)? [y/N]: ").strip().lower() == 'y'

    # Имя выходного файла
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"inventory/discovery_{timestamp}.yaml"

    # Создаем аргументы
    class Args:
        pass

    args = Args()
    args.ip_list = ip_list_input
    args.credentials = credentials_input
    args.output = output_file
    args.workers = workers
    args.timeout = timeout
    args.format = format_output
    args.generate_netmiko = generate_netmiko
    args.generate_ansible = generate_ansible
    args.generate_report = generate_report
    args.generate_all = False  # Управляется отдельно
    args.protocol = protocol_output
    args.verbose = verbose_output
    args.check_deps = False
    args.interactive = True

    print(f"\n{colors['green']}✓ Параметры сохранены!{colors['reset']}")
    return args


def print_summary(discovery: NetworkDiscovery, start_time: float):
    """Вывод сводки по результатам обнаружения"""
    colors = get_color_codes()
    elapsed_time = time.time() - start_time

    stats = discovery.get_statistics()

    print(f"\n{colors['green']}{'='*60}{colors['reset']}")
    print(f"{colors['bold']}СВОДКА РЕЗУЛЬТАТОВ:{colors['reset']}")
    print(f"{colors['green']}{'='*60}{colors['reset']}")

    print(f"\nОбщее время: {colors['yellow']}{elapsed_time:.2f} секунд{colors['reset']}")
    print(f"Обнаружено устройств: {colors['yellow']}{stats['total_devices']}{colors['reset']}")

    if stats['vendors']:
        print(f"\n{colors['bold']}Распределение по производителям:{colors['reset']}")
        for vendor, count in sorted(stats['vendors'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {vendor}: {colors['cyan']}{count}{colors['reset']}")

    if stats['device_types']:
        print(f"\n{colors['bold']}Распределение по типам устройств:{colors['reset']}")
        for device_type, count in sorted(stats['device_types'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {device_type}: {colors['blue']}{count}{colors['reset']}")

    print(f"\n{colors['bold']}Распределение по протоколам:{colors['reset']}")
    print(f"  SSH: {colors['blue']}{stats['protocols']['ssh']}{colors['reset']}")
    print(f"  Telnet: {colors['blue']}{stats['protocols']['telnet']}{colors['reset']}")

    print(f"\n{colors['green']}{'='*60}{colors['reset']}")


def run_discovery(args):
    """Основная функция запуска обнаружения"""
    try:
        # Настраиваем окружение
        setup_environment()

        # Выводим баннер
        print_banner()

        # Проверяем требования
        check_requirements()

        # Проверяем зависимости если нужно
        if args.check_deps:
            print("Все зависимости установлены!")
            return

        # Настраиваем уровень логирования
        log_level = 'DEBUG' if args.verbose else 'INFO'
        logger.setLevel(log_level)

        # Выводим информацию о системе
        if args.verbose:
            system_info = get_system_info()
            logger.debug(f"Информация о системе: {system_info}")

        # Загружаем данные
        logger.info("1. Загрузка данных...")

        # Проверяем, является ли ip-list файлом или CIDR/диапазоном
        if os.path.exists(args.ip_list):
            # Это файл
            ip_list = DataLoader.load_ip_list(args.ip_list)
        else:
            # Это CIDR, диапазон или одиночный IP
            # Создаем временный файл с этим IP/диапазоном
            import tempfile
            temp_ip_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            temp_ip_file.write(args.ip_list + '\n')
            temp_ip_file.close()
            ip_list = DataLoader.load_ip_list(temp_ip_file.name)
            # Не удаляем временный файл сразу, он удалится при завершении программы

        if not ip_list:
            logger.error("Не загружены IP адреса. Проверьте формат ввода.")
            return

        credentials = DataLoader.load_credentials(args.credentials)
        if not credentials:
            logger.error("Не загружены учетные данные. Проверьте файл или формат.")
            return

        logger.info(f"  Загружено IP адресов: {len(ip_list)}")
        logger.info(f"  Загружено учетных записей: {len(credentials)}")

        # Создаем объект обнаружения
        logger.info("2. Инициализация Network Discovery...")
        discovery = NetworkDiscovery(
            max_workers=args.workers,
            timeout=args.timeout
        )

        # Выполняем обнаружение
        logger.info("3. Запуск обнаружения устройств...")
        logger.info(f"  Потоков: {args.workers}")
        logger.info(f"  Таймаут: {args.timeout} секунд")
        logger.info(f"  Протокол: {args.protocol}")

        start_time = time.time()

        # Фильтруем протоколы если нужно
        if args.protocol != 'both':
            logger.info(f"  Фильтрация по протоколу: {args.protocol}")
            # Создаем копию credentials с указанием протокола
            filtered_credentials = []
            for cred in credentials:
                # Для SSH-only или Telnet-only мы можем настроить таймауты
                if args.protocol == 'ssh':
                    cred.ssh_timeout = args.timeout
                elif args.protocol == 'telnet':
                    cred.telnet_timeout = args.timeout
                filtered_credentials.append(cred)
            credentials = filtered_credentials

        discovered_devices = discovery.discover_devices(ip_list, credentials)

        if not discovered_devices:
            logger.warning("Устройства не обнаружены. Проверьте сеть и учетные данные.")
            return

        # Сохраняем результаты
        logger.info("4. Сохранение результатов...")

        base_filename = args.output
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Определяем какие форматы сохранять
        formats_to_save = []

        if args.format == 'all':
            formats_to_save = ['yaml', 'json', 'csv']
        else:
            formats_to_save.append(args.format)

        # Если в интерактивном режиме выбраны дополнительные форматы, добавляем их
        if args.generate_all:
            formats_to_save = ['yaml', 'json', 'csv']
            args.generate_netmiko = True
            args.generate_ansible = True
            args.generate_report = True

        # Сохраняем в выбранных форматах
        saved_files = []

        for fmt in formats_to_save:
            if fmt == 'yaml':
                filename = base_filename
                saved_files.append(InventorySaver.save_yaml(discovered_devices, filename))

            elif fmt == 'json':
                filename = base_filename.replace('.yaml', '.json').replace('.yml', '.json')
                saved_files.append(InventorySaver.save_json(discovered_devices, filename))

            elif fmt == 'csv':
                filename = base_filename.replace('.yaml', '.csv').replace('.yml', '.csv')
                saved_files.append(InventorySaver.save_csv(discovered_devices, filename))

        # Дополнительные форматы
        if args.generate_netmiko:
            filename = f"inventory/netmiko_inventory_{timestamp}.yaml"
            saved_files.append(InventorySaver.save_netmiko_inventory(discovered_devices, filename))

        if args.generate_ansible:
            filename = f"inventory/ansible_inventory_{timestamp}.yaml"
            saved_files.append(InventorySaver.save_ansible_inventory(discovered_devices, filename))

        if args.generate_report:
            filename = f"reports/discovery_report_{timestamp}.txt"
            saved_files.append(InventorySaver.save_report(discovered_devices, filename))

        # Выводим сводку
        print_summary(discovery, start_time)

        # Выводим информацию о сохраненных файлах
        colors = get_color_codes()
        print(f"\n{colors['bold']}Сохраненные файлы:{colors['reset']}")
        for file in saved_files:
            print(f"  {colors['green']}✓{colors['reset']} {file}")

        logger.info("Обнаружение успешно завершено!")

    except Exception as e:
        logger.error(f"Ошибка при выполнении обнаружения: {e}", exc_info=True)
        raise


def main():
    """Основная функция программы"""
    try:
        # Парсим аргументы
        args = parse_arguments()

        # Если запрошена проверка зависимостей
        if args.check_deps:
            check_requirements()
            print("Все зависимости установлены!")
            return

        # Если запущен с флагом --interactive или без аргументов
        if args.interactive or (not args.ip_list and not args.credentials):
            # Проверяем, нужно ли выйти из интерактивного режима
            colors = get_color_codes()
            print(f"\n{colors['yellow']}Запуск в интерактивном режиме...{colors['reset']}")
            print("Нажмите Ctrl+C для отмены в любой момент.\n")

            args = interactive_mode()
            if args is None:
                return

        # Если все еще нет обязательных параметров
        if not args.ip_list or not args.credentials:
            print("\nОШИБКА: Не указаны обязательные параметры!")
            print("Используйте --help для просмотра справки или запустите с --interactive")
            return

        # Запускаем обнаружение
        run_discovery(args)

    except KeyboardInterrupt:
        print("\n\nОбнаружение прервано пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

logger = setup_logger(__name__)

if __name__ == "__main__":
    main()