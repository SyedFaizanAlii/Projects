import pytest

from data_pipeline import prepare_training_sample
from model_ensemble import FraudModelEnsemble


def test_sample_generation():
    df = prepare_training_sample(80)
    assert len(df) == 80
    assert "amount" in df.columns
    assert "merchant_risk_score" in df.columns


def test_ensemble_training_and_scoring():
    df = prepare_training_sample(120)
    model = FraudModelEnsemble()
    model.fit(df)
    sample = df.iloc[0].to_dict()
    result = model.score(sample)
    assert "fraud_probability" in result
    assert 0.0 <= result["fraud_probability"] <= 1.0
    assert result["reconstruction_error"] >= 0.0
