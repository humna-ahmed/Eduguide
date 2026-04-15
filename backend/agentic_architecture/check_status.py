from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

job = client.fine_tuning.jobs.retrieve("ftjob-NVg3Y4xd2r8BJNyVQ27Wqm4K")

print("Status:", job.status)
print("Model:", job.fine_tuned_model)
print("Error:", job.error)