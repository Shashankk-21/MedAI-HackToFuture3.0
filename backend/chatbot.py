import json
import ast
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

# System prompt for the general chat assistant (patient-facing)
SYSTEM_INSTRUCTION = (
    "You are a compassionate, knowledgeable medical AI assistant helping a patient understand their chest X-ray results. You have access to their scan findings as context.\n"
    "STRICT RULES:\n\n"
    "You are NOT a doctor and cannot diagnose. Always frame answers as 'this may suggest', 'findings like this are often associated with', never 'you have X'.\n"
    "Bold key medical terms using double asterisks when first introduced.\n"
    "If asked what a finding means — explain it in plain English first, then one sentence of clinical context.\n"
    "If asked 'should I be worried' — acknowledge the concern warmly, reference their specific top finding, and recommend seeing a physician without causing panic.\n"
    "If asked anything outside chest radiology or the patient's findings (politics, coding, general knowledge) — politely say: 'I'm specialized in helping you understand your chest X-ray results. For other questions, please consult the appropriate professional.'\n"
    "Keep every response under 100 words unless the patient explicitly asks for more detail.\n"
    "Never repeat the full findings list in every message — vary your responses naturally like a real conversation.\n"
    "Always end responses that touch on severity or treatment with: 'Please discuss this with your physician.'\n"
    "Maintain a warm, calm tone throughout. The patient may be anxious."
)

# System prompt used exclusively for explain_diagnosis (clinician-style summary)
DIAGNOSIS_SYSTEM_PROMPT = (
    "You are a clinical AI assistant embedded in a chest X-ray analysis platform. Your job is to translate structured model findings into a clear, empathetic, medically accurate summary for a patient.\n"
    "STRICT RULES:\n"
    "- Your FIRST sentence must name the most prominent finding directly. Never open vaguely.\n"
    "- Bold ALL disease names using double asterisks.\n"
    "- Use bullet points for secondary findings.\n"
    "- If the clinical context contains 'Pattern note: Elevated Lung Opacity' — you MUST mention pneumonia or infectious process explicitly in your response.\n"
    "- If the clinical context contains 'bacterial pneumonia with pleural involvement' — state this pattern clearly.\n"
    "- If all findings are below 0.25 — respond only with: 'This scan appears within normal limits. No significant abnormalities were detected. Please consult a licensed physician for confirmation.'\n"
    "- Never use vague phrases like 'hazy areas', 'a bit cloudy', or 'some differences'. Use the actual clinical term.\n"
    "- Keep response between 4–7 sentences total.\n"
    "- Always end with exactly: 'Please consult a licensed physician before drawing any conclusions.'\n"
    "- Never claim to provide a diagnosis. Frame everything as 'the scan suggests' or 'findings are consistent with'."
)

DIAGNOSIS_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

_medical_harm_category = getattr(HarmCategory, "HARM_CATEGORY_MEDICAL", None)
if _medical_harm_category is not None:
    DIAGNOSIS_SAFETY_SETTINGS[_medical_harm_category] = HarmBlockThreshold.BLOCK_ONLY_HIGH

SAFE_FALLBACK_MESSAGE = (
    "I am unable to provide a detailed explanation right now. Please consult a "
    "licensed physician to review your chest X-ray findings."
)

SAFE_CHAT_FALLBACK_MESSAGE = (
    "I'm sorry, I couldn't process that request. Please consult a physician."
)

EXPLANATION_WORD_LIMIT = 170
CHAT_WORD_LIMIT = 250

# Score thresholds (must match xray_model.py)
_NOISE_THRESHOLD = 0.25
_POSSIBLE_THRESHOLD = 0.50
_LIKELY_THRESHOLD = 0.70

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
# CLINICAL CONTEXT BUILDER  (used by explain_diagnosis only)
# -----------------------------------------------------------------------------

def _build_clinical_context(scores: dict) -> str:
    """
    Classifies each disease score into confidence tiers, filters out noise
    (< 0.25), and returns a structured clinical context string with pattern
    detection notes appended where applicable.

    Tiers:
        High Confidence  : score > 0.70
        Likely           : 0.50 < score <= 0.70
        Possible         : 0.25 <= score <= 0.50
        (below 0.25 → silently excluded)
    """
    high_confidence: list[str] = []
    likely: list[str] = []
    possible: list[str] = []
    not_significant: list[str] = []

    for disease, score in scores.items():
        s = float(score)
        if s > _LIKELY_THRESHOLD:
            high_confidence.append(disease)
        elif s > _POSSIBLE_THRESHOLD:
            likely.append(disease)
        elif s >= _NOISE_THRESHOLD:
            possible.append(disease)
        else:
            not_significant.append(disease)

    def _fmt(lst: list[str]) -> str:
        return ", ".join(lst) if lst else "None"

    primary_findings = high_confidence + likely
    secondary_findings = possible

    context = (
        f"Primary findings: {_fmt(primary_findings)}. "
        f"Secondary findings: {_fmt(secondary_findings)}. "
        f"Not significant: {_fmt(not_significant)}."
    )

    # --- Pattern detection ---
    lung_opacity_score = float(scores.get("Lung Opacity", 0.0))
    effusion_score = float(scores.get("Effusion", 0.0))

    if lung_opacity_score > _LIKELY_THRESHOLD:
        context += (
            " Pattern note: Elevated Lung Opacity is the primary radiological "
            "indicator of infectious/inflammatory lung disease including pneumonia."
        )
        if effusion_score > 0.30:
            context += (
                " This combination is commonly associated with bacterial pneumonia "
                "with pleural involvement."
            )

    return context


