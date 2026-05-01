import os
import joblib
import numpy as np
import pandas as pd
import shap
from catboost import CatBoostClassifier
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from imblearn.combine import SMOTEENN
from tensorflow import keras
from tensorflow.keras import layers
from bias_mitigation import (
    add_location_group,
    compute_reweighing_weights,
    adversarial_reweighting,
    EqualizedOddsCalibrator,
    generate_fairness_audit_report,
    location_group_from_country,
)
from feature_store import extract_feature_columns
from utils import save_model, generate_shap_report


class FraudModelEnsemble:
    def __init__(self):
        self.xgb_model = None
        self.catboost_model = None
        self.iforest = None
        self.autoencoder = None
        self.pipeline = None
        self.feature_names = []
        self.location_group_map = {"low_risk": 0, "high_risk": 1}
        self.calibrator = EqualizedOddsCalibrator()
        self.fairness_report_path = None
        self.reconstruction_threshold = None
        self.anomaly_threshold = None

    def build_autoencoder(self, input_dim: int):
        model = keras.Sequential([
            layers.Input(shape=(input_dim,)),
            layers.Dense(max(16, input_dim // 2), activation="relu"),
            layers.Dense(max(8, input_dim // 4), activation="relu"),
            layers.Dense(max(16, input_dim // 2), activation="relu"),
            layers.Dense(input_dim, activation="linear"),
        ])
        model.compile(optimizer="adam", loss="mse")
        return model

    def fit(self, df: pd.DataFrame, target_column: str = "is_fraud", tune: bool = False):
        df = add_location_group(df)
        self.feature_names = extract_feature_columns()
        df["location_group_encoded"] = df["location_group"].map(self.location_group_map)

        feature_columns = self.feature_names + ["location_group_encoded"]
        X = df[feature_columns].astype(float)
        y = df[target_column].astype(int)

        sample_weights = compute_reweighing_weights(df, label_col=target_column, protected_attr="location_group")
        sampler = SMOTEENN(random_state=42)
        X_resampled, y_resampled = sampler.fit_resample(X, y)

        group_resampled = np.where(X_resampled["location_group_encoded"] == 1, "high_risk", "low_risk")
        X_resampled = X_resampled.drop(columns=["location_group_encoded"])

        mapping = {}
        for group in df["location_group"].unique():
            for label in df[target_column].unique():
                mask = (df["location_group"] == group) & (df[target_column] == label)
                mapping[(group, label)] = float(sample_weights[mask].mean() if mask.any() else 1.0)

        resampled_weights = np.array(
            [mapping.get((group, label), 1.0) for group, label in zip(group_resampled, y_resampled)],
            dtype=float,
        )
        resampled_weights = adversarial_reweighting(
            X_resampled.to_numpy(),
            y_resampled.to_numpy(),
            np.array(group_resampled),
            resampled_weights,
            gamma=0.4,
        )

        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
        ])
        X_scaled = self.pipeline.fit_transform(X_resampled)

        if tune:
            self._bayesian_optimize(X_scaled, y_resampled)

        self.xgb_model = CatBoostClassifier(
            iterations=150,
            learning_rate=0.06,
            depth=5,
            verbose=False,
            random_seed=42,
        )
        self.xgb_model.fit(X_scaled, y_resampled, sample_weight=resampled_weights)

        self.iforest = IsolationForest(n_estimators=150, contamination=0.015, random_state=42)
        self.iforest.fit(X_scaled)

        self.autoencoder = self.build_autoencoder(X_scaled.shape[1])
        self.autoencoder.fit(
            X_scaled[y_resampled == 0],
            X_scaled[y_resampled == 0],
            epochs=20,
            batch_size=64,
            verbose=0,
            validation_split=0.1,
        )

        recon_train = self.autoencoder.predict(X_scaled, verbose=0)
        recon_errors = np.mean(np.square(X_scaled - recon_train), axis=1)
        self.reconstruction_threshold = float(np.mean(recon_errors) + 2 * np.std(recon_errors))
        self.anomaly_threshold = float(np.percentile(-self.iforest.decision_function(X_scaled), 95))

        _, X_val, _, y_val, _, group_val = train_test_split(
            X_scaled,
            y_resampled,
            np.array(group_resampled),
            test_size=0.2,
            random_state=42,
            stratify=y_resampled,
        )
        self.calibrator.fit(self.xgb_model, X_val, y_val, sensitive_features=group_val)

        post_preds = self.calibrator.predict(X_val, sensitive_features=group_val)
        self.fairness_report_path = generate_fairness_audit_report(
            y_val,
            post_preds,
            group_val,
            output_path="reports/fairness_compliance.pdf",
        )

    def _bayesian_optimize(self, X: np.ndarray, y: np.ndarray):
        import optuna

        def objective(trial):
            params = {
                "depth": trial.suggest_int("depth", 3, 8),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2),
                "iterations": trial.suggest_int("iterations", 100, 250),
            }
            model = CatBoostClassifier(**params, verbose=False, random_seed=42)
            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
            model.fit(X_train, y_train)
            preds = model.predict_proba(X_val)[:, 1]
            return np.mean((y_val - preds) ** 2)

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=15)
        return study.best_params

    def score(self, transaction: dict) -> dict:
        if self.pipeline is None or self.xgb_model is None:
            raise RuntimeError("Model ensemble is not trained yet")

        feature_columns = extract_feature_columns(transaction)
        x = np.array([transaction[col] for col in feature_columns], dtype=float).reshape(1, -1)
        x_scaled = self.pipeline.transform(x)

        fraud_prob = float(self.xgb_model.predict_proba(x_scaled)[:, 1][0])
        anomaly_score = float(-self.iforest.decision_function(x_scaled)[0])
        reconstruction = self.autoencoder.predict(x_scaled, verbose=0)
        recon_error = float(np.mean(np.square(x_scaled - reconstruction)))

        recon_threshold = self.reconstruction_threshold if self.reconstruction_threshold is not None else 0.12
        anomaly_threshold = self.anomaly_threshold if self.anomaly_threshold is not None else 0.20

        if fraud_prob >= 0.75 or (recon_error > recon_threshold and anomaly_score > anomaly_threshold):
            risk_label = "high"
        elif fraud_prob >= 0.35 or recon_error > recon_threshold or anomaly_score > anomaly_threshold:
            risk_label = "medium"
        else:
            risk_label = "low"

        score = {
            "fraud_probability": fraud_prob,
            "anomaly_score": anomaly_score,
            "reconstruction_error": recon_error,
            "risk_label": risk_label,
        }

        try:
            group = location_group_from_country(transaction["location"]["country"])
            calibrated_label = self.calibrator.predict(x_scaled, sensitive_features=np.array([group]))
            score["fairness_adjusted_label"] = int(calibrated_label[0])
            if score["fairness_adjusted_label"] == 1 and score["risk_label"] == "low":
                score["risk_label"] = "medium"
        except Exception:
            score["fairness_adjusted_label"] = None

        return score

    def explain(self, transaction: dict, transaction_id: str, output_dir: str = "reports") -> str:
        if self.pipeline is None or self.xgb_model is None:
            raise RuntimeError("Model ensemble is not trained yet")

        os.makedirs(output_dir, exist_ok=True)

        feature_columns = extract_feature_columns(transaction)
        x = np.array([transaction[col] for col in feature_columns], dtype=float).reshape(1, -1)
        x_scaled = self.pipeline.transform(x)

        explainer = shap.TreeExplainer(self.xgb_model)
        shap_values = explainer.shap_values(x_scaled)
        output_path = os.path.join(output_dir, f"shap_report_{transaction_id}.pdf")
        generate_shap_report(shap_values, x_scaled, feature_columns, output_path)
        return output_path

    def save(self, model_path: str = "models/fraud_ensemble.joblib"):
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        save_model({
            "pipeline": self.pipeline,
            "xgb": self.xgb_model,
            "iforest": self.iforest,
            "autoencoder": self.autoencoder,
            "features": self.feature_names,
        }, model_path)

    def load(self, model_path: str = "models/fraud_ensemble.joblib"):
        data = joblib.load(model_path)
        self.pipeline = data["pipeline"]
        self.xgb_model = data["xgb"]
        self.iforest = data["iforest"]
        self.autoencoder = data["autoencoder"]
        self.feature_names = data["features"]
