# 🏡 House Price Prediction Pipeline

A complete **CI/CD pipeline with Jenkins** for training, testing, and deploying a machine learning model that predicts house prices.  
The project uses **Python, Scikit-learn, Docker, and Streamlit**.

---

## 🚀 Features
- **Preprocessing & Training**: Clean housing dataset and train a Random Forest model.
- **CI/CD with Jenkins**: Automated build, test, code quality, security checks, and deployment.
- **Dockerized App**: Streamlit web app for price prediction.
- **Staging & Prod Environments**: Deploy via `docker-compose` with health checks.

---

house-price-pipeline/
│
├── artifacts/                 # Saved ML artifacts (model, scaler, feature maps…)
│   ├── rf_model.joblib
│   ├── scaler.joblib
│   ├── feature_columns.json
│   └── suburb_te.json
│
├── scripts/                   # Helper scripts (security parsers, etc.)
│   ├── parse_pipaudit.py
│   └── parse_trivy.py
│
├── tests/                     # Unit tests for preprocessing / model validation
│   └── test_preprocess.py
│
├── app.py                     # Streamlit app for prediction
├── preprocess_and_train.py    # Preprocessing + training pipeline
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Build ML app image
├── docker-compose.staging.yml # Docker Compose for staging deploy
├── docker-compose.prod.yml    # Docker Compose for production deploy
├── Jenkinsfile                # Full CI/CD pipeline definition
├── README.md                  # Project overview + usage guide
└── data.csv                   # Training dataset (cleaned version)

--- 
