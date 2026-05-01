import os
from typing import Dict, List

import joblib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def save_model(model: object, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)


def load_model(path: str):
    return joblib.load(path)


def generate_shap_report(shap_values, data, feature_names: List[str], output_path: str):
    plt.switch_backend("Agg")
    with PdfPages(output_path) as pdf:
        if hasattr(shap_values, "values"):
            values = shap_values.values[0]
            base_value = shap_values.base_values[0]
        else:
            values = shap_values[0]
            base_value = 0.0
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(feature_names, values.flatten())
        ax.set_title("SHAP Feature Impact")
        ax.set_xlabel("Contribution")
        pdf.savefig(fig)
        plt.close(fig)

        fig2, ax2 = plt.subplots(figsize=(10, 6))
        ax2.plot(data.flatten(), marker="o")
        ax2.set_title("Feature input values")
        ax2.set_ylabel("Scaled feature value")
        pdf.savefig(fig2)
        plt.close(fig2)

    return output_path