def _confidence_label(score: float) -> str:
    """Returns a human-readable confidence label for a given score."""
    if score > _LIKELY_THRESHOLD:
        return "High Confidence Finding"
    if score > _POSSIBLE_THRESHOLD:
        return "Likely"
    return "Possible"


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
    recent = assistant_turns[-PHYSICIAN_REMINDER_EVERY_N:]
    for turn in recent:
        content = turn.get("content", "").lower()
        if "consult" in content and "physician" in content:
            return False
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


def _build_diagnosis_prompt(clinical_context: str, predictions: dict) -> str:
    """
    Builds the prompt for explain_diagnosis.
    The DIAGNOSIS_SYSTEM_PROMPT is embedded directly in the prompt so the
    model receives the exact instruction text requested by the UI contract.
    """
    overall = predictions.get("overall_assessment", "")
    overall_line = f"Overall assessment: {overall}\n\n" if overall else ""

    user_message = (
        f"{overall_line}"
        f"Clinical context derived from model scores:\n{clinical_context}\n\n"
        "Using the clinical context above, write a structured chest X-ray summary "
        "for a patient."
    )

    return (
        f"{DIAGNOSIS_SYSTEM_PROMPT}\n\n"
        f"{user_message}"
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
        f"Patient scan context — {context}\n\nPatient asks: {message}"
        if context else
        f"Patient asks: {message}"
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
        "\n"
        "Answer clearly in plain language. No jargon. Stay educational and "
        "non-alarming. Do not diagnose. Keep it under 120 words. "
        f"{reminder_instruction}"
    )


