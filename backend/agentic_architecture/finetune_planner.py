from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 1. Upload file
file = client.files.create(
    file=open("dataset/dataset_planner.jsonl", "rb"),   # make sure path is correct
    purpose="fine-tune"
)

print("File ID:", file.id)

# 2. Create fine-tuning job
job = client.fine_tuning.jobs.create(
    training_file=file.id,
    model="gpt-4o-mini-2024-07-18"   # ✅ FIXED MODEL
)

print("Fine-tune Job ID:", job.id)