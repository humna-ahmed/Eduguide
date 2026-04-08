# backend/agents/__init__.py

import asyncio
from agents import Runner
from .triage_agent import triage_agent
from .tools import set_tool_context


async def run_agent_query(
    user_query: str,
    student_id: int,
    db_connection
) -> str:
    try:
        # Set global context for tools
        set_tool_context(student_id, db_connection)

        # Run agent (NO tools argument)
        result = await Runner.run(
            triage_agent,
            user_query
        )

        return (
            result.final_output
            if hasattr(result, "final_output")
            else str(result)
        )

    except Exception as e:
        import traceback
        print("❌ AGENT ERROR:", str(e))
        print(traceback.format_exc())
        return "⚠️ Something went wrong while processing your request."


def run_agent_query_sync(
    user_query: str,
    student_id: int,
    db_connection
) -> str:
    try:
        return asyncio.run(
            run_agent_query(user_query, student_id, db_connection)
        )
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                run_agent_query(user_query, student_id, db_connection)
            )
        finally:
            loop.close()