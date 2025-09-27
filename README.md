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

## Repository Structure

The project is organized as follows:

```bash
## Repository Structure

The project is organized as follows:

house-price-pipeline/
│
├── tests/                     # Unit tests for preprocessing / model validation
│   ├── test_preprocess.py
│   └── test_sample.py
│
├── app.py                     # Streamlit app for prediction
├── preprocess_and_train.py    # Preprocessing + training pipeline
├── data.csv                   # Training dataset (cleaned version)
│
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Ruff linting config
├── Dockerfile                 # Build ML app image
├── docker-compose.staging.yml # Docker Compose for staging deploy
├── docker-compose.prod.yml    # Docker Compose for production deploy
├── Jenkinsfile                # Full CI/CD pipeline definition
├── .gitignore                 # Ignore rules
└── README.md                  # Project overview + usage guide

> Note: During pipeline execution, additional directories such as `artifacts/` (for trained models) 
> and `scripts/` (for security parsers) are generated automatically.

```
---

## 🛠️ Quick Start

```bash
# 1. Clone repo
git clone https://github.com/tommyanhnguyen/house-price-pipeline.git
cd house-price-pipeline

# 2. Build Docker image
docker build -t house-price .

# 3. Run Streamlit app
docker run -p 8501:8501 house-price
```
