import asyncio
import random
import time
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
import json
import logging
import argparse

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("simulator")

# Параметры MQTT по умолчанию
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

# Конфигурация датчиков, соответствующая init_db.py
SENSORS = {
    # Датчики линии подготовки сырья
    "raw_material_temp": {"id": 1, "topic": "pet/raw-material/temperature", "min": 20, "max": 80, "unit": "°C", 
                         "name": "Датчик температуры сырья"},
    "raw_material_pressure": {"id": 2, "topic": "pet/raw-material/pressure", "min": 1, "max": 10, "unit": "bar", 
                             "name": "Датчик давления сырья"},
    "raw_material_level": {"id": 3, "topic": "pet/raw-material/level", "min": 10, "max": 90, "unit": "%", 
                          "name": "Датчик уровня сырья"},
    
    # Датчики формования бутылок
    "forming_temp": {"id": 4, "topic": "pet/bottleforming/temperature", "min": 20, "max": 80, "unit": "°C", 
                    "name": "Датчик температуры форм"},
    "forming_pressure": {"id": 5, "topic": "pet/bottleforming/pressure", "min": 1, "max": 10, "unit": "bar", 
                        "name": "Датчик давления формователя"},
    "forming_speed": {"id": 6, "topic": "pet/bottleforming/speed", "min": 10, "max": 100, "unit": "rpm", 
                     "name": "Датчик скорости формователя"},
    
    # Датчики системы охлаждения
    "cooling_temp": {"id": 7, "topic": "pet/cooling/temperature", "min": 20, "max": 80, "unit": "°C", 
                    "name": "Датчик температуры охлаждения"},
    "cooling_pressure": {"id": 8, "topic": "pet/cooling/pressure", "min": 1, "max": 10, "unit": "bar", 
                        "name": "Датчик давления охлаждения"},
    "cooling_flow": {"id": 9, "topic": "pet/cooling/flow", "min": 50, "max": 150, "unit": "л/мин", 
                    "name": "Датчик расхода охлаждающей жидкости"},
    
    # Датчики контроля качества
    "quality_thickness": {"id": 10, "topic": "pet/quality/thickness", "min": 85, "max": 100, "unit": "%", 
                         "name": "Датчик качества толщины"},
    "quality_dimensions": {"id": 11, "topic": "pet/quality/dimensions", "min": 85, "max": 100, "unit": "%", 
                          "name": "Датчик качества размеров"},
    
    # Датчики упаковки
    "packaging_speed": {"id": 12, "topic": "pet/packaging/speed", "min": 10, "max": 100, "unit": "шт/мин", 
                       "name": "Датчик скорости упаковки"},
    "packaging_weight": {"id": 13, "topic": "pet/packaging/weight", "min": 0.5, "max": 2.0, "unit": "кг", 
                        "name": "Датчик веса упаковки"}
}


# Функция для генерации случайных значений для датчика
def generate_value(sensor, anomaly_chance=0.05):
    """Генерирует случайное значение для датчика с возможностью аномалий"""
    base_value = random.uniform(sensor["min"], sensor["max"])

    # Иногда генерируем аномальные значения для тестирования системы оповещений
    if random.random() < anomaly_chance:
        # 50% шанс превышения максимального значения
        if random.random() < 0.5:
            return sensor["max"] * (1 + random.uniform(0.1, 0.5))
        # 50% шанс значения ниже минимального
        else:
            return sensor["min"] * (1 - random.uniform(0.1, 0.5))

    return base_value


# Функция для отправки данных в MQTT
def send_sensor_data(client, sensor_name, sensor_config, anomaly_chance=0.05):
    """Отправляет сгенерированные данные датчика в MQTT топик"""
    value = generate_value(sensor_config, anomaly_chance)
    timestamp = datetime.now().isoformat()

    # Формируем сообщение
    message = {
        "sensor_id": sensor_config["id"],
        "timestamp": timestamp,
        "unit": sensor_config["unit"]
    }

    # Добавляем специфичное название параметра в зависимости от датчика
    if "temp" in sensor_name:
        message["temperature"] = round(value, 1)
    elif "pressure" in sensor_name:
        message["pressure"] = round(value, 2)
    elif "level" in sensor_name:
        message["level"] = round(value, 1)
    elif "flow" in sensor_name:
        message["flow_rate"] = round(value, 2)
    elif "thickness" in sensor_name:
        message["quality_index"] = round(value, 1)
    elif "dimensions" in sensor_name:
        message["quality_index"] = round(value, 1)
    elif "speed" in sensor_name:
        message["speed"] = round(value)
    elif "weight" in sensor_name:
        message["weight"] = round(value, 3)
    else:
        message["value"] = round(value, 2)

    # Отправляем сообщение
    client.publish(sensor_config["topic"], json.dumps(message))
    logger.info(f"Отправлено: {sensor_config['topic']} - {json.dumps(message)}")


