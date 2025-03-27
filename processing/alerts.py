import logging
from sqlalchemy import select
from database.models import EquipmentSetting, Event, Sensor
from database.connection import async_session
import asyncio

logger = logging.getLogger(__name__)


async def check_alert_conditions(sensor_id, value, topic=None):
    """Проверка условий для генерации оповещений"""
    async with async_session() as session:
        try:
            # Получаем настройки для датчика
            query = select(EquipmentSetting).where(EquipmentSetting.sensor_id == sensor_id)
            result = await session.execute(query)
            setting = result.scalars().first()

            if not setting:
                logger.warning(f"Настройки для датчика {sensor_id} не найдены")
                return  # Настройки не найдены, выходим

            # Список единиц измерения и нечисловых полей, которые нужно пропустить
            skip_values = ['°C', 'mm', '%', 'bar', 'unit', 'status', 'name', 'description']

            # Проверяем, не является ли значение единицей измерения
            if isinstance(value, str):
                for skip_value in skip_values:
                    if skip_value in value:
                        logger.debug(f"Пропускаем проверку для значения {value}, содержащего {skip_value}")
                        return  # Это единица измерения, пропускаем

            # Пытаемся преобразовать к числу
            try:
                # Очищаем значение от нечисловых символов, если это строка
                if isinstance(value, str):
                    # Заменяем запятую на точку для корректного преобразования
                    cleaned_value = value.replace(',', '.')
                    # Оставляем только цифры, точку и знак минуса
                    cleaned_value = ''.join(c for c in cleaned_value if c.isdigit() or c in '.-')
                    numeric_value = float(cleaned_value)
                else:
                    numeric_value = float(value)

                # Преобразуем граничные значения
                min_value = float(setting.min_value) if setting.min_value is not None else None
                max_value = float(setting.max_value) if setting.max_value is not None else None

                alert_triggered = False
                alert_message = ""

                # Проверяем условия для оповещения
                if min_value is not None and numeric_value < min_value:
                    alert_message = f"Значение {numeric_value} ниже допустимого {min_value}"
                    alert_triggered = True
                    logger.warning(alert_message)
                elif max_value is not None and numeric_value > max_value:
                    alert_message = f"Значение {numeric_value} выше допустимого {max_value}"
                    alert_triggered = True
                    logger.warning(alert_message)
                else:
                    logger.debug(f"Значение {numeric_value} в пределах нормы: мин={min_value}, макс={max_value}")

                # Если оповещение сработало, создаем запись в таблице событий
                if alert_triggered:
                    # Проверка существования датчика
                    sensor_query = select(Sensor).where(Sensor.id == sensor_id)
                    sensor_result = await session.execute(sensor_query)
                    sensor = sensor_result.scalars().first()

                    if sensor:
                        new_event = Event(
                            sensor_id=sensor_id,
                            alert_type="warning",
                            message=alert_message,
                            location_id=sensor.location_id,
                            value=str(numeric_value)
                        )
                        session.add(new_event)
                        await session.commit()
                        logger.info(f"Создано оповещение: {alert_message}, sensor_id={sensor_id}")
                    else:
                        logger.warning(f"Датчик с id={sensor_id} не найден при создании оповещения")

            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка преобразования к числу: {e}, value='{value}'")

        except Exception as e:
            logger.error(f"Ошибка при проверке условий оповещения: {e}")