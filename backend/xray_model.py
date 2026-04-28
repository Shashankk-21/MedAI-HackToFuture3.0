import cv2
from pathlib import Path
import numpy as np
import torch
import torchxrayvision as xrv
from PIL import Image
import torchvision.transforms as transforms


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ENSEMBLE_MODEL_NAMES = [
	"densenet121-res224-all",
	"densenet121-res224-nih",
	"densenet121-res224-chex",
]

ENSEMBLE_SPECS = [
	{
		"name": "densenet121-res224-all",
		"weights_key": "densenet121-res224-all",
		"weight_file": "densenet121-res224-all.pth",
	},
	{
		"name": "densenet121-res224-nih",
		"weights_key": "densenet121-res224-nih",
		"weight_file": "densenet121-res224-nih.pth",
	},
	{
		"name": "densenet121-res224-chex",
		"weights_key": "densenet121-res224-chex",
		"weight_file": "densenet121-res224-chex.pth",
	},
]


def _resolve_weight_path(filename, weights_key):
	base_dir = Path(__file__).resolve().parent
	cache_dir = Path.home() / ".torchxrayvision" / "models_data"
	official_filename = Path(xrv.models.model_urls[weights_key]["weights_url"]).name
	candidates = [
		base_dir / filename,
		base_dir / "weights" / filename,
		cache_dir / filename,
		cache_dir / official_filename,
	]

	stem = Path(filename).stem
	for folder in [base_dir, base_dir / "weights", cache_dir]:
		for ext in (".pth", ".pt"):
			candidates.append(folder / f"{stem}{ext}")

	for candidate in candidates:
		if candidate.exists():
			return candidate

	raise FileNotFoundError(
		f"Required ensemble weight file not found for {filename}. "
		f"Looked in: {', '.join(str(path) for path in candidates)}"
	)


def _extract_state_dict(loaded_weights):
	if hasattr(loaded_weights, "state_dict"):
		return loaded_weights.state_dict()
	if isinstance(loaded_weights, dict):
		for key in ("state_dict", "model_state_dict", "model"):
			if key in loaded_weights and isinstance(loaded_weights[key], dict):
				return loaded_weights[key]
		return loaded_weights
	raise ValueError("Unsupported weight file format for DenseNet121 ensemble")


def _build_ensemble_models():
	models = {}
	for spec in ENSEMBLE_SPECS:
		labels = xrv.models.model_urls[spec["weights_key"]]["labels"]
		model = xrv.models.DenseNet(weights=None, num_classes=len(labels))
		model.targets = labels
		model.pathologies = labels
		weight_path = _resolve_weight_path(spec["weight_file"], spec["weights_key"])
		loaded_weights = torch.load(weight_path, map_location="cpu", weights_only=False)
		state_dict = _extract_state_dict(loaded_weights)
		model.load_state_dict(state_dict, strict=False)
		model = model.to(DEVICE)
		model.eval()
		models[spec["name"]] = model
	return models


ENSEMBLE_MODELS = None


def _get_ensemble_models():
	global ENSEMBLE_MODELS
	if ENSEMBLE_MODELS is None:
		ENSEMBLE_MODELS = _build_ensemble_models()
	return ENSEMBLE_MODELS

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

HIGH_CONFIDENCE_THRESHOLD = 0.65
MODERATE_CONFIDENCE_THRESHOLD = 0.40

XRAY_PREPROCESS = transforms.Compose(
	[xrv.datasets.XRayCenterCrop(), xrv.datasets.XRayResizer(224)]
)


def _preprocess_image(image_path):
	img = Image.open(image_path)
	img = img.convert("L")
	img = np.array(img)
	clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
	img = clahe.apply(img)
	img = Image.fromarray(img).convert("RGB")
	img = np.array(img)
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
	output = model(tensor)
	output_array = output[0].detach().cpu().numpy()
	return {
		pathology: float(score)
		for pathology, score in zip(model.pathologies, output_array)
		if pathology
	}


def _confidence_band(score):
	if score >= HIGH_CONFIDENCE_THRESHOLD:
		return "strong"
	if score >= MODERATE_CONFIDENCE_THRESHOLD:
		return "moderate"
	return "low"


def _build_interpretation(scores):
	ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
	top_findings = [
		{"name": name, "score": round(float(score), 4), "confidence": _confidence_band(score)}
		for name, score in ranked[:4]
	]

	likely_findings = [
		name for name, score in ranked if score >= HIGH_CONFIDENCE_THRESHOLD
	]
	possible_findings = [
		name
		for name, score in ranked
		if MODERATE_CONFIDENCE_THRESHOLD <= score < HIGH_CONFIDENCE_THRESHOLD
	]

	pneumonia_score = round(float(scores.get("Pneumonia", 0.0)), 4)
	pneumonia_signal = _confidence_band(pneumonia_score)

	return {
		"top_findings": top_findings,
		"likely_findings": likely_findings,
		"possible_findings": possible_findings,
		"pneumonia": {
			"score": pneumonia_score,
			"signal": pneumonia_signal,
		},
	}


def predict(image_path, use_ensemble=False):
	tensor = _preprocess_image(image_path).to(DEVICE)
	models = _get_ensemble_models()

	with torch.no_grad():
		predictions = [
			_run_model(models[model_name], tensor)
			for model_name in ENSEMBLE_MODEL_NAMES
		]

	scores = {}
	for disease in REQUESTED_DISEASES:
		# Collect raw logits from each model for this pathology (match by name)
		available_logits = [prediction[disease] for prediction in predictions if disease in prediction]
		if not available_logits:
			raise KeyError(f"Required pathology not found in model output: {disease}")
		# Average logits first
		avg_logit = float(np.mean(available_logits))
		# Apply sigmoid once to the averaged logit to get probability
		prob = float(torch.sigmoid(torch.tensor(avg_logit)).item())
		scores[disease] = round(prob, 4)

	return {
		"scores": scores,
		"limitations": {
			"Tuberculosis": TB_LIMITATION_MESSAGE,
		},
		"model_info": {
			"primary": "densenet121-res224-all",
			"ensemble_enabled": True,
			"models_used": ENSEMBLE_MODEL_NAMES,
		},
		"interpretation": _build_interpretation(scores),
	}