# Функция для генерации исторических данных
def generate_historical_data(client, days=7, interval_minutes=15, anomaly_chance=0.05):
    """Генерирует исторические данные за указанный период"""
    logger.info(f"Генерация исторических данных за {days} дней с интервалом {interval_minutes} минут")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    current_time = start_time
    bottles_count = 0

    while current_time < end_time:
        # Формируем временную метку
        timestamp = current_time.isoformat()

        # Проходим по всем датчикам
        for sensor_name, sensor_config in SENSORS.items():
            # Создаем сообщение
            value = generate_value(sensor_config, anomaly_chance)
            message = {
                "sensor_id": sensor_config["id"],
                "timestamp": timestamp,
                "unit": sensor_config["unit"]
            }

            # Добавляем специфичное название параметра
            if "temp" in sensor_name:
                message["temperature"] = round(value, 1)
            elif "pressure" in sensor_name:
                message["pressure"] = round(value, 2)
            elif "level" in sensor_name:
                message["level"] = round(value, 1)
            elif "flow" in sensor_name:
                message["flow_rate"] = round(value, 2)
            elif "thickness" in sensor_name or "dimensions" in sensor_name:
                message["quality_index"] = round(value, 1)
            elif "speed" in sensor_name:
                message["speed"] = round(value)
            elif "weight" in sensor_name:
                message["weight"] = round(value, 3)
            else:
                message["value"] = round(value, 2)

            # Отправляем сообщение
            client.publish(sensor_config["topic"], json.dumps(message))

        # Логируем процесс через равные промежутки времени
        if current_time.minute % 60 == 0 and current_time.second == 0:
            logger.info(f"Генерация данных для {current_time}")

        # Увеличиваем время на интервал
        current_time += timedelta(minutes=interval_minutes)

        # Пауза для предотвращения перегрузки брокера
        time.sleep(0.01)

    logger.info("Генерация исторических данных завершена")


# Основная функция для запуска симулятора
def run_simulator(broker=MQTT_BROKER, port=MQTT_PORT, username=MQTT_USERNAME,
                  password=MQTT_PASSWORD, interval=5, historical=False,
                  days=7, anomaly_chance=0.05):
    """Запускает симулятор данных датчиков"""
    logger.info(f"Запуск симулятора датчиков с подключением к {broker}:{port}")

    # Настройка MQTT клиента
    client = mqtt.Client()

    # Установка аутентификации, если требуется
    if username and password:
        client.username_pw_set(username, password)

    # Подключение к брокеру
    try:
        client.connect(broker, port, 60)
        logger.info(f"Подключено к MQTT брокеру {broker}:{port}")
    except Exception as e:
        logger.error(f"Ошибка подключения к MQTT брокеру: {e}")
        return

    client.loop_start()

    try:
        # Если нужны исторические данные, генерируем их
        if historical:
            generate_historical_data(client, days, 15, anomaly_chance)

        # Бесконечный цикл генерации текущих данных
        while True:
            # Отправляем данные со всех датчиков
            for sensor_name, sensor_config in SENSORS.items():
                send_sensor_data(client, sensor_name, sensor_config, anomaly_chance)

            # Задержка между отправками
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Симулятор остановлен пользователем")
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info("Отключено от MQTT брокера")


if __name__ == "__main__":
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Симулятор датчиков для системы мониторинга ПЭТ бутылок')

    parser.add_argument('--broker', default=MQTT_BROKER, help='Адрес MQTT брокера')
    parser.add_argument('--port', type=int, default=MQTT_PORT, help='Порт MQTT брокера')
    parser.add_argument('--username', default=MQTT_USERNAME, help='Имя пользователя MQTT')
    parser.add_argument('--password', default=MQTT_PASSWORD, help='Пароль MQTT')
    parser.add_argument('--interval', type=int, default=5, help='Интервал отправки данных (сек)')
    parser.add_argument('--historical', action='store_true', help='Генерировать исторические данные')
    parser.add_argument('--days', type=int, default=7, help='Количество дней для исторических данных')
    parser.add_argument('--anomaly', type=float, default=0.05, help='Вероятность аномалий (0-1)')

    args = parser.parse_args()

    # Запуск симулятора с указанными параметрами
    run_simulator(
        broker=args.broker,
        port=args.port,
        username=args.username,
        password=args.password,
        interval=args.interval,
        historical=args.historical,
        days=args.days,
        anomaly_chance=args.anomaly
    )