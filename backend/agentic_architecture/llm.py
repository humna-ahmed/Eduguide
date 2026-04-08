import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

class GeminiLLM:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY missing")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )

        # ✅ Correct Gemini model
        self.model_name = "gemini-2.5-flash"

    async def complete(self, prompt: str) -> str:
        response = await self.client.responses.create(
            model=self.model_name,
            input=prompt
        )

        return response.output_text
