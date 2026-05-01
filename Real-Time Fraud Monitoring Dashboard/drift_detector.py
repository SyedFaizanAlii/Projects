from river.drift import ADWIN


class AdaptiveDriftDetector:
    def __init__(self, delta: float = 0.002):
        self.adwin = ADWIN(delta=delta)
        self.latest_drift = None
        self.steps = 0

    def observe(self, error_rate: float) -> bool:
        self.steps += 1
        drift_detected = self.adwin.update(error_rate)
        if drift_detected:
            self.latest_drift = self.steps
        return drift_detected

    def should_retrain(self, error_rate: float) -> bool:
        return self.observe(error_rate)

    def get_status(self) -> dict:
        return {
            "drift_detected": self.latest_drift is not None,
            "latest_drift_step": self.latest_drift,
            "observations": self.steps,
        }
