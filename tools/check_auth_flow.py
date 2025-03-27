import httpx
import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_auth_flow():
    """Проверка полного процесса аутентификации"""
    try:
        base_url = "http://localhost:8000"
        
        # Создаем клиент, который будет сохранять cookies
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # Шаг 1: Попробуем получить токен через POST /token
            logger.info("Шаг 1: Получение токена через POST /token")
            token_response = await client.post(
                f"{base_url}/token",
                data={"username": "admin", "password": "admin123"},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            logger.info(f"Статус ответа: {token_response.status_code}")
            logger.info(f"Cookies: {client.cookies}")
            logger.info(f"Ответ: {token_response.text[:100]}...")
            
            # Проверим, что мы получили токен
            if token_response.status_code == 200:
                token_data = token_response.json()
                token = token_data.get("access_token")
                logger.info(f"Токен получен: {token[:10]}...")
            else:
                logger.warning(f"Не удалось получить токен: {token_response.text}")
            
            # Шаг 2: Проверим доступ к защищенному ресурсу
            logger.info("\nШаг 2: Проверка доступа к /dashboard")
            dashboard_response = await client.get(f"{base_url}/dashboard")
            
            logger.info(f"Статус ответа: {dashboard_response.status_code}")
            logger.info(f"URL после перенаправлений: {dashboard_response.url}")
            
            # Шаг 3: Авторизуемся через форму входа
            logger.info("\nШаг 3: Авторизация через форму входа")
            login_response = await client.post(
                f"{base_url}/login",
                data={"username": "admin", "password": "admin"},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            logger.info(f"Статус ответа: {login_response.status_code}")
            logger.info(f"URL после перенаправлений: {login_response.url}")
            logger.info(f"Cookies после входа: {client.cookies}")
            
            # Шаг 4: Снова проверим доступ к защищенному ресурсу
            logger.info("\nШаг 4: Повторная проверка доступа к /dashboard")
            dashboard_response2 = await client.get(f"{base_url}/dashboard")
            
            logger.info(f"Статус ответа: {dashboard_response2.status_code}")
            logger.info(f"URL после перенаправлений: {dashboard_response2.url}")
    
    except Exception as e:
        logger.error(f"Ошибка при тестировании аутентификации: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth_flow()) 