import paho.mqtt.client as mqtt
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Параметры подключения
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

# Колбеки
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Успешное подключение к MQTT брокеру")
        # Подписываемся на тестовый топик
        client.subscribe("test/topic")
    else:
        logger.error(f"Не удалось подключиться, код возврата: {rc}")

def on_message(client, userdata, msg):
    logger.info(f"Получено сообщение: {msg.topic} {msg.payload.decode()}")

def on_disconnect(client, userdata, rc):
    logger.info(f"Отключение от брокера, код возврата: {rc}")

def on_log(client, userdata, level, buf):
    logger.debug(f"MQTT лог: {buf}")

# Создаем клиент
client = mqtt.Client()

# Устанавливаем колбеки
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect
client.on_log = on_log

# Устанавливаем логин и пароль, если они указаны
if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

try:
    logger.info(f"Попытка подключения к {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    # Запускаем цикл обработки сетевого трафика в отдельном потоке
    client.loop_start()
    
    # Публикуем тестовое сообщение
    logger.info("Отправка тестового сообщения...")
    client.publish("test/topic", "Hello from Python!")
    
    # Ждем немного, чтобы сообщение было доставлено
    time.sleep(3)
    
    # Останавливаем цикл и отключаемся
    client.loop_stop()
    client.disconnect()
    logger.info("Тест завершен")
    
except Exception as e:
    logger.error(f"Ошибка: {e}") 