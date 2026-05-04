# agentic_architecture/ml_predictor.py
"""
ML predictor — drop-in replacement for the old math formula.
Takes current semester IA components, returns predicted final exam score.
No historical data needed.
"""

import os
import pickle
import numpy as np

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "svm_predictor.pkl")

_model    = None
_scaler   = None
_features = None


def _load_model():
    global _model, _scaler, _features
    if _model is not None:
        return
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run train_model.py first."
        )
    with open(MODEL_PATH, "rb") as f:
        bundle    = pickle.load(f)
    _model    = bundle["model"]
    _scaler   = bundle["scaler"]
    _features = bundle["features"]
    print(f"✅ ML model loaded from {MODEL_PATH}")


def predict_final_exam_ml(
    quiz_total:       float,   # 0–10
    assignment_total: float,   # 0–20
    midterm:          float,   # 0–20
) -> int:
    """
    Predicts Sem4 final exam score (0–50) from current IA components only.
    No historical data required.
    """
    _load_model()

    features = np.array([[
        quiz_total,
        assignment_total,
        midterm,
    ]])

    features_scaled = _scaler.transform(features)
    prediction      = _model.predict(features_scaled)[0]

    return max(5, min(50, round(float(prediction))))