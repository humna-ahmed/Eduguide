from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

job = client.fine_tuning.jobs.retrieve("ftjob-wjWXWGaDGZcra5jDcxjPHICt")

print("Status:", job.status)
print("Model:", job.fine_tuned_model)
print("Error:", job.error)