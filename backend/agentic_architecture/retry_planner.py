from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Re-upload the planner dataset fresh (previous upload may be stale on OpenAI's end)
print("Re-uploading planner dataset...")
plan_file = client.files.create(
    file=open("dataset/dataset_planner_v2.jsonl", "rb"),
    purpose="fine-tune"
)
print(f"New Planner File ID: {plan_file.id}")

# Submit a new fine-tuning job
print("Creating new planner fine-tuning job...")
plan_job = client.fine_tuning.jobs.create(
    training_file=plan_file.id,
    model="gpt-4o-mini-2024-07-18",
    hyperparameters={"n_epochs": 3}
)
print(f"New Planner Job ID : {plan_job.id}")
print(f"Status             : {plan_job.status}")

# Update finetune_jobs.txt so check_status.py picks up the new job ID
jobs = {}
try:
    with open("finetune_jobs.txt") as f:
        for line in f:
            key, val = line.strip().split("=")
            jobs[key] = val
except FileNotFoundError:
    pass

jobs["PLANNER_JOB_ID"] = plan_job.id

with open("finetune_jobs.txt", "w") as f:
    for key, val in jobs.items():
        f.write(f"{key}={val}\n")

print("\nfinetune_jobs.txt updated with new planner job ID.")
print("Run check_status.py to monitor both jobs.")