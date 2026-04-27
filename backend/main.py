from contextlib import asynccontextmanager
import os
import shutil
import uuid
import traceback

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from chatbot import chat, explain_diagnosis
from xray_model import predict


UPLOAD_DIR = "uploads"


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    context: str = ""


class ChatResponse(BaseModel):
    response: str


@app.middleware("http")
async def log_chat_requests(request: Request, call_next):
    if request.url.path != "/chat":
        return await call_next(request)

    print("--- INCOMING CHAT REQUEST ---")
    print(f"method={request.method} path={request.url.path}")

    if request.method == "OPTIONS":
        return await call_next(request)

    try:
        payload = await request.json()
        print(f"payload keys={list(payload.keys())}")
    except Exception as exc:
        print(f"json_parse_error={exc}")
        return JSONResponse(
            status_code=400,
            content={"detail": "Request body must be valid JSON."},
        )

    request.state.chat_payload = payload
    response = await call_next(request)
    print(f"chat_response_status={response.status_code}")
    return response


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    original_name = file.filename or ""
    ext = os.path.splitext(original_name)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save uploaded image") from exc
    finally:
        await file.close()

    try:
        predictions = predict(filepath)
        explanation = explain_diagnosis(predictions)
        return {"predictions": predictions, "explanation": explanation}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to analyze image") from exc
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request):
    try:
        payload = getattr(request.state, "chat_payload", None) or {}
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        raw_message = payload.get("message")
        raw_context = payload.get("context", payload.get("explanation", ""))
        raw_history = payload.get("history", [])

        message = raw_message.strip() if isinstance(raw_message, str) else ""
        context = raw_context.strip() if isinstance(raw_context, str) else ""
        history = raw_history if isinstance(raw_history, list) else []

        if not message:
            raise HTTPException(
                status_code=422,
                detail="'message' is required and must be a non-empty string",
            )

        response = chat(message, context, history)
        return {"response": response}

    except HTTPException:
        raise
    except Exception as exc:
        print(f"chat_endpoint_error={exc}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process chat request") from exc