import json
import asyncio
from aiokafka import AIOKafkaConsumer
from config import config
from processing.data_processor import process_data
import logging

logger = logging.getLogger(__name__)


async def consume_messages(topics):
    """Асинхронный консьюмер для Kafka топиков"""
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id="pet_bottle_monitoring"
    )

    try:
        await consumer.start()
        logger.info(f"Kafka консьюмер запущен для топиков: {topics}")

        async for msg in consumer:
            logger.debug(f"Получено сообщение из {msg.topic}: {msg.value}")

            # Асинхронная обработка сообщения
            await process_data(msg.topic, msg.value)

    except Exception as e:
        logger.error(f"Ошибка при работе Kafka консьюмера: {e}")
    finally:
        await consumer.stop()
        logger.info("Kafka консьюмер остановлен")


async def start_consumers():
    """Запускает консьюмеры для всех нужных топиков"""
    topics = [
        "raw_material_data",
        "bottle_forming_data",
        "cooling_data",
        "quality_data",
        "packaging_data",
        "alerts"
    ]

    # Запускаем консьюмер как отдельную задачу
    consumer_task = asyncio.create_task(consume_messages(topics))
    return consumer_task