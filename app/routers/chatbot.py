from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import sys
import os 
from fastapi import UploadFile, File, Form
from fastapi.responses import JSONResponse
import shutil
import json
from app.database import bucket, db
import uuid
from pathlib import Path

# Dynamically resolve the path
agora_rag_path = Path("/Users/kubak/Desktop/PhiloBot/github/AgoraRAG").resolve()

# Add the resolved path to sys.path
sys.path.append(str(agora_rag_path))

from my_code.load_models.load_rag import load_rag_based_on_pdfs, load_saved_rag_model

router = APIRouter(
    prefix="/chatbot",
    tags=["chatbot"],
)

class ChatBotRAG():
    model_name : str
    model = None 

    def __init__(self, model_name="PhiloBot"):
        self.model_name = model_name

    def load_model(self, RAG_name):
        persist_directory = f'docs/chroma/{RAG_name}'
        self.model_name = RAG_name

        self.model = load_saved_rag_model(persist_directory)

    def create_model(self, docs_dir_path, RAG_name):
        self.model_name = RAG_name
        self.model = load_rag_based_on_pdfs(docs_dir_path, RAG_name)

    def get_response(self, query):
        result = self.model({"question": query})

        return result['answer']
    
# Inicjalizacja chatbota
chat_bot_RAG = ChatBotRAG() 


# Model danych dla żądania
class ChatRequest(BaseModel):
    message: str

# Model danych dla odpowiedzi
class ChatResponse(BaseModel):
    reply: str

class ChatbotRequest(BaseModel):
    dir_path: str
    rag_name: str

@router.post("/load", response_model=ChatResponse)
async def chat_endpoint(request: ChatbotRequest):
    global chat_bot_RAG

    print("Loading RAG!")
    # Tworzenie PhiloBota
    chat_bot_RAG.load_model(request.rag_name)

    reply_message = f"Załadowałem pomyślnie RAG: {request.dir_path}"

    return ChatResponse(reply=reply_message)

@router.post("/query", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    # Logika chatbota – tutaj prosty przykład, który zwraca echo odebranej wiadomości.
    # Możesz zastąpić poniższy kod swoim algorytmem lub wywołaniem zewnętrznego API.
    if chat_bot_RAG.model is not None:
        response = chat_bot_RAG.get_response(request.message)
    else:
        reply_message = f"Chat jeszcze nie istnieje."
        return ChatResponse(reply=reply_message)
    
    reply_message = f"{response}"
    
    return ChatResponse(reply=reply_message)

class RAGListResponse(BaseModel):
    names: list[str]


@router.get("/list_rags", response_model=RAGListResponse)
async def get_rag_list():

    prefix = "rags/"

    # Pobieramy listę wszystkich plików w Firebase Storage z prefiksem "rags/"
    blobs = bucket.list_blobs(prefix=prefix)
 
    # Używamy setu do przechowywania unikalnych nazw folderów
    folder_names = set()
    for blob in blobs:
        # Pomijamy same foldery (które kończą się na '/')
        if blob.name.endswith("/"):
            continue

        # Usuwamy prefix i uzyskujemy nazwę folderu
        parts = blob.name[len(prefix):].split("/")

        if parts:
            folder_names.add(parts[0])

    return RAGListResponse(names=sorted(folder_names))

from app.routers.files import delete_all_pdfs_local

@router.post("/create_rag")
async def create_rag(
    rag_name: str = Form(...),
    selected_model: str = Form(...)
):
    local_temp_dir = f"./tmp/{selected_model}/"

    # Tworzenie PhiloBota na podstawie pobranych plików
    chat_bot_RAG.create_model(local_temp_dir, rag_name)

    # Ścieżka do stworzonej bazy wektorowej
    vectordb_path = f"docs/chroma/{rag_name}/"

    # Wysłanie plików do Firebase Storage
    for root, _, files in os.walk(vectordb_path):
        for file in files:
            local_path = os.path.join(root, file)
            remote_path = os.path.join("rags", rag_name, os.path.relpath(local_path, vectordb_path))
            blob = bucket.blob(remote_path)
            blob.upload_from_filename(local_path)

    reply_message = f"Utworzono RAG na podstawie plików z Firebase Storage dla: {rag_name}"

    delete_all_pdfs_local(temp_dir="tmp")

    delete_all_pdfs_local(temp_dir="docs")

    return {"reply": reply_message}

