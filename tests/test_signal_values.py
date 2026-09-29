"""
Автотест для десктоп-приложения управления сигналами.

Сценарий: проверка того, что значения сигналов, отображаемые в приложении,
соответствуют данным, полученным от сервиса-симулятора по TCP.

Логика теста:
1. Поднимаем сервис-симулятор (или используем уже запущенный на порту 2001).
2. Подключаемся к нему напрямую как клиент и получаем эталонные данные.
3. Подключаем приложение к сервису и нажимаем "Обновить".
4. Считываем значения из таблицы приложения.
5. Сравниваем: значения в приложении должны совпадать с эталонными.

Зависимости:
    pip install pytest pywinauto
    (pywinauto — для работы с desktop UI; для Linux/macOS заменить на соответствующий
     инструмент, например dogtail или pyautogui)

---------------------------------------------------------------------------
Automated test for the signal management desktop application.

Scenario: verify that the signal values displayed in the application
match the data received from the simulator service over TCP.

Test logic:
1. Start the simulator service (or use one already running on port 2001).
2. Connect to it directly as a client and retrieve the reference data.
3. Connect the application to the service and click "Refresh".
4. Read the values from the application's table.
5. Compare: the values in the application must match the reference data.

Dependencies:
    pip install pytest pywinauto
    (pywinauto — for desktop UI automation; for Linux/macOS replace it with
     an equivalent tool such as dogtail or pyautogui)
"""

import socket
import time
import re
import pytest
from pywinauto.application import Application


# --- Конфигурация ---
SERVICE_HOST = "127.0.0.1"
SERVICE_PORT = 2001
APP_PATH = r"C:\Path\To\SignalApp.exe"   # путь к исполняемому файлу приложения
EXPECTED_SIGNAL_COUNT = 10


def read_reference_signals(host, port, timeout=5):
    """
    Подключается к сервису-симулятору напрямую и считывает эталонные значения.
    Возвращает список словарей: [{"id": ..., "value": ...}, ...].

    Предполагается, что сервис отдаёт данные в простом текстовом формате,
    например: 'ID=1;VALUE=42.5\nID=2;VALUE=17.3\n...'
    Если формат другой — парсер нужно адаптировать под него.
    """
    signals = []
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        buffer = b""
        # Читаем данные, пока не получим все сигналы или не истечёт таймаут
        deadline = time.time() + timeout
        while len(signals) < EXPECTED_SIGNAL_COUNT and time.time() < deadline:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
            except socket.timeout:
                break

        # Парсим полученные строки
        text = buffer.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            match = re.match(r"ID=(\d+);VALUE=([\d.\-]+)", line.strip())
            if match:
                signals.append({
                    "id": int(match.group(1)),
                    "value": float(match.group(2)),
                })
    return signals


def read_app_signals(window):
    """
    Считывает значения сигналов из таблицы главного окна приложения.
    Возвращает словарь {id: value}.

    Логика: находим таблицу в окне, проходим по строкам, забираем ID и значение.
    Конкретные имена контролов зависят от реализации приложения —
    их нужно уточнить через Inspect.exe или аналогичный инструмент.
    """
    app_signals = {}
    table = window.child_window(control_type="Table")  # уточнить control_type

    # Получаем все строки таблицы
    rows = table.children(control_type="DataItem")
    for row in rows:
        cells = row.children()
        if len(cells) < 3:
            continue
        try:
            signal_id = int(cells[0].window_text().strip())   # колонка ID
            value = float(cells[2].window_text().strip())     # колонка "значение"
            app_signals[signal_id] = value
        except (ValueError, AttributeError):
            # Пропускаем строки, которые не удалось распарсить
            continue
    return app_signals


@pytest.fixture(scope="module")
def app():
    """
    Фикстура: запускает приложение, подключается к сервису, дожидается загрузки данных.
    После завершения теста — корректно закрывает приложение.
    """
    application = Application(backend="uia").start(APP_PATH)
    main_window = application.window(title_re=".*Signal.*")  # уточнить заголовок окна
    main_window.wait("ready", timeout=10)

    # Нажимаем "Подключиться"
    main_window.child_window(title="Подключиться", control_type="Button").click()
    time.sleep(2)  # даём время на установку соединения и первичную загрузку

    yield main_window

    # Закрываем приложение после тестов
    main_window.close()
    time.sleep(1)


def test_signal_values_match_service(app):
    """
    Критичный сценарий: значения сигналов в приложении должны совпадать
    с данными, которые отдаёт сервис-симулятор.

    Шаги:
    1. Получаем эталонные данные от сервиса напрямую (как TCP-клиент).
    2. Нажимаем "Обновить" в приложении.
    3. Считываем значения из таблицы.
    4. Сравниваем — расхождение считается дефектом.
    """
    # Шаг 1: эталонные данные от сервиса
    reference_signals = read_reference_signals(SERVICE_HOST, SERVICE_PORT)

    # Проверяем, что сервис вообще отдал данные — иначе тест бессмысленен
    assert len(reference_signals) == EXPECTED_SIGNAL_COUNT, (
        f"Сервис-симулятор вернул {len(reference_signals)} сигналов, "
        f"ожидалось {EXPECTED_SIGNAL_COUNT}"
    )

    # Шаг 2: запрашиваем обновление в приложении
    app.child_window(title="Обновить", control_type="Button").click()
    time.sleep(2)  # даём приложению получить и отобразить новые значения

    # Шаг 3: считываем значения из таблицы приложения
    app_signals = read_app_signals(app)

    # Шаг 4: сравниваем
    assert len(app_signals) == EXPECTED_SIGNAL_COUNT, (
        f"Приложение отображает {len(app_signals)} сигналов, "
        f"ожидалось {EXPECTED_SIGNAL_COUNT}"
    )

    mismatches = []
    for ref in reference_signals:
        signal_id = ref["id"]
        expected_value = ref["value"]

        assert signal_id in app_signals, (
            f"Сигнал ID={signal_id} отсутствует в таблице приложения"
        )

        actual_value = app_signals[signal_id]

        # Допуск на округление: значения с плавающей точкой могут отображаться
        # с меньшей точностью, чем приходят по сети
        if abs(actual_value - expected_value) > 0.01:
            mismatches.append(
                f"ID={signal_id}: в приложении {actual_value}, "
                f"от сервиса {expected_value}"
            )

    # Если есть расхождения — тест падает с понятным списком
    assert not mismatches, (
        "Значения сигналов в приложении не совпадают с данными от сервиса:\n"
        + "\n".join(mismatches)
    )