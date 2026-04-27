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

EXPLANATION_WORD_LIMIT = 170
CHAT_WORD_LIMIT = 170
HIGH_CONFIDENCE_THRESHOLD = 0.65
MODERATE_CONFIDENCE_THRESHOLD = 0.40

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
			generation_config={
				"max_output_tokens": 260,
				"temperature": 0.45,
				"top_p": 0.9,
			},
		)
		return _extract_response_text(response)
	except Exception:
		return ""


def _normalize_predictions_payload(predictions):
	scores = {}
	limitations = {}
	model_info = {}
	interpretation = {}

	if not isinstance(predictions, dict):
		return scores, limitations, model_info, interpretation

	if isinstance(predictions.get("scores"), dict):
		for disease, value in predictions["scores"].items():
			if isinstance(value, bool):
				continue
			if isinstance(value, (int, float)):
				scores[disease] = float(value)

	if isinstance(predictions.get("limitations"), dict):
		limitations = predictions["limitations"]

	if isinstance(predictions.get("model_info"), dict):
		model_info = predictions["model_info"]

	if isinstance(predictions.get("interpretation"), dict):
		interpretation = predictions["interpretation"]

	# Backward-compatible path for older callers that pass plain disease-score maps.
	if not scores:
		for disease, value in predictions.items():
			if isinstance(value, bool):
				continue
			if isinstance(value, (int, float)):
				scores[disease] = float(value)
			else:
				limitations[disease] = value

	return scores, limitations, model_info, interpretation


def _confidence_band(score):
	if score >= HIGH_CONFIDENCE_THRESHOLD:
		return "strong"
	if score >= MODERATE_CONFIDENCE_THRESHOLD:
		return "moderate"
	return "low"


def _human_join(items):
	if not items:
		return ""
	if len(items) == 1:
		return items[0]
	if len(items) == 2:
		return f"{items[0]} and {items[1]}"
	return f"{', '.join(items[:-1])}, and {items[-1]}"


def _score_pct(score):
	return f"{score * 100:.1f}%"


def _derive_probability_groups(scores, interpretation):
	likely = []
	possible = []

	if isinstance(interpretation, dict):
		likely_raw = interpretation.get("likely_findings")
		possible_raw = interpretation.get("possible_findings")
		if isinstance(likely_raw, list):
			likely = [item for item in likely_raw if isinstance(item, str)]
		if isinstance(possible_raw, list):
			possible = [item for item in possible_raw if isinstance(item, str)]

	if likely or possible:
		return likely, possible

	ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
	for name, score in ranked:
		if score >= HIGH_CONFIDENCE_THRESHOLD:
			likely.append(name)
		elif score >= MODERATE_CONFIDENCE_THRESHOLD:
			possible.append(name)
	return likely, possible


def _build_profile_summary(scores):
	ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
	if not ranked:
		return "No clear signal profile available."

	top_name, top_score = ranked[0]
	second_score = ranked[1][1] if len(ranked) > 1 else 0.0
	gap = top_score - second_score

	if top_score >= HIGH_CONFIDENCE_THRESHOLD and gap >= 0.15:
		return f"Dominant pattern: {top_name} ({_score_pct(top_score)}), clearly above the next finding."
	if top_score >= HIGH_CONFIDENCE_THRESHOLD:
		return f"Mixed high-signal pattern with leading finding {top_name} ({_score_pct(top_score)})."
	if top_score >= MODERATE_CONFIDENCE_THRESHOLD:
		return f"Moderate signal pattern, led by {top_name} ({_score_pct(top_score)})."
	return "No strong disease-specific signal is present in this screening profile."


def _build_explanation_prompt(scores, limitations, model_info, interpretation):
	ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
	top_findings = ranked[:4]
	pneumonia_score = scores.get("Pneumonia")
	likely, possible = _derive_probability_groups(scores, interpretation)
	profile_summary = _build_profile_summary(scores)

	findings_lines = [
		f"- {name}: {score:.4f} ({_confidence_band(score)} signal)"
		for name, score in top_findings
	]
	if pneumonia_score is not None and "Pneumonia" not in {name for name, _ in top_findings}:
		findings_lines.append(
			f"- Pneumonia: {pneumonia_score:.4f} ({_confidence_band(pneumonia_score)} signal)"
		)

	limitations_block = "- None provided"
	if limitations:
		limitations_block = "\n".join([f"- {k}: {v}" for k, v in limitations.items()])

	model_block = "- Not provided"
	if model_info:
		model_block = "\n".join([f"- {k}: {v}" for k, v in model_info.items()])

	probability_block = "- likely_findings: None\n- possible_findings: None"
	if likely or possible:
		probability_block = (
			f"- likely_findings: {likely or ['None']}\n"
			f"- possible_findings: {possible or ['None']}"
		)

	return _build_guardrailed_prompt(
		"You are speaking directly to a patient. Write a natural, calm explanation in 2 short paragraphs "
		"plus one brief next-step sentence. Use plain language and avoid sounding like raw model output. "
		"Do not list every number. Mention only the most relevant findings and what they might mean. "
		"Use probability language such as 'most likely', 'possible', or 'less likely' based on confidence bands. "
		"If pneumonia is moderate or strong, acknowledge it clearly but avoid definitive diagnosis. "
		"If pneumonia is low, say that clearly too. Mention uncertainty and model limitations naturally. "
		"Keep the response under 170 words and end with: Please consult a licensed physician.\n\n"
		f"Signal profile summary:\n- {profile_summary}\n\n"
		f"Probability grouping:\n{probability_block}\n\n"
		f"Key screening findings:\n{'\n'.join(findings_lines)}\n\n"
		f"Limitations/context:\n{limitations_block}\n\n"
		f"Model metadata:\n{model_block}"
	)


