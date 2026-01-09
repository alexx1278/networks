"""
Этап 1: Базовое подключение к одному устройству
Цель: Освоить взаимодействие с одним сетевым устройством через SSH
"""

from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException
import sys
from datetime import datetime
import os

# Создаем директорию для логов, если её нет
os.makedirs('../logs', exist_ok=True)

# Параметры подключения к устройству
device_params = {
    'device_type': 'cisco_ios_telnet',  # тип устройства
    'host': '192.168.12.178',       # IP-адрес устройства
    'username': 'admin',         # имя пользователя
    'password': 'cisco123',      # пароль
    'secret': 'cisco123',        # enable пароль (если нужен)
    'timeout': 10,               # таймаут подключения
}

# Команды для выполнения
commands = [
    'show version',
    'show running-config',
]

def connect_to_device(device_params, commands):
    """Функция для подключения к устройству и выполнения команд"""

    print(f"Попытка подключения к {device_params['host']}...")

    try:
        # Устанавливаем соединение
        connection = ConnectHandler(**device_params)

        # Переходим в режим enable (привилегированный режим)
        connection.enable()

        results = []

        # Выполняем каждую команду
        for command in commands:
            print(f"Выполняю команду: {command}")
            output = connection.send_command(command)
            results.append(f"\n{'='*60}\nКоманда: {command}\n{'='*60}\n{output}")

            # Для show running-config можно добавить паузу для длинных выводов
            if 'running-config' in command:
                print(f"Конфигурация получена (длина: {len(output)} символов)")

        # Закрываем соединение
        connection.disconnect()
        print(f"Подключение к {device_params['host']} закрыто")

        return results

    except NetMikoTimeoutException:
        print(f"Ошибка: Не удалось подключиться к {device_params['host']} (таймаут)")
        return None
    except NetMikoAuthenticationException:
        print(f"Ошибка: Неверные учетные данные для {device_params['host']}")
        return None
    except Exception as e:
        print(f"Неизвестная ошибка при подключении к {device_params['host']}: {str(e)}")
        return None

def save_results_to_file(hostname, results):
    """Сохранение результатов в файл"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"../logs/{hostname}_{timestamp}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Лог подключения к устройству {hostname}\n")
        f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n\n")

        for result in results:
            f.write(result)

    print(f"Результаты сохранены в файл: {filename}")
    return filename

def main():
    print("=" * 60)
    print("Этап 1: Базовое подключение к одному устройству")
    print("=" * 60)

    # Получаем результаты от устройства
    results = connect_to_device(device_params, commands)

    if results:
        # Выводим результаты на экран (первые 500 символов каждой команды)
        print("\n" + "="*60)
        print("КРАТКИЙ ВЫВОД РЕЗУЛЬТАТОВ (первые 500 символов):")
        print("="*60)

        for result in results:
            print(result[:500] + "..." if len(result) > 500 else result)
            print()

        # Сохраняем полные результаты в файл
        save_results_to_file(device_params['host'], results)

        print("=" * 60)
        print("Задание успешно выполнено!")
        print("=" * 60)

if __name__ == "__main__":
    main()