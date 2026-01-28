import json
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .schemas import User, UserInDB, TokenData

# Secret keys (In production, use env variables)
SECRET_KEY = "MP_MOTORSPORT_SECRET_POWER"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 Week

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

DB_FILE = os.path.join(os.path.dirname(__file__), "users.json")

def load_users():
    if not os.path.exists(DB_FILE):
        # Initial user
        initial = {
            "jaap": {
                "username": "jaap",
                "full_name": "Jaap van Oort",
                "email": "jaap@mponemedia.com",
                "hashed_password": pwd_context.hash("admin123"),
                "disabled": False
            },
            "eric": {
                "username": "eric",
                "full_name": "Eric",
                "email": "eric@mponemedia.com",
                "hashed_password": pwd_context.hash("Speed123"),
                "disabled": False
            }
        }
        with open(DB_FILE, "w") as f:
            json.dump(initial, f)
    with open(DB_FILE, "r") as f:
        return json.load(f)

def get_user(username: str):
    users = load_users()
    if username in users:
        return UserInDB(**users[username])
    return None

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user
