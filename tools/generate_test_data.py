import asyncio
import random
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from database.connection import async_session, engine
from database.models import Base, Sensor, Location, SensorReading, Event, EquipmentSetting
import json

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def create_initial_data():
    """Создает начальные данные для тестирования системы"""
    async with async_session() as session:
        try:
            # Проверяем, есть ли записи в таблице местоположений
            location_query = select(Location)
            location_result = await session.execute(location_query)
            locations = location_result.scalars().all()

            if not locations:
                logger.info("Создаем местоположения...")
                locations = [
                    Location(name="Линия подготовки сырья"),
                    Location(name="Формование бутылок"),
                    Location(name="Система охлаждения"),
                    Location(name="Контроль качества"),
                    Location(name="Упаковка")
                ]
                session.add_all(locations)
                await session.commit()

                # Перезагружаем местоположения после добавления
                location_result = await session.execute(location_query)
                locations = location_result.scalars().all()
                logger.info(f"Создано {len(locations)} местоположений")
            else:
                logger.info(f"Найдено {len(locations)} существующих местоположений")

            # Проверяем, есть ли записи в таблице датчиков
            sensor_query = select(Sensor)
            sensor_result = await session.execute(sensor_query)
            sensors = sensor_result.scalars().all()

            if not sensors:
                logger.info("Создаем датчики...")
                test_sensors = [
                    Sensor(sensor_name="Датчик температуры сырья", sensor_type="temperature", status="active",
                           location_id=locations[0].id),
                    Sensor(sensor_name="Датчик давления сырья", sensor_type="pressure", status="active",
                           location_id=locations[0].id),
                    Sensor(sensor_name="Датчик уровня сырья", sensor_type="level", status="active",
                           location_id=locations[0].id),
                    Sensor(sensor_name="Датчик температуры форм", sensor_type="temperature", status="active",
                           location_id=locations[1].id),
                    Sensor(sensor_name="Датчик давления формователя", sensor_type="pressure", status="active",
                           location_id=locations[1].id),
                    Sensor(sensor_name="Датчик скорости формователя", sensor_type="speed", status="active",
                           location_id=locations[1].id),
                    Sensor(sensor_name="Датчик температуры охлаждения", sensor_type="temperature", status="active",
                           location_id=locations[2].id),
                    Sensor(sensor_name="Датчик давления охлаждения", sensor_type="pressure", status="active",
                           location_id=locations[2].id),
                    Sensor(sensor_name="Датчик качества толщины", sensor_type="quality", status="active",
                           location_id=locations[3].id),
                    Sensor(sensor_name="Датчик качества размеров", sensor_type="quality", status="active",
                           location_id=locations[3].id),
                    Sensor(sensor_name="Датчик скорости упаковки", sensor_type="speed", status="active",
                           location_id=locations[4].id),
                    Sensor(sensor_name="Датчик веса упаковки", sensor_type="weight", status="active",
                           location_id=locations[4].id)
                ]
                session.add_all(test_sensors)
                await session.commit()

                # Перезагружаем датчики после добавления
                sensor_result = await session.execute(sensor_query)
                sensors = sensor_result.scalars().all()
                logger.info(f"Создано {len(sensors)} датчиков")
            else:
                logger.info(f"Найдено {len(sensors)} существующих датчиков")

            # Создаем настройки оборудования для датчиков
            for sensor in sensors:
                # Проверяем, есть ли настройки для этого датчика
                settings_query = select(EquipmentSetting).where(
                    EquipmentSetting.sensor_id == sensor.id
                )
                settings_result = await session.execute(settings_query)
                setting = settings_result.scalars().first()

                if not setting:
                    logger.info(f"Создаем настройки для датчика {sensor.sensor_name}...")
                    # Определяем диапазоны в зависимости от типа датчика
                    if "temperature" in sensor.sensor_type:
                        new_setting = EquipmentSetting(
                            sensor_id=sensor.id,
                            min_value="20",
                            max_value="80",
                            interval="60"
                        )
                    elif "pressure" in sensor.sensor_type:
                        new_setting = EquipmentSetting(
                            sensor_id=sensor.id,
                            min_value="1",
                            max_value="10",
                            interval="60"
                        )
                    elif "speed" in sensor.sensor_type:
                        new_setting = EquipmentSetting(
                            sensor_id=sensor.id,
                            min_value="10",
                            max_value="100",
                            interval="60"
                        )
                    elif "level" in sensor.sensor_type:
                        new_setting = EquipmentSetting(
                            sensor_id=sensor.id,
                            min_value="10",
                            max_value="90",
                            interval="60"
                        )
                    elif "quality" in sensor.sensor_type:
                        new_setting = EquipmentSetting(
                            sensor_id=sensor.id,
                            min_value="85",
                            max_value="100",
                            interval="60"
                        )
                    elif "weight" in sensor.sensor_type:
                        new_setting = EquipmentSetting(
                            sensor_id=sensor.id,
                            min_value="0.5",
                            max_value="2.0",
                            interval="60"
                        )
                    else:
                        new_setting = EquipmentSetting(
                            sensor_id=sensor.id,
                            min_value="0",
                            max_value="100",
                            interval="60"
                        )

                    session.add(new_setting)

            await session.commit()
            logger.info("Настройки оборудования созданы или обновлены")

            # Генерируем исторические данные для датчиков за последние 24 часа
            readings_count = await generate_historical_data(session, sensors, hours=24)
            logger.info(f"Сгенерировано {readings_count} исторических показаний датчиков")

        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании начальных данных: {e}")
            raise


