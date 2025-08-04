# Multi-account Twitter Playwright implementation

import os
import time
import random
import asyncio
from playwright.async_api import async_playwright, TimeoutError
import logging
from dotenv import load_dotenv, find_dotenv
from typing import Optional, Dict, List
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

class MultiTwitterPlaywright:
    def __init__(self):
        # Initialize multiple Twitter accounts
        self.accounts = {
            'primary': {
                'username': os.getenv('TWITTER_USERNAME'),
                'password': os.getenv('TWITTER_PASSWORD'),
                'session_dir': os.path.join(SESSION_DIR, 'primary')
            },
            'secondary': {
                'username': os.getenv('TWITTER_USERNAME_2'),
                'password': os.getenv('TWITTER_PASSWORD_2'),
                'session_dir': os.path.join(SESSION_DIR, 'secondary')
            }
        }
        
        # Create session directories for each account
        for account_name, account_data in self.accounts.items():
            if not os.path.exists(account_data['session_dir']):
                os.makedirs(account_data['session_dir'])
        
        # Check if X Server is running, if not, force headless mode
        self.headless = not is_x_server_running() or os.getenv('HEADLESS', 'true').lower() == 'true'
        self.browsers = {}
        self.contexts = {}
        self.pages = {}
        self._logged_in = {}
        self.max_retries = 3
        self.playwright = None
        
        logger.info(f"MultiTwitterPlaywright initialized with:")
        for account_name, account_data in self.accounts.items():
            logger.info(f"- {account_name}: {account_data['username']}")
        logger.info(f"- Headless mode: {self.headless}")
        logger.info(f"- X Server running: {is_x_server_running()}")
        
        if not self.headless and not is_x_server_running():
            logger.warning("X Server not detected, forcing headless mode")
            self.headless = True

    async def check_login_status(self, account_name: str):
        """Check if user is logged in by verifying we're on the home page and can see tweet composition elements."""
        logger.info(f"Checking login status for {account_name}...")
        
        page = self.pages.get(account_name)
        if not page:
            logger.error(f"No page found for account {account_name}")
            return False
        
        # First check if we're on the home page
        current_url = page.url
        logger.info(f"Current URL for {account_name}: {current_url}")
        
        if 'login' in current_url.lower():
            logger.info(f"On login page for {account_name}, not logged in")
            return False
            
        # Wait a bit for the page to stabilize
        await page.wait_for_timeout(3000)
        
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
                logger.info(f"Checking for {selector} on {account_name}")
                element = await page.query_selector(selector)
                if element:
                    logger.info(f"Found logged-in indicator: {selector} for {account_name}")
                    return True
            except Exception as e:
                logger.warning(f"Error checking {selector} for {account_name}: {str(e)}")
                continue
        
        # If we're on the home page but don't see login form, assume we're logged in
        if 'home' in current_url.lower():
            login_form = await page.query_selector('input[name="session[username_or_email]"], input[autocomplete="username"]')
            if not login_form:
                logger.info(f"On home page with no login form for {account_name}, assuming logged in")
                return True
        
        logger.info(f"No login indicators found for {account_name}, assuming not logged in")
        return False

    async def _init_browser(self, account_name: str):
        """Initialize the browser in persistent context mode for a specific account."""
        try:
            account_data = self.accounts[account_name]
            session_dir = account_data['session_dir']
            
            logger.info(f"Initializing browser for {account_name} with session dir: {session_dir}")
            
            self.playwright = await async_playwright().start()
            
            # Launch browser with persistent context
            self.browsers[account_name] = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=session_dir,
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
            
            self.contexts[account_name] = self.browsers[account_name]
            self.pages[account_name] = await self.contexts[account_name].new_page()
            
            # Set default timeouts
            self.pages[account_name].set_default_timeout(120000)
            self.pages[account_name].set_default_navigation_timeout(120000)
            
            logger.info(f"Browser initialized for {account_name}")
            
            # Try to navigate to home page and check for existing session
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Navigation attempt {attempt + 1}/{max_retries} for {account_name}")
                    await self.pages[account_name].goto("https://x.com/home", wait_until='domcontentloaded', timeout=60000)
                    
                    # Wait for either the main content or login form
                    logger.info(f"Waiting for page content to load for {account_name}...")
                    try:
                        await self.pages[account_name].wait_for_selector('[data-testid="primaryColumn"], input[name="session[username_or_email]"]', 
                                                        state='visible', 
                                                        timeout=30000)
                    except Exception as e:
                        logger.warning(f"Timeout waiting for main content or login form for {account_name}: {str(e)}")
                    
                    # Additional wait for page stability
                    await self.pages[account_name].wait_for_timeout(5000)
                    
                    # Check if we're actually on the home page
                    current_url = self.pages[account_name].url
                    logger.info(f"Current URL for {account_name}: {current_url}")
                    
                    if 'home' in current_url.lower():
                        # Use robust login status check
                        login_status = await self.check_login_status(account_name)
                        logger.info(f"Login status check result for {account_name}: {login_status}")
                        
                        if login_status:
                            logger.info(f"Already logged in for {account_name} (session restored)")
                            self._logged_in[account_name] = True
                            return True
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Navigation attempt failed for {account_name}, retrying...")
                        await self.pages[account_name].reload()
                        await self.pages[account_name].wait_for_timeout(5000)
                    else:
                        logger.info(f"All navigation attempts failed for {account_name}, will need to login")
                        
                except Exception as e:
                    logger.warning(f"Navigation attempt {attempt + 1} failed for {account_name}: {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying navigation for {account_name}...")
                        await self.pages[account_name].wait_for_timeout(5000)
                    else:
                        logger.info(f"All navigation attempts failed for {account_name}, will need to login")
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing browser for {account_name}: {str(e)}")
            return False

    async def _wait_for_selector(self, selector: str, timeout: int = 30000, account_name: str = 'primary') -> Optional[any]:
        """Wait for a selector to appear on the page."""
        try:
            page = self.pages.get(account_name)
            if not page:
                logger.error(f"No page found for account {account_name}")
                return None
                
            element = await page.wait_for_selector(selector, timeout=timeout)
            return element
        except TimeoutError:
            logger.warning(f"Timeout waiting for selector: {selector} on {account_name}")
            return None
        except Exception as e:
            logger.error(f"Error waiting for selector {selector} on {account_name}: {str(e)}")
            return None

    async def _login(self, account_name: str):
        """Login to Twitter for a specific account."""
        try:
            account_data = self.accounts[account_name]
            username = account_data['username']
            password = account_data['password']
            
            logger.info(f"Attempting to login for {account_name} with username: {username}")
            
            page = self.pages.get(account_name)
            if not page:
                logger.error(f"No page found for account {account_name}")
                return False
            
            # Navigate to Twitter login page
            await page.goto('https://twitter.com/i/flow/login', wait_until='networkidle')
            await page.wait_for_timeout(5000)
            
            # Enter username
            logger.info(f"Entering username for {account_name}...")
            username_input = await page.wait_for_selector('input[autocomplete="username"]', timeout=60000)
            if not username_input:
                raise Exception(f"Could not find username input field for {account_name}")
            await username_input.fill(username)
            await page.wait_for_timeout(2000)
            
            # Click Next button - try multiple selectors
            logger.info(f"Clicking Next button for {account_name}...")
            next_button = None
            
            # First try data-testid
            try:
                next_button = await page.wait_for_selector('[data-testid="LoginNextButton"]', timeout=10000)
                if next_button:
                    await next_button.click()
            except:
                pass
            
            # If not found, try role and text
            if not next_button:
                try:
                    await page.get_by_role("button", name="Next").click()
                    next_button = True
                except:
                    pass
            
            # If still not found, try text content
            if not next_button:
                try:
                    await page.get_by_text("Next").click()
                    next_button = True
                except:
                    pass
            
            # If still not found, try evaluating JavaScript
            if not next_button:
                try:
                    next_button = await page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
                        return buttons.find(button => button.textContent.includes('Next'));
                    }''')
                    if next_button:
                        await page.click('div[role="button"]:has-text("Next")')
                        next_button = True
                except:
                    pass
            
            if not next_button:
                raise Exception(f"Could not find Next button for {account_name}")
            
            # Wait for password field to appear
            logger.info(f"Waiting for password field for {account_name}...")
            try:
                # Wait for the password field to be visible
                await page.wait_for_selector('input[name="password"]', state='visible', timeout=10000)
                await page.wait_for_timeout(2000)  # Additional wait to ensure field is ready
            except:
                logger.error(f"Password field did not appear after clicking Next for {account_name}")
                raise Exception(f"Password field not found for {account_name}")
            
            # Enter password
            logger.info(f"Entering password for {account_name}...")
            password_input = await page.wait_for_selector('input[name="password"]', timeout=60000)
            if not password_input:
                raise Exception(f"Could not find password input field for {account_name}")
            await password_input.fill(password)
            await page.wait_for_timeout(2000)
            
            # Click Login button - try multiple selectors
            logger.info(f"Clicking Login button for {account_name}...")
            login_button = None
            
            # First try data-testid
            try:
                login_button = await page.wait_for_selector('[data-testid="LoginForm_Login_Button"]', timeout=10000)
                if login_button:
                    await login_button.click()
            except:
                pass
            
            # If not found, try role and text
            if not login_button:
                try:
                    await page.get_by_role("button", name="Log in").click()
                    login_button = True
                except:
                    pass
            
            # If still not found, try text content
            if not login_button:
                try:
                    await page.get_by_text("Log in").click()
                    login_button = True
                except:
                    pass
            
            # If still not found, try evaluating JavaScript
            if not login_button:
                try:
                    login_button = await page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
                        return buttons.find(button => button.textContent.includes('Log in'));
                    }''')
                    if login_button:
                        await page.click('div[role="button"]:has-text("Log in")')
                        login_button = True
                except:
                    pass
            
            if not login_button:
                raise Exception(f"Could not find Login button for {account_name}")
            
            # Wait for login to complete
            await page.wait_for_timeout(5000)
            
            # Check if login was successful
            if await self.check_login_status(account_name):
                logger.info(f"Successfully logged in for {account_name}")
                self._logged_in[account_name] = True
                return True
            else:
                logger.error(f"Login failed for {account_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error during login for {account_name}: {str(e)}")
            return False

    async def ensure_logged_in(self, account_name: str = 'primary'):
        """Ensure the specified account is logged in."""
        try:
            # Initialize browser if not already done
            if account_name not in self.browsers:
                if not await self._init_browser(account_name):
                    return False
            
            # Check if already logged in (session was restored during initialization)
            if self._logged_in.get(account_name, False):
                logger.info(f"Session already restored for {account_name}")
                return True
            
            # If not logged in, try to login
            logger.info(f"No existing session found for {account_name}, attempting login...")
            return await self._login(account_name)
            
        except Exception as e:
            logger.error(f"Error ensuring login for {account_name}: {str(e)}")
            return False

    async def post_tweet(self, text: str, account_name: str = 'primary') -> bool:
        """Post a tweet using the specified account."""
        try:
            logger.info(f"Attempting to post tweet with {account_name}: {text[:50]}...")
            
            # Ensure logged in
            if not await self.ensure_logged_in(account_name):
                logger.error(f"Failed to login for {account_name}")
                return False
            
            page = self.pages.get(account_name)
            if not page:
                logger.error(f"No page found for account {account_name}")
                return False
            
            # Navigate to home page
            await page.goto('https://twitter.com/home')
            await page.wait_for_timeout(3000)
            
            # Find and click the tweet composition button
            tweet_button = await self._wait_for_selector('[data-testid="SideNav_NewTweet_Button"]', account_name=account_name)
            if not tweet_button:
                logger.error(f"Tweet button not found for {account_name}")
                return False
            
            await tweet_button.click()
            await page.wait_for_timeout(2000)
            
            # Find the tweet textarea and enter text
            textarea = await self._wait_for_selector('[data-testid="tweetTextarea_0"]', account_name=account_name)
            if not textarea:
                logger.error(f"Tweet textarea not found for {account_name}")
                return False
            
            await textarea.fill(text)
            await page.wait_for_timeout(1000)
            
            # Click the tweet button
            post_button = await self._wait_for_selector('[data-testid="tweetButton"]', account_name=account_name)
            if not post_button:
                logger.error(f"Post button not found for {account_name}")
                return False
            
            await post_button.click()
            await page.wait_for_timeout(3000)
            
            logger.info(f"Tweet posted successfully with {account_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error posting tweet with {account_name}: {str(e)}")
            return False

    async def search_and_like_tweets(self, search_term: str, max_likes: int = 5, account_name: str = 'primary') -> bool:
        """Search for tweets and like them using the specified account."""
        max_retries = 2  # Try up to 2 times
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Searching and liking tweets with {account_name} using term: {search_term} (attempt {attempt + 1}/{max_retries})")
                
                # Ensure logged in
                if not await self.ensure_logged_in(account_name):
                    logger.error(f"Failed to login for {account_name}")
                    return False
                
                page = self.pages.get(account_name)
                if not page:
                    logger.error(f"No page found for account {account_name}")
                    return False
                
                # Try multiple search approaches
                search_success = False
                
                # Approach 1: Direct search URL
                try:
                    logger.info(f"Trying direct search URL for {account_name}...")
                    search_url = f'https://x.com/search?q={search_term}&src=typed_query&f=live'
                    logger.info(f"Navigating to search URL for {account_name}: {search_url}")
                    
                    # Set shorter timeout for navigation
                    await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                    await page.wait_for_timeout(3000)
                    
                    # Check if we're on a search page
                    current_url = page.url
                    if 'search' in current_url.lower():
                        logger.info(f"Successfully navigated to search page for {account_name}")
                        search_success = True
                    else:
                        logger.warning(f"Navigation didn't reach search page for {account_name}, current URL: {current_url}")
                        
                except Exception as e:
                    logger.warning(f"Direct search URL approach failed for {account_name}: {str(e)}")
                
                # Approach 2: If direct URL failed, try home page + search box
                if not search_success:
                    try:
                        logger.info(f"Trying home page + search box approach for {account_name}...")
                        
                        # Navigate to home page
                        await page.goto('https://x.com/home', wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(3000)
                        
                        # Try to find and use search box
                        search_selectors = [
                            '[data-testid="SearchBox_Search_Input"]',
                            'input[placeholder*="Search"]',
                            'input[aria-label*="Search"]',
                            '[data-testid="searchbox"]'
                        ]
                        
                        search_box = None
                        for selector in search_selectors:
                            try:
                                search_box = await page.wait_for_selector(selector, timeout=5000)
                                if search_box:
                                    logger.info(f"Found search box with selector '{selector}' for {account_name}")
                                    break
                            except:
                                continue
                        
                        if search_box:
                            await search_box.click()
                            await page.wait_for_timeout(1000)
                            await search_box.fill(search_term)
                            await page.wait_for_timeout(1000)
                            await page.keyboard.press('Enter')
                            await page.wait_for_timeout(3000)
                            search_success = True
                            logger.info(f"Search initiated via search box for {account_name}")
                        
                    except Exception as e:
                        logger.warning(f"Home page + search box approach failed for {account_name}: {str(e)}")
                
                if not search_success:
                    logger.error(f"All search approaches failed for {account_name}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying search for {account_name}...")
                        await page.wait_for_timeout(5000)  # Wait before retry
                        continue
                    else:
                        return False
                
                # Wait for search results with shorter timeout
                timeout = 15000 if account_name == 'secondary' else 20000
                logger.info(f"Waiting for search results to load for {account_name} with timeout {timeout}ms...")
                
                # Try multiple selectors for search results with shorter timeouts
                result_selectors = [
                    '[data-testid="cellInnerDiv"]',
                    '[data-testid="tweet"]',
                    '[data-testid="tweetText"]',
                    'article[data-testid="tweet"]',
                    '[data-testid="tweetTextarea_0"]'  # Sometimes this appears
                ]
                
                results_found = False
                for selector in result_selectors:
                    try:
                        # Use shorter timeout for each selector
                        await page.wait_for_selector(selector, timeout=timeout//2)
                        logger.info(f"Search results loaded with selector '{selector}' for {account_name}")
                        results_found = True
                        break
                    except Exception as e:
                        logger.warning(f"Selector '{selector}' failed for {account_name}: {str(e)}")
                        continue
                
                if not results_found:
                    logger.warning(f"Could not find search results for {account_name}, but continuing anyway")
                    # Continue anyway, might still find like buttons
                
                # Scroll down to load more tweets (fewer scrolls for secondary)
                scroll_count = 2 if account_name == 'secondary' else 3
                logger.info(f"Scrolling to load more tweets for {account_name} ({scroll_count} times)...")
                for i in range(scroll_count):
                    await page.evaluate("window.scrollBy(0, 1000)")
                    await page.wait_for_timeout(1500)  # Shorter wait
                
                # Find tweet like buttons with multiple selectors
                logger.info(f"Looking for like buttons for {account_name}...")
                like_buttons = []
                
                # Try multiple selectors for like buttons
                selectors = [
                    '[data-testid="like"]',
                    '[aria-label*="Like"]',
                    '[aria-label*="like"]',
                    '[data-testid="unlike"]',  # In case already liked
                    'div[role="button"][aria-label*="Like"]',
                    'div[data-testid="like"]',
                    'div[aria-label*="Like"]',
                    'div[role="button"]'  # More generic, then filter
                ]
                
                for selector in selectors:
                    buttons = await page.query_selector_all(selector)
                    if buttons:
                        # Filter buttons to only include like buttons
                        filtered_buttons = []
                        for button in buttons:
                            try:
                                aria_label = await button.get_attribute('aria-label')
                                if aria_label and ('like' in aria_label.lower() or 'unlike' in aria_label.lower()):
                                    filtered_buttons.append(button)
                            except:
                                continue
                        
                        if filtered_buttons:
                            logger.info(f"Found {len(filtered_buttons)} like buttons with selector '{selector}' for {account_name}")
                            like_buttons = filtered_buttons
                            break
                
                if not like_buttons:
                    logger.warning(f"No like buttons found for {account_name} with any selector")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying search for {account_name}...")
                        await page.wait_for_timeout(5000)  # Wait before retry
                        continue
                    else:
                        return False
                
                # Like up to max_likes tweets
                liked_count = 0
                for button in like_buttons[:max_likes]:
                    try:
                        # Check if already liked
                        aria_label = await button.get_attribute('aria-label')
                        if aria_label and 'Unlike' in aria_label:
                            logger.info(f"Tweet already liked for {account_name}, skipping")
                            continue
                        
                        await button.click()
                        liked_count += 1
                        logger.info(f"Liked tweet {liked_count} for {account_name}")
                        await page.wait_for_timeout(random.randint(1000, 2000))  # Shorter random delay
                        
                    except Exception as e:
                        logger.warning(f"Error liking tweet for {account_name}: {str(e)}")
                        continue
                
                logger.info(f"Successfully liked {liked_count} tweets with {account_name}")
                return liked_count > 0  # Return True if we liked at least one tweet
                
            except Exception as e:
                logger.error(f"Error searching and liking tweets with {account_name} (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying search for {account_name}...")
                    await asyncio.sleep(5000)  # Wait before retry
                    continue
                else:
                    return False
        
        return False

    async def close_session(self):
        """Close all browser sessions."""
        try:
            for account_name in list(self.browsers.keys()):
                try:
                    if self.browsers[account_name]:
                        await self.browsers[account_name].close()
                    logger.info(f"Closed browser session for {account_name}")
                except Exception as e:
                    logger.error(f"Error closing browser for {account_name}: {str(e)}")
            
            if self.playwright:
                await self.playwright.stop()
                logger.info("Stopped Playwright")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def get_status(self) -> Dict[str, bool]:
        """Get status of all accounts."""
        return {
            account_name: self._logged_in.get(account_name, False)
            for account_name in self.accounts.keys()
        } 