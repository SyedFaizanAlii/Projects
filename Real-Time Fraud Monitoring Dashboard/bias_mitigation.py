import os

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder
from fairlearn.metrics import MetricFrame, selection_rate, false_positive_rate, true_positive_rate
from fairlearn.postprocessing import ThresholdOptimizer

try:
    from aif360.algorithms.preprocessing import Reweighing
    from aif360.datasets import BinaryLabelDataset
    AIF360_AVAILABLE = True
except ImportError:
    AIF360_AVAILABLE = False

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import matplotlib.pyplot as plt

PROTECTED_GROUPS = {
    "high_risk": {"IN", "CN", "RU", "BR", "NG", "PK"},
    "low_risk": {"US", "GB", "DE", "FR", "CA", "AU"},
}


def location_group_from_country(country: str) -> str:
    if not isinstance(country, str):
        return "low_risk"
    upper = country.upper()
    for label, countries in PROTECTED_GROUPS.items():
        if upper in countries:
            return label
    return "low_risk"


def add_location_group(df: pd.DataFrame, country_column: str = "location") -> pd.DataFrame:
    df = df.copy()
    if country_column in df.columns:
        df["location_country"] = df[country_column].apply(
            lambda value: value.get("country") if isinstance(value, dict) else value
        )
    if "location_country" not in df.columns:
        raise ValueError("Dataframe must contain a location or location_country column")

    df["location_group"] = df["location_country"].apply(location_group_from_country)
    return df


def compute_reweighing_weights(df: pd.DataFrame, label_col: str = "is_fraud", protected_attr: str = "location_group") -> np.ndarray:
    group_values = df[protected_attr].astype(str)
    labels = df[label_col].astype(int)

    if AIF360_AVAILABLE:
        try:
            df_numeric = pd.DataFrame({
                label_col: labels.astype(float),
                protected_attr: pd.factorize(group_values)[0].astype(float),
            })
            dataset = BinaryLabelDataset(
                df=df_numeric,
                label_names=[label_col],
                protected_attribute_names=[protected_attr],
                favorable_label=0,
                unfavorable_label=1,
            )
            rw = Reweighing(protected_attribute_names=[protected_attr], favorable_label=0, unfavorable_label=1)
            transformed = rw.fit_transform(dataset)
            return transformed.instance_weights
        except Exception:
            pass

    label_counts = labels.value_counts(normalize=True).to_dict()
    group_counts = group_values.value_counts(normalize=True).to_dict()
    joint_counts = df.groupby([protected_attr, label_col]).size() / len(df)

    weights = []
    for group, label in zip(group_values, labels):
        p_y = label_counts[label]
        p_a = group_counts[group]
        p_ay = joint_counts.get((group, label), 1e-9)
        weights.append((p_y * p_a) / max(p_ay, 1e-9))
    return np.array(weights, dtype=float)


class GradientReversalLayer(layers.Layer):
    def __init__(self, hp_lambda=1.0, **kwargs):
        super().__init__(**kwargs)
        self.hp_lambda = hp_lambda

    def call(self, x):
        @tf.custom_gradient
        def reverse(x):
            def grad(dy):
                return -self.hp_lambda * dy

            return x, grad

        return reverse(x)


