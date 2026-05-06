# agentic_architecture/check_accuracy.py
"""
Comprehensive accuracy report for the SVM predictor.
Run: python check_accuracy.py
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    mean_absolute_percentage_error,
)
from sklearn.model_selection import cross_val_score, KFold

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH   = os.path.join(BASE_DIR, "model", "svm_predictor.pkl")
DATASET_PATH = os.path.join(BASE_DIR, "model", "student_performance_dataset (3).csv")


def load_bundle():
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def section(title):
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print(f"{'═' * 55}")


def grade_from_total(total: float) -> str:
    if total >= 85:  return "A"
    if total >= 80:  return "A-"
    if total >= 75:  return "B+"
    if total >= 70:  return "B"
    if total >= 65:  return "B-"
    if total >= 60:  return "C+"
    if total >= 55:  return "C"
    if total >= 50:  return "C-"
    if total >= 45:  return "D+"
    if total >= 40:  return "D"
    return "F"


# ── 1. Load everything ─────────────────────────────────────
bundle   = load_bundle()
model    = bundle["model"]
scaler   = bundle["scaler"]
features = bundle["features"]
saved    = bundle["training_metrics"]

df = pd.read_csv(DATASET_PATH)
X  = df[features].values
y  = df["Final_Exam"].values

X_scaled = scaler.transform(X)
y_pred   = model.predict(X_scaled)
y_pred   = np.clip(np.round(y_pred).astype(int), 5, 50)


# ── 2. Saved training metrics ──────────────────────────────
section("SAVED TRAINING METRICS (from train_model.py)")
print(f"  Cross-Val MAE  : {saved['mae_cv_mean']:.3f} marks")
print(f"  Cross-Val RMSE : {saved['rmse_cv_mean']:.3f}")
print(f"  Cross-Val R²   : {saved['r2_cv_mean']:.4f}")
print(f"  Test MAE       : {saved['test_mae']:.3f} marks")
print(f"  Test RMSE      : {saved['test_rmse']:.3f}")
print(f"  Test R²        : {saved['test_r2']:.4f}")


# ── 3. Full dataset metrics ────────────────────────────────
section("FULL DATASET METRICS (all rows)")
mae  = mean_absolute_error(y, y_pred)
rmse = np.sqrt(mean_squared_error(y, y_pred))
r2   = r2_score(y, y_pred)
mape = mean_absolute_percentage_error(y, y_pred) * 100

print(f"  Total samples  : {len(y)}")
print(f"  MAE            : {mae:.3f} marks   ← avg error per prediction")
print(f"  RMSE           : {rmse:.3f} marks")
print(f"  R²             : {r2:.4f}          ← 1.0 = perfect")
print(f"  MAPE           : {mape:.2f}%       ← avg % error")


# ── 4. Error distribution ──────────────────────────────────
section("ERROR DISTRIBUTION")
errors     = np.abs(y - y_pred)
within_1   = np.mean(errors <= 1)  * 100
within_2   = np.mean(errors <= 2)  * 100
within_3   = np.mean(errors <= 3)  * 100
within_5   = np.mean(errors <= 5)  * 100
over_5     = np.mean(errors >  5)  * 100

print(f"  Within ±1 mark : {within_1:.1f}%")
print(f"  Within ±2 marks: {within_2:.1f}%")
print(f"  Within ±3 marks: {within_3:.1f}%")
print(f"  Within ±5 marks: {within_5:.1f}%")
print(f"  Over   ±5 marks: {over_5:.1f}%   ← concerning if high")
print(f"\n  Max error      : {errors.max():.0f} marks")
print(f"  Min error      : {errors.min():.0f} marks")
print(f"  Median error   : {np.median(errors):.1f} marks")


# ── 5. Grade prediction accuracy ──────────────────────────
section("GRADE PREDICTION ACCURACY")

# Recreate sessional totals from dataset
# Sessional = Quiz_Total + Assignment_Total + Midterm
sessional = df["Quiz_Total"] + df["Assignment_Total"] + df["Midterm"]

actual_grades    = [grade_from_total(s + fe)
                    for s, fe in zip(sessional, y)]
predicted_grades = [grade_from_total(s + pe)
                    for s, pe in zip(sessional, y_pred)]

exact_match  = sum(a == p for a, p in zip(actual_grades, predicted_grades))
within_1_grd = 0

grade_order = ["F","D","D+","C-","C","C+","B-","B","B+","A-","A"]

for a, p in zip(actual_grades, predicted_grades):
    if abs(grade_order.index(a) - grade_order.index(p)) <= 1:
        within_1_grd += 1

print(f"  Exact grade match     : {exact_match}/{len(y)} "
      f"({exact_match/len(y)*100:.1f}%)")
print(f"  Within 1 grade band   : {within_1_grd}/{len(y)} "
      f"({within_1_grd/len(y)*100:.1f}%)")

# Grade-by-grade breakdown
from collections import Counter
print(f"\n  Actual grade distribution:")
for g in grade_order:
    count = actual_grades.count(g)
    if count:
        bar = "█" * (count // max(1, len(y) // 40))
        print(f"    {g:<4}: {count:>4}  {bar}")


# ── 6. Fresh 5-fold cross validation ──────────────────────
section("FRESH 5-FOLD CROSS VALIDATION")
kf      = KFold(n_splits=5, shuffle=True, random_state=99)  # different seed
mae_cv  = cross_val_score(model, X_scaled, y,
                           cv=kf, scoring='neg_mean_absolute_error')
r2_cv   = cross_val_score(model, X_scaled, y,
                           cv=kf, scoring='r2')

print(f"  MAE per fold   : {[-round(m,2) for m in mae_cv]}")
print(f"  Avg MAE        : {-mae_cv.mean():.3f} ± {mae_cv.std():.3f}")
print(f"  Avg R²         : {r2_cv.mean():.4f} ± {r2_cv.std():.4f}")
print()
if mae_cv.std() > 1.5:
    print("  ⚠️  High variance across folds — model may be unstable")
else:
    print("  ✅ Low variance across folds — model is stable")


# ── 7. Prediction vs actual sample ────────────────────────
section("SAMPLE: ACTUAL vs PREDICTED (first 15 rows)")
print(f"  {'#':<4} {'Actual':>7} {'Predicted':>10} {'Error':>7} {'Grade A':>8} {'Grade P':>8}")
print(f"  {'-'*50}")
for i in range(min(15, len(y))):
    err   = y_pred[i] - y[i]
    match = "✅" if actual_grades[i] == predicted_grades[i] else "❌"
    print(f"  {i+1:<4} {y[i]:>7} {y_pred[i]:>10} "
          f"  {err:>+5}   {actual_grades[i]:>6}   "
          f"{predicted_grades[i]:>6} {match}")


# ── 8. Your student's data check ──────────────────────────
section("YOUR STUDENT's PREDICTED SCORES CHECK")

student_courses = [
    {"name": "Operating Systems",            "quiz": 6.3, "assign": 13.2, "mid": 14.1},
    {"name": "Database Management Systems",  "quiz": 6.4, "assign": 13.2, "mid": 14.0},
    {"name": "Software Design & Arch",       "quiz": 6.5, "assign": 13.2, "mid": 13.8},
    {"name": "Design & Analysis Algorithms", "quiz": 6.9, "assign": 13.6, "mid": 12.3},
]

print(f"  {'Course':<35} {'Sessional':>10} {'Pred Final':>11} {'Total':>7} {'Grade':>6}")
print(f"  {'-'*70}")

for c in student_courses:
    inp      = np.array([[c["quiz"], c["assign"], c["mid"]]])
    inp_sc   = scaler.transform(inp)
    pred     = model.predict(inp_sc)[0]
    pred     = max(5, min(50, round(float(pred))))
    sessional_total = c["quiz"] + c["assign"] + c["mid"]
    total    = sessional_total + pred
    grade    = grade_from_total(total)
    print(f"  {c['name']:<35} {sessional_total:>10.1f} {pred:>11} "
          f"{total:>7.1f} {grade:>6}")

# ── 9. Overall verdict ─────────────────────────────────────
section("VERDICT")
if r2 >= 0.85 and mae <= 3:
    verdict = "🟢 EXCELLENT — model is highly accurate"
elif r2 >= 0.70 and mae <= 5:
    verdict = "🟡 GOOD — acceptable for grade prediction"
elif r2 >= 0.50:
    verdict = "🟠 MODERATE — usable but consider retraining"
else:
    verdict = "🔴 POOR — model needs improvement"

print(f"\n  {verdict}")
print(f"\n  R² = {r2:.4f}  |  MAE = {mae:.2f} marks  |  "
      f"Grade Accuracy = {exact_match/len(y)*100:.1f}%")
print()