import asyncio
from agents import Runner, RunConfig, OpenAIChatCompletionsModel, Agent
from openai import AsyncOpenAI
import nest_asyncio
nest_asyncio.apply()

external_client=AsyncOpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key="AIzaSyCXwq_BDPbEs52lYw1HhbsaETIqpbaDOAw"
)

model= OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=external_client
)

config=RunConfig(
    model=model
)

agent=Agent(name="math-teacher",
            instructions="you are a math expert, respond only math related questions!",
            model=model)


async def main():
    result = await Runner.run(
        starting_agent=agent,
        input="what is 2+2?",
        run_config=config
    )
    print(result.final_output)

asyncio.run(main())
