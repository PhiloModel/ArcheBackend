from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud, models, schemas, database

router = APIRouter(
    prefix="/items",
    tags=["items"],
)

def get_db():
    db = database.Session
