import random
import string
from collections import deque
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from feature_store import FeatureBuilder

MERCHANT_CATEGORIES = [
    "electronics", "travel", "entertainment", "grocery", "utilities", "health", "fashion", "gaming"
]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]

COUNTRIES = ["US", "GB", "DE", "FR", "CA", "AU", "IN", "CN"]
HIGH_RISK_COUNTRIES = {"IN", "CN", "BR", "NG", "PK", "RU"}

RISKY_MERCHANTS = {"gaming": 0.22, "electronics": 0.18, "travel": 0.16, "fashion": 0.12}


def random_transaction_id(length: int = 12) -> str:
    return "TX" + "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def random_amount() -> float:
    return round(np.random.exponential(scale=120.0) + 1.0, 2)


def random_location() -> dict:
    return {
        "country": random.choice(COUNTRIES),
        "latitude": round(np.random.uniform(-90, 90), 5),
        "longitude": round(np.random.uniform(-180, 180), 5),
    }


def random_device() -> dict:
    return {
        "device_type": random.choice(DEVICE_TYPES),
        "device_id": random.choice(["device_a", "device_b", "device_c", "device_d"]),
        "browser": random.choice(["chrome", "safari", "firefox", "edge"]),
    }


def merchant_risk(category: str) -> float:
    return RISKY_MERCHANTS.get(category, 0.05)


class TransactionGenerator:
    def __init__(self, fraud_rate: float = 0.02):
        self.fraud_rate = fraud_rate
        self.current_time = datetime.utcnow()
        self.history = deque(maxlen=10000)
        self.feature_builder = FeatureBuilder()

    def _estimate_fraud_probability(self, transaction: dict) -> float:
        base = 0.02
        base += merchant_risk(transaction["merchant_category"]) * 0.45
        base += 0.12 if transaction["location"]["country"] in HIGH_RISK_COUNTRIES else 0.0
        base += 0.15 if transaction["amount"] > 300 else 0.0
        base += 0.08 if transaction["merchant_category"] in {"gaming", "electronics", "travel"} else 0.0
        base += 0.06 if transaction["device"]["device_type"] == "mobile" else 0.0
        base += np.random.normal(0.0, 0.02)
        return float(min(max(base * (1.0 + self.fraud_rate), 0.01), 0.65))

    def generate_transaction(self) -> dict:
        self.current_time += timedelta(seconds=random.randint(5, 25))
        merchant_category = random.choice(MERCHANT_CATEGORIES)
        transaction = {
            "transaction_id": random_transaction_id(),
            "timestamp": self.current_time.isoformat(),
            "amount": random_amount(),
            "merchant_category": merchant_category,
            "merchant_id": f"M-{random.randint(100, 999)}",
            "customer_id": f"C-{random.randint(10000, 99999)}",
            "location": random_location(),
            "device": random_device(),
        }
        fraud_prob = self._estimate_fraud_probability(transaction)
        transaction["is_fraud"] = int(random.random() < fraud_prob)
        return transaction

    def generate_batch(self, batch_size: int = 32):
        batch = []
        for _ in range(batch_size):
            txn = self.generate_transaction()
            features = self.feature_builder.build_features(txn)
            batch.append({**txn, **features})
            self.history.append(txn)
        return pd.DataFrame(batch)

    def simulate_kafka_stream(self, total_events: int = 200, batch_size: int = 32):
        produced = 0
        while produced < total_events:
            yield self.generate_batch(min(batch_size, total_events - produced))
            produced += batch_size


def prepare_training_sample(n_samples: int = 3000) -> pd.DataFrame:
    generator = TransactionGenerator(fraud_rate=0.035)
    records = []
    for batch in generator.simulate_kafka_stream(total_events=n_samples, batch_size=128):
        records.append(batch)
    df = pd.concat(records, ignore_index=True)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    return df


if __name__ == "__main__":
    sample = prepare_training_sample(500)
    print(sample.head())
    print("Sample shape:", sample.shape)
