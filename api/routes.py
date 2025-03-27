from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from database.connection import get_async_session
from database.models import SensorReading, Sensor, Event, Employee, Role, Location, EquipmentSetting
from datetime import datetime, timedelta
from sqlalchemy import func, select
from api.schemas import SensorData, AlertData, SensorOverview
import sqlalchemy as sa

from mqtt.client import logger

router = APIRouter()

@router.get("/sensors", response_model=List[SensorOverview])
async def get_sensors(db: AsyncSession = Depends(get_async_session)):
    """Получение списка всех датчиков"""
    result = await db.execute(select(Sensor))
    sensors = result.scalars().all()
    return sensors


@router.get("/sensors/{sensor_id}/data", response_model=List[SensorData])
async def get_sensor_data(
        sensor_id: int,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        db: AsyncSession = Depends(get_async_session)
):
    """Получение данных с конкретного датчика за период"""
    query = select(SensorReading).filter(SensorReading.sensor_id == sensor_id)

    if from_time:
        query = query.filter(SensorReading.time >= from_time)
    if to_time:
        query = query.filter(SensorReading.time <= to_time)
    else:
        # По умолчанию данные за последние 24 часа
        if not from_time:
            query = query.filter(SensorReading.time >= datetime.now() - timedelta(days=1))

    query = query.order_by(SensorReading.time)
    result = await db.execute(query)
    readings = result.scalars().all()

    if not readings:
        raise HTTPException(status_code=404, detail="Данные не найдены")

    return readings


@router.get("/alerts")
async def get_alerts(
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    event_type: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session)
):
    """Получение списка оповещений с возможностью фильтрации"""
    try:
        query = sa.select(
            Event, 
            Sensor.sensor_name
        ).outerjoin(
            Sensor, Event.sensor_id == Sensor.id
        ).filter(
            Event.event_type.in_(["high_value", "low_value", "value_exceeded"])
        )
        
        # Применяем фильтры
        if event_type:
            query = query.filter(Event.event_type == event_type)
            
        if from_time:
            query = query.filter(Event.time >= from_time)
        if to_time:
            query = query.filter(Event.time <= to_time)
        else:
            # По умолчанию оповещения за последние 7 дней
            if not from_time:
                query = query.filter(Event.time >= datetime.now() - timedelta(days=7))
        
        query = query.order_by(Event.time.desc())
        
        result = await db.execute(query)
        alerts = result.all()
        
        return [
            {
                "id": row.Event.id,
                "time": row.Event.time.isoformat(),
                "event_type": row.Event.event_type,
                "description": row.Event.description,
                "sensor_id": row.Event.sensor_id,
                "sensor_name": row.sensor_name
            }
            for row in alerts
        ]
    except Exception as e:
        logger.error(f"Ошибка получения оповещений: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/production")
async def get_production_statistics(
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        db: AsyncSession = Depends(get_async_session)
):
    """Получение статистики производства за период"""
    if not from_time:
        from_time = datetime.now() - timedelta(days=7)
    if not to_time:
        to_time = datetime.now()

    # Получение данных о количестве бутылок
    bottle_query = select(
        func.date_trunc('day', SensorReading.time).label('date'),
        func.sum(SensorReading.value).label('bottles')
    ).join(Sensor).filter(
        Sensor.sensor_name.like('%bottles_packed%'),
        SensorReading.time.between(from_time, to_time)
    ).group_by(func.date_trunc('day', SensorReading.time))

    bottle_result = await db.execute(bottle_query)
    bottle_counts = bottle_result.all()

    # Получение данных о дефектах
    defect_query = select(
        func.date_trunc('day', SensorReading.time).label('date'),
        func.avg(SensorReading.value).label('defect_rate')
    ).join(Sensor).filter(
        Sensor.sensor_name.like('%defect_rate%'),
        SensorReading.time.between(from_time, to_time)
    ).group_by(func.date_trunc('day', SensorReading.time))

    defect_result = await db.execute(defect_query)
    defect_rates = defect_result.all()

    return {
        "bottle_production": [{"date": item.date, "bottles": item.bottles} for item in bottle_counts],
        "defect_rates": [{"date": item.date, "rate": item.defect_rate} for item in defect_rates]
    }


