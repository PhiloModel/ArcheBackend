import firebase_admin
from firebase_admin import storage
from fastapi import FastAPI
from firebase_admin import credentials, firestore

# Ścieżka do pliku konfiguracyjnego
SERVICE_ACCOUNT_KEY_PATH = './config/philo-bot-firebase-adminsdk-fbsvc-37571ede52.json'

# Inicjalizacja Firebase Admin SDK
cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)

firebase_admin.initialize_app(cred, {
    'storageBucket': 'philo-bot.firebasestorage.app'  # Użyj poprawnej nazwy bucketu
})

bucket = storage.bucket() # Pobranie referencji do bucketu Cloud Storage

db = firestore.client() # Pobranie referencji do Cloud Firestore

def get_db():
    return db



