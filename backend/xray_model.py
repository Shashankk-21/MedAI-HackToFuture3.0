import numpy as np
import skimage.io
import torch
import torchxrayvision as xrv
import torchvision.transforms as transforms


PRIMARY_MODEL = xrv.models.DenseNet(weights="densenet121-res224-all")
PRIMARY_MODEL.eval()

NIH_MODEL = None
CHEX_MODEL = None

TB_LIMITATION_MESSAGE = (
	"Not detected by primary model scan (Requires specific TB assay)"
)

REQUESTED_DISEASES = [
	"Pneumonia",
	"Lung Opacity",
	"Effusion",
	"Consolidation",
	"Atelectasis",
	"Cardiomegaly",
	"Edema",
]

# --- Confidence thresholds ---
NOISE_THRESHOLD = 0.25
MINIMAL_SIGNAL_THRESHOLD = 0.45
POSSIBLE_THRESHOLD = 0.65
LIKELY_THRESHOLD = 0.80

XRAY_PREPROCESS = transforms.Compose(
	[xrv.datasets.XRayCenterCrop(), xrv.datasets.XRayResizer(224)]
)


def _get_optional_ensemble_models():
	global NIH_MODEL
	global CHEX_MODEL

	if NIH_MODEL is None:
		NIH_MODEL = xrv.models.DenseNet(weights="densenet121-res224-nih")
		NIH_MODEL.eval()

	if CHEX_MODEL is None:
		CHEX_MODEL = xrv.models.DenseNet(weights="densenet121-res224-chex")
		CHEX_MODEL.eval()

	return [NIH_MODEL, CHEX_MODEL]


def _preprocess_image(image_path):
	img = skimage.io.imread(image_path)
	img = xrv.datasets.normalize(img, 255)

	# Keep the official xrv grayscale conversion pathway.
	if img.ndim == 3:
		img = img.mean(2)[None, :, :]
	elif img.ndim == 2:
		img = img[None, :, :]
	else:
		raise ValueError("Unsupported image shape for X-ray inference")

	img = XRAY_PREPROCESS(img)

	img = np.asarray(img, dtype=np.float32)
	tensor = torch.from_numpy(img).to(dtype=torch.float32).unsqueeze(0)
	return tensor


def _run_model(model, tensor):
	with torch.no_grad():
		output = model(tensor)
	output_array = output[0].cpu().numpy()
	return dict(zip(model.pathologies, output_array))


def _confidence_label(score):
	"""
	Returns a human-readable confidence label for a given score.
	Scores below NOISE_THRESHOLD should already be excluded before calling this.
	"""
	if score >= LIKELY_THRESHOLD:
		return "High confidence finding"
	if score >= POSSIBLE_THRESHOLD:
		return "Likely"
	if score >= MINIMAL_SIGNAL_THRESHOLD:
		return "Possible"
	return "Minimal signal"


def _overall_assessment(max_score):
	"""
	Derives a top-level assessment string from the maximum raw score.
	"""
	if max_score >= 0.80:
		return "Significant findings detected"
	if max_score >= 0.60:
		return "Findings warrant attention"
	if max_score >= 0.40:
		return "Mild findings, monitoring recommended"
	return "No significant abnormalities detected"


def _build_interpretation(raw_scores):
	"""
	Builds the interpretation block from the raw scores dict.
	"""
	ranked = sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)
	filtered_ranked = [
		(name, score)
		for name, score in ranked
		if score >= NOISE_THRESHOLD
	]
	max_score = max(raw_scores.values()) if raw_scores else 0.0

	top_findings = [
		{
			"name": name,
			"score": round(float(score), 4),
			"confidence": _confidence_label(score),
		}
		for name, score in filtered_ranked[:4]
	]

	likely_findings = [
		name for name, score in filtered_ranked if score >= LIKELY_THRESHOLD
	]
	possible_findings = [
		name
		for name, score in filtered_ranked
		if MINIMAL_SIGNAL_THRESHOLD <= score < POSSIBLE_THRESHOLD
	]

	pneumonia_score = round(float(raw_scores.get("Pneumonia", 0.0)), 4)
	pneumonia_confidence = (
		_confidence_label(pneumonia_score)
		if pneumonia_score >= NOISE_THRESHOLD
		else "Below detection threshold"
	)

	return {
		"overall_assessment": _overall_assessment(max_score),
		"top_findings": top_findings,
		"likely_findings": likely_findings,
		"possible_findings": possible_findings,
		"pneumonia": {
			"score": pneumonia_score,
			"signal": pneumonia_confidence,
		},
	}


def predict(image_path, use_ensemble=False):
	tensor = _preprocess_image(image_path)

	model_outputs = [_run_model(PRIMARY_MODEL, tensor)]
	used_models = ["densenet121-res224-all"]

	if use_ensemble:
		for extra_model, name in zip(
			_get_optional_ensemble_models(),
			["densenet121-res224-nih", "densenet121-res224-chex"],
		):
			model_outputs.append(_run_model(extra_model, tensor))
			used_models.append(name)

	raw_scores = {}
	for disease in REQUESTED_DISEASES:
		available_scores = [
			output[disease] for output in model_outputs if disease in output
		]
		if not available_scores:
			raise KeyError(f"Required pathology not found in model output: {disease}")
		raw_scores[disease] = round(float(np.mean(available_scores)), 4)

	# Remove pure-noise entries (below 0.25) from the scores dict entirely
	scores = {
		disease: score
		for disease, score in raw_scores.items()
		if score >= NOISE_THRESHOLD
	}
	overall_assessment = _overall_assessment(max(raw_scores.values()))

	return {
		"scores": scores,
		"overall_assessment": overall_assessment,
		"limitations": {
			"Tuberculosis": TB_LIMITATION_MESSAGE,
		},
		"model_info": {
			"primary": "densenet121-res224-all",
			"ensemble_enabled": bool(use_ensemble),
			"models_used": used_models,
		},
		"interpretation": _build_interpretation(raw_scores),
	}