import asyncio
import logging
import random
import json
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select

from database.connection import engine, async_session
from database.models import Base, Employee, Role, Sensor, SensorReading, Event, Location, EquipmentSetting


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Тестовые данные
ROLES = [
    {"name": "admin", "description": "Администратор системы"},
    {"name": "operator", "description": "Оператор производства"},
    {"name": "manager", "description": "Менеджер производства"},
    {"name": "technician", "description": "Технический специалист"}
]

EMPLOYEES = [
    {"username": "admin", "email": "admin@example.com", "password": "admin123", "role": "admin"},
    {"username": "operator1", "email": "operator1@example.com", "password": "operator123", "role": "operator"},
    {"username": "operator2", "email": "operator2@example.com", "password": "operator123", "role": "operator"},
    {"username": "manager", "email": "manager@example.com", "password": "manager123", "role": "manager"},
    {"username": "tech", "email": "tech@example.com", "password": "tech123", "role": "technician"}
]

LOCATIONS = [
    {"name": "Линия подготовки сырья"},
    {"name": "Формование бутылок"},
    {"name": "Система охлаждения"},
    {"name": "Контроль качества"},
    {"name": "Упаковка"}
]

SENSORS = [
    {"sensor_name": "Датчик температуры сырья", "sensor_type": "temperature", "status": "active",
     "location": "Линия подготовки сырья"},
    {"sensor_name": "Датчик давления сырья", "sensor_type": "pressure", "status": "active",
     "location": "Линия подготовки сырья"},
    {"sensor_name": "Датчик уровня сырья", "sensor_type": "level", "status": "active",
     "location": "Линия подготовки сырья"},
    {"sensor_name": "Датчик температуры форм", "sensor_type": "temperature", "status": "active",
     "location": "Формование бутылок"},
    {"sensor_name": "Датчик давления формователя", "sensor_type": "pressure", "status": "active",
     "location": "Формование бутылок"},
    {"sensor_name": "Датчик скорости формователя", "sensor_type": "speed", "status": "active",
     "location": "Формование бутылок"},
    {"sensor_name": "Датчик температуры охлаждения", "sensor_type": "temperature", "status": "active",
     "location": "Система охлаждения"},
    {"sensor_name": "Датчик давления охлаждения", "sensor_type": "pressure", "status": "active",
     "location": "Система охлаждения"},
    {"sensor_name": "Датчик расхода охлаждающей жидкости", "sensor_type": "flow", "status": "active",
     "location": "Система охлаждения"},
    {"sensor_name": "Датчик качества толщины", "sensor_type": "quality", "status": "active",
     "location": "Контроль качества"},
    {"sensor_name": "Датчик качества размеров", "sensor_type": "quality", "status": "active",
     "location": "Контроль качества"},
    {"sensor_name": "Датчик скорости упаковки", "sensor_type": "speed", "status": "active", "location": "Упаковка"},
    {"sensor_name": "Датчик веса упаковки", "sensor_type": "weight", "status": "active", "location": "Упаковка"}
]


async def create_tables():
    """Создание всех таблиц в базе данных"""
    async with engine.begin() as conn:
        # Удаляем существующие таблицы, если указан флаг пересоздания
        # await conn.run_sync(Base.metadata.drop_all)

        # Создаем таблицы
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы созданы успешно")


async def create_roles():
    """Создание ролей в системе"""
    async with async_session() as session:
        try:
            # Проверяем наличие существующих ролей
            existing_query = select(Role)
            existing_result = await session.execute(existing_query)
            existing_roles = existing_result.scalars().all()

            if existing_roles:
                logger.info(f"Найдено {len(existing_roles)} существующих ролей")
                return {role.name: role for role in existing_roles}

            # Создаем роли
            roles = []
            for role_data in ROLES:
                role = Role(**role_data)
                roles.append(role)
                session.add(role)

            await session.commit()
            logger.info(f"Создано {len(roles)} ролей")

            # Возвращаем словарь ролей для использования в других функциях
            role_dict = {}
            for role in roles:
                await session.refresh(role)
                role_dict[role.name] = role

            return role_dict
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании ролей: {e}")
            raise


