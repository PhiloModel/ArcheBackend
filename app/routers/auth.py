from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import json

# Import konfiguracji
from config.secret import ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

# Ścieżka do pliku konfiguracyjnego
config_path = './config/client_secret.json'

# Otwórz i załaduj plik JSON
with open(config_path, 'r') as config_file:
    config_data = json.load(config_file)

# Pobierz wartości z załadowanego słownika
GOOGLE_CLIENT_ID = config_data.get('client_id')
GOOGLE_CLIENT_SECRET = config_data.get('client_secret')
GOOGLE_REDIRECT_URI = config_data.get('token_uri')

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
    encoded_jwt = jwt.encode(to_encode, CLIENT_SECRET)
    return encoded_jwt

@router.post("/register", response_model=UserResponse)
async def register(auth_data: AuthData):
    # Przykładowa logika rejestracji:
    # 1. Sprawdzenie, czy użytkownik już istnieje w bazie (pseudokod)
    # user = get_user_by_email(auth_data.email)
    # if user:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Użytkownik już istnieje")
    
    # 2. Haszowanie hasła
    hashed_password = pwd_context.hash(auth_data.password)
    
    # 3. Zapis użytkownika do bazy
    # new_user = User(email=auth_data.email, hashed_password=hashed_password)
    # db.add(new_user)
    # db.commit()
    # db.refresh(new_user)
    
    # 4. Generowanie tokena JWT
    access_token = create_access_token(data={"sub": auth_data.email})
    
    return UserResponse(email=auth_data.email, token=access_token)

@router.post("/google", response_model=UserResponse)
async def auth_google(token: dict):

    google_token = token.get("token")
    if not google_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brak tokena w żądaniu")
    print('TOKEN: ', google_token)
    try:
        # Weryfikacja tokena Google
        idinfo = id_token.verify_oauth2_token(google_token, google_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowy token Google")
    
    email = idinfo.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brak emaila w tokenie Google")
    
    # Sprawdzenie, czy użytkownik istnieje w bazie danych
    user = await get_user_by_email(email)

    if not user:
        # Rejestracja nowego użytkownika
        user = await create_new_user(email=email)
    
    # Generowanie tokena JWT
    access_token = create_access_token(data={"sub": email})
    return UserResponse(email=email, token=access_token)

