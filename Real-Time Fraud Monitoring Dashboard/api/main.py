import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict

from data_pipeline import prepare_training_sample, TransactionGenerator
from feature_store import FeatureBuilder
from model_ensemble import FraudModelEnsemble
from drift_detector import AdaptiveDriftDetector

app = FastAPI(title="Fraud Detection API", version="0.1.0")

MODEL = FraudModelEnsemble()
DRIFT_DETECTOR = AdaptiveDriftDetector()
FEATURE_BUILDER = FeatureBuilder()
METRICS = {
    "transactions_scored": 0,
    "fraud_rate": 0.0,
    "false_positive_rate": 0.0,
    "drift_alert": False,
}


class LocationModel(BaseModel):
    country: str
    latitude: float
    longitude: float


class DeviceModel(BaseModel):
    device_type: str
    device_id: str
    browser: str


class TransactionPayload(BaseModel):
    transaction_id: str = Field(..., example="TX123ABC")
    timestamp: str = Field(..., example="2026-05-01T12:34:56")
    amount: float
    merchant_category: str
    merchant_id: str
    customer_id: str
    location: LocationModel
    device: DeviceModel
    is_fraud: int | None = None


@app.on_event("startup")
def startup_event():
    training_data = prepare_training_sample(600)
    MODEL.fit(training_data)


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "message": "Fraud Detection API is running",
        "health": "/health",
        "docs": "/docs",
        "metrics": "/metrics",
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {"status": "ok", "model_loaded": MODEL.xgb_model is not None}


@app.post("/score")
def score_transaction(transaction: TransactionPayload) -> Dict[str, Any]:
    txn_dict = transaction.dict()
    txn_features = {**txn_dict, **FEATURE_BUILDER.build_features(txn_dict)}
    try:
        result = MODEL.score(txn_features)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    METRICS["transactions_scored"] += 1
    METRICS["fraud_rate"] = (
        METRICS["fraud_rate"] * (METRICS["transactions_scored"] - 1) + result["fraud_probability"]
    ) / METRICS["transactions_scored"]

    if transaction.is_fraud is not None:
        predicted_flag = result["fraud_probability"] > 0.5
        if predicted_flag and transaction.is_fraud == 0:
            METRICS["false_positive_rate"] = (METRICS["false_positive_rate"] * (METRICS["transactions_scored"] - 1) + 1) / METRICS["transactions_scored"]
        else:
            METRICS["false_positive_rate"] = (METRICS["false_positive_rate"] * (METRICS["transactions_scored"] - 1)) / METRICS["transactions_scored"]

    if DRIFT_DETECTOR.should_retrain(result["fraud_probability"]):
        METRICS["drift_alert"] = True

    return {"transaction_id": transaction.transaction_id, "score": result, "metrics": METRICS}


@app.post("/explain")
def explain_transaction(transaction: TransactionPayload) -> Dict[str, Any]:
    txn_dict = transaction.dict()
    txn_features = {**txn_dict, **FEATURE_BUILDER.build_features(txn_dict)}
    report_path = MODEL.explain(txn_features, transaction.transaction_id)
    return {"transaction_id": transaction.transaction_id, "report_path": report_path}


@app.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    return METRICS


@app.get("/simulate")
def simulate_stream(batch_size: int = 32, events: int = 128) -> Dict[str, Any]:
    generator = TransactionGenerator()
    payloads = []
    for batch in generator.simulate_kafka_stream(total_events=events, batch_size=batch_size):
        payloads.append(batch.to_dict(orient="records"))
    return {"batches": payloads}
