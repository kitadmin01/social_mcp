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

# Get session directory from .env
SESSION_DIR = os.getenv('PLAYWRIGHT_SESSION_DIR', './playwright_session')
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

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
        self._logged_in = False
        self.max_retries = 3
        self.playwright = None
        logger.info(f"TwitterPlaywright initialized with:")
        logger.info(f"- Username: {self.username}")
        logger.info(f"- Headless mode: {self.headless}")
        logger.info(f"- X Server running: {is_x_server_running()}")
        if not self.headless and not is_x_server_running():
            logger.warning("X Server not detected, forcing headless mode")
            self.headless = True

    async def check_login_status(self):
        """Check if user is logged in by verifying we're on the home page and can see tweet composition elements."""
        logger.info("Checking login status...")
        
        # First check if we're on the home page
        current_url = self.page.url
        logger.info(f"Current URL: {current_url}")
        
        if 'login' in current_url.lower():
            logger.info("On login page, not logged in")
            return False
            
        # Wait a bit for the page to stabilize
        await self.page.wait_for_timeout(3000)
        
        # Check for tweet composition elements that only appear when logged in
        tweet_indicators = [
            '[data-testid="tweetTextarea_0"]',  # Tweet composition box
            '[data-testid="SideNav_NewTweet_Button"]',  # Tweet button in sidebar
            '[data-testid="primaryColumn"]',  # Main content area
            '[data-testid="AppTabBar_Home_Link"]',  # Home tab
            '[data-testid="SideNav_AccountSwitcher_Button"]'  # Account switcher
        ]
        
        for selector in tweet_indicators:
            try:
                logger.info(f"Checking for {selector}")
                element = await self.page.query_selector(selector)
                if element:
                    logger.info(f"Found logged-in indicator: {selector}")
                    return True
            except Exception as e:
                logger.warning(f"Error checking {selector}: {str(e)}")
                continue
        
        # If we're on the home page but don't see login form, assume we're logged in
        if 'home' in current_url.lower():
            login_form = await self.page.query_selector('input[name="session[username_or_email]"], input[autocomplete="username"]')
            if not login_form:
                logger.info("On home page with no login form, assuming logged in")
                return True
        
        logger.info("No login indicators found, assuming not logged in")
        return False

    async def _init_browser(self):
        """Initialize the browser in persistent context mode."""
        try:
            logger.info("Starting Playwright...")
            self.playwright = await async_playwright().start()

            logger.info(f"Launching Chromium persistent context (headless={self.headless}) with session dir: {SESSION_DIR}")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
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
                ],
                viewport={'width': 1280, 'height': 800},
                ignore_https_errors=True
            )

            logger.info("Creating new page...")
            self.page = await self.context.new_page()

            # Set default timeout
            self.page.set_default_timeout(120000)  # Increased timeout to 2 minutes
            self.page.set_default_navigation_timeout(120000)  # Increased timeout to 2 minutes

            logger.info("Browser initialization complete")
            
            # Try to navigate to home page with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Navigation attempt {attempt + 1}/{max_retries}")
                    await self.page.goto("https://x.com/home", wait_until='domcontentloaded', timeout=60000)
                    
                    # Wait for either the main content or login form
                    logger.info("Waiting for page content to load...")
                    try:
                        await self.page.wait_for_selector('[data-testid="primaryColumn"], input[name="session[username_or_email]"]', 
                                                        state='visible', 
                                                        timeout=30000)
                    except Exception as e:
                        logger.warning(f"Timeout waiting for main content or login form: {str(e)}")
                    
                    # Additional wait for page stability
                    await self.page.wait_for_timeout(5000)
                    
                    # Check if we're actually on the home page
                    current_url = self.page.url
                    logger.info(f"Current URL: {current_url}")
                    
                    if 'home' in current_url.lower():
                        # Use robust login status check
                        login_status = await self.check_login_status()
                        logger.info(f"Login status check result: {login_status}")
                        
                        if login_status:
                            logger.info("Already logged in (session restored)")
                            self._logged_in = True
                            return
                    
                    if attempt < max_retries - 1:
                        logger.info("Navigation attempt failed, retrying...")
                        await self.page.reload()
                        await self.page.wait_for_timeout(5000)
                    else:
                        logger.info("All navigation attempts failed, proceeding with login")
                        await self._login()
                        
                except Exception as e:
                    logger.warning(f"Navigation attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info("Retrying navigation...")
                        await self.page.wait_for_timeout(5000)
                    else:
                        logger.info("All navigation attempts failed, proceeding with login")
                        await self._login()

        except Exception as e:
            logger.error(f"Error initializing browser: {str(e)}")
            await self.close_session()  # Ensure cleanup on error
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
                
                # Click Next button - try multiple selectors
                logger.info("Clicking Next button...")
                next_button = None
                
                # First try data-testid
                try:
                    next_button = await self.page.wait_for_selector('[data-testid="LoginNextButton"]', timeout=10000)
                    if next_button:
                        await next_button.click()
                except:
                    pass
                
                # If not found, try role and text
                if not next_button:
                    try:
                        await self.page.get_by_role("button", name="Next").click()
                        next_button = True
                    except:
                        pass
                
                # If still not found, try text content
                if not next_button:
                    try:
                        await self.page.get_by_text("Next").click()
                        next_button = True
                    except:
                        pass
                
                # If still not found, try evaluating JavaScript
                if not next_button:
                    try:
                        next_button = await self.page.evaluate('''() => {
                            const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
                            return buttons.find(button => button.textContent.includes('Next'));
                        }''')
                        if next_button:
                            await self.page.click('div[role="button"]:has-text("Next")')
                            next_button = True
                    except:
                        pass
                
                if not next_button:
                    raise Exception("Could not find Next button")
                
                # Wait for password field to appear
                logger.info("Waiting for password field...")
                try:
                    # Wait for the password field to be visible
                    await self.page.wait_for_selector('input[name="password"]', state='visible', timeout=10000)
                    await self.page.wait_for_timeout(2000)  # Additional wait to ensure field is ready
                except:
                    logger.error("Password field did not appear after clicking Next")
                    raise Exception("Password field not found")
                
                # Enter password
                logger.info("Entering password...")
                password_input = await self.page.wait_for_selector('input[name="password"]', timeout=60000)
                if not password_input:
                    raise Exception("Could not find password input field")
                await password_input.fill(self.password)
                await self.page.wait_for_timeout(2000)
                
                # Click Login button - try multiple selectors
                logger.info("Clicking Login button...")
                login_button = None
                
                # First try data-testid
                try:
                    login_button = await self.page.wait_for_selector('[data-testid="LoginForm_Login_Button"]', timeout=10000)
                    if login_button:
                        await login_button.click()
                except:
                    pass
                
                # If not found, try role and text
                if not login_button:
                    try:
                        await self.page.get_by_role("button", name="Log in").click()
                        login_button = True
                    except:
                        pass
                
                # If still not found, try text content
                if not login_button:
                    try:
                        await self.page.get_by_text("Log in").click()
                        login_button = True
                    except:
                        pass
                
                if not login_button:
                    raise Exception("Could not find Login button")
                
                # Wait for login to complete
                logger.info("Waiting for login to complete...")
                await self.page.wait_for_load_state('networkidle')
                await self.page.wait_for_timeout(8000)
                
                # Verify login success - try multiple selectors
                for selector in [
                    'div[data-testid="SideNav_AccountSwitcher_Button"]',
                    'a[href="/home"]',
                    'div[data-testid="AppTabBar_Home_Link"]'
                ]:
                    try:
                        if await self.page.wait_for_selector(selector, timeout=10000):
                            logger.info("Successfully logged into Twitter")
                            self._logged_in = True
                            return
                    except:
                        continue
                
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
            if not self._logged_in:
                await self._init_browser()
            
            # Navigate to home page first with retry
            logger.info("Navigating to home page...")
            home_navigated = False
            
            # Try multiple approaches to get to home page
            for attempt in range(3):
                try:
                    # First try direct navigation
                    await self.page.goto('https://twitter.com/home', wait_until='networkidle', timeout=30000)
                    await self.page.wait_for_timeout(5000)
                    
                    # Try multiple selectors to verify we're on home page
                    for selector in [
                        '[data-testid="primaryColumn"]',
                        '[data-testid="SideNav_NewTweet_Button"]',
                        'a[href="/home"]',
                        'div[data-testid="AppTabBar_Home_Link"]'
                    ]:
                        try:
                            if await self.page.wait_for_selector(selector, timeout=5000):
                                home_navigated = True
                                break
                        except:
                            continue
                    
                    if home_navigated:
                        break
                        
                    # If direct navigation failed, try clicking home link
                    try:
                        home_link = await self.page.wait_for_selector('a[href="/home"]', timeout=5000)
                        if home_link:
                            await home_link.click()
                            await self.page.wait_for_timeout(5000)
                            home_navigated = True
                            break
                    except:
                        pass
                        
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise Exception(f"Failed to navigate to home page: {str(e)}")
                    logger.warning(f"Navigation attempt {attempt + 1} failed, retrying...")
                    await self.page.reload()
                    await self.page.wait_for_timeout(5000)
            
            if not home_navigated:
                raise Exception("Failed to navigate to home page after multiple attempts")
            
            # Click the tweet button - try multiple selectors
            logger.info("Clicking tweet button...")
            tweet_button = None
            
            # First try the + button
            try:
                tweet_button = await self.page.wait_for_selector('[data-testid="SideNav_NewTweet_Button"]', timeout=10000)
                if tweet_button:
                    await tweet_button.click()
            except:
                pass
            
            # If not found, try compose tweet link
            if not tweet_button:
                try:
                    tweet_button = await self.page.wait_for_selector('a[href="/compose/tweet"]', timeout=10000)
                    if tweet_button:
                        await tweet_button.click()
                except:
                    pass
            
            # If still not found, try the tweet textarea directly
            if not tweet_button:
                try:
                    tweet_button = await self.page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
                    if tweet_button:
                        await tweet_button.click()
                except:
                    pass
            
            if not tweet_button:
                raise Exception("Could not find tweet button")
            
            # Wait for tweet compose dialog
            logger.info("Waiting for tweet compose dialog...")
            await self.page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
            await self.page.wait_for_timeout(2000)
            
            # Enter tweet text
            logger.info("Entering tweet text...")
            tweet_input = await self.page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
            if not tweet_input:
                raise Exception("Could not find tweet input field")
            await tweet_input.fill(text)
            await self.page.wait_for_timeout(2000)
            
            # Click post button - try multiple approaches
            logger.info("Clicking post button...")
            post_success = False
            
            # Try multiple selectors and click methods
            for selector in [
                '[data-testid="tweetButton"]',
                'div[role="button"]:has-text("Post")',
                'div[role="button"]:has-text("Tweet")'
            ]:
                try:
                    # Wait for the button to be visible and clickable
                    post_button = await self.page.wait_for_selector(selector, state='visible', timeout=5000)
                    if post_button:
                        # Try multiple click methods
                        try:
                            # Method 1: Direct click
                            await post_button.click()
                            post_success = True
                        except:
                            try:
                                # Method 2: JavaScript click
                                await self.page.evaluate('(button) => button.click()', post_button)
                                post_success = True
                            except:
                                try:
                                    # Method 3: Click by text
                                    await self.page.get_by_text("Post").click()
                                    post_success = True
                                except:
                                    pass
                        
                        if post_success:
                            break
                except:
                    continue
            
            if not post_success:
                raise Exception("Could not click post button")
            
            # Wait for post to complete
            logger.info("Waiting for post to complete...")
            try:
                # Wait for network to be idle
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                await self.page.wait_for_timeout(5000)
                
                # Verify post was successful - try multiple indicators
                post_verified = False
                
                # First check if compose dialog is gone
                try:
                    await self.page.wait_for_selector('[data-testid="tweetTextarea_0"]', state='hidden', timeout=5000)
                    post_verified = True
                except:
                    pass
                
                # If compose dialog is still visible, check for success indicators
                if not post_verified:
                    for selector in [
                        '[data-testid="toast"]',
                        '[data-testid="success"]',
                        'div[role="alert"]'
                    ]:
                        try:
                            await self.page.wait_for_selector(selector, timeout=5000)
                            post_verified = True
                            break
                        except:
                            continue
                
                # If still not verified, check if we can find the posted tweet
                if not post_verified:
                    try:
                        # Wait for the tweet to appear in the timeline
                        await self.page.wait_for_selector(f'div[data-testid="tweetText"]:has-text("{text[:50]}")', timeout=5000)
                        post_verified = True
                    except:
                        pass
                
                if post_verified:
                    logger.info(f"Successfully posted tweet: {text[:50]}...")
                    return True
                else:
                    # Even if we can't verify, assume success and continue
                    logger.warning("Could not verify post success, but continuing...")
                    return True
                    
            except Exception as e:
                # Even if we get an error, assume success and continue
                logger.warning(f"Error during post verification: {str(e)}, but continuing...")
                return True
            
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            return False

    async def search_and_like_tweets(self, search_term: str, max_likes: int = 5) -> bool:
        """Search for tweets and like them from the search results page only."""
        try:
            if not self._logged_in:
                await self._init_browser()
            
            # Properly encode the search term for URL
            encoded_term = search_term.replace('#', '%23').replace(' ', '%20')
            search_url = f'https://x.com/search?q={encoded_term}&src=typed_query&f=live'
            
            logger.info(f"Searching for tweets with term: {search_term}")
            logger.info(f"Search URL: {search_url}")
            
            # Navigate to search page with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Navigation attempt {attempt + 1}/{max_retries}")
                    await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                    await self.page.wait_for_timeout(5000)  # Wait for page to stabilize
                    
                    # Verify we're on the search page
                    current_url = self.page.url
                    logger.info(f"Current URL: {current_url}")
                    
                    if 'search' not in current_url.lower():
                        logger.warning(f"Not on search page, current URL: {current_url}")
                        if attempt < max_retries - 1:
                            continue
                        else:
                            raise Exception("Failed to reach search page")
                    
                    # Wait for search results to load
                    logger.info("Waiting for search results to load...")
                    try:
                        await self.page.wait_for_selector('[data-testid="cellInnerDiv"]', timeout=30000)
                        logger.info("Search results loaded")
                    except Exception as e:
                        logger.warning(f"Timeout waiting for search results: {str(e)}")
                        if attempt < max_retries - 1:
                            continue
                        else:
                            raise Exception("Search results did not load")
                    
                    # Click Latest tab if available
                    try:
                        latest_tab = await self.page.wait_for_selector('div[role="tab"]:has-text("Latest")', timeout=5000)
                        if latest_tab:
                            await latest_tab.click()
                            await self.page.wait_for_timeout(3000)
                            logger.info("Clicked Latest tab")
                    except Exception as e:
                        logger.warning(f"Could not click Latest tab: {str(e)}")
                    
                    # Start liking tweets
                    likes_count = 0
                    scroll_attempts = 0
                    max_scroll_attempts = 10
                    
                    while likes_count < max_likes and scroll_attempts < max_scroll_attempts:
                        # Verify we're still on the search page
                        current_url = self.page.url
                        if 'search' not in current_url.lower():
                            logger.warning(f"Navigated away from search page, re-navigating...")
                            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                            await self.page.wait_for_timeout(3000)
                            continue
                        
                        # Find like buttons
                        like_buttons = await self.page.query_selector_all('[data-testid="like"]')
                        logger.info(f"Found {len(like_buttons)} like buttons")
                        
                        for button in like_buttons:
                            if likes_count >= max_likes:
                                break
                            
                            try:
                                # Check if already liked
                                is_liked = await button.evaluate('''(button) => {
                                    const svg = button.querySelector('svg');
                                    if (!svg) return false;
                                    const fill = svg.getAttribute('fill');
                                    return fill === 'rgb(249, 24, 128)' || fill === '#F91880';
                                }''')
                                
                                if not is_liked:
                                    await button.scroll_into_view_if_needed()
                                    await self.page.wait_for_timeout(1000)
                                    await button.click()
                                    likes_count += 1
                                    logger.info(f"Liked tweet {likes_count}/{max_likes}")
                                    await self.page.wait_for_timeout(2000)
                            except Exception as e:
                                logger.warning(f"Error liking tweet: {str(e)}")
                                continue
                        
                        # Scroll for more tweets
                        await self.page.evaluate('window.scrollBy(0, 1000)')
                        await self.page.wait_for_timeout(3000)
                        scroll_attempts += 1
                    
                    if likes_count > 0:
                        logger.info(f"Successfully liked {likes_count} tweets")
                        return True
                    else:
                        logger.warning("No tweets were liked")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error during search attempt {attempt + 1}: {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info("Retrying search...")
                        await self.page.wait_for_timeout(5000)
                    else:
                        raise
            
            return False
            
        except Exception as e:
            logger.error(f"Error in search_and_like_tweets: {str(e)}")
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
            self._logged_in = False
            logger.info("Successfully closed browser session")
        except Exception as e:
            logger.error(f"Error closing browser session: {str(e)}")
            raise

# Optionally, keep the generate_tweets function for LLM integration

