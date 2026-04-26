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

	scores = {}
	for disease in REQUESTED_DISEASES:
		available_scores = [
			output[disease] for output in model_outputs if disease in output
		]
		if not available_scores:
			raise KeyError(f"Required pathology not found in model output: {disease}")
		scores[disease] = round(float(np.mean(available_scores)), 4)

	return {
		"scores": scores,
		"limitations": {
			"Tuberculosis": TB_LIMITATION_MESSAGE,
		},
		"model_info": {
			"primary": "densenet121-res224-all",
			"ensemble_enabled": bool(use_ensemble),
			"models_used": used_models,
		},
	}
