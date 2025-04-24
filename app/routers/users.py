from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud, models, schemas, database
from app.database import bucket, db

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

def get_user_by_email(email: str):
    print("++++++++++get_user_by_email")
    users_ref = db.collection("users")
    query = users_ref.where("email", "==", email).stream()
    return [doc.to_dict() for doc in query]

def create_new_user(email: str):
    print("++++++++create_new_user")
    users_ref = db.collection("users")
    users_ref.add({"email": email})
