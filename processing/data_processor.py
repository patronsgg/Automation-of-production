import asyncio
import logging
import json
from sqlalchemy import select
from database.connection import async_session
from database.models import SensorReading, Sensor, Event, EquipmentSetting
from processing.alerts import check_alert_conditions

logger = logging.getLogger(__name__)


async def process_data(topic, data):
    """Асинхронная обработка данных, полученных из MQTT/Kafka"""
    try:
        logger.debug(f"Обработка данных из топика {topic}: {data}")

        # Если данные пришли в виде строки, преобразуем их в словарь
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logger.error(f"Невозможно преобразовать данные в JSON: {data}")
                return

        # Проверяем, есть ли в данных идентификатор датчика
        if "sensor_id" in data:
            sensor_id = data["sensor_id"]
        elif "id" in data:
            sensor_id = data["id"]
        else:
            # Пытаемся определить датчик из топика
            async with async_session() as session:
                # Извлекаем последнюю часть топика как имя датчика
                topic_parts = topic.split('/')
                sensor_type = topic_parts[-1] if len(topic_parts) > 1 else topic

                # Ищем датчик по типу
                query = select(Sensor).where(Sensor.sensor_name.like(f"%{sensor_type}%"))
                result = await session.execute(query)
                sensor = result.scalars().first()

                if sensor:
                    sensor_id = sensor.id
                    logger.debug(f"Определен sensor_id={sensor_id} из топика {topic}")
                else:
                    logger.warning(f"Не удалось определить датчик из топика {topic}")
                    return

        # Определяем тип значения для сохранения
        if isinstance(data, dict):
            # Извлекаем числовое значение для проверки оповещений
            numeric_value = None

            # Пытаемся найти числовое значение для оповещений
            for key in ['value', 'temperature', 'pressure', 'humidity', 'speed', 'level', 'weight', 'flow_rate',
                        'wall_thickness']:
                if key in data and isinstance(data[key], (int, float)):
                    numeric_value = data[key]
                    break

            # Сохраняем всё как JSON-строку
            value_to_save = json.dumps(data)

            # Сохраняем показание датчика
            await save_sensor_reading(sensor_id, value_to_save, numeric_value)
        else:
            # Если это не словарь, сохраняем как есть
            await save_sensor_reading(sensor_id, str(data))

    except Exception as e:
        logger.error(f"Ошибка обработки данных: {e}")


async def save_sensor_reading(sensor_id, value, numeric_value=None):
    """Сохранение показаний датчика в БД"""
    async with async_session() as session:
        try:
            # Создаем новую запись показаний датчика
            new_reading = SensorReading(sensor_id=sensor_id, value=value)
            session.add(new_reading)

            # Проверяем условия для оповещений, только если есть числовое значение
            if numeric_value is not None:
                await check_alert_conditions(sensor_id, numeric_value)

            await session.commit()
            logger.debug(f"Сохранено показание датчика: sensor_id={sensor_id}, value={value}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при сохранении показания датчика: {e}")


async def process_raw_material_data(data):
    """Обработка данных по сырью"""
    try:
        # Обработка специфичная для сырья
        logger.debug(f"Обработка данных по сырью: {data}")
        # Здесь может быть дополнительная логика...
    except Exception as e:
        logger.error(f"Ошибка обработки данных по сырью: {e}")


async def process_bottle_forming_data(data):
    """Обработка данных по формованию бутылок"""
    try:
        # Обработка специфичная для формования
        logger.debug(f"Обработка данных по формованию бутылок: {data}")
        # Здесь может быть дополнительная логика...
    except Exception as e:
        logger.error(f"Ошибка обработки данных по формованию бутылок: {e}")


async def process_cooling_data(data):
    """Обработка данных по охлаждению"""
    try:
        # Обработка специфичная для охлаждения
        logger.debug(f"Обработка данных по охлаждению: {data}")
        # Здесь может быть дополнительная логика...
    except Exception as e:
        logger.error(f"Ошибка обработки данных по охлаждению: {e}")


async def process_quality_data(data):
    """Обработка данных по контролю качества"""
    try:
        # Обработка специфичная для контроля качества
        logger.debug(f"Обработка данных по контролю качества: {data}")
        # Здесь может быть дополнительная логика...
    except Exception as e:
        logger.error(f"Ошибка обработки данных по контролю качества: {e}")


async def process_packaging_data(data):
    """Обработка данных по упаковке"""
    try:
        # Обработка специфичная для упаковки
        logger.debug(f"Обработка данных по упаковке: {data}")
        # Здесь может быть дополнительная логика...
    except Exception as e:
        logger.error(f"Ошибка обработки данных по упаковке: {e}")