import firebase_admin
from firebase_admin import storage
from fastapi import FastAPI
from firebase_admin import credentials, firestore

# Ścieżka do pliku konfiguracyjnego
SERVICE_ACCOUNT_KEY_PATH = './config/philo-bot-firebase-adminsdk-fbsvc-8402a5b8c0.json'

# Inicjalizacja Firebase Admin SDK
cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)

# Inicjalizacja aplikacji Firebase
firebase_admin.initialize_app(cred, {
    'storageBucket': 'philo-bot.firebasestorage.app',
    "project_id": "philo-bot"
})

bucket = storage.bucket() # Pobranie referencji do bucketu Cloud Storage

db = firestore.client() # Pobranie referencji do Cloud Firestore

users_ref = db.collection()
docs = users_ref.stream()
for doc in docs:
    print(f"{doc.id} => {doc.to_dict()}")

def get_db():
    return db