async def generate_historical_data(session, sensors, hours=24):
    """Генерирует исторические данные показаний датчиков"""
    try:
        # Получаем настройки для всех датчиков
        settings_dict = {}
        for sensor in sensors:
            settings_query = select(EquipmentSetting).where(
                EquipmentSetting.sensor_id == sensor.id
            )
            settings_result = await session.execute(settings_query)
            setting = settings_result.scalars().first()

            if setting:
                settings_dict[sensor.id] = {
                    'min_value': float(setting.min_value) if setting.min_value else 0,
                    'max_value': float(setting.max_value) if setting.max_value else 100,
                    'interval': int(setting.interval) if setting.interval else 60
                }

        # Генерируем данные
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        total_readings = 0

        # Используем батчи для более эффективной вставки
        batch_size = 100
        readings_batch = []
        events_batch = []

        for sensor in sensors:
            # Пропускаем, если нет настроек
            if sensor.id not in settings_dict:
                continue

            settings = settings_dict[sensor.id]

            # Определяем интервал между точками данных
            interval_minutes = settings['interval'] / 60
            current_time = start_time

            while current_time <= end_time:
                # Генерируем значение с небольшой случайностью
                normal_value = random.uniform(
                    settings['min_value'] + (settings['max_value'] - settings['min_value']) * 0.3,
                    settings['max_value'] - (settings['max_value'] - settings['min_value']) * 0.3
                )

                # Иногда генерируем аномальное значение (10% шанс)
                if random.random() < 0.1:
                    if random.random() < 0.5:
                        # Ниже минимума
                        value = random.uniform(
                            settings['min_value'] * 0.5,
                            settings['min_value'] * 0.9
                        )
                    else:
                        # Выше максимума
                        value = random.uniform(
                            settings['max_value'] * 1.1,
                            settings['max_value'] * 1.5
                        )

                    # Округляем в зависимости от типа датчика
                    if "temperature" in sensor.sensor_type:
                        str_value = str(round(value, 1))
                    elif "pressure" in sensor.sensor_type:
                        str_value = str(round(value, 2))
                    elif "speed" in sensor.sensor_type or "quality" in sensor.sensor_type or "level" in sensor.sensor_type:
                        str_value = str(round(value))
                    elif "weight" in sensor.sensor_type:
                        str_value = str(round(value, 3))
                    else:
                        str_value = str(round(value, 1))

                    # Создаем показание
                    new_reading = SensorReading(
                        sensor_id=sensor.id,
                        value=str_value,
                        time=current_time
                    )
                    readings_batch.append(new_reading)

                    # Создаем оповещение
                    if value < settings['min_value']:
                        message = f"Значение {str_value} ниже допустимого {settings['min_value']}"
                    else:
                        message = f"Значение {str_value} выше допустимого {settings['max_value']}"

                    new_event = Event(
                        sensor_id=sensor.id,
                        alert_type="warning",
                        message=message,
                        location_id=sensor.location_id,
                        value=str_value,
                        timestamp=current_time
                    )
                    events_batch.append(new_event)
                else:
                    # Создаем более реалистичные JSON-данные в зависимости от типа датчика
                    if "temperature" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "°C",
                            "temperature": normal_value
                        }
                    elif "pressure" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "bar",
                            "pressure": normal_value
                        }
                    elif "speed" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "rpm",
                            "speed": normal_value
                        }
                    elif "level" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "%",
                            "level": normal_value
                        }
                    elif "quality" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "%",
                            "quality_index": normal_value
                        }
                    elif "weight" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "kg",
                            "weight": normal_value
                        }
                    else:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "value": normal_value
                        }
                    
                    # Преобразуем словарь в JSON-строку
                    json_value = json.dumps(value_dict)
                    
                    # Создаем показание
                    new_reading = SensorReading(
                        sensor_id=sensor.id,
                        value=json_value,
                        time=current_time
                    )
                    readings_batch.append(new_reading)
                    # Добавляем к счетчику
                    total_readings += 1

                    # Сохраняем батч в БД, если достигнут размер
                    if len(readings_batch) >= batch_size:
                        session.add_all(readings_batch)
                        readings_batch = []

                    if len(events_batch) >= batch_size:
                        session.add_all(events_batch)
                        events_batch = []

                    # Увеличиваем время на интервал
                    current_time += timedelta(minutes=interval_minutes)

            # Сохраняем оставшиеся данные в батчах
            if readings_batch:
                session.add_all(readings_batch)

            if events_batch:
                session.add_all(events_batch)

            await session.commit()
            return total_readings

    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка при генерации исторических данных: {e}")
        raise


async def main():
    # Создаем таблицы, если они не существуют
    async with engine.begin() as conn:
        # Перед созданием таблиц проверим, есть ли они уже
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = result.fetchall()

        if tables:
            logger.info(f"Существующие таблицы в БД: {[t[0] for t in tables]}")
        else:
            logger.info("База данных пуста, создаем схему...")
            await conn.run_sync(Base.metadata.create_all)

    # Создаем начальные данные
    await create_initial_data()

    logger.info("Генерация тестовых данных завершена успешно!")


if __name__ == "__main__":
    import sqlalchemy
    from sqlalchemy.sql import text

    asyncio.run(main())