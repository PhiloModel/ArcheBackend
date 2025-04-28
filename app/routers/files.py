from fastapi import APIRouter, UploadFile, status, File, Form, HTTPException, Depends
from pydantic import BaseModel
import sys
import os 
from fastapi import UploadFile, File, Form
from fastapi.responses import JSONResponse
import shutil
import json
from app.database import bucket, db
import uuid
from app.routers.users import get_current_user, User
from firebase_admin import auth



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
async def get_rag_list(current_user: User = Depends(get_current_user)):
    try:
        prefix = f"uploaded_pdfs/{current_user.uid}/"
        blobs = bucket.list_blobs(prefix=prefix)

        file_names = set()
        for blob in blobs:
            if blob.name.endswith("/"):
                continue
            parts = blob.name[len(prefix):].split("/")
            if parts:
                file_names.add(parts[0])
        print(f"File names for user {current_user.email}:")
        for name in file_names:
            print(name)
        return ListResponse(names=sorted(file_names))
    except Exception as e:
        print(f"Error in get_rag_list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
class LoadPDFsRequest(BaseModel):
    rag_name: str

class ListResponse(BaseModel):
    names: list[str]

@router.post("/load_pdfs", response_model=ListResponse)
async def load_pdfs(
    request: LoadPDFsRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        rag_name = request.rag_name
        
        # Include user ID in the prefix path
        prefix = f"uploaded_pdfs/{current_user.uid}/{rag_name}/"
        print(f"Prefix for user {current_user.email}: {prefix}")

        # Include user ID in the local temp directory
        local_temp_dir = f"./tmp/{current_user.uid}/{rag_name}/"
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

        print(f"Downloaded files for user {current_user.email}:", downloaded_files)
        return ListResponse(names=downloaded_files)
        
    except Exception as e:
        print(f"Error in load_pdfs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
def delete_all_pdfs_local(temp_dir = "./tmp/"):
    
    if os.path.exists(temp_dir):
        for folder_name in os.listdir(temp_dir):
            folder_path = os.path.join(temp_dir, folder_name)
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)

    return {"detail": "Temporary PDFs folder cleared."}


@router.post("/upload_pdfs")
async def upload_files(
    rag_name: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    try:
        print(f"Authenticated user: {current_user.email}")
        uploaded_files = []

        for file in files:
            # Validate file type
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {file.filename} is not a PDF"
                )

            # Generate unique filename with user-specific path
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            blob_path = f"uploaded_pdfs/{current_user.uid}/{rag_name}/{unique_filename}"
            blob = bucket.blob(blob_path)

            # Upload file to Firebase Storage
            blob.upload_from_file(file.file, content_type=file.content_type)
            
            uploaded_files.append(blob_path)
            print(f"Uploaded file {file.filename} for user {current_user.email}")

        reply_message = f"Załadowano {len(uploaded_files)} plików do modelu '{rag_name}'."
        return {"reply": reply_message, "files": uploaded_files}

    except Exception as e:
        print(f"Error in upload_files: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd podczas przesyłania plików: {str(e)}"
        )
    
@router.delete("/files/clear_pdfs")
async def delete_all_pdfs_endpoint():
    return delete_all_pdfs_local()