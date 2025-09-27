# tests/test_artifacts_and_model.py
from pathlib import Path
import json
import numpy as np
import pandas as pd
import joblib
import pytest

ART_DIR = Path("artifacts")
MODEL_P = ART_DIR / "rf_model.joblib"
SCALER_P = ART_DIR / "scaler.joblib"
COLS_P = ART_DIR / "feature_columns.json"

@pytest.mark.ci
@pytest.mark.parametrize("p", [MODEL_P, SCALER_P, COLS_P])
def test_artifact_files_exist(p: Path):
    """All trained artifacts must be produced in Build stage."""
    assert p.exists(), f"Missing artifact: {p}"

def _load_contract():
    """Helper: load model, scaler, and feature columns."""
    rf = joblib.load(MODEL_P)
    scaler = joblib.load(SCALER_P)
    with open(COLS_P, "r") as f:
        cols = json.load(f)
    assert isinstance(cols, list), "feature_columns.json must be a JSON list"
    return rf, scaler, cols

@pytest.mark.ci
def test_feature_columns_contract_is_valid():
    """Columns must be non-empty, unique, and ordered (order matters)."""
    _, scaler, cols = _load_contract()
    assert len(cols) > 0, "No feature columns found"
    assert len(cols) == len(set(cols)), "Duplicate feature names detected"
    # If scaler has n_features_in_, ensure it matches columns length
    if hasattr(scaler, "n_features_in_"):
        assert scaler.n_features_in_ == len(cols), (
            f"Scaler expects {scaler.n_features_in_} features, "
            f"but feature_columns.json has {len(cols)}"
        )

@pytest.mark.ci
def test_model_contract_matches_columns():
    """Model input size must match feature_columns length."""
    rf, _, cols = _load_contract()
    if hasattr(rf, "n_features_in_"):
        assert rf.n_features_in_ == len(cols), (
            f"Model expects {rf.n_features_in_} features, got {len(cols)}"
        )

@pytest.mark.ci
def test_model_can_predict_on_dummy_vector():
    """Sanity check: model produces finite predictions on a zero vector."""
    rf, _, cols = _load_contract()
    X = pd.DataFrame([0] * len(cols), index=cols).T  # 1xF zero row (ordered)
    yhat = rf.predict(X)
    assert np.ndim(yhat) == 1 and yhat.size == 1, "Prediction must be 1-D scalar"
    assert np.isfinite(yhat).all(), "Prediction contains NaN/Inf"
    # Optional realism check for house price regression (non-failing bound)
    assert yhat[0] > 0, "Predicted house price should be positive"

@pytest.mark.ci
def test_predictions_are_deterministic_for_same_input():
    """Loading the same persisted model twice should produce identical outputs."""
    rf1 = joblib.load(MODEL_P)
    rf2 = joblib.load(MODEL_P)
    with open(COLS_P, "r") as f:
        cols = json.load(f)
    X = pd.DataFrame([0] * len(cols), index=cols).T
    y1 = rf1.predict(X)
    y2 = rf2.predict(X)
    assert np.allclose(y1, y2), "Non-deterministic predictions detected"
