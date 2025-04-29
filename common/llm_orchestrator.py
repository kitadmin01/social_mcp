import os
from openai import OpenAI
import aiohttp
import logging

logger = logging.getLogger(__name__)

class LLMOrchestrator:
    def __init__(self, provider: str = 'openai'):
        self.provider = provider.lower()
        if self.provider == 'openai':
            self.api_key = os.getenv('OPENAI_API_KEY')
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self.client = OpenAI(api_key=self.api_key)
        elif self.provider == 'ollama':
            self.ollama_url = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def generate_content(self, prompt: str, model: str = 'gpt-3.5-turbo'):
        logger.info(f"Generating content with {self.provider} using model {model}")
        if self.provider == 'openai':
            return await self._generate_openai(prompt, model)
        elif self.provider == 'ollama':
            return await self._generate_ollama(prompt, model)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_openai(self, prompt: str, model: str):
        try:
            # OpenAI's create method is not async, so we need to run it in a thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating content with OpenAI: {str(e)}")
            raise

    async def _generate_ollama(self, prompt: str, model: str):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.ollama_url}/api/generate"
                payload = {"model": model, "prompt": prompt}
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get('response', '')
        except Exception as e:
            logger.error(f"Error generating content with Ollama: {str(e)}")
            raise 