def _build_local_explanation(scores, limitations, interpretation):
	ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
	top_findings = ranked[:4]
	top_name = top_findings[0][0] if top_findings else ""
	pneumonia_score = scores.get("Pneumonia", 0.0)
	likely, possible = _derive_probability_groups(scores, interpretation)
	profile_summary = _build_profile_summary(scores)

	intro = "Thanks for sharing your X-ray screening result."
	if pneumonia_score >= HIGH_CONFIDENCE_THRESHOLD and "Pneumonia" in likely:
		pneumonia_line = (
			"Based on these confidence scores, pneumonia is among the more probable findings. "
			"This can match patterns seen with lung infection or inflammation. "
			"This still needs medical confirmation with symptoms, examination, and possibly additional tests."
		)
	elif pneumonia_score >= MODERATE_CONFIDENCE_THRESHOLD:
		pneumonia_line = (
			"There is a possible pneumonia-related signal. It may fit patterns seen with infection, "
			"but the result is not a diagnosis by itself."
		)
	else:
		pneumonia_line = (
			"The pneumonia-related signal is low on this screening result, so this scan alone does not strongly point to pneumonia."
		)

	most_probable = [
		name for name in likely if name not in {"Pneumonia", top_name}
	]
	if not most_probable:
		most_probable = [
			name for name, score in top_findings
			if name not in {"Pneumonia", top_name} and score >= MODERATE_CONFIDENCE_THRESHOLD
		]

	possible_only = [
		name
		for name in possible
		if name not in {"Pneumonia", top_name} and name not in most_probable
	][:2]

	findings_line = ""
	if most_probable:
		joined = _human_join(most_probable[:2])
		findings_line = (
			f"The most probable additional findings are {joined}, based on stronger confidence signals."
		)
	elif possible_only:
		joined = _human_join(possible_only)
		findings_line = (
			f"Possible additional findings include {joined}, but these remain uncertain and need clinical correlation."
		)

	profile_line = profile_summary

	limitations_line = ""
	if isinstance(limitations, dict) and "Tuberculosis" in limitations:
		limitations_line = (
			"This model also cannot rule in or rule out tuberculosis from this scan alone, and a dedicated TB test is needed for that."
		)

	parts = [intro, profile_line, pneumonia_line]
	if findings_line:
		parts.append(findings_line)
	if limitations_line:
		parts.append(limitations_line)
	parts.append("Please consult a licensed physician.")
	return _trim_to_word_limit(" ".join(parts), EXPLANATION_WORD_LIMIT)


def _looks_like_old_template(text):
	if not isinstance(text, str):
		return True
	lower_text = text.lower()
	old_markers = [
		"the strongest screening signals are",
		"these are the image patterns the model noticed most strongly",
		"the tuberculosis note is a separate limitation",
	]
	if any(marker in lower_text for marker in old_markers):
		return True

	# Reject list-like rigid phrasing that tends to feel repetitive.
	if lower_text.count(":") >= 5:
		return True
	return False


def explain_diagnosis(predictions: dict) -> str:
	try:
		if not isinstance(predictions, dict) or not predictions:
			return SAFE_FALLBACK_MESSAGE

		scores, limitations, model_info, interpretation = _normalize_predictions_payload(predictions)
		if not scores:
			return SAFE_FALLBACK_MESSAGE

		text = ""
		if MODEL is not None:
			prompt = _build_explanation_prompt(scores, limitations, model_info, interpretation)
			text = _generate_text(prompt)
		if text:
			text = _ensure_physician_consult_closing(text, EXPLANATION_WORD_LIMIT)
			if _looks_like_old_template(text):
				text = ""
		if not text:
			text = _build_local_explanation(scores, limitations, interpretation)
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
			"Stay educational, simple, and non-alarming. Sound human and conversational, not robotic. "
			"If the patient asks basic medical questions, provide general educational guidance in plain language. "
			"Do not prescribe treatment or claim certainty from an X-ray score alone. "
			"Do not provide a definitive medical diagnosis. Use short, clear sentences. If uncertainty exists, "
			"recommend consulting a licensed physician. Keep the answer under 170 words and end with: "
			"Please consult a licensed physician.\n\n"
			f"Previous X-ray context:\n{clean_context or 'No prior context provided.'}\n\n"
			f"Patient question:\n{clean_message}"
		)

		text = _generate_text(prompt)
		if text:
			text = _ensure_physician_consult_closing(text, CHAT_WORD_LIMIT)
		return text if text else SAFE_CHAT_FALLBACK_MESSAGE
	except Exception as e:
		print(f"GEMINI ERROR: {e}")
		return SAFE_CHAT_FALLBACK_MESSAGE
