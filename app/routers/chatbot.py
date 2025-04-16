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

sys.path.append(r"C:\Users\kubak\Desktop\PhiloModel\github\AgoraRAG")
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

    prefix = "uploaded_pdfs/"
    delimiter = "/"
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


@router.post("/create_rag")
async def upload_files(
    rag_name: str = Form(...),
    files: list[UploadFile] = File(...)
):
    upload_dir = f"uploaded_rags/{rag_name}/"
    os.makedirs(upload_dir, exist_ok=True)

    for file in files:
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # Można tutaj utworzyć ChatBotRAG na podstawie upload_dir
    reply_message = f"Załadowano {len(files)} plików do modelu '{rag_name}'."

    print("Creating RAG!")
    print(upload_dir)

    # Tworzenie PhiloBota
    chat_bot_RAG.create_model(upload_dir, rag_name)

    reply_message = f"Utworzyłem RAG na podstawie folderu: {upload_dir}"

    return {"reply": reply_message}

@router.post("/upload_pdfs")
async def upload_files(
    rag_name: str = Form(...),
    files: list[UploadFile] = File(...)
):
    try:
        uploaded_files = []

        for file in files:
            # Generowanie unikalnej nazwy pliku
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            blob_path = f"uploaded_pdfs/{rag_name}/{unique_filename}"
            blob = bucket.blob(blob_path)

            # Przesyłanie pliku do Firebase Storage
            blob.upload_from_file(file.file, content_type=file.content_type)

            # Opcjonalnie: Ustawienie pliku jako publicznego
            # blob.make_public()
            # download_url = blob.public_url

            uploaded_files.append(blob_path)

        reply_message = f"Załadowano {len(uploaded_files)} plików do modelu '{rag_name}'."
        return {"reply": reply_message, "files": uploaded_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd podczas przesyłania plików: {str(e)}")
