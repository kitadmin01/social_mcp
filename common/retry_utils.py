import time
import random
import logging
import asyncio

logger = logging.getLogger(__name__)

async def retry_with_backoff(fn, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay:.2f} seconds...")
            await asyncio.sleep(delay) 