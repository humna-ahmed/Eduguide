# backend/agents/patched_agent.py

from agents import Agent as OriginalAgent
from typing import Optional, Any

class PatchedAgent(OriginalAgent):
    """Patched Agent class that accepts custom models"""
    
    def __post_init__(self):
        # Skip validation for custom models
        if hasattr(self.model, 'create_chat_completion'):
            # It's a custom model like GeminiModelSettings
            # Just store it as-is
            pass
        else:
            # Use original validation for OpenAI models
            super().__post_init__()

# Monkey patch the original Agent class
import agents
agents.Agent = PatchedAgent
print("✅ Successfully patched Agent class")