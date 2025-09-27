from pathlib import Path
import json
import numpy as np
import pandas as pd
import joblib
import pytest

ART = Path("artifacts")
MODEL = ART / "rf_model.joblib"
SCALER = ART / "scaler.joblib"
COLS = ART / "feature_columns.json"

# ---------- 1) Existence: core artifacts must be present ----------
@pytest.mark.ci
@pytest.mark.parametrize("p", [MODEL, SCALER, COLS])
def test_core_artifacts_exist(p: Path):
    """Core artifacts produced in Build stage must exist."""
    assert p.exists(), f"Missing artifact: {p}"

# ---------- 2) Contract: columns make sense and match model ----------
@pytest.mark.ci
def test_feature_columns_contract():
    """Columns must be non-empty, unique, and match model's expected size."""
    rf = joblib.load(MODEL)
    with open(COLS) as f:
        cols = json.load(f)
    assert isinstance(cols, list) and len(cols) > 0, "feature_columns.json is empty"
    assert len(cols) == len(set(cols)), "Duplicate feature names"
    if hasattr(rf, "n_features_in_"):
        assert rf.n_features_in_ == len(cols), (
            f"Model expects {rf.n_features_in_} features but got {len(cols)}"
        )

# ---------- 3) Sanity: model can predict on a simple valid row ----------
@pytest.mark.ci
def test_model_predicts_finite_value():
    """Single-row prediction should be a finite positive number."""
    rf = joblib.load(MODEL)
    with open(COLS) as f:
        cols = json.load(f)
    X = pd.DataFrame([0] * len(cols), index=cols).T  # ordered 1×F zero row
    yhat = rf.predict(X)
    assert yhat.shape == (1,), "Prediction must be 1-D scalar"
    assert np.isfinite(yhat).all(), "Prediction contains NaN/Inf"
    assert float(yhat[0]) > 0, "House price should be positive"

# ---------- 4) Stability: same input -> same output ----------
@pytest.mark.ci
def test_predictions_are_deterministic():
    """Persisted model must be deterministic for identical inputs."""
    rf1 = joblib.load(MODEL)
    rf2 = joblib.load(MODEL)
    with open(COLS) as f:
        cols = json.load(f)
    X = pd.DataFrame([0] * len(cols), index=cols).T
    y1 = rf1.predict(X)
    y2 = rf2.predict(X)
    assert np.allclose(y1, y2), "Non-deterministic predictions detected"
