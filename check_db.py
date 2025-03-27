import asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.dialects import postgresql
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Подключение к базе данных
DATABASE_URL = "postgresql://1:1@localhost/production"
async_engine = create_async_engine(f"postgresql+asyncpg://{DATABASE_URL.split('://')[-1]}")

async def check_table_structure(table_name):
    """Проверяет структуру таблицы и выводит информацию о столбцах"""
    try:
        logger.info(f"Проверка структуры таблицы {table_name}")
        
        # SQL запрос для получения информации о структуре таблицы
        query = f"""
        SELECT 
            column_name, 
            data_type,
            is_nullable
        FROM 
            information_schema.columns
        WHERE 
            table_name = '{table_name}'
        ORDER BY 
            ordinal_position;
        """
        
        async with async_engine.connect() as conn:
            result = await conn.execute(sa.text(query))
            columns = result.fetchall()
            
            if not columns:
                logger.warning(f"Таблица {table_name} не найдена или не содержит столбцов")
                return
            
            logger.info(f"Структура таблицы {table_name}:")
            for column in columns:
                logger.info(f"  Столбец: {column[0]}, Тип: {column[1]}, Nullable: {column[2]}")
    
    except Exception as e:
        logger.error(f"Ошибка при проверке структуры таблицы {table_name}: {e}")

async def main():
    """Основная функция для проверки структуры таблиц"""
    tables_to_check = [
        "sensors",
        "sensor_readings", 
        "events",
        "equipment_settings",
        "location"
    ]
    
    for table in tables_to_check:
        await check_table_structure(table)
    
    # Закрываем соединение с движком
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main()) 