from datetime import datetime, timedelta
import jose

# Константы
SECRET_KEY = "ваш_секретный_ключ"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 час

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Создание простого JWT токена"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jose.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt 