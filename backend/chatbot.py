import os
import re
import traceback
import time

from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import (
    HarmBlockThreshold,
    HarmCategory,
    StopCandidateException,
)

# -----------------------------------------------------------------------------
# ENV + MODEL INIT
# -----------------------------------------------------------------------------

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
print("\n--- CRITICAL BOOT CHECK ---")
print(f"API Key Found: {bool(API_KEY)}")

MODEL = None
USES_NATIVE_SYSTEM_INSTRUCTION = False

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        MODEL = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            safety_settings={
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            },
        )
        print("Model Status: ONLINE")
    except Exception as e:
        print(f"Model Status: FAILED -> {e}")
        traceback.print_exc()
else:
    print("Model Status: OFFLINE (Missing Key)")

print("---------------------------\n")

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------

SYSTEM_INSTRUCTION = (
    "You are an empathetic, educational AI assistant helping patients understand "
    "their chest X-ray screening results. You MUST NOT give definitive medical "
    "diagnoses. You MUST use simple, non-alarming language. Only remind the patient "
    "to consult a physician when it is genuinely useful — not on every single reply."
)

SAFE_FALLBACK_MESSAGE = (
    "I am unable to provide a detailed explanation right now. Please consult a "
    "licensed physician to review your chest X-ray findings."
)

SAFE_CHAT_FALLBACK_MESSAGE = (
    "I'm sorry, I couldn't process that request. Please consult a physician."
)

EXPLANATION_WORD_LIMIT = 170
CHAT_WORD_LIMIT = 250

# How many assistant turns before we remind again (avoids repetitive disclaimer)
PHYSICIAN_REMINDER_EVERY_N = 3

_GREETING_PATTERNS = re.compile(
    r"^\s*(hi+|hello+|hey+|howdy|sup|what'?s up|good\s?(morning|afternoon|evening|night)|"
    r"greetings|hiya|yo|namaste|helo|hii+|heya)\s*[!.,?]*\s*$",
    re.IGNORECASE,
)

_MEDICAL_KEYWORDS = re.compile(
    r"x.?ray|report|result|finding|scan|pneumonia|effusion|opacity|consolidation|"
    r"atelectasis|cardiomegaly|edema|score|diagnos|lung|chest|breath|symptom|"
    r"treatment|medicine|doctor|physician|hospital|serious|disease|condition|"
    r"infection|fluid|heart|tb|tuberculosis",
    re.IGNORECASE,
)

# -----------------------------------------------------------------------------
# INTENT DETECTION
# -----------------------------------------------------------------------------

def _detect_intent(message: str) -> str:
    """Returns 'greeting', 'medical', or 'general'."""
    if _GREETING_PATTERNS.match(message.strip()):
        return "greeting"
    if _MEDICAL_KEYWORDS.search(message):
        return "medical"
    return "general"

# -----------------------------------------------------------------------------
# HISTORY FORMATTING
# -----------------------------------------------------------------------------

def _format_history(history: list) -> str:
    """
    Converts the history array from the frontend into a readable
    conversation block to include in the prompt.
    """
    if not history:
        return ""
    lines = []
    for turn in history[:-1]:  # exclude the current message (already in prompt)
        role = "Patient" if turn.get("role") == "user" else "Assistant"
        content = turn.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _physician_reminder_needed(history: list, intent: str) -> bool:
    """
    Returns True only if:
    - This is a medical intent AND
    - The last N assistant messages didn't already include a physician reminder
    """
    if intent != "medical":
        return False

    assistant_turns = [
        m for m in history if m.get("role") == "assistant"
    ]
    # Check the last N assistant replies for an existing reminder
    recent = assistant_turns[-PHYSICIAN_REMINDER_EVERY_N:]
    for turn in recent:
        content = turn.get("content", "").lower()
        if "consult" in content and "physician" in content:
            return False  # already reminded recently
    return True

# -----------------------------------------------------------------------------
# PROMPT BUILDERS
# -----------------------------------------------------------------------------

def _build_guardrailed_prompt(user_prompt: str) -> str:
    if USES_NATIVE_SYSTEM_INSTRUCTION:
        return user_prompt
    return (
        f"System instruction:\n{SYSTEM_INSTRUCTION}\n\n"
        f"User request:\n{user_prompt}"
    )


def _build_greeting_prompt(message: str) -> str:
    return _build_guardrailed_prompt(
        f"The patient just said: \"{message}\"\n\n"
        "Reply warmly in 1-2 short sentences. Let them know you can help them "
        "understand their chest X-ray results. Do not list any findings or "
        "medical information. Keep it natural and brief."
    )


def _build_medical_prompt(message: str, context: str, history_text: str, needs_reminder: bool) -> str:
    context_block = (
        f"The patient's chest X-ray results:\n{context}"
        if context else
        "No specific X-ray results are available."
    )
    history_block = (
        f"\nConversation so far:\n{history_text}\n" if history_text else ""
    )
    reminder_instruction = (
        "End your reply with: Please consult a licensed physician."
        if needs_reminder else
        "Do NOT end with a physician reminder — it was already given recently."
    )
    return _build_guardrailed_prompt(
        f"{context_block}\n"
        f"{history_block}\n"
        f"Patient question: {message}\n\n"
        "Answer clearly in plain language. No jargon. Stay educational and "
        "non-alarming. Do not diagnose. Keep it under 120 words. "
        f"{reminder_instruction}"
    )


def _build_general_prompt(message: str, context: str, history_text: str) -> str:
    context_hint = (
        "(The patient has had a chest X-ray. Only reference it if they ask.)"
        if context else ""
    )
    history_block = (
        f"\nConversation so far:\n{history_text}\n" if history_text else ""
    )
    return _build_guardrailed_prompt(
        f"{context_hint}"
        f"{history_block}\n"
        f"Patient message: {message}\n\n"
        "Respond conversationally and empathetically. Be supportive and brief. "
        "No diagnoses or treatment advice. Under 80 words. "
        "Only mention the X-ray if the patient asks about it directly."
    )

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

def _trim_to_word_limit(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def _ensure_physician_consult_closing(text: str, max_words: int) -> str:
    required_sentence = "Please consult a licensed physician."
    if "consult" in text.lower() and "physician" in text.lower():
        return _trim_to_word_limit(text, max_words)
    reserved = len(required_sentence.split())
    base_words = max(max_words - reserved, 1)
    base_text = _trim_to_word_limit(text, base_words).rstrip(" .")
    return f"{base_text}. {required_sentence}"


def _build_local_explanation(predictions: dict) -> str:
    if not isinstance(predictions, dict) or not predictions:
        return SAFE_FALLBACK_MESSAGE
    scores = predictions.get("scores")
    if not isinstance(scores, dict) or not scores:
        return SAFE_FALLBACK_MESSAGE
    ranked = sorted(
        ((n, float(s)) for n, s in scores.items() if isinstance(s, (int, float))),
        key=lambda x: x[1],
        reverse=True,
    )
    if not ranked:
        return SAFE_FALLBACK_MESSAGE
    top_name, top_score = ranked[0]
    return _trim_to_word_limit(
        f"The model is currently unavailable, but the strongest signal appears to be "
        f"{top_name} at {top_score:.2f}. This is a screening result, not a diagnosis. "
        f"Please consult a licensed physician.",
        EXPLANATION_WORD_LIMIT,
    )


def _build_local_chat_response(message: str, _context: str) -> str:
    clean = message.strip() if isinstance(message, str) else ""
    if clean:
        return (
            f"I'm sorry, I couldn't process that right now. "
            f"You asked: {clean}. Please consult a physician."
        )
    return SAFE_CHAT_FALLBACK_MESSAGE

# -----------------------------------------------------------------------------
# GEMINI CALL
# -----------------------------------------------------------------------------

def _generate_text(prompt: str) -> str:
    """Returns model text or '' on any failure. Never raises."""
    if not prompt or not prompt.strip():
        print("[_generate_text] FAIL: prompt is empty")
        return ""
    if MODEL is None:
        print("[_generate_text] FAIL: MODEL is None")
        return ""

    MAX_RETRIES = 2
    response = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            print(f"[_generate_text] Attempt {attempt + 1}: {len(prompt)} chars...")
            response = MODEL.generate_content(prompt)
            break
        except StopCandidateException as e:
            print(f"[_generate_text] FAIL: StopCandidateException — {e}")
            return ""
        except Exception as e:
            err_str = str(e)
            if "Quota exceeded" in err_str or "429" in err_str or "retry_delay" in err_str:
                match = re.search(r"retry in (\d+)", err_str)
                wait = int(match.group(1)) + 2 if match else 60
                if attempt < MAX_RETRIES:
                    print(f"[_generate_text] QUOTA: waiting {wait}s...")
                    time.sleep(wait)
                    continue
                print("[_generate_text] QUOTA: retries exhausted")
                return ""
            print(f"[_generate_text] FAIL: {type(e).__name__}: {e}")
            traceback.print_exc()
            return ""

    if response is None:
        return ""

    try:
        candidates = response.candidates
    except Exception as e:
        print(f"[_generate_text] FAIL: reading candidates — {e}")
        return ""

    if not candidates:
        feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(feedback, "block_reason", "UNKNOWN")
        print(f"[_generate_text] FAIL: no candidates, block_reason={block_reason}")
        return ""

    candidate = candidates[0]
    finish_reason = str(getattr(candidate, "finish_reason", "UNKNOWN"))
    print(f"[_generate_text] finish_reason={finish_reason}")

    if "SAFETY" in finish_reason:
        print("[_generate_text] FAIL: blocked by safety filters")
        return ""
    if "RECITATION" in finish_reason:
        print("[_generate_text] FAIL: blocked due to recitation")
        return ""

    try:
        text = response.text
        if isinstance(text, str) and text.strip():
            print(f"[_generate_text] OK: {len(text)} chars")
            return text.strip()
    except ValueError as e:
        print(f"[_generate_text] FAIL: response.text ValueError — {e}")
        try:
            raw = candidate.content.parts[0].text
            if isinstance(raw, str) and raw.strip():
                print(f"[_generate_text] RECOVERED via parts[0].text")
                return raw.strip()
        except Exception as inner:
            print(f"[_generate_text] FAIL: parts extraction — {inner}")

    print("[_generate_text] FAIL: empty after all extraction attempts")
    return ""

# -----------------------------------------------------------------------------
# PUBLIC FUNCTIONS
# -----------------------------------------------------------------------------

def explain_diagnosis(predictions: dict) -> str:
    """Called after X-ray analysis — generates a plain-language report summary."""
    if not isinstance(predictions, dict) or not predictions:
        return SAFE_FALLBACK_MESSAGE
    try:
        prompt = _build_guardrailed_prompt(
            "Write a calm, plain-language chest X-ray explanation for a patient. "
            "Do not give a definitive diagnosis. Keep it short and end with: "
            "Please consult a licensed physician.\n\n"
            f"Predictions:\n{predictions}"
        )
        text = _generate_text(prompt)
        if text:
            return _ensure_physician_consult_closing(text, EXPLANATION_WORD_LIMIT)
        return _build_local_explanation(predictions)
    except Exception as e:
        print(f"[explain_diagnosis] FAIL: {type(e).__name__}: {e}")
        traceback.print_exc()
        return _build_local_explanation(predictions)


def chat(message: str, context: str, history: list = None) -> str:
    """
    Main chat handler.
    - Detects intent to pick the right prompt style
    - Uses conversation history for memory
    - Only adds physician disclaimer when genuinely needed
    """
    clean_message = message.strip() if isinstance(message, str) else ""
    clean_context = context.strip() if isinstance(context, str) else ""
    safe_history = history if isinstance(history, list) else []

    print(f"\n{'=' * 60}")
    print(f"[chat] message={repr(clean_message[:80])}")
    print(f"[chat] history_turns={len(safe_history)}")

    if not clean_message:
        print("[chat] FAIL: empty message")
        return SAFE_CHAT_FALLBACK_MESSAGE

    if MODEL is None:
        print("[chat] WARN: MODEL is None -> local fallback")
        return _build_local_chat_response(clean_message, clean_context)

    intent = _detect_intent(clean_message)
    print(f"[chat] intent={intent}")

    history_text = _format_history(safe_history)
    needs_reminder = _physician_reminder_needed(safe_history, intent)

    try:
        if intent == "greeting":
            prompt = _build_greeting_prompt(clean_message)
        elif intent == "medical":
            prompt = _build_medical_prompt(clean_message, clean_context, history_text, needs_reminder)
        else:
            prompt = _build_general_prompt(clean_message, clean_context, history_text)
    except Exception as e:
        print(f"[chat] FAIL: prompt build — {type(e).__name__}: {e}")
        return _build_local_chat_response(clean_message, clean_context)

    print(f"[chat] prompt built ({len(prompt)} chars)")

    text = _generate_text(prompt)

    if not text:
        print("[chat] WARN: empty response -> local fallback")
        return _build_local_chat_response(clean_message, clean_context)

    print(f"[chat] OK: {len(text)} chars (intent={intent}, reminder={needs_reminder})")
    print("=" * 60)
    return text