def _build_general_prompt(message: str, context: str, history_text: str) -> str:
    context_hint = (
        f"Patient scan context — {context}\n\n"
        "(The patient has had a chest X-ray. Only reference it if they ask.)"
        if context else ""
    )
    history_block = (
        f"\nConversation so far:\n{history_text}\n" if history_text else ""
    )
    return _build_guardrailed_prompt(
        f"{context_hint}"
        f"{history_block}\n"
        f"Patient asks: {message}\n\n"
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
    """
    Dynamically generates a formatted markdown fallback summary from the
    Python-computed scores. Used when the Gemini API is unavailable (rate
    limits, timeouts, network errors). The app never looks broken — it
    degrades gracefully to this rule-based summary.

    Format:
        AI Explanation Unavailable (API limit reached)

        Findings Summary:
        - [finding name]: [confidence label]

        Overall: [overall_assessment]

        Please consult a licensed physician.
    """
    if not isinstance(predictions, dict) or not predictions:
        return SAFE_FALLBACK_MESSAGE

    scores = predictions.get("scores")
    if not isinstance(scores, dict) or not scores:
        return SAFE_FALLBACK_MESSAGE

    overall: str = predictions.get("overall_assessment", "No assessment available")

    ranked = sorted(
        ((name, float(score)) for name, score in scores.items() if isinstance(score, (int, float))),
        key=lambda x: x[1],
        reverse=True,
    )

    bullet_lines = [
        f"- **{name}**: {_confidence_label(score)}"
        for name, score in ranked
        if score >= _NOISE_THRESHOLD
    ]

    findings_block = (
        "\n".join(bullet_lines)
        if bullet_lines
        else "- No findings above detection threshold"
    )

    return (
        "AI Explanation Unavailable (API limit reached)\n\n"
        f"Findings Summary:\n{findings_block}\n\n"
        f"Overall: {overall}\n\n"
        "Please consult a licensed physician."
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

def _generate_text(prompt: str, safety_settings: dict | None = None) -> str:
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
            generate_kwargs = {}
            if safety_settings:
                generate_kwargs["safety_settings"] = safety_settings
            response = MODEL.generate_content(prompt, **generate_kwargs)
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
    """
    Called after X-ray analysis.

    Pipeline:
      1. Extract and validate the scores dict from predictions.
      2. Build a structured clinical_context string (confidence tiers + pattern notes).
      3. Build a Gemini prompt that places DIAGNOSIS_SYSTEM_PROMPT as the system
         instruction and clinical_context inside the user message.
      4. Call Gemini and enforce the physician-consult closing.
      5. Fall back to a formatted markdown rule-based summary if Gemini is
         unavailable (API limit, timeout, network error) so the app never
         looks broken to the user.
    """
    if not isinstance(predictions, dict) or not predictions:
        return SAFE_FALLBACK_MESSAGE

    scores = predictions.get("scores")
    if not isinstance(scores, dict) or not scores:
        return SAFE_FALLBACK_MESSAGE

    try:
        # Step 1 — Build the structured clinical context in Python
        clinical_context = _build_clinical_context(scores)
        print(f"[explain_diagnosis] clinical_context={repr(clinical_context)}")

        # Step 2 — Build the diagnosis-specific prompt
        prompt = _build_diagnosis_prompt(clinical_context, predictions)

        # Step 3 — Call Gemini
        text = _generate_text(prompt, safety_settings=DIAGNOSIS_SAFETY_SETTINGS)

        if text:
            return _ensure_physician_consult_closing(text, EXPLANATION_WORD_LIMIT)

        # Step 4 — Formatted markdown fallback if Gemini unavailable
        print("[explain_diagnosis] Gemini unavailable — using rule-based markdown fallback")
        return _build_local_explanation(predictions)

    except Exception as e:
        print(f"[explain_diagnosis] FAIL: {type(e).__name__}: {e}")
        traceback.print_exc()
        return _build_local_explanation(predictions)


def generate_chat_init(predictions: dict, overall_assessment: str) -> dict:
    """
    Generates an opening chat greeting and three patient-facing quick-reply
    pill buttons tailored to the specific X-ray findings detected.

    Makes one Gemini call asking for valid JSON with:
      - greeting: one sentence acknowledging the top finding by name, under 40 words
      - quick_replies: exactly 3 short follow-up questions (each under 8 words)

    Falls back to sensible static defaults if the API call fails or the
    response cannot be parsed as valid JSON.

    Returns:
        {
            "greeting":      "<one-sentence greeting>",
            "quick_replies": ["<q1>", "<q2>", "<q3>"]
        }
    """
    if not isinstance(predictions, dict) or not predictions:
        return _fallback_chat_init(predictions, overall_assessment)

    scores = predictions.get("scores", {})
    clinical_context = _build_clinical_context(scores) if scores else f"Overall assessment: {overall_assessment}"

    prompt = (
        f"Given these chest X-ray findings: {clinical_context}\n"
        "Return ONLY a raw JSON object with no markdown, no backticks, no explanation. Exactly this structure:\n"
        "{\n"
        "'greeting': 'one sentence under 35 words acknowledging the top finding by name and warmly inviting questions',\n"
        "'quick_replies': ['question 1 under 8 words', 'question 2 under 8 words', 'question 3 under 8 words']\n"
        "}\n\n"
        "The quick replies must be specific to THIS patient's findings — not generic. If Lung Opacity is the top finding, one question should reference it by name."
    )

    print(f"[generate_chat_init] Building chat init for overall_assessment={repr(overall_assessment[:60])}")

    text = _generate_text(prompt)

    if text:
        try:
            raw = _extract_json_object(text)
            data = _parse_jsonish_object(raw)
            greeting: str = data.get("greeting", "").strip()
            quick_replies: list = data.get("quick_replies", [])

            # Validate shape; fall through to defaults if malformed
            if not greeting or not isinstance(quick_replies, list) or len(quick_replies) != 3:
                raise ValueError(f"Unexpected JSON shape: greeting={bool(greeting)}, quick_replies count={len(quick_replies)}")

            quick_replies = [str(q).strip() for q in quick_replies[:3]]
            print(f"[generate_chat_init] OK: greeting={repr(greeting[:60])}")
            return {"greeting": greeting, "quick_replies": quick_replies}

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[generate_chat_init] JSON parse FAIL: {e} — using fallback")

    print("[generate_chat_init] Gemini unavailable or parse failed — using static fallback")
    return _fallback_chat_init(predictions, overall_assessment)


def _extract_json_object(text: str) -> str:
    """
    Extract the first JSON-like object from model output.

    Handles common LLM formatting issues such as markdown fences and extra
    prose before or after the object.
    """
    raw = text.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1].strip()

    return raw


def _parse_jsonish_object(raw: str) -> dict:
    """
    Parse a model response that is intended to be JSON but may contain
    single quotes, trailing commas, or code-fence artifacts.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(raw)

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected object at top level, got {type(parsed).__name__}")

    return parsed


def _fallback_chat_init(predictions: dict, overall_assessment: str) -> dict:
    """
    Rule-based fallback for generate_chat_init when Gemini is unavailable
    or returns unparseable output. Derives the top-finding name directly
    from the scores dict so the greeting is still contextually relevant.
    """
    scores: dict = predictions.get("scores", {}) if isinstance(predictions, dict) else {}
    top_name = (
        max(scores, key=lambda k: float(scores[k])) if scores else "the detected findings"
    )
    return {
        "greeting": (
            f"I can see findings related to {top_name} in your X-ray. "
            "Feel free to ask me anything about your results."
        ),
        "quick_replies": [
            "What does this finding mean?",
            "How serious is this?",
            "What should I do next?",
        ],
    }


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