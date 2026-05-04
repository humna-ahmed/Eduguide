# agentic_architecture/train_model.py
"""
Train Linear SVM model on sem4_prediction_dataset.csv
Features: Quiz_Total, Assignment_Total, Midterm
Target:   Final_Exam (out of 50)

Run once: python train_model.py
Saves:    model/svm_predictor.pkl
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.svm import LinearSVR
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, KFold, train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "model", "student_performance_dataset (3).csv")
MODEL_PATH   = os.path.join(BASE_DIR, "model", "svm_predictor.pkl")
os.makedirs(os.path.join(BASE_DIR, "model"), exist_ok=True)

# ── Load ───────────────────────────────────────────────────
df = pd.read_csv(DATASET_PATH)
print(f"Rows: {len(df)}  |  Columns: {list(df.columns)}")
print(f"\nTarget (Final_Exam) stats:\n{df['Final_Exam'].describe().round(2)}")

# ── Features & Target ──────────────────────────────────────
FEATURE_COLS = [
    "Quiz_Total",        # 0–10
    "Assignment_Total",  # 0–20
    "Midterm",           # 0–20
]
TARGET_COL = "Final_Exam"

X = df[FEATURE_COLS].values
y = df[TARGET_COL].values

# ── Scale & cross-validate ─────────────────────────────────
scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X)

kf = KFold(n_splits=5, shuffle=True, random_state=42)

# Linear SVM for Regression (LinearSVR)
svm = LinearSVR(
    C=1.0,              # Regularization (lower = more regularization)
    epsilon=0.0,        # Epsilon-insensitive tube (0 = standard regression)
    random_state=42,
    max_iter=5000,      # Ensure convergence
    dual='auto'         # Automatically choose dual formulation
)

print("\n" + "="*50)
print("TRAINING LINEAR SVM MODEL")
print("="*50)

mae_cv  = cross_val_score(svm, X_scaled, y, cv=kf,
                           scoring='neg_mean_absolute_error')
rmse_cv = cross_val_score(svm, X_scaled, y, cv=kf,
                           scoring='neg_root_mean_squared_error')
r2_cv   = cross_val_score(svm, X_scaled, y, cv=kf, scoring='r2')

print("\n5-FOLD CROSS VALIDATION RESULTS:")
print(f"MAE  : {-mae_cv.mean():.3f} ± {mae_cv.std():.3f}  marks (out of 50)")
print(f"RMSE : {-rmse_cv.mean():.3f} ± {rmse_cv.std():.3f}")
print(f"R²   : {r2_cv.mean():.4f} ± {r2_cv.std():.4f}")

# ── Train/test split for final report ─────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42)

svm.fit(X_train, y_train)
y_pred = svm.predict(X_test)

print("\n" + "="*50)
print("TEST SET RESULTS (80/20 split)")
print("="*50)
print(f"MAE  : {mean_absolute_error(y_test, y_pred):.3f}")
print(f"RMSE : {np.sqrt(mean_squared_error(y_test, y_pred)):.3f}")
print(f"R²   : {r2_score(y_test, y_pred):.4f}")

# ── Train on full data & save ──────────────────────────────
svm.fit(X_scaled, y)

print("\nModel Parameters:")
print(f"  C (regularization)  : {svm.C}")
print(f"  Epsilon             : {svm.epsilon}")
print(f"  Max iterations      : {svm.max_iter}")

# FIXED: LinearSVR returns 1D array for coef_
print("\nFeature Coefficients (importance):")
if hasattr(svm, 'coef_'):
    # LinearSVR returns a 1D array, not a 2D array
    coefficients = svm.coef_ if len(svm.coef_.shape) == 1 else svm.coef_[0]
    for feat, coef in sorted(zip(FEATURE_COLS, coefficients),
                              key=lambda x: abs(x[1]), reverse=True):
        print(f"  {feat:<20} : {coef:+.4f}")
    print(f"  Intercept           : {svm.intercept_[0]:.4f}")
else:
    print("  Coefficients not available for this kernel")

# Save model, scaler, and training metrics
with open(MODEL_PATH, "wb") as f:
    pickle.dump({
        "model":           svm,
        "scaler":          scaler,
        "features":        FEATURE_COLS,
        "training_metrics": {
            "mae_cv_mean": float(-mae_cv.mean()),
            "rmse_cv_mean": float(-rmse_cv.mean()),
            "r2_cv_mean": float(r2_cv.mean()),
            "test_mae": float(mean_absolute_error(y_test, y_pred)),
            "test_rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "test_r2": float(r2_score(y_test, y_pred))
        }
    }, f)

print(f"\n✅ Model saved → {MODEL_PATH}")