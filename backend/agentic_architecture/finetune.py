from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Delete old fine-tuned models (optional but keeps your account clean)
# ─────────────────────────────────────────────────────────────────────────────
# You cannot delete a fine-tuned MODEL via the Python SDK directly —
# do it from the OpenAI dashboard: https://platform.openai.com/finetune
# or via the API delete endpoint shown below (uncomment to run once):
#
# client.models.delete("ft:gpt-4o-mini-2024-07-18:personal::DUsZGTcV")  # old predictive
# client.models.delete("ft:gpt-4o-mini-2024-07-18:personal::DVVFYRLI")  # old planner
#
# NOTE: Deleting the model does NOT affect jobs or billing.
# Old uploaded files can be deleted too (also optional):
#
# client.files.delete("YOUR_OLD_GRADE_FILE_ID")
# client.files.delete("YOUR_OLD_PLANNER_FILE_ID")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Upload the new datasets
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("Uploading new prediction dataset...")
pred_file = client.files.create(
    file=open("dataset/grade_dataset_v2.jsonl", "rb"),
    purpose="fine-tune"
)
print(f"Prediction File ID : {pred_file.id}")

print("\nUploading new planner dataset...")
plan_file = client.files.create(
    file=open("dataset/dataset_planner_v2.jsonl", "rb"),
    purpose="fine-tune"
)
print(f"Planner File ID    : {plan_file.id}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Create fine-tuning jobs
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("Creating fine-tuning job for Prediction Agent...")
pred_job = client.fine_tuning.jobs.create(
    training_file=pred_file.id,
    model="gpt-4o-mini-2024-07-18",
    hyperparameters={
        "n_epochs": 4,          # more epochs = better learning on 514 records
    }
)
print(f"Prediction Job ID  : {pred_job.id}")
print(f"Status             : {pred_job.status}")

print("\nCreating fine-tuning job for Planner Agent...")
plan_job = client.fine_tuning.jobs.create(
    training_file=plan_file.id,
    model="gpt-4o-mini-2024-07-18",
    hyperparameters={
        "n_epochs": 3,
    }
)
print(f"Planner Job ID     : {plan_job.id}")
print(f"Status             : {plan_job.status}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Save job IDs so check_status.py can use them
# ─────────────────────────────────────────────────────────────────────────────

with open("finetune_jobs.txt", "w") as f:
    f.write(f"PREDICTION_JOB_ID={pred_job.id}\n")
    f.write(f"PLANNER_JOB_ID={plan_job.id}\n")

print("\n" + "=" * 60)
print("Job IDs saved to finetune_jobs.txt")
print("Run check_status.py to monitor progress.")
print("Fine-tuning usually takes 20–60 minutes depending on queue.")