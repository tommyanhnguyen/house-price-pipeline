import json
import joblib
import pandas as pd
# import numpy as np
import streamlit as st

st.set_page_config(page_title="House Price Predictor", layout="centered")
st.title("🏠 House Price Predictor (Random Forest)")

# --- Paths ---
MODEL_PATH = "artifacts/rf_model.joblib"
COLUMNS_PATH = "artifacts/feature_columns.json"
SCALER_PATH = "artifacts/scaler.joblib"
NUMERIC_COLS_PATH = "artifacts/numeric_cols_scaled.json"
SUBURB_TE_PATH = "artifacts/suburb_te.json"
ALL_SUBURBS_PATH = "artifacts/all_suburbs.json"

@st.cache_resource
def load_artifacts():
    model = joblib.load(MODEL_PATH)
    with open(COLUMNS_PATH, "r") as f:
        feature_columns = json.load(f)
    scaler = joblib.load(SCALER_PATH)
    with open(NUMERIC_COLS_PATH, "r") as f:
        numeric_cols_scaled = json.load(f)
    with open(SUBURB_TE_PATH, "r") as f:
        suburb_te = json.load(f)
    with open(ALL_SUBURBS_PATH, "r") as f:
        all_suburbs = json.load(f)
    return model, feature_columns, scaler, numeric_cols_scaled, suburb_te, all_suburbs

model, FEATURE_COLUMNS, scaler, NUMERIC_COLS, SUBURB_TE, ALL_SUBURBS = load_artifacts()

def encode_suburb(suburb: str) -> float:
    if suburb in SUBURB_TE["mapping"]:
        return float(SUBURB_TE["mapping"][suburb])
    return float(SUBURB_TE["global_mean"])

st.caption("Numeric fields (e.g., Landsize, BuildingArea) are scaled internally exactly like training.")

with st.form("input_form"):
    col1, col2 = st.columns(2)
    with col1:
        suburb = st.selectbox("Suburb", options=ALL_SUBURBS if ALL_SUBURBS else ["Unknown"])
        prop_type = st.selectbox("Type (h=house, t=townhouse, u=unit)", options=["h","t","u"], index=0)
        rooms = st.number_input("Rooms", min_value=1, max_value=10, value=3, step=1)
        bathroom = st.number_input("Bathroom", min_value=1.0, max_value=6.0, value=1.0, step=1.0)
    with col2:
        car = st.number_input("Car", min_value=0.0, max_value=6.0, value=1.0, step=1.0)
        landsize = st.number_input("Landsize (m²)", min_value=0.0, max_value=5000.0, value=300.0, step=10.0)
        building_area = st.number_input("Building Area (m²)", min_value=0.0, max_value=1000.0, value=120.0, step=10.0)
        year = st.number_input("Sale Year", min_value=2016, max_value=2018, value=2017, step=1)

    submitted = st.form_submit_button("Predict")

if submitted:
    row = {
        "Rooms": rooms,
        "Distance": 0.0,
        "Bathroom": bathroom,
        "Car": car,
        "Landsize": landsize,
        "BuildingArea": building_area,
        "YearBuilt": 0.0,
        "Year": int(year),
        "Month": 0,
        "Rooms_missing": 0,
        "Distance_missing": 0,
        "Bathroom_missing": 0,
        "Car_missing": 0,
        "Landsize_missing": 0 if landsize != 0 else 1,
        "BuildingArea_missing": 0 if building_area != 0 else 1,
        "YearBuilt_missing": 0,
        "Suburb_TE": encode_suburb(suburb),
        "Type_t": 1 if prop_type == "t" else 0,
        "Type_u": 1 if prop_type == "u" else 0,
    }

    X = pd.DataFrame([row]).reindex(columns=FEATURE_COLUMNS, fill_value=0)

    if NUMERIC_COLS:
        X[NUMERIC_COLS] = scaler.transform(X[NUMERIC_COLS])

    pred = float(model.predict(X)[0])
    st.subheader(f"Estimated Price: **${pred:,.0f}** AUD")

