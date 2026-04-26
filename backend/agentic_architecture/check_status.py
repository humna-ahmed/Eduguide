from openai import OpenAI
import os
import time
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─────────────────────────────────────────────────────────────────────────────
# Read job IDs saved by finetune.py
# ─────────────────────────────────────────────────────────────────────────────

jobs = {}
try:
    with open("finetune_jobs.txt") as f:
        for line in f:
            key, val = line.strip().split("=")
            jobs[key] = val
except FileNotFoundError:
    print("finetune_jobs.txt not found. Run finetune.py first.")
    exit(1)

PRED_JOB_ID = jobs.get("PREDICTION_JOB_ID")
PLAN_JOB_ID = jobs.get("PLANNER_JOB_ID")

def check_job(label: str, job_id: str):
    job = client.fine_tuning.jobs.retrieve(job_id)
    print(f"\n{'=' * 50}")
    print(f"  {label}")
    print(f"{'=' * 50}")
    print(f"  Job ID   : {job_id}")
    print(f"  Status   : {job.status}")
    print(f"  Model    : {job.fine_tuned_model or '(not ready yet)'}")

    if job.error and job.error.message:
        print(f"  ⚠️  Error  : {job.error.message}")

    # Show last few training events for progress info
    events = client.fine_tuning.jobs.list_events(fine_tuning_job_id=job_id, limit=5)
    if events.data:
        print(f"  Latest events:")
        for e in reversed(events.data):
            print(f"    [{e.created_at}] {e.message}")

    return job

print("\nChecking fine-tuning job status...\n")

pred_job = check_job("PREDICTION AGENT", PRED_JOB_ID)
plan_job = check_job("PLANNER AGENT", PLAN_JOB_ID)

# ─────────────────────────────────────────────────────────────────────────────
# If both jobs succeeded, print the exact lines to paste into agent.py
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 50)
both_done = (
    pred_job.status == "succeeded" and pred_job.fine_tuned_model and
    plan_job.status == "succeeded" and plan_job.fine_tuned_model
)

if both_done:
    print("✅ Both jobs completed! Update agent.py with these model strings:\n")
    print(f'  predictive_ft_model = OpenAIChatCompletionsModel(')
    print(f'      model="{pred_job.fine_tuned_model}",')
    print(f'      openai_client=openai_client,')
    print(f'      temperature=0.0,')
    print(f'  )\n')
    print(f'  planner_ft_model = OpenAIChatCompletionsModel(')
    print(f'      model="{plan_job.fine_tuned_model}",')
    print(f'      openai_client=openai_client,')
    print(f'  )')
    print("\nCopy-paste those into agent.py and you're done.")
else:
    pending = []
    if pred_job.status not in ("succeeded", "failed"):
        pending.append("Prediction Agent")
    if plan_job.status not in ("succeeded", "failed"):
        pending.append("Planner Agent")
    if pending:
        print(f"⏳ Still running: {', '.join(pending)}")
        print("   Re-run this script in a few minutes to check again.")
    if pred_job.status == "failed" or plan_job.status == "failed":
        print("❌ One or more jobs failed. Check the error above.")