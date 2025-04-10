from fastapi import FastAPI
from app.routers import items, users
from app.database import engine, Base

print("WITAM")

# Tworzenie tabel w bazie danych
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dołączanie routerów
app.include_router(users.router)
app.include_router(items.router)

@app.get("/")
async def root():
    return {"message": "Witaj w aplikacji FastAPI"}
