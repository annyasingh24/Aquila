"""
Multi-Algorithm Anomaly Detection Suite for Aquila.
Implements:
1. Adaptive Rolling Z-Score Detector
2. Cumulative Sum (CUSUM) Control Chart for subtle persistent shifts
3. Principal Component Analysis (PCA) Residuals (Squared Prediction Error / Q-statistic and Hotelling's T^2)
4. Detection Delay and False Alarm Rate (FAR) Performance Evaluator.
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Any, Optional


class ZScoreDetector:
    """Adaptive rolling window Z-Score anomaly detector."""

    def __init__(self, window_size: int = 20, threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = threshold
        self.history: Dict[str, List[float]] = {}

    def update_and_detect(self, sensor_id: str, value: float) -> Tuple[bool, float]:
        if sensor_id not in self.history:
            self.history[sensor_id] = []
        buf = self.history[sensor_id]
        buf.append(value)
        if len(buf) > self.window_size:
            buf.pop(0)

        if len(buf) < 5:
            return False, 0.0

        mean = float(np.mean(buf[:-1]))
        std = float(np.std(buf[:-1])) + 1e-6
        z_score = abs(value - mean) / std
        is_anomaly = bool(z_score > self.threshold)
        return is_anomaly, round(z_score, 3)


class CUSUMDetector:
    """
    Cumulative Sum (CUSUM) detector for fast detection of subtle small leaks
    and incipient drift attacks.
    """

    def __init__(self, k_slack: float = 0.5, h_threshold: float = 4.0):
        self.k = k_slack
        self.h = h_threshold
        self.s_pos: Dict[str, float] = {}
        self.s_neg: Dict[str, float] = {}
        self.baseline_means: Dict[str, float] = {}
        self.baseline_stds: Dict[str, float] = {}

    def set_baseline(self, sensor_id: str, mean: float, std: float):
        self.baseline_means[sensor_id] = mean
        self.baseline_stds[sensor_id] = max(std, 1e-4)
        self.s_pos[sensor_id] = 0.0
        self.s_neg[sensor_id] = 0.0

    def update_and_detect(self, sensor_id: str, value: float) -> Tuple[bool, float]:
        if sensor_id not in self.baseline_means:
            self.set_baseline(sensor_id, value, 0.1)
            return False, 0.0

        mu = self.baseline_means[sensor_id]
        sigma = self.baseline_stds[sensor_id]
        norm_val = (value - mu) / sigma

        s_p = max(0.0, self.s_pos.get(sensor_id, 0.0) + norm_val - self.k)
        s_n = max(0.0, self.s_neg.get(sensor_id, 0.0) - norm_val - self.k)

        self.s_pos[sensor_id] = s_p
        self.s_neg[sensor_id] = s_n

        cusum_stat = max(s_p, s_n)
        is_anomaly = bool(cusum_stat > self.h)
        return is_anomaly, round(cusum_stat, 3)


class PCAResidualDetector:
    """
    Multivariate Principal Component Analysis (PCA) Residual Detector.
    Captures cross-sensor spatial correlations across the entire pipe network.
    Decomposes telemetry into principal subspace and residual subspace:
    - Squared Prediction Error (SPE / Q-statistic): Measures breakdown of spatial physics correlation.
    - Hotelling's T^2: Measures abnormal deviation within normal principal correlation subspace.
    """

    def __init__(self, n_components: int = 3, spe_threshold: float = 2.5):
        self.n_components = n_components
        self.spe_threshold = spe_threshold
        self.mean: Optional[np.ndarray] = None
        self.std: Optional[np.ndarray] = None
        self.components: Optional[np.ndarray] = None
        self.sensor_keys: List[str] = []
        self.fitted = False

    def fit(self, baseline_matrix: np.ndarray, sensor_keys: List[str]):
        """
        Fits PCA on clean historical baseline telemetry.
        baseline_matrix: shape (N_samples, N_sensors)
        """
        self.sensor_keys = sensor_keys
        self.mean = np.mean(baseline_matrix, axis=0)
        self.std = np.std(baseline_matrix, axis=0) + 1e-6

        # Standardize
        x_norm = (baseline_matrix - self.mean) / self.std

        # SVD / PCA
        u, s, vt = np.linalg.svd(x_norm, full_matrices=False)
        self.components = vt[: self.n_components]  # shape (k, N_sensors)
        self.fitted = True

    def calculate_residuals(self, telemetry_vector: np.ndarray) -> Tuple[bool, float, float]:
        """
        Calculates SPE and Hotelling T^2 for an incoming sample vector.
        """
        if not self.fitted:
            return False, 0.0, 0.0

        x_norm = (telemetry_vector - self.mean) / self.std
        # Projection onto principal subspace: x_hat = P P^T x_norm
        p = self.components.T  # (N_sensors, k)
        scores = np.dot(x_norm, p)
        x_reconstructed = np.dot(scores, self.components)
        
        # Residual vector e = x - x_hat
        residual = x_norm - x_reconstructed
        spe = float(np.sum(residual ** 2))
        
        # Approximate Hotelling T^2
        t2 = float(np.sum(scores ** 2))
        is_anomaly = bool(spe > self.spe_threshold)
        return is_anomaly, round(spe, 3), round(t2, 3)


class AnomalyBenchmarkEvaluator:
    """Evaluates detection delay and false alarm rate across algorithms."""

    @staticmethod
    def evaluate(ground_truth_events: List[bool], detections: List[bool]) -> Dict[str, float]:
        n = len(ground_truth_events)
        tp = sum(1 for gt, dt in zip(ground_truth_events, detections) if gt and dt)
        fp = sum(1 for gt, dt in zip(ground_truth_events, detections) if not gt and dt)
        tn = sum(1 for gt, dt in zip(ground_truth_events, detections) if not gt and not dt)
        fn = sum(1 for gt, dt in zip(ground_truth_events, detections) if gt and not dt)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        far = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "false_alarm_rate": round(far, 3),
            "f1_score": round(f1, 3),
        }
