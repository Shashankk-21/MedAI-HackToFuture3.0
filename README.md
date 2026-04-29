# 🫁 Zenith — Multimodal Diagnostic AI

> Making radiologist-level chest X-ray analysis accessible to anyone, anywhere, instantly.

Built for **Hack to Future 3.0** | KLS Gogte Institute of Technology, Belagavi
**Track:** AI/ML | **Problem Statement:** AI-04 — Multimodal Diagnosis & Patient Chat Assistant

---

## 🎬 Demo & Links

| Resource | Link |
|---|---|
| 📹 Demo Video | https://youtu.be/6cxGrB3Zkac |
| 🚀 Deployed Prototype | Not deployed due to hackathon time constraints — please run locally using the instructions below |

---

## 🧠 What is Zenith?

Zenith is an AI-powered chest X-ray diagnostic platform that combines deep learning-based disease detection with a patient-facing conversational assistant. It bridges the gap between raw model output and patient comprehension — translating complex radiological findings into plain, empathetic language.

**1.8 billion people globally lack access to a radiologist.** Zenith is built for them.

---

## ✨ Features

- **Multi-label chest disease detection** — Pneumonia, Lung Opacity, Effusion, Consolidation, Atelectasis, Cardiomegaly, Edema
- **Confidence-tiered results** — High Confidence / Likely / Possible / Not Detected
- **Overall assessment headline** — Immediate clinical signal in plain English
- **CLAHE preprocessing** — Clinically validated contrast enhancement before inference
- **Gemini Pro explanation layer** — Translates model scores into patient-readable Markdown summaries
- **Scope-bounded AI assistant** — Radiology-focused chatbot with dynamic quick replies
- **PDF report generation** — One-click diagnostic report for physician handoff
- **Invalid image rejection** — Guardrail against non-medical uploads
- **Dark/Light mode** — Full theme support
- **FastAPI backend** — Async, on-device inference with zero cloud ML dependency

---

## 🏗️ Architecture
User Upload
↓
CLAHE Contrast Enhancement (OpenCV)
↓
DenseNet121 Inference
(Trained on 700K+ X-rays: NIH ChestX-ray14 + CheXpert + MIMIC-CXR + PadChest)
↓
Confidence Scoring Engine
(Threshold classification + Pattern recognition)
↓
Gemini Pro Explanation Layer
(Clinical narrative generation)
↓
Patient Chat Interface
(Context-aware, scope-bounded assistant)


---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| ML Model | DenseNet121 (torchxrayvision) | Gold standard for chest X-ray classification, trained on 700K+ images |
| Preprocessing | CLAHE via OpenCV | Enhances lung tissue contrast — standard in clinical pipelines |
| Backend | FastAPI (Python) | Async inference, clean REST API, auto-generated docs |
| Explanation | Gemini Pro API | Separated from diagnostic engine — LLM only explains, never diagnoses |
| Frontend | React + Tailwind CSS | Fast, responsive, works on any device |

---

## 🚀 Running Locally

### Prerequisites
- Python 3.9+
- Node.js 18+
- A Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))

### Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file inside `/backend`:
GEMINI_API_KEY=your_key_here

Start the backend:
```bash
uvicorn main: app --reload
```

Backend runs at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

---

## 📁 Project Structure
MedAI-HackToFuture3.0/
├── backend/
│   ├── main.py              # FastAPI app + endpoints
│   ├── xray_model.py        # DenseNet121 inference + CLAHE preprocessing
│   ├── chatbot.py           # Gemini Pro integration + prompt engineering
│   ├── requirements.txt
│   └── uploads/             # Temporary image storage
├── frontend/
│   ├── src/
│   │   ├── components/      # UploadScreen, ResultsScreen, ChatScreen
│   │   └── App.jsx
│   └── package.json
└── README.md

---

## 🔬 Model Details

- **Architecture:** DenseNet121 pretrained weights via `torchxrayvision`
- **Primary weights:** `densenet121-res224-all` — trained across NIH ChestX-ray14, CheXpert, MIMIC-CXR, and PadChest
- **Training data:** 700,000+ chest X-rays across 4 major clinical datasets
- **Inference:** CPU-only, on-device — no cloud ML dependency
- **Diseases detected:** Pneumonia, Lung Opacity, Pleural Effusion, Consolidation, Atelectasis, Cardiomegaly, Edema

---

## ⚖️ Ethics & Safety

- The model **never claims to diagnose** — all outputs are framed as findings consistent with, not definitive diagnoses
- The chatbot is **scope-bounded** — it only discusses the patient's chest X-ray findings, not general medical advice
- **No patient data is stored** — uploads are processed and discarded
- Every response ends with a reminder to consult a licensed physician
- Invalid/non-medical images are rejected at the API level

---

## 👥 Team

Built in 72 hours at Hack to Future 3.0 by:

| Name | Role |
|---|---|
| Shashank | ML Model & Backend |
| Rajvardhan | Frontend & UI/UX |
| Prajwal | Integration, Prompting & Architecture |
| Bilal | Literature Survey & Architecture Decisions |
