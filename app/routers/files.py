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

router = APIRouter(
    prefix="/files",
    tags=["files"],
)

class ListResponse(BaseModel):
    names: list[str]

# Model danych dla odpowiedzi
class ChatResponse(BaseModel):
    reply: str

class ChatbotRequest(BaseModel):
    dir_path: str
    rag_name: str

@router.get("/list_pdfs", response_model=ListResponse)
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

    return ListResponse(names=sorted(folder_names))


class LoadPDFsRequest(BaseModel):
    rag_name: str

class ListResponse(BaseModel):
    names: list[str]

@router.post("/load_pdfs", response_model=ListResponse)
async def load_pdfs(request: LoadPDFsRequest):
    rag_name = request.rag_name

    prefix = f"uploaded_pdfs/{rag_name}/"

    local_temp_dir = f"./tmp/{rag_name}/"
    os.makedirs(local_temp_dir, exist_ok=True)

    blobs = bucket.list_blobs(prefix=prefix)

    downloaded_files = []

    for blob in blobs:
        if blob.name.endswith("/"):
            continue  # pomijamy katalogi

        filename = blob.name.split("/")[-1]
        local_path = os.path.join(local_temp_dir, filename)

        blob.download_to_filename(local_path)
        downloaded_files.append(filename)

    print(downloaded_files)
    return ListResponse(names=downloaded_files)

def delete_all_pdfs_local(temp_dir = "./tmp/"):
    
    if os.path.exists(temp_dir):
        for folder_name in os.listdir(temp_dir):
            folder_path = os.path.join(temp_dir, folder_name)
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)

    return {"detail": "Temporary PDFs folder cleared."}

@router.delete("/files/clear_pdfs")
async def delete_all_pdfs_endpoint():
    return delete_all_pdfs_local()