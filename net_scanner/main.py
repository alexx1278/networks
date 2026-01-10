"""
Главный модуль сканера IP-адресов
"""

import asyncio
import sys
from typing import List

from config import ConfigLoader
from ip_parser import IPParser
from scanner import AsyncPingScanner
from reporter import ReportGenerator
from utils import (
    setup_logging,
    print_banner,
    print_summary,
    validate_environment,
    get_input_file
)


async def main():
    """Основная функция"""
    # Печатаем баннер
    print_banner()

    # Проверяем окружение
    if not validate_environment():
        sys.exit(1)

    try:
        # Загружаем конфигурацию
        print("Загрузка конфигурации...")
        config = ConfigLoader.load()

        # Настраиваем логирование
        setup_logging(config)

        # Получаем файл с IP-адресами
        input_file = get_input_file()
        if input_file is None:
            print(f"Ошибка: Файл с IP-адресами не найден")
            print("Создайте файл ips.txt или укажите другой файл в конфигурации")
            sys.exit(1)

        # Обновляем конфигурацию с фактическим именем файла
        config.input_file = str(input_file)

        # Проверяем файл перед парсингом
        print(f"\nПроверка файла {input_file}...")
        validation = IPParser.validate_file(str(input_file))

        if not validation['valid']:
            print(f"Ошибки в файле {input_file}:")
            for error in validation['errors']:
                print(f"  {error}")

            if validation['ip_count'] == 0:
                print("\nНе найдено корректных IP-адресов.")
                print("Создать пример файла? (y/n): ", end="")
                choice = input().strip().lower()
                if choice == 'y':
                    IPParser._create_example_file(str(input_file))
                    print(f"Пример файла создан: {input_file}")
                    print("Отредактируйте его и запустите сканирование снова.")
                sys.exit(1)

        print(f"Файл проверен: {validation['successful_lines']}/{validation['total_lines']} строк корректны")
        print(f"Найдено IP-адресов: {validation['ip_count']}")

        # Парсим IP-адреса
        print(f"\nЧтение IP-адресов из {input_file}...")
        ip_set = IPParser.parse_file(str(input_file))

        # Фильтруем локальные адреса если нужно
        if config.exclude_self:
            print("Фильтрация локальных адресов...")
            original_count = len(ip_set)
            ip_set = IPParser.filter_local_ips(ip_set)
            if len(ip_set) < original_count:
                print(f"  Удалено {original_count - len(ip_set)} локальных адресов")

        # Преобразуем в список и сортируем
        ip_list = IPParser.sort_ips(list(ip_set))

        if not ip_list:
            print("Ошибка: Не найдено IP-адресов для сканирования")
            sys.exit(1)

        # Печатаем сводку
        print_summary(config, len(ip_list))

        # Создаем и запускаем сканер
        scanner = AsyncPingScanner(config)
        results = await scanner.scan_hosts(ip_list)

        # Получаем данные для отчета
        scan_data = scanner.get_summary()

        # Генерируем отчет
        print("\nГенерация отчета...")
        reporter = ReportGenerator(config)
        report = reporter.generate(scan_data)

        # Сохраняем отчет
        reporter.save_report(report)

        # Сохраняем сырые результаты если нужно
        if config.save_raw_results:
            reporter.save_raw_results({
                "config": config.to_dict(),
                "results": results,
                "summary": scan_data
            })

        # Выводим отчет в консоль для текстового формата
        if config.report_format.value == "text":
            print("\n" + report)
        else:
            print(f"\nОтчет сохранен в файл: {config.output_file}")

        # Итоговая статистика
        print("\n" + "="*60)
        print("ИТОГИ СКАНИРОВАНИЯ:")
        print(f"  Проверено хостов: {scan_data['summary']['total']}")
        print(f"  Доступно: {scan_data['summary']['alive']} "
              f"({scan_data['summary']['alive_percent']:.1f}%)")
        print(f"  Среднее время отклика: {scan_data['summary']['avg_latency_ms']:.2f} мс")
        print(f"  Общее время сканирования: {scan_data['summary']['scan_duration_seconds']:.1f} сек")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\nСканирование прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\nОшибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())