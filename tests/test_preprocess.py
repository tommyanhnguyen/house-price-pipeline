import json, numpy as np, pandas as pd, joblib, os

def test_artifacts_exist_after_train():
    assert os.path.exists("artifacts/rf_model.joblib")
    assert os.path.exists("artifacts/scaler.joblib")
    assert os.path.exists("artifacts/feature_columns.json")

def test_model_can_predict_dummy():
    rf = joblib.load("artifacts/rf_model.joblib")
    cols = json.load(open("artifacts/feature_columns.json"))
    X = pd.DataFrame([0]*len(cols), index=cols).T
    yhat = rf.predict(X)
    assert np.isfinite(yhat).all()