@router.get("/dashboard/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_async_session)):
    """Получение сводной информации для дашборда"""
    try:
        # Получаем последние показания датчиков
        latest_readings_query = sa.select(
            SensorReading.sensor_id,
            sa.func.max(SensorReading.time).label("latest_time")
        ).group_by(SensorReading.sensor_id).subquery()
        
        latest_data_query = sa.select(
            SensorReading, 
            Sensor.sensor_name, 
            Location.name.label("location_name")
        ).join(
            latest_readings_query,
            sa.and_(
                SensorReading.sensor_id == latest_readings_query.c.sensor_id,
                SensorReading.time == latest_readings_query.c.latest_time
            )
        ).join(
            Sensor, SensorReading.sensor_id == Sensor.id
        ).join(
            Location, Sensor.location_id == Location.id
        )
        
        result = await db.execute(latest_data_query)
        latest_readings = result.all()
        
        # Получаем последние 5 оповещений
        alerts_query = sa.select(Event).filter(
            Event.event_type.in_(["high_value", "low_value", "value_exceeded"])
        ).order_by(Event.time.desc()).limit(5)
        
        result = await db.execute(alerts_query)
        recent_alerts = result.scalars().all()
        
        # Статистика производства за последний день
        day_ago = datetime.now() - timedelta(days=1)
        stats_query = sa.select(
            sa.func.sum(SensorReading.value).label("total")
        ).join(
            Sensor
        ).filter(
            Sensor.sensor_name.contains("bottles_packed"),
            SensorReading.time >= day_ago
        )
        
        result = await db.execute(stats_query)
        total_bottles = result.scalar() or 0
        
        # Получаем текущие данные процесса производства
        process_data = {}
        for stage in ["raw_material", "bottleforming", "cooling", "quality", "packaging"]:
            stage_query = sa.select(
                SensorReading, Sensor.sensor_name
            ).join(
                Sensor, SensorReading.sensor_id == Sensor.id
            ).join(
                Location, Sensor.location_id == Location.id
            ).filter(
                Location.name.contains(stage)
            ).order_by(
                SensorReading.time.desc()
            ).limit(5)
            
            result = await db.execute(stage_query)
            stage_data = result.all()
            process_data[stage] = [
                {
                    "sensor_name": row.Sensor.sensor_name,
                    "value": row.SensorReading.value,
                    "time": row.SensorReading.time.isoformat(),
                }
                for row in stage_data
            ]
        
        return {
            "latest_readings": [
                {
                    "sensor_id": row.SensorReading.sensor_id,
                    "sensor_name": row.sensor_name,
                    "location": row.location_name,
                    "value": row.SensorReading.value,
                    "time": row.SensorReading.time.isoformat()
                }
                for row in latest_readings
            ],
            "recent_alerts": [
                {
                    "id": alert.id,
                    "type": alert.event_type,
                    "description": alert.description,
                    "time": alert.time.isoformat()
                }
                for alert in recent_alerts
            ],
            "total_bottles_24h": total_bottles,
            "process_data": process_data
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения данных для дашборда: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensors/latest")
async def get_latest_sensor_data(db: AsyncSession = Depends(get_async_session)):
    """Получение последних показаний всех датчиков"""
    try:
        # Подзапрос для получения последнего времени для каждого датчика
        latest_time_subquery = sa.select(
            SensorReading.sensor_id,
            sa.func.max(SensorReading.time).label("latest_time")
        ).group_by(SensorReading.sensor_id).subquery()
        
        # Основной запрос с джойнами для получения всей информации
        query = sa.select(
            SensorReading, 
            Sensor.sensor_name, 
            Location.name.label("location_name"),
            EquipmentSetting.min_value,
            EquipmentSetting.max_value
        ).join(
            latest_time_subquery,
            sa.and_(
                SensorReading.sensor_id == latest_time_subquery.c.sensor_id,
                SensorReading.time == latest_time_subquery.c.latest_time
            )
        ).join(
            Sensor, SensorReading.sensor_id == Sensor.id
        ).join(
            Location, Sensor.location_id == Location.id
        ).outerjoin(
            EquipmentSetting, Sensor.id == EquipmentSetting.sensor_id
        ).order_by(Location.name, Sensor.sensor_name)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                "sensor_id": row.SensorReading.sensor_id,
                "sensor_name": row.sensor_name,
                "location": row.location_name,
                "value": row.SensorReading.value,
                "time": row.SensorReading.time.isoformat(),
                "min_value": row.min_value,
                "max_value": row.max_value,
                "status": "normal" if (row.min_value <= row.SensorReading.value <= row.max_value) else "alert"
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Ошибка получения данных датчиков: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/production")
async def get_production_statistics(
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        db: AsyncSession = Depends(get_async_session)
):
    """Получение статистики производства за период"""
    try:
        if not from_time:
            from_time = datetime.now() - timedelta(days=7)
        if not to_time:
            to_time = datetime.now()

        # Получение данных о количестве произведенных бутылок по дням
        bottle_query = sa.select(
            sa.func.date_trunc('day', SensorReading.time).label('date'),
            sa.func.sum(SensorReading.value).label('bottles')
        ).join(
            Sensor, SensorReading.sensor_id == Sensor.id
        ).filter(
            Sensor.sensor_name.contains('bottles_packed'),
            SensorReading.time.between(from_time, to_time)
        ).group_by(
            sa.func.date_trunc('day', SensorReading.time)
        ).order_by(
            sa.func.date_trunc('day', SensorReading.time)
        )

        bottle_result = await db.execute(bottle_query)
        bottle_counts = bottle_result.all()

        # Получение данных о проценте брака по дням
        defect_query = sa.select(
            sa.func.date_trunc('day', SensorReading.time).label('date'),
            sa.func.avg(SensorReading.value).label('defect_rate')
        ).join(
            Sensor, SensorReading.sensor_id == Sensor.id
        ).filter(
            Sensor.sensor_name.contains('defect_rate'),
            SensorReading.time.between(from_time, to_time)
        ).group_by(
            sa.func.date_trunc('day', SensorReading.time)
        ).order_by(
            sa.func.date_trunc('day', SensorReading.time)
        )

        defect_result = await db.execute(defect_query)
        defect_rates = defect_result.all()

        # Если данных нет, создаем пустые массивы
        if not bottle_counts:
            bottle_counts = []
        if not defect_rates:
            defect_rates = []

        return {
            "bottle_production": [
                {
                    "date": item.date.isoformat() if item.date else None,
                    "bottles": float(item.bottles) if item.bottles else 0
                }
                for item in bottle_counts
            ],
            "defect_rates": [
                {
                    "date": item.date.isoformat() if item.date else None,
                    "rate": float(item.defect_rate) if item.defect_rate else 0
                }
                for item in defect_rates
            ]
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики производства: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики производства: {str(e)}")