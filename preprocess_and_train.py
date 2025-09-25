import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


RAW_CSV = "data.csv"              # <— dữ liệu CHƯA filter
ART_DIR = Path("artifacts")
ART_DIR.mkdir(exist_ok=True)

KEEP_COLS = [
    "Suburb","Rooms","Type","Price","Date",
    "Distance","Bathroom","Car","Landsize","BuildingArea","YearBuilt"
]

RANDOM_STATE = 42

def compute_te_map(cat: pd.Series, y: np.ndarray, smoothing: float = 50.0):
    gmean = float(np.mean(y))
    grp = pd.DataFrame({"y": y, "cat": cat.fillna("Unknown").astype(str)})
    stats = grp.groupby("cat")["y"].agg(["mean", "count"])
    enc = (stats["count"] * stats["mean"] + smoothing * gmean) / (stats["count"] + smoothing)
    return {"mapping": enc.to_dict(), "global_mean": gmean, "smoothing": smoothing}

def apply_te(cat: pd.Series, te: dict) -> np.ndarray:
    mp = te["mapping"]
    gmean = te["global_mean"]
    return cat.map(mp).fillna(gmean).astype(float).to_numpy()

# Load
df = pd.read_csv(RAW_CSV, parse_dates=["Date"])
for col in KEEP_COLS:
    if col not in df.columns:
        df[col] = np.nan
df = df[KEEP_COLS].copy()
df = df[df["Price"].notna()].copy()

for c in ["Suburb","Type"]:
    df[c] = df[c].astype(str).str.strip()

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Year"] = df["Date"].dt.year
df["Month"] = df["Date"].dt.month

numeric_cols = ["Rooms","Distance","Bathroom","Car","Landsize","BuildingArea","YearBuilt"]
for col in numeric_cols:
    df[col+"_missing"] = pd.to_numeric(df[col], errors="coerce").isna().astype(int)
    series = pd.to_numeric(df[col], errors="coerce")
    med = series.median()
    if pd.isna(med):
        med = 0.0
    df[col] = series.fillna(med)

y = df["Price"].to_numpy()
X = df.drop(columns=["Price","Date"])

# Simple smoothed TE
te = compute_te_map(X["Suburb"], y, smoothing=50.0)
X["Suburb_TE"] = apply_te(X["Suburb"], te)
X = X.drop(columns=["Suburb"])

# OHE Type
X = pd.get_dummies(X, columns=["Type"], drop_first=True)

# Scale numerics
scaler = StandardScaler()
num_cols_scaled = [c for c in numeric_cols if c in X.columns]
X[num_cols_scaled] = scaler.fit_transform(X[num_cols_scaled])

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)

# Optional sampling for speed
MAX_TRAIN = 40000
if len(X_train) > MAX_TRAIN:
    sample_idx = np.random.RandomState(RANDOM_STATE).choice(len(X_train), size=MAX_TRAIN, replace=False)
    X_fit = X_train.iloc[sample_idx]
    y_fit = y_train[sample_idx]
else:
    X_fit, y_fit = X_train, y_train

# Compact RF
rf = RandomForestRegressor(n_estimators=120, random_state=RANDOM_STATE, n_jobs=1)
rf.fit(X_fit, y_fit)

# Evaluate
y_pred = rf.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
rmse = mean_squared_error(y_test, y_pred, squared=False)
r2 = r2_score(y_test, y_pred)

metrics_fast = {"MAE_AUD": float(mae), "RMSE_AUD": float(rmse), "R2": float(r2),
                "n_train_used": int(len(X_fit)), "n_train_total": int(len(X_train)), "n_features": int(X.shape[1])}

# Save artifacts
joblib.dump(rf, ART_DIR / "rf_model.joblib")
joblib.dump(scaler, ART_DIR / "scaler.joblib")
with open(ART_DIR / "feature_columns.json", "w") as f:
    json.dump(list(X.columns), f)
with open(ART_DIR / "numeric_cols_scaled.json", "w") as f:
    json.dump(num_cols_scaled, f)
with open(ART_DIR / "suburb_te.json", "w") as f:
    json.dump({
        "mapping": {k: float(v) for k,v in te["mapping"].items()},
        "global_mean": float(te["global_mean"]),
        "smoothing": float(te["smoothing"])
    }, f)
all_suburbs = sorted(df["Suburb"].dropna().unique().tolist())
with open(ART_DIR / "all_suburbs.json", "w") as f:
    json.dump(all_suburbs, f)
