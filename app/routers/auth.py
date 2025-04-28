from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import json
from app.database import bucket, db
from app.routers.users import get_user_by_email, create_new_user


# Import konfiguracji
from config.secret import ACCESS_TOKEN_EXPIRE_MINUTES, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from config.secret import ALGORITHM, SECRET_KEY

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


# Model do przyjmowania danych rejestracyjnych
class AuthData(BaseModel):
    email: EmailStr
    password: str

# Model odpowiedzi dla użytkownika
class UserResponse(BaseModel):
    email: EmailStr
    token: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Funkcja do generowania tokena
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    print('Creating token with SECRET_KEY:', SECRET_KEY[:5] + '...')
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Funkcja do weryfikacji hasła
@router.post("/google", response_model=UserResponse)
async def auth_google(token: dict):

    google_token = token.get("token")
    print('google_token: ', google_token)

    if not google_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Brak tokena w żądaniu"
        )
    
    try:
        idinfo = id_token.verify_oauth2_token(
            google_token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        email = idinfo.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Brak emaila w tokenie Google"
            )
        
        user = await get_user_by_email(email)
        if not user:
            user = await create_new_user(email=email)
        
        access_token = create_access_token(data={"sub": email})
        
        return UserResponse(
            email=email,
            token=access_token
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Nieprawidłowy token Google"
        )
