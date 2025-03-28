from fastapi import FastAPI, Request, Depends, HTTPException, status, Form, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from database.connection import get_async_session
from database.models import Employee, Role, SensorReading, Sensor, Location, Event, EquipmentSetting
from api.routes import router as api_router
from api.schemas import LoginRequest, TokenResponse
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timedelta
from config import config
import sqlalchemy as sa
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import typing
from web.websockets import manager
import logging
import asyncio
import random
from sqlalchemy.orm import joinedload
import traceback
import json

logger = logging.getLogger(__name__)

app = FastAPI(title="Система мониторинга производства ПЭТ бутылок")

# Подключение статических файлов и шаблонов
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Настройка OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Создание токена доступа
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    # Используем JWT из jose
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt


# Верификация пользователя
async def authenticate_user(db: AsyncSession, username: str, password: str):
    """Аутентификация пользователя"""
    try:
        # Ищем пользователя по имени
        query = select(Employee).where(Employee.username == username)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return None
        if user.hashed_password != password:
            return None

        return user
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {e}")
        return None


async def get_current_user_from_cookie(request: Request, db: AsyncSession = Depends(get_async_session)):
    try:
        token = request.cookies.get('access_token')
        if not token:
            logger.warning("Токен отсутствует в cookie")
            return None

        # Извлекаем сам токен из строки "Bearer ..."
        if token.startswith("Bearer "):
            token = token.split("Bearer ")[1]

        # Упрощенная проверка - без верификации подписи
        try:
            # Только для отладки - распаковываем без проверки подписи
            decoded_payload = jwt.decode(
                token,
                config.SECRET_KEY,  # Используем правильный ключ из конфигурации
                options={"verify_signature": False}
            )
            username = decoded_payload.get("sub")
            role = decoded_payload.get("role")

            logger.info(f"Декодирован токен для пользователя: {username}, роль: {role}")

            # Создаем временный объект пользователя для отладки
            if username in ["admin", "operator"]:
                user = type('User', (), {
                    'username': username,
                    'role': role or ("admin" if username == "admin" else "operator")
                })
                return user

        except Exception as decode_error:
            logger.error(f"Ошибка при базовом декодировании токена: {decode_error}")

        # Пытаемся найти пользователя в БД (если он там есть)
        try:
            # Более безопасное декодирование с проверкой подписи
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])  # Используем config.SECRET_KEY вместо "тестовый_ключ_123"
            username = payload.get("sub")

            if username:
                # Ищем в БД
                query = sa.select(Employee).where(Employee.username == username)
                result = await db.execute(query)
                user = result.scalars().first()

                if user:
                    return user
        except Exception as e:
            logger.warning(f"Ошибка при проверке токена с подписью: {e}")
            # Продолжаем использовать упрощенный вариант без проверки подписи

        return None

    except Exception as e:
        logger.error(f"Общая ошибка при получении пользователя из cookie: {e}")
        return None

# Подключение API маршрутов
app.include_router(api_router, prefix="/api")


