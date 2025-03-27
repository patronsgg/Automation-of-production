import asyncio
import logging
from kafka.producer import get_producer, produce_message, close_producer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_kafka_connection():
    try:
        # Тест продюсера
        logger.info("Тестирование подключения к Kafka...")
        producer = await get_producer()

        if producer:
            logger.info("Kafka продюсер успешно создан")

            # Тест отправки сообщения
            test_data = {"test": "message", "value": 123}
            await produce_message("raw_material_data", test_data)
            logger.info(f"Тестовое сообщение отправлено: {test_data}")

            # Закрытие продюсера
            await close_producer()
        else:
            logger.error("Не удалось создать Kafka продюсер")

    except Exception as e:
        logger.error(f"Ошибка при тестировании Kafka: {e}")


if __name__ == "__main__":
    asyncio.run(test_kafka_connection())