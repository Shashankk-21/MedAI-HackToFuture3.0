import importlib
import pytest

from chatbot import explain_diagnosis


def make_predictions(scores):
    return {"scores": scores}


def test_lung_opacity_alone_creates_synthetic():
    preds = make_predictions({"Lung Opacity": 0.75, "Effusion": 0.1})
    text = explain_diagnosis(preds)
    assert "pneumonia" in text.lower() or "infectious" in text.lower()
    assert "synthetic_findings" in preds
    assert "pneumonia_pattern" in preds["synthetic_findings"]
    assert preds["synthetic_findings"]["pneumonia_pattern"]["score"] == pytest.approx(0.75, rel=1e-3)


def test_lung_opacity_with_effusion_mentions_combination():
    preds = make_predictions({"Lung Opacity": 0.8, "Effusion": 0.35})
    text = explain_diagnosis(preds)
    assert "pleural" in text.lower() or "pleural involvement" in text.lower() or "bacterial" in text.lower()
    assert "pneumonia_pattern" in preds.get("synthetic_findings", {})


def test_all_scores_below_normal_statement():
    preds = make_predictions({"Pneumonia": 0.1, "Lung Opacity": 0.1, "Effusion": 0.05})
    text = explain_diagnosis(preds)
    assert "within normal limits" in text.lower()
    assert "synthetic_findings" in preds
    assert "pneumonia_pattern" not in preds["synthetic_findings"]


def test_no_false_positive_when_below_threshold():
    preds = make_predictions({"Lung Opacity": 0.7, "Effusion": 0.29})
    text = explain_diagnosis(preds)
    # Exactly 0.7 should not trigger (>0.70 strict)
    assert "pneumonia_pattern" not in preds.get("synthetic_findings", {})
*** End File