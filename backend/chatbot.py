import os

import google.generativeai as genai
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
	genai.configure(api_key=API_KEY)

SYSTEM_INSTRUCTION = (
	"You are an empathetic, educational AI assistant helping patients understand "
	"their chest X-ray screening results. You MUST NOT give definitive medical "
	"diagnoses. You MUST use simple, non-alarming language. You MUST conclude "
	"every initial explanation by advising the patient to consult a licensed "
	"physician."
)

SAFE_FALLBACK_MESSAGE = (
	"I am unable to provide a detailed explanation right now. Please consult a "
	"licensed physician to review your chest X-ray findings."
)

SAFE_CHAT_FALLBACK_MESSAGE = (
	"I am having trouble answering right now. Please consult a licensed physician "
	"for personalized medical guidance."
)

MODEL = None
USES_NATIVE_SYSTEM_INSTRUCTION = False
if API_KEY:
	try:
		MODEL = genai.GenerativeModel(
			"gemini-2.5-flash",
			system_instruction=SYSTEM_INSTRUCTION,
		)
		USES_NATIVE_SYSTEM_INSTRUCTION = True
	except TypeError:
		# Older SDK versions may not support system_instruction in constructor.
		MODEL = genai.GenerativeModel("gemini-2.5-flash")
		USES_NATIVE_SYSTEM_INSTRUCTION = False
	except Exception:
		MODEL = None


def _extract_response_text(response):
	text = getattr(response, "text", None)
	if isinstance(text, str) and text.strip():
		return text.strip()

	candidates = getattr(response, "candidates", None)
	if candidates:
		for candidate in candidates:
			content = getattr(candidate, "content", None)
			if content is not None:
				candidate_text = getattr(content, "text", None)
				if isinstance(candidate_text, str) and candidate_text.strip():
					return candidate_text.strip()

				parts = getattr(content, "parts", None) or []
				for part in parts:
					part_text = getattr(part, "text", None)
					if isinstance(part_text, str) and part_text.strip():
						return part_text.strip()

	parts = getattr(response, "parts", None)
	if parts:
		for part in parts:
			part_text = getattr(part, "text", None)
			if isinstance(part_text, str) and part_text.strip():
				return part_text.strip()

	if isinstance(response, dict):
		for key in ("text", "content"):
			value = response.get(key)
			if isinstance(value, str) and value.strip():
				return value.strip()
	return ""


def _trim_to_word_limit(text, max_words):
	words = text.split()
	if len(words) <= max_words:
		return text.strip()
	return " ".join(words[:max_words]).strip()


def _ensure_physician_consult_closing(text, max_words):
	required_sentence = "Please consult a licensed physician."
	lower_text = text.lower()
	if "consult" in lower_text and "physician" in lower_text:
		return _trim_to_word_limit(text, max_words)

	reserved = len(required_sentence.split())
	base_words = max(max_words - reserved, 1)
	base_text = _trim_to_word_limit(text, base_words).rstrip(" .")
	return f"{base_text}. {required_sentence}"


def _build_guardrailed_prompt(user_prompt):
	if USES_NATIVE_SYSTEM_INSTRUCTION:
		return user_prompt
	return (
		f"System instruction:\n{SYSTEM_INSTRUCTION}\n\n"
		f"User request:\n{user_prompt}"
	)


def _generate_text(prompt):
	if MODEL is None:
		return ""
	try:
		response = MODEL.generate_content(
			prompt,
			generation_config={"max_output_tokens": 220},
		)
		return _extract_response_text(response)
	except Exception:
		return ""


