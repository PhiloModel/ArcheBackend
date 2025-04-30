from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud, models, schemas, database
from app.database import bucket, db
from config.secret import SECRET_KEY, ALGORITHM
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
import uuid

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

# Model danych użytkownika
class User(BaseModel):
    email: str
    uid: str

async def get_user_by_email(email: str):
    users_ref = db.collection("users")
    query = users_ref.where("email", "==", email).stream()
    users = [doc.to_dict() for doc in query]
    # Return the first user found or None
    return users[0] if users else None

async def create_new_user(email: str):
    users_ref = db.collection("users")
    users_ref.add({"email": email, "uid": str(uuid.uuid4())})

# Inicjalizacja OAuth2PasswordBearer z odpowiednim URL-em tokenu
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nie można zweryfikować poświadczeń",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Dekodowanie tokenu JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        user = await get_user_by_email(email)
        if not user:
            raise credentials_exception

        return User(**user)
    
    except JWTError as e:
        print('JWT Error:', str(e))
        raise credentials_exception