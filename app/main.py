from fastapi import FastAPI
from app.routers import items, users
from app.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv
import sys
import os 

sys.path.append(r"C:\Users\kubak\Desktop\PhiloModel\github\AgoraRAG")
from app.routers import chatbot  # import routera chat

# Tworzenie tabel w bazie danych
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Lista dozwolonych źródeł (np. frontend działający na porcie 3000)
origins = [
    "http://localhost:3000",
    "https://yourfrontenddomain.com",
]

# Dodanie middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Dozwolone źródła
    allow_credentials=True,
    allow_methods=["*"],  # Dozwolone metody, np. ["GET", "POST", "OPTIONS"]
    allow_headers=["*"],  # Dozwolone nagłówki
)

# Dołączanie routerów
app.include_router(users.router)
app.include_router(items.router)

# Dołączenie routera chat
app.include_router(chatbot.router)

@app.get("/")
async def root():
    return {"message": "Witaj w aplikacji FastAPI"}