async def create_employees(roles):
    """Создание тестовых сотрудников"""
    async with async_session() as session:
        try:
            # Проверяем наличие существующих сотрудников
            existing_query = select(Employee)
            existing_result = await session.execute(existing_query)
            existing_employees = existing_result.scalars().all()

            if existing_employees:
                logger.info(f"Найдено {len(existing_employees)} существующих сотрудников")
                return

            # Создаем сотрудников
            employees = []
            for emp_data in EMPLOYEES:
                role_name = emp_data.pop("role")
                # Хешируем пароль
                password = emp_data.pop("password")
                hashed_password = password

                # Создаем сотрудника
                employee = Employee(
                    **emp_data,
                    hashed_password=hashed_password,
                    role_id=roles[role_name].id
                )
                employees.append(employee)
                session.add(employee)

            await session.commit()
            logger.info(f"Создано {len(employees)} сотрудников")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании сотрудников: {e}")
            raise


async def create_locations():
    """Создание местоположений в системе"""
    async with async_session() as session:
        try:
            # Проверяем наличие существующих местоположений
            existing_query = select(Location)
            existing_result = await session.execute(existing_query)
            existing_locations = existing_result.scalars().all()

            if existing_locations:
                logger.info(f"Найдено {len(existing_locations)} существующих местоположений")
                return {location.name: location for location in existing_locations}

            # Создаем местоположения
            locations = []
            for loc_data in LOCATIONS:
                location = Location(**loc_data)
                locations.append(location)
                session.add(location)

            await session.commit()
            logger.info(f"Создано {len(locations)} местоположений")

            # Возвращаем словарь местоположений для использования в других функциях
            location_dict = {}
            for location in locations:
                await session.refresh(location)
                location_dict[location.name] = location

            return location_dict
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании местоположений: {e}")
            raise


async def create_sensors(locations):
    """Создание датчиков в системе"""
    async with async_session() as session:
        try:
            # Проверяем наличие существующих датчиков
            existing_query = select(Sensor)
            existing_result = await session.execute(existing_query)
            existing_sensors = existing_result.scalars().all()

            if existing_sensors:
                logger.info(f"Найдено {len(existing_sensors)} существующих датчиков")
                return existing_sensors

            # Создаем датчики
            sensors = []
            for sensor_data in SENSORS:
                location_name = sensor_data.pop("location")
                sensor = Sensor(
                    **sensor_data,
                    location_id=locations[location_name].id
                )
                sensors.append(sensor)
                session.add(sensor)

            await session.commit()
            logger.info(f"Создано {len(sensors)} датчиков")

            # Возвращаем список датчиков для использования в других функциях
            return sensors
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании датчиков: {e}")
            raise


async def create_equipment_settings(sensors):
    """Создание настроек оборудования для датчиков"""
    async with async_session() as session:
        try:
            # Проверяем наличие существующих настроек
            existing_query = select(EquipmentSetting)
            existing_result = await session.execute(existing_query)
            existing_settings = existing_result.scalars().all()

            if existing_settings:
                logger.info(f"Найдено {len(existing_settings)} существующих настроек оборудования")
                return

            # Создаем настройки для датчиков
            settings = []
            for sensor in sensors:
                # Определяем диапазоны в зависимости от типа датчика
                if "temperature" in sensor.sensor_type:
                    min_value, max_value = 20, 80
                elif "pressure" in sensor.sensor_type:
                    min_value, max_value = 1, 10
                elif "speed" in sensor.sensor_type:
                    min_value, max_value = 10, 100
                elif "level" in sensor.sensor_type:
                    min_value, max_value = 10, 90
                elif "quality" in sensor.sensor_type:
                    min_value, max_value = 85, 100
                elif "weight" in sensor.sensor_type:
                    min_value, max_value = 0.5, 2.0
                elif "flow" in sensor.sensor_type:
                    min_value, max_value = 50, 150
                else:
                    min_value, max_value = 0, 100

                setting = EquipmentSetting(
                    sensor_id=sensor.id,
                    min_value=min_value,
                    max_value=max_value,
                )
                settings.append(setting)
                session.add(setting)

            await session.commit()
            logger.info(f"Создано {len(settings)} настроек оборудования")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании настроек оборудования: {e}")
            raise


