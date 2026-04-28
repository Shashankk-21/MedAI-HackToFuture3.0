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
import xray_model as xray_model
import time
import tracemalloc


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



@app.get("/health")
async def health_check():
    """Health check for the backend: ensemble status, models loaded, CLAHE active"""
    info = {
        "ensemble_loaded": False,
        "models_loaded": [],
        "weights_present": [],
        "clahe_active": False,
        "load_error": None,
    }

    # Check CLAHE availability
    try:
        info["clahe_active"] = hasattr(xray_model, "cv2") and hasattr(xray_model.cv2, "createCLAHE")
    except Exception:
        info["clahe_active"] = False

    # Check weight files in backend/weights
    weights_dir = os.path.join(os.path.dirname(__file__), "weights")
    try:
        if os.path.isdir(weights_dir):
            info["weights_present"] = [f for f in os.listdir(weights_dir) if os.path.isfile(os.path.join(weights_dir, f))]
        else:
            info["weights_present"] = []
    except Exception:
        info["weights_present"] = []

    # Attempt to lazily load ensemble models and measure time
    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        models = xray_model._get_ensemble_models()
        info["ensemble_loaded"] = True
        info["models_loaded"] = list(models.keys())
    except Exception as exc:
        info["ensemble_loaded"] = False
        info["load_error"] = f"{type(exc).__name__}: {exc}"
    t1 = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    info["load_seconds"] = round(t1 - t0, 3)
    info["tracemalloc_current_mb"] = round(current / (1024 * 1024), 2)
    info["tracemalloc_peak_mb"] = round(peak / (1024 * 1024), 2)

    status = 200 if info["ensemble_loaded"] else 503
    return JSONResponse(status_code=status, content=info)