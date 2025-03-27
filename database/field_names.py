"""
Модуль для определения правильных имен полей в моделях.
Это позволяет избежать ошибок при использовании полей в запросах.
"""

import logging
from sqlalchemy import Column
from sqlalchemy.inspection import inspect
from database.models import SensorReading, Event, EquipmentSetting
from database.connection import engine

logger = logging.getLogger(__name__)

# Значения по умолчанию на основе проверки моделей
SENSOR_ID_FIELD = "sensor_id"  # Уже подтверждено
EMPLOYEE_ID_FIELD = "employee_id"  # По умолчанию

# Простая инициализация без использования асинхронного движка
def initialize_field_names():
    """Определение правильных имен полей в моделях"""
    global SENSOR_ID_FIELD, EMPLOYEE_ID_FIELD
    
    try:
        # Проверяем поля моделей напрямую
        sensor_reading_attrs = [attr for attr in dir(SensorReading) if not attr.startswith('_')]
        event_attrs = [attr for attr in dir(Event) if not attr.startswith('_')]
        
        # Выводим все поля для отладки
        logger.info(f"Поля SensorReading: {sensor_reading_attrs}")
        logger.info(f"Поля Event: {event_attrs}")
        
        # Проверяем SensorReading
        if 'sensor_id' in sensor_reading_attrs:
            SENSOR_ID_FIELD = 'sensor_id'
            logger.info("Используем имя поля 'sensor_id' для связи с датчиком")
        elif 'sensors_id' in sensor_reading_attrs:
            SENSOR_ID_FIELD = 'sensors_id'
            logger.info("Используем имя поля 'sensors_id' для связи с датчиком")
        
        # Проверяем Event
        if 'employee_id' in event_attrs:
            EMPLOYEE_ID_FIELD = 'employee_id'
            logger.info("Используем имя поля 'employee_id' для связи с сотрудником")
        elif 'employees_id' in event_attrs:
            EMPLOYEE_ID_FIELD = 'employees_id'
            logger.info("Используем имя поля 'employees_id' для связи с сотрудником")
        
    except Exception as e:
        logger.error(f"Ошибка при определении имен полей: {e}")

async def initialize_field_names():
    """Определение правильных имен полей в моделях"""
    global SENSOR_ID_FIELD, EMPLOYEE_ID_FIELD
    
    try:
        # Получаем инспектор SQLAlchemy
        inspector = inspect(engine)
        
        # Проверяем наличие таблицы sensor_readings
        if await inspector.has_table("sensor_readings"):
            # Получаем список столбцов таблицы
            columns = await inspector.get_columns("sensor_readings")
            column_names = [col["name"] for col in columns]
            
            # Определяем правильное имя поля для связи с датчиком
            if "sensors_id" in column_names:
                SENSOR_ID_FIELD = "sensors_id"
                logger.info("Используем имя поля 'sensors_id' для связи с датчиком в таблице sensor_readings")
            elif "sensor_id" in column_names:
                SENSOR_ID_FIELD = "sensor_id"
                logger.info("Используем имя поля 'sensor_id' для связи с датчиком в таблице sensor_readings")
            else:
                logger.warning("Не найдено поле для связи с датчиком в таблице sensor_readings")
        
        # Повторяем для таблицы events
        if await inspector.has_table("events"):
            columns = await inspector.get_columns("events")
            column_names = [col["name"] for col in columns]
            
            if "employees_id" in column_names:
                EMPLOYEE_ID_FIELD = "employees_id"
                logger.info("Используем имя поля 'employees_id' для связи с сотрудником в таблице events")
            elif "employee_id" in column_names:
                EMPLOYEE_ID_FIELD = "employee_id"
                logger.info("Используем имя поля 'employee_id' для связи с сотрудником в таблице events")
            else:
                logger.warning("Не найдено поле для связи с сотрудником в таблице events")
        
    except Exception as e:
        logger.error(f"Ошибка при определении имен полей: {e}")
        # В случае ошибки оставляем значения по умолчанию 