async def generate_sensor_readings(sensors, hours=24):
    """Генерация исторических данных показаний датчиков"""
    async with async_session() as session:
        try:
            # Проверяем наличие существующих показаний
            count_query = select(SensorReading).limit(1)
            count_result = await session.execute(count_query)
            has_readings = count_result.first() is not None

            if has_readings:
                logger.info("В базе уже есть показания датчиков")

                # Подсчитываем количество
                count_query = text("SELECT COUNT(*) FROM sensor_readings")
                count_result = await session.execute(count_query)
                readings_count = count_result.scalar()
                logger.info(f"Найдено {readings_count} показаний датчиков")
                return

            # Получаем настройки для всех датчиков
            settings_dict = {}
            for sensor in sensors:
                settings_query = select(EquipmentSetting).where(EquipmentSetting.sensor_id == sensor.id)
                settings_result = await session.execute(settings_query)
                setting = settings_result.scalars().first()

                if setting:
                    settings_dict[sensor.id] = {
                        'min_value': float(setting.min_value) if setting.min_value else 0,
                        'max_value': float(setting.max_value) if setting.max_value else 100,
                    }

            # Генерируем данные
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            total_readings = 0
            total_events = 0

            # Используем батчи для более эффективной вставки
            batch_size = 100
            readings_batch = []
            events_batch = []

            for sensor in sensors:
                # Пропускаем, если нет настроек
                if sensor.id not in settings_dict:
                    continue

                settings = settings_dict[sensor.id]

                # Определяем интервал между точками данных (в минутах)
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
                            anomaly = True
                            anomaly_type = "low"
                        else:
                            # Выше максимума
                            value = random.uniform(
                                settings['max_value'] * 1.1,
                                settings['max_value'] * 1.5
                            )
                            anomaly = True
                            anomaly_type = "high"
                    else:
                        value = normal_value
                        anomaly = False
                        anomaly_type = None

                    # Создаем JSON данные в зависимости от типа датчика
                    if "temperature" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "°C",
                            "temperature": round(value, 1)
                        }
                    elif "pressure" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "bar",
                            "pressure": round(value, 2)
                        }
                    elif "speed" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "rpm",
                            "speed": round(value)
                        }
                    elif "level" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "%",
                            "level": round(value, 1)
                        }
                    elif "quality" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "%",
                            "quality_index": round(value, 1)
                        }
                    elif "weight" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "kg",
                            "weight": round(value, 3)
                        }
                    elif "flow" in sensor.sensor_type:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "unit": "l/min",
                            "flow_rate": round(value, 2)
                        }
                    else:
                        value_dict = {
                            "sensor_id": sensor.id,
                            "timestamp": current_time.isoformat(),
                            "value": round(value, 2)
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
                    total_readings += 1

                    # Если обнаружена аномалия, создаем оповещение
                    if anomaly:
                        if anomaly_type == "low":
                            message = f"Значение {round(value, 2)} ниже допустимого {settings['min_value']}"
                        else:
                            message = f"Значение {round(value, 2)} выше допустимого {settings['max_value']}"

                        new_event = Event(
                            sensor_id=sensor.id,
                            alert_type="warning",
                            message=message,
                            location_id=sensor.location_id,
                            value=str(round(value, 2)),
                            timestamp=current_time
                        )
                        events_batch.append(new_event)
                        total_events += 1

                    # Сохраняем батч в БД, если достигнут размер
                    if len(readings_batch) >= batch_size:
                        session.add_all(readings_batch)
                        await session.commit()
                        readings_batch = []

                    if len(events_batch) >= batch_size:
                        session.add_all(events_batch)
                        await session.commit()
                        events_batch = []

                    # Увеличиваем время на интервал
                    current_time += timedelta(minutes=5)  # Увеличиваем время на 5 минут

            # Сохраняем оставшиеся данные в батчах
            if readings_batch:
                session.add_all(readings_batch)

            if events_batch:
                session.add_all(events_batch)

            await session.commit()
            logger.info(f"Сгенерировано {total_readings} показаний датчиков и {total_events} оповещений")

        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при генерации показаний датчиков: {e}")
            raise


async def main():
    """Основная функция инициализации базы данных"""
    try:
        # Создаем таблицы
        await create_tables()

        # Создаем роли
        roles = await create_roles()

        # Создаем сотрудников
        await create_employees(roles)

        # Создаем местоположения
        locations = await create_locations()

        # Создаем датчики
        sensors = await create_sensors(locations)

        # Создаем настройки оборудования
        await create_equipment_settings(sensors)

        # Генерируем исторические данные
        await generate_sensor_readings(sensors, hours=48)

        logger.info("Инициализация базы данных завершена успешно")

    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")


if __name__ == "__main__":
    asyncio.run(main())