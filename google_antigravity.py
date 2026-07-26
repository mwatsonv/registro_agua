import os
from dotenv import load_dotenv
from google.antigravity import Agent as RealAgent, LocalAgentConfig, CapabilitiesConfig
from google.antigravity.hooks import policy

# Automatically load environment variables from the project .env file
load_dotenv()

class CallableString(str):
    def __call__(self):
        return self

class ChatResponseWrapper:
    def __init__(self, real_response):
        self._real_response = real_response

    @property
    def text(self):
        val = self._real_response.text()
        return CallableString(val)

    @property
def structured_output(self):
    return getattr(self._real_response, "structured_output", None)

    def __getattr__(self, name):
        return getattr(self._real_response, name)

    def __aiter__(self):
        return self._real_response.__aiter__()

class Agent(RealAgent):
    """
    A wrapper class to map user-facing google_antigravity.Agent syntax
    to the underlying google.antigravity SDK structure.
    """
    def __init__(self, model="gemini-1.5-flash", system_instruction=None, **kwargs):
        api_key = os.getenv("GEMINI_API_KEY")
        
        # Configure capabilities to allow all policies by default
        config = LocalAgentConfig(
            model=model,
            system_instructions=system_instruction,
            api_key=api_key,
            policies=[policy.allow_all()],
            **kwargs
        )
        super().__init__(config)

    async def run(self, prompt: str, attachments=None, **kwargs):
        # Ensure session is started
        if not self.is_started:
            await self.__aenter__()

        from google.antigravity import types

        content_parts = [prompt]
        if attachments:
            for att in attachments:
                if hasattr(att, "read") and hasattr(att, "content_type"):
                    content_bytes = await att.read()
                    if hasattr(att, "seek"):
                        await att.seek(0)
                    if content_bytes:
                        media = types.from_bytes(
                            content_bytes,
                            att.content_type,
                            description=getattr(att, "filename", None)
                        )
                        content_parts.append(media)
                else:
                    content_parts.append(att)

        input_content = content_parts[0] if len(content_parts) == 1 else content_parts
        real_response = await self.chat(input_content)
        return ChatResponseWrapper(real_response)

    async def chat(self, prompt, **kwargs):
        real_response = await super().chat(prompt, **kwargs)
        return ChatResponseWrapper(real_response)
