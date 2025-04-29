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
from app.routers.files import delete_all_pdfs_local
from fastapi import Depends, HTTPException, status
from app.routers.users import User, get_current_user
from datetime import datetime, timedelta

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

@router.post("/load_private", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatbotRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        print(f"Loading RAG for user {current_user.email}")
        global chat_bot_RAG

        # Create user-specific local directory
        local_dir = f"./tmp/{current_user.uid}/{request.rag_name}"
        os.makedirs(local_dir, exist_ok=True)

        # Define Firebase Storage prefix for user's RAG
        storage_prefix = f"rags/{current_user.uid}/{request.rag_name}/"
        
        # Download files from Firebase Storage
        blobs = bucket.list_blobs(prefix=storage_prefix)
        for blob in blobs:
            if blob.name.endswith('/'):
                continue
                
            # Create local path maintaining directory structure
            relative_path = blob.name[len(storage_prefix):]
            local_path = os.path.join(local_dir, relative_path)
            print(f"Downloading {blob.name} to {local_path}")

            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            blob.download_to_filename(local_path)
            print(f"Downloaded: {blob.name} to {local_path}")

        # Load the RAG model from downloaded files
        chat_bot_RAG.load_model(local_dir)

        reply_message = f"Załadowano pomyślnie RAG '{request.rag_name}' dla użytkownika {current_user.email}"
        return ChatResponse(reply=reply_message)

    except Exception as e:
        print(f"Error loading RAG: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd podczas ładowania RAG: {str(e)}"
        )
    finally:
        # Cleanup temporary files
        if os.path.exists(local_dir):
            shutil.rmtree(local_dir)
            print(f"Cleaned up temporary directory: {local_dir}")


class ChatQueryRequest(BaseModel):
    message: str
    chat_id: str
    chat_name: str

@router.post("/query", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        print(f"Processing query for user {current_user.email}, chat: {request.chat_name}")
        
        # Define chat history path
        history_prefix = f"chat_history/{current_user.uid}/"
        blobs = bucket.list_blobs(prefix=history_prefix)
        
        # Find existing chat history
        chat_history = None
        for blob in blobs:
            if blob.name.endswith('.json') and request.chat_id in blob.name:
                content = blob.download_as_string()
                chat_history = json.loads(content)
                chat_blob = blob
                break
        
        if not chat_history:
            # Initialize new chat history if not found
            chat_history = {
                "chat_name": request.chat_name,
                "chat_id": request.chat_id,
                "messages": []
            }
        
        # Get response from RAG model
        if chat_bot_RAG.model is not None:
            response = chat_bot_RAG.get_response(request.message)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RAG model not loaded"
            )

        # Create new messages
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        new_messages = [
            {
                "role": "user",
                "content": request.message,
                "timestamp": timestamp
            },
            {
                "role": "assistant",
                "content": response,
                "timestamp": timestamp
            }
        ]
        
        # Add new messages to history
        chat_history["messages"].extend(new_messages)
        
        # Upload updated chat history
        blob_path = f"chat_history/{current_user.uid}/{request.chat_id}_{timestamp}.json"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(
            json.dumps(chat_history, ensure_ascii=False),
            content_type='application/json'
        )
        
        # Delete old chat history file if it exists
        if 'chat_blob' in locals():
            chat_blob.delete()
        
        return ChatResponse(reply=response)

    except Exception as e:
        print(f"Error processing query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd podczas przetwarzania zapytania: {str(e)}"
        )
    
class RAGListResponse(BaseModel):
    names: list[str]

@router.get("/list_rags", response_model=RAGListResponse)
async def get_rag_list(current_user: User = Depends(get_current_user)):
    # Add user-specific prefix
    prefix = f"rags/{current_user.uid}/"

    # List blobs with user-specific prefix
    blobs = bucket.list_blobs(prefix=prefix)
 
    folder_names = set()
    for blob in blobs:
        if blob.name.endswith("/"):
            continue

        # Remove user-specific prefix to get folder name
        parts = blob.name[len(prefix):].split("/")
        if parts:
            folder_names.add(parts[0])

    print(f"RAG models for user {current_user.email}:", folder_names)
    return RAGListResponse(names=sorted(folder_names))

@router.post("/create_rag")
async def create_rag(
    rag_name: str = Form(...),
    selected_model: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    try:
        print(f"Creating RAG for user {current_user.email}")
        
        # Set up directories
        local_temp_dir = f"./tmp/{current_user.uid}/{selected_model}/"
        persist_directory = f"./docs/chroma/{current_user.uid}/{rag_name}/"
        
        # Create temp directory if it doesn't exist
        os.makedirs(local_temp_dir, exist_ok=True)
        
        # Download files from Firebase Storage
        storage_prefix = f"uploaded_pdfs/{current_user.uid}/{selected_model}/"
        print(f"Downloading files from {storage_prefix}")
        
        blobs = bucket.list_blobs(prefix=storage_prefix)
        downloaded_files = []
        
        for blob in blobs:
            if blob.name.endswith('/'):
                continue
                
            # Get filename from blob path
            filename = blob.name.split('/')[-1]
            local_path = os.path.join(local_temp_dir, filename)
            
            # Download file
            blob.download_to_filename(local_path)
            downloaded_files.append(local_path)
            print(f"Downloaded: {blob.name} to {local_path}")
            
        if not downloaded_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No files found for model {selected_model}"
            )
            
        # Create RAG model
        chat_bot_RAG.create_model(local_temp_dir, persist_directory)
        print(f'Created RAG model: {chat_bot_RAG.model_name}')

        # Upload vector database to Firebase Storage
        for root, _, files in os.walk(persist_directory):
            print(f"Uploading files from {root} to Firebase Storage")
            for file in files:
                local_path = os.path.join(root, file)
                remote_path = os.path.join(
                    "rags", 
                    current_user.uid, 
                    rag_name, 
                    os.path.relpath(local_path, persist_directory)
                )
                print(f"Uploading {local_path} to {remote_path}")
                blob = bucket.blob(remote_path)
                blob.upload_from_filename(local_path)

        reply_message = f"Utworzono RAG '{rag_name}' dla użytkownika {current_user.email}"

        # Clean up temporary files
        delete_all_pdfs_local(temp_dir=f"./tmp/{current_user.uid}")
        delete_all_pdfs_local(temp_dir=f"./docs/chroma/{current_user.uid}")

        return {"reply": reply_message}

    except Exception as e:
        print(f"Error creating RAG: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd podczas tworzenia RAG: {str(e)}"
        )
    finally:
        # Ensure cleanup in case of errors
        if os.path.exists(local_temp_dir):
            shutil.rmtree(local_temp_dir)



# Add new model for chat list response
class ChatSessionInfo(BaseModel):
    id: str
    name: str
    timestamp: str

class ChatListResponse(BaseModel):
    chats: list[ChatSessionInfo]

@router.get("/chat_sessions", response_model=ChatListResponse)
async def get_chat_sessions(current_user: User = Depends(get_current_user)):
    try:
        print(f"Fetching chat sessions for user {current_user.email}")
        
        # Define Firebase Storage prefix for user's chat history
        history_prefix = f"chat_history/{current_user.uid}/"
        
        # List blobs with user-specific prefix
        blobs = bucket.list_blobs(prefix=history_prefix)
        
        chat_sessions = []
        for blob in blobs:

            if blob.name.endswith('.json'):
                # Parse filename to get information
                filename = blob.name.split('/')[-1]  # Get just the filename
                chat_id = filename.split('_')[0]     # First part is ID
                timestamp = filename.split('_')[1].replace('.json', '')  # Second part is timestamp
                
                # Download just the chat name from metadata
                content = blob.download_as_string()
                chat_data = json.loads(content)
                chat_name = chat_data.get('chat_name', f"Chat {chat_id}")  # Fallback name if not set
                
                print(f'timestamp {timestamp} ')
                chat_sessions.append(ChatSessionInfo(
                    id=chat_id,
                    name=chat_name,
                    timestamp=timestamp
                ))
        
        # Sort chat sessions by timestamp, newest first
        chat_sessions.sort(key=lambda x: x.timestamp, reverse=True)
        
        print(f"Found {len(chat_sessions)} chat sessions for user {current_user.email}")
        return ChatListResponse(chats=chat_sessions)

    except Exception as e:
        print(f"Error fetching chat sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd podczas pobierania listy czatów: {str(e)}"
        )
    
# Add new response model for chat history
class ChatHistoryDetailResponse(BaseModel):
    chat_id: str
    chat_name: str
    timestamp: str
    messages: list[dict]

class ChatIdRequest(BaseModel):
    chat_id: str

@router.get("/get_chat_history/{chat_id}", response_model=ChatHistoryDetailResponse)
async def get_chat_history(
    chat_id: str,  # Changed from ChatIdRequest to str
    current_user: User = Depends(get_current_user)
):
    try:
        print(f"Fetching chat {chat_id} for user {current_user.email}")
        
        # Define Firebase Storage prefix for user's chat history
        history_prefix = f"chat_history/{current_user.uid}/"
        
        # List blobs to find the specific chat file
        blobs = bucket.list_blobs(prefix=history_prefix)
        
        # Find the latest version of the chat history
        target_blob = None
        latest_timestamp = "0"
        
        for blob in blobs:
            if blob.name.endswith('.json') and chat_id in blob.name:
                timestamp = blob.name.split('_')[1].replace('.json', '')
                if timestamp > latest_timestamp:
                    target_blob = blob
                    latest_timestamp = timestamp
        
        if not target_blob:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat {chat_id} not found"
            )
        
        # Download and parse chat history
        content = target_blob.download_as_string()
        chat_data = json.loads(content)
        
        return ChatHistoryDetailResponse(
            chat_id=chat_data["chat_id"],
            chat_name=chat_data["chat_name"],
            timestamp=latest_timestamp,
            messages=chat_data["messages"]
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching chat history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd podczas pobierania historii czatu: {str(e)}"
        )

# Add after existing BaseModel classes
class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str

class CreateChatHistoryRequest(BaseModel):
    chat_name: str
    messages: list[ChatMessage]

@router.post("/create_chat_history")
async def save_chat_history(
    request: CreateChatHistoryRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        print(f"Saving chat history for user {current_user.email}")
        
        # Generate unique chat ID and timestamp
        chat_id = str(uuid.uuid4())[:8]  # First 8 characters of UUID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Create chat history data
        chat_data = {
            "chat_name": request.chat_name,
            "chat_id": chat_id,
            "timestamp": timestamp,
            "messages": [msg.dict() for msg in request.messages]
        }
        
        # Define blob path for the chat history
        blob_path = f"chat_history/{current_user.uid}/{chat_id}_{timestamp}.json"
        blob = bucket.blob(blob_path)
        
        # Upload chat history as JSON
        blob.upload_from_string(
            json.dumps(chat_data, ensure_ascii=False),
            content_type='application/json'
        )
        
        print(f"Saved chat history: {blob_path}")
        return {
            "message": "Chat history saved successfully",
            "chat_id": chat_id,
            "timestamp": timestamp
        }

    except Exception as e:
        print(f"Error saving chat history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd podczas zapisywania historii czatu: {str(e)}"
        )
