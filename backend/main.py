from contextlib import asynccontextmanager
import os
import shutil
import traceback
import uuid

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import numpy as np
from PIL import Image

from chatbot import chat, explain_diagnosis, generate_chat_init
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
        "https://med-ai-hack-to-future3-0-nu6b755zs-shashanks-projects-7e332267.vercel.app/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    context: str = ""


class ChatResponse(BaseModel):
    response: str


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Accept a chest X-ray image, run inference, generate an AI explanation,
    and return chat initialisation data (greeting + quick-reply pills) so the
    frontend can populate the first chat bubble immediately.

    Response shape:
        {
            "predictions":  { ... },          # raw model output
            "explanation":  "...",             # AI/rule-based markdown explanation
            "chat_init": {
                "greeting":      "...",        # first chat bubble text
                "quick_replies": ["...", ...]  # clickable pill buttons (3 items)
            }
        }
    """
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
        raise HTTPException(
            status_code=500, detail="Failed to save uploaded image"
        ) from exc
    finally:
        await file.close()

    # Validate image before processing
    try:
        img = Image.open(filepath)
        width, height = img.size
        
        # Check image dimensions
        if width < 100 or height < 100:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid image", "message": "Please upload a valid chest X-ray image. Natural photos, screenshots, or non-medical images cannot be analyzed."}
            )
        
        # Convert to grayscale and compute statistics
        gray_img = img.convert("L")
        img_array = np.array(gray_img, dtype=np.float32)
        mean_pixel = np.mean(img_array)
        std_pixel = np.std(img_array)
        
        # Check mean brightness and uniformity
        if mean_pixel > 180 or std_pixel < 20:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid image", "message": "Please upload a valid chest X-ray image. Natural photos, screenshots, or non-medical images cannot be analyzed."}
            )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to validate image"
        ) from exc

    try:
        predictions = predict(filepath)
        overall_assessment: str = predictions.get("overall_assessment", "")

        # Both calls are intentionally independent so one failure does not
        # block the other.
        explanation = explain_diagnosis(predictions)
        chat_init = generate_chat_init(predictions, overall_assessment)

        return {
            "predictions": predictions,
            "explanation": explanation,
            "chat_init": chat_init,
            # Shape: { "greeting": "...", "quick_replies": ["...", "...", "..."] }
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to analyze image"
        ) from exc
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request):
    try:
        payload = getattr(request.state, "chat_payload", None) or {}
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400, detail="Request body must be a JSON object"
            )

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
        raise HTTPException(
            status_code=500, detail="Failed to process chat request"
        ) from exc