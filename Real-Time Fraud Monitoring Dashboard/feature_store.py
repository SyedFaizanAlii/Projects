import hashlib
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Any

import numpy as np

MERCHANT_RISK = {
    "electronics": 0.18,
    "travel": 0.16,
    "entertainment": 0.20,
    "grocery": 0.04,
    "utilities": 0.02,
    "health": 0.03,
    "fashion": 0.10,
    "gaming": 0.24,
}

FIVE_MINUTES = timedelta(minutes=5)
FIFTEEN_MINUTES = timedelta(minutes=15)


class FeatureBuilder:
    def __init__(self):
        self.history = deque(maxlen=10000)

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value

    @staticmethod
    def _device_hash_vector(device_id: str) -> float:
        digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % 1000 / 1000.0

    def _window_count(self, now: datetime, customer_id: str, delta: timedelta) -> int:
        return sum(
            1
            for record in self.history
            if record["customer_id"] == customer_id
            and now - self._parse_timestamp(record["timestamp"]) <= delta
        )

    def build_features(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        now = self._parse_timestamp(transaction["timestamp"])
        customer_id = transaction["customer_id"]
        merchant_category = transaction["merchant_category"]
        device_id = transaction["device"]["device_id"]

        features = {
            "velocity_1m": self._window_count(now, customer_id, timedelta(minutes=1)),
            "velocity_5m": self._window_count(now, customer_id, FIVE_MINUTES),
            "velocity_15m": self._window_count(now, customer_id, FIFTEEN_MINUTES),
            "merchant_risk_score": MERCHANT_RISK.get(merchant_category, 0.05),
            "location_score": float(hash(merchant_category + transaction["location"]["country"]) % 100) / 100.0,
            "device_fingerprint": self._device_hash_vector(device_id),
            "is_high_value": float(transaction["amount"] > 250.0),
        }

        self.history.append(transaction)
        return features


def extract_feature_columns(*args, **kwargs) -> list:
    return [
        "amount",
        "velocity_1m",
        "velocity_5m",
        "velocity_15m",
        "merchant_risk_score",
        "location_score",
        "device_fingerprint",
        "is_high_value",
    ]