def _build_local_explanation(top_findings, limitations_block):
	term_meanings = {
		"Pneumonia": (
			"Pneumonia means the image may show a pattern that can be seen with infection or inflammation in the lungs. "
			"It is a screening signal, not a final diagnosis."
		),
		"Lung Opacity": (
			"Lung opacity means part of the image looks hazier or denser than expected. "
			"That can happen for several reasons, including infection, fluid, or overlapping structures."
		),
		"Effusion": (
			"Effusion refers to possible fluid around the lungs. "
			"It is a descriptive imaging finding that needs clinical review."
		),
		"Consolidation": (
			"Consolidation means an area of the lung looks more solid than usual. "
			"This can sometimes be seen with infection or inflammation, but it is not a diagnosis by itself."
		),
		"Atelectasis": (
			"Atelectasis means a portion of the lung may be partially collapsed or not fully expanded. "
			"It can occur for different reasons and must be interpreted in context."
		),
		"Cardiomegaly": (
			"Cardiomegaly means the heart appears larger than expected on the image. "
			"This is a screening observation and does not confirm heart disease on its own."
		),
		"Edema": (
			"Edema refers to possible fluid-related patterns in the lungs. "
			"Doctors use this together with symptoms and other findings."
		),
	}

	if top_findings:
		lead_names = ", ".join([f"{name} ({score:.4f})" for name, score in top_findings])
		lead = (
			f"The strongest screening signals are {lead_names}. These are the image patterns the model noticed most strongly, "
			"and they should be treated as clues for review rather than a diagnosis."
		)
	else:
		lead = (
			"The model did not identify a single dominant screening signal. That can still be useful, because it suggests the image does not strongly match one specific pattern."
		)

	details = []
	for name, score in top_findings:
		meaning = term_meanings.get(
			name,
			"This is a screening label describing an image pattern and should be reviewed by a clinician in context."
		)
		details.append(f"{name} ({score:.4f}): {meaning}")

	limitations_text = ""
	if limitations_block and "Tuberculosis" in limitations_block:
		limitations_text = (
			"The Tuberculosis note is a separate limitation from the main screening scores, which means a specific TB assay is needed to evaluate that question."
		)

	parts = [lead] + details
	if limitations_text:
		parts.append(limitations_text)
	parts.append("Please consult a licensed physician.")
	return " ".join(parts)


def explain_diagnosis(predictions: dict) -> str:
	try:
		if MODEL is None:
			return SAFE_FALLBACK_MESSAGE

		if not isinstance(predictions, dict) or not predictions:
			return SAFE_FALLBACK_MESSAGE

		numeric_findings = []
		non_numeric_notes = []

		for disease, value in predictions.items():
			if isinstance(value, bool):
				non_numeric_notes.append(f"- {disease}: {value}")
			elif isinstance(value, (int, float)):
				numeric_findings.append((disease, float(value)))
			else:
				non_numeric_notes.append(f"- {disease}: {value}")

		if not numeric_findings:
			return SAFE_FALLBACK_MESSAGE

		top_findings = sorted(numeric_findings, key=lambda item: item[1], reverse=True)[:3]

		findings_block = "\n".join(
			[f"- {name}: {score:.4f}" for name, score in top_findings]
		)
		limitations_block = (
			"\n".join(non_numeric_notes)
			if non_numeric_notes
			else "- None provided"
		)

		prompt = _build_guardrailed_prompt(
			"Explain the following chest X-ray screening findings in simple language "
			"for a patient in under 150 words. Be supportive and non-alarming. Do not "
			"provide a definitive medical diagnosis. End by advising the patient to consult a "
			"licensed physician.\n\n"
			f"Top findings (numeric scores):\n{findings_block}\n\n"
			f"Additional limitations/context:\n{limitations_block}"
		)

		text = _generate_text(prompt)
		if text:
			text = _ensure_physician_consult_closing(text, 150)
		else:
			text = _build_local_explanation(top_findings, limitations_block)
		return text if text else SAFE_FALLBACK_MESSAGE
	except Exception:
		return SAFE_FALLBACK_MESSAGE


def chat(message: str, context: str) -> str:
	try:
		if MODEL is None:
			return SAFE_CHAT_FALLBACK_MESSAGE

		clean_message = message.strip() if isinstance(message, str) else ""
		clean_context = context.strip() if isinstance(context, str) else ""

		if not clean_message:
			return SAFE_CHAT_FALLBACK_MESSAGE

		prompt = _build_guardrailed_prompt(
			"Answer the patient's question using the prior chest X-ray screening context below. "
			"Stay educational, simple, and non-alarming. Do not provide a definitive "
			"medical diagnosis. If uncertainty exists, clearly recommend consulting a "
			"licensed physician.\n\n"
			f"Previous X-ray context:\n{clean_context or 'No prior context provided.'}\n\n"
			f"Patient question:\n{clean_message}"
		)

		text = _generate_text(prompt)
		if text:
			text = _ensure_physician_consult_closing(text, 150)
		return text if text else SAFE_FALLBACK_MESSAGE
	except Exception as e:
		print(f"GEMINI ERROR: {e}")
		return SAFE_FALLBACK_MESSAGE
