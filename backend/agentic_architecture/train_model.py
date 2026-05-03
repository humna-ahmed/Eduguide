# agentic_architecture/train_model.py
"""
Train Linear Regression model on sem4_prediction_dataset.csv
Features: Quiz1-4, Quiz_Total, Assignment1-4, Assignment_Total, Midterm, Sessional_Total
Target:   Final_Exam (out of 50)

Run once: python train_model.py
Saves:    model/lr_predictor.pkl
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, KFold, train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "model", "sem4_dataset_clean.csv")
MODEL_PATH   = os.path.join(BASE_DIR, "model", "lr_predictor.pkl")
os.makedirs(os.path.join(BASE_DIR, "model"), exist_ok=True)

# ── Load ───────────────────────────────────────────────────
df = pd.read_csv(DATASET_PATH)
print(f"Rows: {len(df)}  |  Columns: {list(df.columns)}")
print(f"\nTarget (Final_Exam) stats:\n{df['Final_Exam'].describe().round(2)}")

# ── Features & Target ──────────────────────────────────────
# We use the totals only — individual quiz/assignment marks
# add noise without adding signal since the model sees totals anyway.
# Change this list if you want to include individual marks.
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
lr = LinearRegression()

mae_cv  = cross_val_score(lr, X_scaled, y, cv=kf,
                           scoring='neg_mean_absolute_error')
rmse_cv = cross_val_score(lr, X_scaled, y, cv=kf,
                           scoring='neg_root_mean_squared_error')
r2_cv   = cross_val_score(lr, X_scaled, y, cv=kf, scoring='r2')

print("\n" + "="*50)
print("5-FOLD CROSS VALIDATION")
print("="*50)
print(f"MAE  : {-mae_cv.mean():.3f} ± {mae_cv.std():.3f}  marks (out of 50)")
print(f"RMSE : {-rmse_cv.mean():.3f} ± {rmse_cv.std():.3f}")
print(f"R²   : {r2_cv.mean():.4f} ± {r2_cv.std():.4f}")

# ── Train/test split for final report ─────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42)

lr.fit(X_train, y_train)
y_pred = lr.predict(X_test)

print("\n" + "="*50)
print("TEST SET RESULTS (80/20 split)")
print("="*50)
print(f"MAE  : {mean_absolute_error(y_test, y_pred):.3f}")
print(f"RMSE : {np.sqrt(mean_squared_error(y_test, y_pred)):.3f}")
print(f"R²   : {r2_score(y_test, y_pred):.4f}")

# ── Train on full data & save ──────────────────────────────
lr.fit(X_scaled, y)

print("\nFeature Coefficients:")
for feat, coef in sorted(zip(FEATURE_COLS, lr.coef_),
                          key=lambda x: abs(x[1]), reverse=True):
    print(f"  {feat:<20} : {coef:+.4f}")
print(f"  Intercept           : {lr.intercept_:.4f}")

with open(MODEL_PATH, "wb") as f:
    pickle.dump({
        "model":    lr,
        "scaler":   scaler,
        "features": FEATURE_COLS,
    }, f)

print(f"\n✅ Model saved → {MODEL_PATH}")