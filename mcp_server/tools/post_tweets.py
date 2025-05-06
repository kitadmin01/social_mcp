# Placeholder for tweet generation using LLM

import os
import time
import random
import asyncio
from playwright.async_api import async_playwright, TimeoutError
import logging
from dotenv import load_dotenv, find_dotenv
from typing import Optional
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dotenv_path = find_dotenv()
print("Loading .env from:", dotenv_path)
load_dotenv(dotenv_path)

def is_x_server_running():
    """Check if X Server is running."""
    try:
        subprocess.run(['xdpyinfo'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except:
        return False

class TwitterPlaywright:
    def __init__(self):
        self.username = os.getenv('TWITTER_USERNAME')
        self.password = os.getenv('TWITTER_PASSWORD')
        # Check if X Server is running, if not, force headless mode
        self.headless = not is_x_server_running() or os.getenv('HEADLESS', 'true').lower() == 'true'
        self.browser = None
        self.context = None
        self.page = None
        self.is_logged_in = False
        self.max_retries = 3
        self.playwright = None
        print("Loaded Twitter username:", self.username)
        print("Loaded Twitter password:", self.password)
        print("Headless mode:", self.headless)
        if not self.headless and not is_x_server_running():
            print("Warning: X Server not detected, forcing headless mode")

    async def _init_browser(self):
        """Initialize the browser in headless mode."""
        try:
            logger.info("Starting Playwright...")
            self.playwright = await async_playwright().start()
            
            logger.info(f"Launching Chromium browser (headless={self.headless})...")
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1280,800',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            logger.info("Creating new browser context...")
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                ignore_https_errors=True
            )
            
            logger.info("Creating new page...")
            self.page = await self.context.new_page()
            
            # Set default timeout
            self.page.set_default_timeout(30000)
            self.page.set_default_navigation_timeout(30000)
            
            logger.info("Browser initialization complete")
            await self._login()
            
        except Exception as e:
            logger.error(f"Error initializing browser: {str(e)}")
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            raise

    async def _wait_for_selector(self, selector: str, timeout: int = 30000) -> Optional[any]:
        """Wait for a selector with retry logic."""
        for attempt in range(self.max_retries):
            try:
                element = await self.page.wait_for_selector(selector, timeout=timeout)
                if element:
                    return element
            except TimeoutError:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Timeout waiting for selector {selector}, attempt {attempt + 1}/{self.max_retries}")
                    await self.page.reload()
                    await self.page.wait_for_load_state('networkidle')
                else:
                    raise
        return None

    async def _login(self):
        """Login to Twitter with retry logic."""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Login attempt {attempt + 1}/{self.max_retries}")
                
                # Navigate to login page
                logger.info("Navigating to Twitter login page...")
                await self.page.goto('https://twitter.com/i/flow/login', wait_until='networkidle')
                await self.page.wait_for_timeout(5000)
                
                # Enter username
                logger.info("Entering username...")
                username_input = await self.page.wait_for_selector('input[autocomplete="username"]', timeout=60000)
                if not username_input:
                    raise Exception("Could not find username input field")
                await username_input.fill(self.username)
                await self.page.wait_for_timeout(2000)
                
                # Click Next button
                logger.info("Clicking Next button...")
                next_button = await self.page.wait_for_selector('[data-testid="LoginNextButton"]', timeout=10000)
                if not next_button:
                    raise Exception("Could not find Next button")
                await next_button.click()
                await self.page.wait_for_timeout(3000)
                
                # Enter password
                logger.info("Entering password...")
                password_input = await self.page.wait_for_selector('input[name="password"]', timeout=60000)
                if not password_input:
                    raise Exception("Could not find password input field")
                await password_input.fill(self.password)
                await self.page.wait_for_timeout(2000)
                
                # Click Login button
                logger.info("Clicking Login button...")
                login_button = await self.page.wait_for_selector('[data-testid="LoginForm_Login_Button"]', timeout=10000)
                if not login_button:
                    raise Exception("Could not find Login button")
                await login_button.click()
                
                # Wait for login to complete
                logger.info("Waiting for login to complete...")
                await self.page.wait_for_load_state('networkidle')
                await self.page.wait_for_timeout(8000)
                
                # Verify login success
                home_link = await self.page.wait_for_selector('a[href="/home"]', timeout=10000)
                if home_link:
                    logger.info("Successfully logged into Twitter")
                    self.is_logged_in = True
                    return
                else:
                    raise Exception("Login verification failed")
                    
            except TimeoutError as e:
                logger.error(f"Timeout during Twitter login attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info("Retrying login...")
                    await self.page.reload()
                    await self.page.wait_for_load_state('networkidle')
                else:
                    raise
            except Exception as e:
                logger.error(f"Error during Twitter login attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info("Retrying login...")
                    await self.page.reload()
                    await self.page.wait_for_load_state('networkidle')
                else:
                    raise

    async def post_tweet(self, text: str) -> bool:
        """Post a tweet to Twitter."""
        try:
            if not self.is_logged_in:
                await self._init_browser()
            
            # Click the tweet button
            logger.info("Clicking tweet button...")
            tweet_button = await self._wait_for_selector('a[href="/compose/tweet"]')
            if not tweet_button:
                raise Exception("Could not find tweet button")
            await tweet_button.click()
            await self.page.wait_for_load_state('networkidle')
            
            # Enter tweet text
            logger.info("Entering tweet text...")
            tweet_input = await self._wait_for_selector('div[role="textbox"]')
            if not tweet_input:
                raise Exception("Could not find tweet input field")
            await tweet_input.fill(text)
            await self.page.wait_for_timeout(2000)
            
            # Click post button
            logger.info("Clicking post button...")
            post_button = await self._wait_for_selector('div[role="button"]:has-text("Post")')
            if not post_button:
                raise Exception("Could not find post button")
            await post_button.click()
            await self.page.wait_for_load_state('networkidle')
            
            logger.info(f"Successfully posted tweet: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            return False

    async def like_blockchain_tweets(self, min_likes: int = 5, max_likes: int = 5) -> bool:
        """Like blockchain-related tweets."""
        try:
            if not self.is_logged_in:
                await self._init_browser()
            
            # Search for blockchain tweets
            logger.info("Searching for blockchain tweets...")
            await self.page.goto('https://twitter.com/search?q=blockchain&src=typed_query&f=live', wait_until='networkidle')
            await self.page.wait_for_timeout(5000)  # Increased wait time
            
            # Like tweets
            likes_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while likes_count < min_likes and scroll_attempts < max_scroll_attempts:
                # Find like buttons that haven't been clicked
                logger.info(f"Looking for like buttons (attempt {scroll_attempts + 1})...")
                like_buttons = await self.page.query_selector_all('div[role="button"][data-testid="like"]')
                
                if not like_buttons:
                    logger.info("No like buttons found, scrolling for more tweets...")
                    await self.page.evaluate('window.scrollBy(0, 1000)')
                    await self.page.wait_for_timeout(3000)  # Increased wait time
                    scroll_attempts += 1
                    continue
                
                for button in like_buttons:
                    if likes_count >= max_likes:
                        break
                    
                    try:
                        # Check if already liked
                        is_liked = await button.evaluate('''(button) => {
                            const svg = button.querySelector('svg');
                            return svg ? svg.getAttribute('fill') === 'rgb(249, 24, 128)' : false;
                        }''')
                        
                        if not is_liked:
                            await button.click()
                            likes_count += 1
                            logger.info(f"Liked tweet {likes_count}/{max_likes}")
                            await asyncio.sleep(2)  # Increased delay between likes
                    except Exception as e:
                        logger.error(f"Error liking tweet: {str(e)}")
                        continue
                
                # Scroll to load more tweets
                await self.page.evaluate('window.scrollBy(0, 1000)')
                await self.page.wait_for_timeout(3000)  # Increased wait time
                scroll_attempts += 1
            
            logger.info(f"Successfully liked {likes_count} tweets")
            return True
        except Exception as e:
            logger.error(f"Error in like_blockchain_tweets: {str(e)}")
            return False

    async def close_session(self):
        """Close the browser session."""
        try:
            logger.info("Closing browser session...")
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            self.context = None
            self.page = None
            self.is_logged_in = False
            logger.info("Successfully closed browser session")
        except Exception as e:
            logger.error(f"Error closing browser session: {str(e)}")
            raise

# Optionally, keep the generate_tweets function for LLM integration