def build_adversarial_model(input_dim: int, num_groups: int, hidden_size: int = 64, gamma: float = 1.0):
    inputs = layers.Input(shape=(input_dim,), name="features")
    shared = layers.Dense(hidden_size, activation="relu")(inputs)
    predictions = layers.Dense(1, activation="sigmoid", name="main_output")(shared)

    reversed_shared = GradientReversalLayer(hp_lambda=gamma)(shared)
    adversary = layers.Dense(hidden_size // 2, activation="relu")(reversed_shared)
    adversary_output = layers.Dense(num_groups, activation="softmax", name="adversary_output")(adversary)

    model = keras.Model(inputs=inputs, outputs=[predictions, adversary_output])
    model.compile(
        optimizer="adam",
        loss={"main_output": "binary_crossentropy", "adversary_output": "categorical_crossentropy"},
        loss_weights={"main_output": 1.0, "adversary_output": 1.0},
    )
    return model


def adversarial_reweighting(X: np.ndarray, y: np.ndarray, groups: np.ndarray, base_weights: np.ndarray, gamma: float = 0.5) -> np.ndarray:
    if len(np.unique(groups)) < 2:
        return base_weights

    encoder_args = {"handle_unknown": "ignore"}
    try:
        encoder_args["sparse_output"] = False
    except Exception:
        encoder_args["sparse"] = False

    encoder = OneHotEncoder(**encoder_args)
    group_ohe = encoder.fit_transform(groups.reshape(-1, 1))
    if hasattr(group_ohe, "toarray"):
        group_ohe = group_ohe.toarray()
    group_ohe = np.asarray(group_ohe, dtype=float)

    model = build_adversarial_model(X.shape[1], group_ohe.shape[1], gamma=gamma)

    y_binary = np.asarray(y.reshape(-1, 1), dtype=float)
    model.fit(
        X,
        [y_binary, group_ohe],
        sample_weight=[base_weights, base_weights],
        epochs=12,
        batch_size=64,
        verbose=0,
    )

    _, adv_probs = model.predict(X, verbose=0)
    group_confidence = np.max(adv_probs, axis=1)
    adjustment = 1.0 + gamma * np.clip(group_confidence - 0.5, 0.0, 0.5)
    return base_weights * adjustment


class EqualizedOddsCalibrator:
    def __init__(self):
        self.calibrator = None

    def fit(self, estimator, X, y, sensitive_features):
        self.calibrator = ThresholdOptimizer(
            estimator=estimator,
            constraints="equalized_odds",
            predict_method="predict_proba",
            prefit=True,
        )
        self.calibrator.fit(X, y, sensitive_features=sensitive_features)

    def predict(self, X, sensitive_features):
        if self.calibrator is None:
            raise RuntimeError("EqualizedOddsCalibrator has not been fitted")
        return self.calibrator.predict(X, sensitive_features=sensitive_features)


def disparate_impact_ratio(y_pred: np.ndarray, group: np.ndarray) -> float:
    favorable = np.asarray(1 - y_pred, dtype=float)
    dummy = np.zeros_like(favorable, dtype=float)
    mf = MetricFrame(
        metrics=selection_rate,
        y_true=dummy,
        y_pred=favorable,
        sensitive_features=group,
    )
    rates = mf.by_group
    if len(rates) < 2:
        return 1.0
    return float(rates.min() / rates.max())


def equalized_odds_difference(y_true: np.ndarray, y_pred: np.ndarray, group: np.ndarray) -> float:
    tpr = MetricFrame(
        metrics=true_positive_rate,
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=group,
    ).by_group
    fpr = MetricFrame(
        metrics=false_positive_rate,
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=group,
    ).by_group
    if len(tpr) < 2 or len(fpr) < 2:
        return 0.0
    return float((tpr.max() - tpr.min()) + (fpr.max() - fpr.min()))


def theil_index(y_pred: np.ndarray, group: np.ndarray) -> float:
    favorable = 1 - y_pred.astype(np.float64)
    overall = favorable.mean()
    if overall <= 0:
        return 0.0

    groups = np.unique(group)
    theil = 0.0
    for g in groups:
        mask = group == g
        if np.sum(mask) == 0:
            continue
        p = favorable[mask].mean()
        if p > 0:
            theil += (mask.sum() / len(group)) * (p / overall) * np.log((p / overall) + 1e-9)
    return float(theil)


def generate_fairness_audit_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    group: np.ndarray,
    output_path: str = "reports/fairness_compliance.pdf",
    model_name: str = "Fraud Detection Ensemble",
):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred)
    if y_pred.dtype.kind in "fc":
        y_pred = (y_pred > 0.5).astype(int)

    di_ratio = disparate_impact_ratio(y_pred, group)
    eod_difference = equalized_odds_difference(y_true, y_pred, group)
    theil = theil_index(y_pred, group)

    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")
    body = (
        f"Fairness Compliance Audit Report\n"
        f"Model: {model_name}\n"
        f"Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Key metrics:\n"
        f"- Disparate Impact Ratio: {di_ratio:.4f}\n"
        f"- Equalized Odds Difference: {eod_difference:.4f}\n"
        f"- Theil Index: {theil:.4f}\n\n"
        "Interpretation:\n"
        "- A Disparate Impact Ratio close to 1.0 indicates similar approval rates across groups.\n"
        "- A small Equalized Odds Difference indicates similar false positive and true positive rates.\n"
        "- The Theil Index measures overall group-level unfairness; lower values are better.\n\n"
        "Recommendations:\n"
        "1. Use Reweighing to remove dataset-level bias from location-based demographics.\n"
        "2. Apply adversarial debiasing during training to reduce demographic signal in predictions.\n"
        "3. Use Equalized Odds post-processing to align decision thresholds across groups.\n"
    )
    ax.text(0.01, 0.99, body, va="top", family="monospace", fontsize=11)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


if __name__ == "__main__":
    from data_pipeline import prepare_training_sample

    df = prepare_training_sample(500)
    df = add_location_group(df)
    weights = compute_reweighing_weights(df)

    sample = df.sample(200, random_state=42)
    y_sample = sample["is_fraud"].astype(int).to_numpy()
    group_sample = sample["location_group"].to_numpy()

    report_path = generate_fairness_audit_report(
        y_sample,
        np.random.randint(0, 2, size=len(y_sample)),
        group_sample,
    )
    print(f"Generated sample fairness audit report at {report_path}")
