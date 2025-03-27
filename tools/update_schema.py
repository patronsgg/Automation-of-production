import asyncio
import logging
from sqlalchemy import text
from database.connection import engine

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def modify_column_type():
    """Изменение типа колонки value в таблице sensor_readings"""
    async with engine.begin() as conn:
        try:
            # Проверяем тип колонки
            column_info = await conn.execute(text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'sensor_readings' 
                AND column_name = 'value'
            """))
            
            column_type = column_info.scalar()
            logger.info(f"Текущий тип колонки 'value': {column_type}")
            
            if column_type and column_type.lower() != 'text':
                # Изменяем тип колонки на TEXT
                logger.info("Изменение типа колонки 'value' на TEXT...")
                
                # Для PostgreSQL
                await conn.execute(text("""
                    ALTER TABLE sensor_readings
                    ALTER COLUMN value TYPE TEXT
                """))
                
                logger.info("Тип колонки успешно изменен")
            else:
                logger.info("Колонка 'value' уже имеет тип TEXT или не найдена")
            
        except Exception as e:
            logger.error(f"Ошибка при изменении типа колонки: {e}")
            raise

async def main():
    logger.info("Начинаем обновление схемы базы данных...")
    await modify_column_type()
    logger.info("Обновление схемы базы данных завершено")

if __name__ == "__main__":
    asyncio.run(main()) 