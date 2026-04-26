from contextlib import asynccontextmanager
import os
import shutil
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chatbot import chat, explain_diagnosis
from xray_model import predict


UPLOAD_DIR = "uploads"
ALLOWED_ORIGINS = [
	"http://localhost:3000",
	"http://127.0.0.1:3000",
]
ALLOWED_METHODS = ["GET", "POST", "OPTIONS"]
ALLOWED_HEADERS = ["Authorization", "Content-Type"]


@asynccontextmanager
async def lifespan(_: FastAPI):
	os.makedirs(UPLOAD_DIR, exist_ok=True)
	yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=ALLOWED_ORIGINS,
	allow_credentials=True,
	allow_methods=ALLOWED_METHODS,
	allow_headers=ALLOWED_HEADERS,
)


class ChatRequest(BaseModel):
	message: str
	context: str


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

		explanation_input = {}
		if isinstance(predictions, dict):
			if isinstance(predictions.get("scores"), dict):
				explanation_input.update(predictions["scores"])
			if isinstance(predictions.get("limitations"), dict):
				explanation_input.update(predictions["limitations"])

		if not explanation_input and isinstance(predictions, dict):
			explanation_input = predictions

		explanation = explain_diagnosis({**predictions.get("scores", {}), **predictions.get("limitations", {})})
		return {"predictions": predictions, "explanation": explanation}
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to analyze image") from exc


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
	try:
		response = chat(request.message, request.context)
		return {"response": response}
	except Exception as exc:
		raise HTTPException(status_code=500, detail="Failed to process chat request") from exc
