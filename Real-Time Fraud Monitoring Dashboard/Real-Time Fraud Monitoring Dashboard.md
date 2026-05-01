# Real-Time Financial Fraud Detection Engine

A production-ready prototype for an end-to-end fraud detection system with streaming ingestion, feature engineering, adaptive drift detection, explainability, and deployment support.

## Architecture

- Data ingestion via simulated Kafka-style transaction stream
- Real-time velocity and geolocation features
- Ensemble scoring with XGBoost, Isolation Forest, and Autoencoder
- Concept drift detection using ADWIN
- SHAP explainability and PDF report generation
- Streamlit monitoring dashboard and FastAPI scoring endpoint
- Docker / docker-compose deployment and GitHub Actions CI

## Getting Started

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run API locally:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

3. Run dashboard locally:

```bash
streamlit run dashboard/app.py --server.port 8501
```

4. Build with Docker:

```bash
docker compose up --build
```

## How to test the dashboard

1. Start the API:

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

2. Open the dashboard:

```bash
http://127.0.0.1:8501
```

3. Use the dashboard form to submit a sample transaction and inspect:
   - fraud probability
   - anomaly score
   - risk label
   - SHAP explanation report

4. View the API docs for transaction schema and endpoints:

```bash
http://127.0.0.1:8000/docs
```

## Key Files

- `data_pipeline.py`
- `feature_store.py`
- `model_ensemble.py`
- `bias_mitigation.py`
- `drift_detector.py`
- `api/main.py`
- `dashboard/app.py`
- `Dockerfile`
- `docker-compose.yml`

## Fairness and Compliance

- `bias_mitigation.py` implements:
  - AIF360 Reweighing for location-based protected groups
  - adversarial debiasing sample weighting
  - Fairlearn Equalized Odds post-processing
  - automated fairness audit reporting
- `reports/fairness_compliance.pdf` is a sample compliance report for executive review.

## Notes

This project scaffolds a complete fraud detection pipeline and is designed to be extended with real data sources such as IEEE-CIS Fraud Detection or PaySim.
