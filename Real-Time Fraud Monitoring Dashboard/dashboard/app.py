import datetime
import json
import os
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Fraud Monitoring Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: #f4f7fb;
    }
    .metric-card {
        border-radius: 12px;
        padding: 24px;
        background: #ffffff;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }
    .section-title {
        font-size: 24px;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("# Real-Time Fraud Monitoring Dashboard")
st.markdown("Manage scoring, review fraud metrics, and test transactions all from one interface.")

st.sidebar.title("Quick Actions")
st.sidebar.markdown(
    "Use this panel to check API health, submit a transaction for fraud scoring, and generate explainability reports."
)

st.sidebar.markdown("---")
if st.sidebar.button("Refresh metrics"):
    st.experimental_rerun()

st.sidebar.markdown("### API Configuration")
st.sidebar.write(API_URL)


def fetch_metrics():
    try:
        response = requests.get(f"{API_URL}/metrics", timeout=4)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"Unable to connect to API at {API_URL}: {exc}")
        st.stop()


def score_transaction(payload):
    response = requests.post(f"{API_URL}/score", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def explain_transaction(payload):
    response = requests.post(f"{API_URL}/explain", json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


metrics = fetch_metrics()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Transactions scored", metrics.get("transactions_scored", 0))
col2.metric("Fraud rate", f"{metrics.get('fraud_rate', 0.0):.2%}")
col3.metric("False positive rate", f"{metrics.get('false_positive_rate', 0.0):.2%}")
col4.metric("Drift alert", "ACTIVE" if metrics.get("drift_alert") else "Clear")

st.markdown("---")

with st.container():
    st.markdown("## Transaction Scoring Simulator")
    st.write(
        "Fill in transaction details below and click `Score Transaction` to see the fraud prediction, anomaly scores, and risk label."
    )

    default_payload = {
        "transaction_id": "TX-0001",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "amount": 342.75,
        "merchant_category": "electronics",
        "merchant_id": "M-762",
        "customer_id": "C-21745",
        "location": {"country": "US", "latitude": 37.7749, "longitude": -122.4194},
        "device": {"device_type": "mobile", "device_id": "device_a", "browser": "chrome"},
        "is_fraud": 0,
    }

    with st.form(key="score_form"):
        c1, c2, c3 = st.columns([1, 1, 1])
        transaction_id = c1.text_input("Transaction ID", value=default_payload["transaction_id"])
        timestamp = c2.text_input("Timestamp", value=default_payload["timestamp"])
        amount = c3.number_input("Amount", min_value=0.0, value=default_payload["amount"], format="%.2f")

        c4, c5, c6 = st.columns([1, 1, 1])
        merchant_category = c4.selectbox(
            "Merchant category",
            ["electronics", "travel", "entertainment", "grocery", "utilities", "health", "fashion", "gaming"],
            index=0,
        )
        merchant_id = c5.text_input("Merchant ID", value=default_payload["merchant_id"])
        customer_id = c6.text_input("Customer ID", value=default_payload["customer_id"])

        c7, c8, c9 = st.columns([1, 1, 1])
        country = c7.selectbox("Country", ["US", "GB", "DE", "FR", "CA", "AU", "IN", "CN"], index=0)
        latitude = c8.number_input("Latitude", value=default_payload["location"]["latitude"])
        longitude = c9.number_input("Longitude", value=default_payload["location"]["longitude"])

        c10, c11, c12 = st.columns([1, 1, 1])
        device_type = c10.selectbox("Device type", ["mobile", "desktop", "tablet"], index=0)
        device_id = c11.text_input("Device ID", value=default_payload["device"]["device_id"])
        browser = c12.selectbox("Browser", ["chrome", "safari", "firefox", "edge"], index=0)

        is_fraud = st.selectbox("Known fraud label (optional)", ["Unknown", "Fraud", "Not fraud"])
        submit = st.form_submit_button("Score Transaction")

    if submit:
        payload = {
            "transaction_id": transaction_id,
            "timestamp": timestamp,
            "amount": amount,
            "merchant_category": merchant_category,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "location": {"country": country, "latitude": latitude, "longitude": longitude},
            "device": {"device_type": device_type, "device_id": device_id, "browser": browser},
        }
        if is_fraud != "Unknown":
            payload["is_fraud"] = 1 if is_fraud == "Fraud" else 0

        try:
            result = score_transaction(payload)
            score = result["score"]
            metrics = result["metrics"]

            st.success("Transaction scored successfully")
            st.markdown(f"### Fraud score: **{score['fraud_probability']:.2%}**")
            st.markdown(f"- Risk label: **{score['risk_label'].upper()}**")
            st.markdown(f"- Anomaly score: **{score['anomaly_score']:.4f}**")
            st.markdown(f"- Reconstruction error: **{score['reconstruction_error']:.4f}**")

            if score["risk_label"] == "high":
                st.error("This transaction is likely fraudulent. Review the score and investigate immediately.")
            elif score["risk_label"] == "medium":
                st.warning("This transaction is moderately risky. Review the transaction details and verify before approving.")
            else:
                st.success("This transaction appears low risk. Continue monitoring and validate if needed.")

            st.markdown("---")
            with st.expander("View full API response"):
                st.json(result)

            if st.button("Generate SHAP explanation report"):
                explain_result = explain_transaction(payload)
                st.info(f"SHAP report generated: {explain_result['report_path']}")

        except Exception as exc:
            st.error(f"Failed to score transaction: {exc}")

st.markdown("---")

st.markdown("## Dashboard summary")
col_a, col_b = st.columns(2)
with col_a:
    st.write("### Model metrics")
    st.write(
        "Final fraud metrics are based on the API scoring stream. Use this interface for human-in-the-loop review and monitoring."
    )

with col_b:
    st.write("### Connectivity")
    st.write(
        {
            "API endpoint": API_URL,
            "Metrics available": metrics is not None,
            "Drift active": metrics.get("drift_alert"),
        }
    )