@app.post("/token")
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session)
):
    """Получение токена доступа - совсем простая версия"""
    try:
        # Получаем сотрудника
        query = select(Employee).where(Employee.username == form_data.username)
        result = await db.execute(query)
        employee = result.scalar_one_or_none()
        
        if not employee or employee.hashed_password != form_data.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Используем прямое значение поля role, если оно есть
        role_value = "operator"
        if hasattr(employee, 'role') and isinstance(employee.role, str):
            role_value = employee.role
        
        # Создаем JWT токен
        access_token_expires = timedelta(minutes=60)
        access_token = create_access_token(
            data={"sub": employee.username, "role": role_value},
            expires_delta=access_token_expires
        )
        
        # Устанавливаем cookie
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=3600,
            path="/",
            samesite="lax"
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except Exception as e:
        logger.error(f"Ошибка при авторизации: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )


@app.get("/")
async def root():
    return {"message": "Система мониторинга производства ПЭТ бутылок работает!"}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/dashboard"):
    """Страница входа с формой авторизации"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "next": next,
        "user": None
    })


@app.post("/login")
async def login_form(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        next: str = Form("/dashboard")  # Параметр для перенаправления
):
    """Максимально упрощенная обработка формы входа"""
    try:
        # Проверяем логин/пароль напрямую, без запросов к БД
        valid_credentials = {
            "admin": "admin",
            "operator": "operator"
        }

        if username not in valid_credentials or password != valid_credentials[username]:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Неверное имя пользователя или пароль", "next": next}
            )

        # Роль правильная - admin для admin, operator для operator
        role = "admin" if username == "admin" else "operator"

        # Создаем JWT токен с минимальными данными
        token_data = {
            "sub": username,
            "role": role,  # Используем правильную роль
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }

        # Логируем, чтобы видеть, что передается
        logger.info(f"Создаем токен для пользователя {username} с ролью {role}")

        # Кодируем токен напрямую
        access_token = jwt.encode(token_data, config.SECRET_KEY, algorithm="HS256")

        # Создаем ответ с редиректом на исходную страницу
        response = RedirectResponse(url=next, status_code=303)

        # Добавляем cookie максимально просто
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            path="/",
            httponly=True,
            max_age=3600
        )

        return response

    except Exception as e:
        logger.error(f"Ошибка при обработке формы входа: {e}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": f"Ошибка сервера: {str(e)}", "next": next}
        )

@app.get("/dashboard")
async def dashboard(request: Request, db: AsyncSession = Depends(get_async_session)):
    """Защищенная страница с проверкой пользователя из cookie"""
    user = await get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url='/login?next=/dashboard')

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "username": getattr(user, 'username', 'Гость'),
            "role": getattr(user, 'role', 'guest'),
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@app.get("/sensors")
async def sensors_page(request: Request, db: AsyncSession = Depends(get_async_session)):
    user = await get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url=f'/login?next=/sensors')

    return templates.TemplateResponse("sensors.html", {
        "request": request,
        "user": user
    })


@app.get("/alerts")
async def alerts_page(request: Request, db: AsyncSession = Depends(get_async_session)):
    user = await get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url=f'/login?next=/alerts')

    # Получаем токен из cookie для передачи в шаблон
    token = request.cookies.get('access_token', '')
    
    return templates.TemplateResponse("alerts.html", {
        "request": request,
        "user": user,
        "token": token  # Передаем токен в шаблон
    })


@app.get("/reports")
async def reports_page(request: Request, db: AsyncSession = Depends(get_async_session)):
    user = await get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url=f'/login?next=/reports')

    return templates.TemplateResponse("reports.html", {
        "request": request,
        "user": user
    })


# Добавьте маршрут для выхода из системы
@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="access_token", path="/")
    return response



# Маршрут для WebSocket дашборда
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket, db: AsyncSession = Depends(get_async_session)):
    await websocket.accept()
    
    try:
        while True:
            # Получаем данные для дашборда
            try:
                dashboard_data = await generate_dashboard_data(db)
                await websocket.send_json(dashboard_data)
            except Exception as e:
                logger.error(f"Ошибка при генерации данных дашборда: {e}")
                # Создаем новую сессию для следующей попытки
                await websocket.send_json({
                    "error": "Ошибка получения данных дашборда",
                    "sensor_readings": [],
                    "recent_alerts": [],
                    "production_status": {
                        "status": "error",
                        "message": "Ошибка получения данных",
                        "metrics": {}
                    }
                })
            
            # Ждем перед следующим обновлением
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        logger.info("WebSocket клиент отключен от /ws/dashboard")
    except Exception as e:
        logger.error(f"Ошибка при отправке данных дашборда: {e}")
        try:
            await websocket.send_json({"error": f"Ошибка получения данных дашборда: {str(e)}"})
        except:
            pass

async def generate_dashboard_data(db: AsyncSession):
    try:
        # Получаем последние показания датчиков
        latest_readings_query = sa.select(
            SensorReading.sensor_id,
            sa.func.max(SensorReading.time).label("latest_time")
        ).group_by(SensorReading.sensor_id).subquery()
        
        latest_data_query = sa.select(
            SensorReading, 
            Sensor.sensor_name,
            Sensor.sensor_type,
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
        
        latest_data_result = await db.execute(latest_data_query)
        latest_readings = latest_data_result.fetchall()
        
        sensor_readings = []
        for row in latest_readings:
            sensor_readings.append({
                "sensor_id": row.SensorReading.sensor_id,
                "sensor_name": row.sensor_name,
                "sensor_type": row.sensor_type,
                "location_name": row.location_name,
                "value": row.SensorReading.value,
                "time": row.SensorReading.time.strftime("%Y-%m-%d %H:%M:%S") if row.SensorReading.time else None
            })
        
        # Получаем последние оповещения
        alerts_query = sa.select(
            Event,
            Sensor.sensor_name,
            Location.name.label("location_name")
        ).join(
            Sensor, Event.sensor_id == Sensor.id
        ).join(
            Location, Event.location_id == Location.id
        ).order_by(
            Event.timestamp.desc()
        ).limit(5)
        
        alerts_result = await db.execute(alerts_query)
        alerts = alerts_result.fetchall()
        
        recent_alerts = []
        for alert in alerts:
            recent_alerts.append({
                "id": alert.Event.id,
                "sensor_id": alert.Event.sensor_id,
                "sensor_name": alert.sensor_name,
                "alert_type": alert.Event.alert_type,
                "message": alert.Event.message,
                "value": alert.Event.value,
                "location": alert.location_name,
                "timestamp": alert.Event.timestamp.strftime("%Y-%m-%d %H:%M:%S") if alert.Event.timestamp else None
            })
        
        # Формируем данные о текущем статусе производства
        production_status = await generate_production_status(db)
        
        return {
            "sensor_readings": sensor_readings,
            "recent_alerts": recent_alerts,
            "production_status": production_status
        }
    except Exception as e:
        logger.error(f"Ошибка при генерации данных дашборда: {e}")
        # Заворачиваем ошибку в транзакцию, чтобы не прерывать сессию
        await db.rollback()
        
        return {
            "error": f"Ошибка при генерации данных: {str(e)}",
            "sensor_readings": [],
            "recent_alerts": [],
            "production_status": {"status": "error", "message": f"Ошибка: {str(e)}", "metrics": {}}
        }

async def generate_production_status(db: AsyncSession):
    """Генерация статуса производства с PostgreSQL-совместимым синтаксисом"""
    try:
        # Запрос для PostgreSQL - используем INTERVAL вместо datetime()
        alerts_count_query = sa.select(sa.func.count(Event.id)).where(
            Event.timestamp > sa.text("NOW() - INTERVAL '1 day'")
        )
        alerts_result = await db.execute(alerts_count_query)
        alerts_count = alerts_result.scalar()
        
        # Получаем данные о активных датчиках
        active_sensors_query = sa.select(sa.func.count(Sensor.id)).where(
            Sensor.status == "active"
        )
        active_sensors_result = await db.execute(active_sensors_query)
        active_sensors = active_sensors_result.scalar()
        
        # Определяем статус производства на основе имеющихся данных
        if alerts_count > 10:
            status = "critical"
            status_message = "Критический: обнаружено множество оповещений"
        elif alerts_count > 5:
            status = "warning"
            status_message = "Внимание: обнаружены оповещения"
        elif active_sensors > 0:
            status = "normal"
            status_message = "Нормальный: производство работает стабильно"
        else:
            status = "unknown"
            status_message = "Неизвестно: недостаточно данных"
        
        # Получаем основные показатели производства
        production_metrics = {
            "active_sensors": active_sensors,
            "alerts_24h": alerts_count,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return {
            "status": status,
            "message": status_message,
            "metrics": production_metrics
        }
    except Exception as e:
        logger.error(f"Ошибка при генерации статуса производства: {e}")
        return {
            "status": "error",
            "message": f"Ошибка получения статуса",
            "metrics": {
                "active_sensors": 0,
                "alerts_24h": 0,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }

# Функция для создания тестовых показаний датчиков
async def create_test_readings(db: AsyncSession, sensors):
    try:
        # Создаем тестовые настройки оборудования, если их нет
        for sensor in sensors:
            # Проверяем, есть ли настройки для этого датчика
            settings_query = sa.select(EquipmentSetting).where(
                EquipmentSetting.sensor_id == sensor.id
            )
            settings_result = await db.execute(settings_query)
            setting = settings_result.scalars().first()
            
            if not setting:
                # Создаем новую настройку
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
                else:
                    new_setting = EquipmentSetting(
                        sensor_id=sensor.id,
                        min_value="0",
                        max_value="100",
                        interval="60"
                    )
                
                db.add(new_setting)
        
        await db.commit()
        
        # Создаем тестовые показания
        test_readings = []
        current_time = datetime.now()
        
        for sensor in sensors:
            # Генерируем случайное значение в зависимости от типа датчика
            if "temperature" in sensor.sensor_type:
                value = str(round(random.uniform(15, 85), 1))
            elif "pressure" in sensor.sensor_type:
                value = str(round(random.uniform(0.5, 12), 2))
            elif "speed" in sensor.sensor_type:
                value = str(round(random.uniform(5, 120)))
            else:
                value = str(round(random.uniform(0, 100), 1))
            
            new_reading = SensorReading(
                sensor_id=sensor.id,
                value=value,
                time=current_time
            )
            test_readings.append(new_reading)
            
            # Создаем оповещение, если значение превышает норму
            settings_query = sa.select(EquipmentSetting).where(
                EquipmentSetting.sensor_id == sensor.id
            )
            settings_result = await db.execute(settings_query)
            setting = settings_result.scalars().first()
            
            if setting:
                try:
                    float_value = float(value)
                    
                    # Дополнительная проверка на существование значений и корректность типов
                    min_value = None
                    if setting.min_value and setting.min_value.strip():
                        try:
                            min_value = float(setting.min_value)
                        except (ValueError, TypeError):
                            min_value = None
                    
                    max_value = None
                    if setting.max_value and setting.max_value.strip():
                        try:
                            max_value = float(setting.max_value)
                        except (ValueError, TypeError):
                            max_value = None
                    
                    # Добавляем событие только если значения корректны
                    # и мы можем безопасно выполнить сравнение
                    if min_value is not None and isinstance(min_value, (int, float)) and float_value < min_value:
                        message = f"Значение {float_value} ниже допустимого {min_value}"
                        
                        new_event = Event(
                            sensor_id=sensor.id,
                            alert_type="warning",
                            message=message,
                            location_id=sensor.location_id,
                            value=value,
                            timestamp=current_time
                        )
                        db.add(new_event)
                    elif max_value is not None and isinstance(max_value, (int, float)) and float_value > max_value:
                        message = f"Значение {float_value} выше допустимого {max_value}"
                        
                        new_event = Event(
                            sensor_id=sensor.id,
                            alert_type="warning",
                            message=message,
                            location_id=sensor.location_id,
                            value=value,
                            timestamp=current_time
                        )
                        db.add(new_event)
                
                except (ValueError, TypeError) as e:
                    logger.error(f"Ошибка при проверке значений датчика: {e}")
        
        db.add_all(test_readings)
        await db.commit()
        
        logger.info("Успешно созданы тестовые показания датчиков")
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при создании тестовых показаний: {e}")

# Маршрут для WebSocket мониторинга датчиков
@app.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket, db: AsyncSession = Depends(get_async_session)):
    await websocket.accept()
    try:
        # Получаем информацию о датчиках
        query = sa.select(
            Sensor.id,
            Sensor.sensor_name,
            Sensor.sensor_type,
            Sensor.status,
            Location.name.label("location_name")
        ).join(
            Location, Sensor.location_id == Location.id
        )
        
        result = await db.execute(query)
        sensors = result.fetchall()
        
        # Если датчиков нет, добавляем несколько тестовых
        if not sensors:
            logger.warning("Датчики не найдены в базе данных. Создаю тестовые датчики.")
            await create_test_sensors(db)
            
            # Повторяем запрос после создания тестовых датчиков
            result = await db.execute(query)
            sensors = result.fetchall()
            
        sensors_data = []
        
        if sensors:
            for sensor in sensors:
                # Получаем последние показания для датчика
                readings_query = sa.select(SensorReading).where(
                    SensorReading.sensor_id == sensor.id
                ).order_by(
                    SensorReading.time.desc()
                ).limit(1)
                
                readings_result = await db.execute(readings_query)
                reading = readings_result.scalars().first()
                
                sensor_dict = {
                    "id": sensor.id,
                    "name": sensor.sensor_name,
                    "type": sensor.sensor_type,
                    "status": sensor.status,
                    "location": sensor.location_name,
                    "last_reading": reading.value if reading else "Нет данных",
                    "last_updated": reading.time.strftime("%Y-%m-%d %H:%M:%S") if reading else "Никогда"
                }
                
                sensors_data.append(sensor_dict)
        
        # Отправляем данные клиенту
        await websocket.send_json({"sensors": sensors_data})
        
    except WebSocketDisconnect:
        logger.info("WebSocket клиент отключен от /ws/sensors")
    except Exception as e:
        logger.error(f"Ошибка при отправке данных датчиков: {e}")
        try:
            await websocket.send_json({"error": f"Ошибка получения данных датчиков: {str(e)}"})
        except:
            pass

# Функция для создания тестовых датчиков, если они отсутствуют
async def create_test_sensors(db: AsyncSession):
    try:
        # Проверяем, есть ли записи о местоположениях
        location_query = sa.select(Location)
        location_result = await db.execute(location_query)
        locations = location_result.scalars().all()
        
        if not locations:
            # Создаем базовые местоположения
            locations = [
                Location(name="Линия подготовки сырья"),
                Location(name="Формование бутылок"),
                Location(name="Система охлаждения"),
                Location(name="Контроль качества"),
                Location(name="Упаковка")
            ]
            db.add_all(locations)
            await db.commit()
            
            # Перезагружаем местоположения после добавления
            location_result = await db.execute(location_query)
            locations = location_result.scalars().all()
        
        # Создаем тестовые датчики
        test_sensors = [
            Sensor(sensor_name="Датчик температуры 1", sensor_type="temperature", status="active", location_id=locations[0].id),
            Sensor(sensor_name="Датчик давления 1", sensor_type="pressure", status="active", location_id=locations[0].id),
            Sensor(sensor_name="Датчик температуры форм", sensor_type="temperature", status="active", location_id=locations[1].id),
            Sensor(sensor_name="Датчик формователя", sensor_type="speed", status="active", location_id=locations[1].id),
            Sensor(sensor_name="Датчик охлаждения", sensor_type="temperature", status="active", location_id=locations[2].id),
            Sensor(sensor_name="Датчик качества 1", sensor_type="quality", status="active", location_id=locations[3].id),
            Sensor(sensor_name="Датчик упаковщика", sensor_type="speed", status="active", location_id=locations[4].id)
        ]
        
        db.add_all(test_sensors)
        await db.commit()
        
        logger.info("Успешно созданы тестовые датчики и местоположения")
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при создании тестовых датчиков: {e}")

# Маршрут для WebSocket оповещений
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket, db: AsyncSession = Depends(get_async_session)):
    await manager.connect(websocket, "alerts")
    
    # Генератор данных для оповещений
    async def generate_alerts_data():
        try:
            query = sa.select(
                Event, 
                Sensor.sensor_name
            ).outerjoin(
                Sensor, Event.sensor_id == Sensor.id
            ).filter(
                sa.and_(
                    Event.event_type.is_not(None),  # Проверяем, что не NULL
                    Event.event_type.in_(["high_value", "low_value", "value_exceeded"])
                )
            ).order_by(Event.time.desc()).limit(100)
            
            result = await db.execute(query)
            alerts = result.all()
            
            return {
                "alerts": [
                    {
                        "id": row.Event.id,
                        "time": row.Event.time.isoformat(),
                        "event_type": row.Event.event_type,
                        "description": row.Event.description,
                        "sensor_id": row.Event.sensor_id,
                        "sensor_name": row.sensor_name
                    }
                    for row in alerts
                ],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Ошибка получения оповещений: {e}")
            return {"error": str(e)}
    
    # Запускаем периодическую отправку данных
    task = await manager.start_broadcast_task("alerts", 10, generate_alerts_data)
    
    try:
        # Ждем отключения клиента
        while True:
            data = await websocket.receive_text()
            # Если клиент отправил сообщение, можно обработать его здесь
    except WebSocketDisconnect:
        manager.disconnect(websocket, "alerts")


@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """Простой тестовый WebSocket для проверки соединения"""
    await websocket.accept()
    
    try:
        # Отправляем тестовое сообщение
        await websocket.send_json({"message": "Привет! WebSocket соединение работает!"})
        
        # Каждые 5 секунд отправляем время
        counter = 0
        while True:
            counter += 1
            await asyncio.sleep(5)
            await websocket.send_json({
                "counter": counter,
                "time": datetime.now().isoformat(),
                "message": "Это тестовое сообщение от сервера"
            })
    except WebSocketDisconnect:
        logger.info("Клиент отключился от тестового WebSocket")
    except Exception as e:
        logger.error(f"Ошибка в тестовом WebSocket: {e}")


@app.get("/test-websocket")
async def test_websocket_page(request: Request):
    """Страница для тестирования WebSocket"""
    return templates.TemplateResponse("test_websocket.html", {
        "request": request,
        "user": None
    })


@app.get("/api/auth-status")
async def get_auth_status(request: Request):
    """API для проверки состояния аутентификации"""
    token = request.cookies.get("access_token", "")
    user = getattr(request.state, "user", None)
    role = getattr(request.state, "role", None)
    
    return {
        "authenticated": user is not None,
        "username": user,
        "role": role,
        "has_token": bool(token),
        "token_starts_with_bearer": token.startswith("Bearer ") if token else False
    }


# Функция для обработки WebSocket ошибок
def handle_websocket_error(websocket, error_message):
    """Вспомогательная функция для отправки сообщения об ошибке через WebSocket"""
    try:
        asyncio.create_task(websocket.send_json({
            "error": error_message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }))
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


@app.get("/api/sensors/latest")
async def get_latest_sensor_readings(request: Request, db: AsyncSession = Depends(get_async_session)):
    """Получение последних показаний всех датчиков - упрощенная версия"""
    try:
        # Сначала проверим, есть ли в базе датчики и показания
        sensor_query = sa.select(sa.func.count(Sensor.id))
        sensor_count = await db.execute(sensor_query)
        count = sensor_count.scalar() or 0
        
        if count == 0:
            # Создаем тестовые датчики, если их нет
            await create_test_sensors(db)
        
        # Получаем все датчики
        sensors_query = sa.select(Sensor).options(joinedload(Sensor.location))
        sensors_result = await db.execute(sensors_query)
        sensors = sensors_result.scalars().all()
        
        response_data = []
        
        for sensor in sensors:
            # Получаем последнее показание
            reading_query = sa.select(SensorReading).where(
                SensorReading.sensor_id == sensor.id
            ).order_by(SensorReading.time.desc()).limit(1)
            
            reading_result = await db.execute(reading_query)
            reading = reading_result.scalar_one_or_none()
            
            # Получаем настройки датчика
            setting_query = sa.select(EquipmentSetting).where(
                EquipmentSetting.sensor_id == sensor.id
            )
            setting_result = await db.execute(setting_query)
            setting = setting_result.scalar_one_or_none()
            
            if not reading:
                # Если нет показаний, создаем тестовое
                if "temperature" in sensor.sensor_type:
                    value = str(round(random.uniform(15, 85), 1))
                elif "pressure" in sensor.sensor_type:
                    value = str(round(random.uniform(0.5, 12), 2))
                elif "speed" in sensor.sensor_type:
                    value = str(round(random.uniform(5, 120)))
                else:
                    value = str(round(random.uniform(0, 100), 1))
                
                new_reading = SensorReading(
                    sensor_id=sensor.id,
                    value=value,
                    time=datetime.now()
                )
                db.add(new_reading)
                await db.commit()
                
                reading = new_reading
            
            # Переменные по умолчанию
            value_float = 0
            min_value = None
            max_value = None
            status = "normal"
            
            # Безопасное получение текущего значения
            if reading and reading.value:
                try:
                    # Проверяем, является ли значение JSON-строкой
                    if reading.value.startswith('{') and reading.value.endswith('}'):
                        # Парсим JSON
                        data = json.loads(reading.value)
                        # Ищем числовое значение в JSON (берем первое найденное числовое значение)
                        value_found = False
                        for key, val in data.items():
                            if isinstance(val, (int, float)) and key not in ['sensor_id', 'timestamp']:
                                value_float = val
                                value_found = True
                                break
                        
                        if not value_found:
                            # Если числового значения нет, пытаемся использовать само значение
                            value_float = float(reading.value)
                    else:
                        # Если не JSON, пробуем преобразовать как обычное число
                        value_float = float(reading.value)
                except (ValueError, TypeError, json.JSONDecodeError) as e:
                    logger.warning(f"Не удалось преобразовать значение {reading.value} в число: {e}")
                    value_float = 0
            
            # Безопасное получение минимального значения
            if setting and setting.min_value:
                try:
                    min_value_str = setting.min_value.strip() if isinstance(setting.min_value, str) else setting.min_value
                    if min_value_str:  # Проверяем, что строка не пустая
                        min_value = float(min_value_str)
                except (ValueError, TypeError, AttributeError):
                    logger.warning(f"Не удалось преобразовать минимальное значение {setting.min_value} в число")
            
            # Безопасное получение максимального значения
            if setting and setting.max_value:
                try:
                    max_value_str = setting.max_value.strip() if isinstance(setting.max_value, str) else setting.max_value
                    if max_value_str:  # Проверяем, что строка не пустая
                        max_value = float(max_value_str)
                except (ValueError, TypeError, AttributeError):
                    logger.warning(f"Не удалось преобразовать максимальное значение {setting.max_value} в число")
            
            # Определение статуса только если все значения правильно установлены
            if isinstance(min_value, (int, float)) and isinstance(value_float, (int, float)) and value_float < min_value:
                status = "alert"
                logger.info(f"Датчик {sensor.sensor_name} в статусе alert: значение {value_float} < {min_value}")
            elif isinstance(max_value, (int, float)) and isinstance(value_float, (int, float)) and value_float > max_value:
                status = "alert"
                logger.info(f"Датчик {sensor.sensor_name} в статусе alert: значение {value_float} > {max_value}")
            else:
                logger.info(f"Датчик {sensor.sensor_name} в статусе normal: значение {value_float}, диапазон: {min_value}-{max_value}")
            
            location_name = sensor.location.name if sensor.location else "Неизвестно"
            
            sensor_data = {
                "sensor_id": sensor.id,
                "sensor_name": sensor.sensor_name,
                "location": location_name,
                "value": value_float,
                "min_value": min_value,
                "max_value": max_value,
                "status": status,
                "time": reading.time.isoformat() if reading and reading.time else datetime.now().isoformat()
            }
            
            response_data.append(sensor_data)
        
        return response_data
    
    except Exception as e:
        logger.error(f"Ошибка при получении данных датчиков: {e}")
        logger.error(f"Детали ошибки: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении данных датчиков: {str(e)}"
        )


@app.get("/api/generate-test-data")
async def generate_test_data(request: Request, db: AsyncSession = Depends(get_async_session)):
    """Генерация тестовых данных для отладки"""
    try:
        # Проверяем, авторизован ли пользователь
        user = await get_current_user_from_cookie(request, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Требуется авторизация"
            )
            
        # Получаем все датчики
        query = sa.select(Sensor)
        result = await db.execute(query)
        sensors = result.scalars().all()
        
        # Если датчиков нет, создаем их
        if not sensors:
            await create_test_sensors(db)
            
            # Получаем созданные датчики
            query = sa.select(Sensor)
            result = await db.execute(query)
            sensors = result.scalars().all()
        
        # Создаем тестовые показания
        await create_test_readings(db, sensors)
        
        return {"message": "Тестовые данные успешно созданы", "sensors_count": len(sensors)}
        
    except Exception as e:
        logger.error(f"Ошибка при генерации тестовых данных: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при генерации тестовых данных: {str(e)}"
        )


@app.get("/equipment-settings/generate-test")
async def generate_test_equipment_settings(db: AsyncSession = Depends(get_async_session)):
    """Создание тестовых настроек оборудования для датчиков"""
    try:
        result = await create_test_equipment_settings(db)
        return {"success": result, "message": "Тестовые настройки оборудования созданы"}
    except Exception as e:
        logger.error(f"Ошибка при генерации тестовых настроек: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка при генерации тестовых настроек: {str(e)}"
        )

async def create_test_equipment_settings(db: AsyncSession):
    """Создание тестовых настроек оборудования для датчиков"""
    try:
        # Получаем все датчики
        sensors_query = sa.select(Sensor)
        sensors_result = await db.execute(sensors_query)
        sensors = sensors_result.scalars().all()
        
        if not sensors:
            logger.warning("Датчики не найдены для создания настроек")
            return
        
        # Проверяем наличие существующих настроек
        existing_query = sa.select(EquipmentSetting)
        existing_result = await db.execute(existing_query)
        existing_settings = existing_result.scalars().all()
        
        # Создаем словарь существующих настроек по sensor_id
        existing_settings_dict = {es.sensor_id: es for es in existing_settings}
        
        # Счетчики для логирования
        created_count = 0
        updated_count = 0
        
        # Создаем настройки для датчиков
        for sensor in sensors:
            # Определяем диапазоны в зависимости от типа датчика - используем числа вместо строк
            if "temperature" in sensor.sensor_type:
                min_value, max_value = 20.0, 80.0
            elif "pressure" in sensor.sensor_type:
                min_value, max_value = 1.0, 10.0
            elif "speed" in sensor.sensor_type:
                min_value, max_value = 10.0, 100.0
            elif "level" in sensor.sensor_type:
                min_value, max_value = 10.0, 90.0
            elif "quality" in sensor.sensor_type:
                min_value, max_value = 85.0, 100.0
            elif "weight" in sensor.sensor_type:
                min_value, max_value = 0.5, 2.0
            elif "flow" in sensor.sensor_type:
                min_value, max_value = 50.0, 150.0
            else:
                min_value, max_value = 0.0, 100.0
            
            # Проверяем существует ли настройка для этого датчика
            if sensor.id in existing_settings_dict:
                # Обновляем существующую настройку
                existing_setting = existing_settings_dict[sensor.id]
                existing_setting.min_value = min_value
                existing_setting.max_value = max_value
                updated_count += 1
            else:
                # Создаем новую настройку с числовыми значениями
                new_setting = EquipmentSetting(
                    sensor_id=sensor.id,
                    min_value=min_value,
                    max_value=max_value,
                )
                db.add(new_setting)
                created_count += 1
        
        # Сохраняем изменения
        await db.commit()
        logger.info(f"Создано {created_count} и обновлено {updated_count} настроек оборудования")
        
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при создании настроек оборудования: {e}")
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)