# Placeholder for tweet generation using LLM

import os
import time
import random
from playwright.async_api import async_playwright
import logging
from dotenv import load_dotenv, find_dotenv

dotenv_path = find_dotenv()
print("Loading .env from:", dotenv_path)
load_dotenv(dotenv_path)

logger = logging.getLogger(__name__)

class TwitterPlaywright:
    def __init__(self):
        self.username = os.getenv('TWITTER_USERNAME')
        self.password = os.getenv('TWITTER_PASSWORD')
        print("Loaded Twitter username:", self.username)
        print("Loaded Twitter password:", self.password)

    async def _handle_login(self, page):
        """Handle the Twitter login process."""
        logger.info("Navigating to Twitter login...")
        await page.goto('https://twitter.com/i/flow/login', wait_until='networkidle')
        await page.wait_for_timeout(2000)
        
        # Handle username input
        logger.info("Filling username...")
        await page.wait_for_selector('input[autocomplete="username"][name="text"]', timeout=10000)
        await page.fill('input[autocomplete="username"][name="text"]', self.username)
        await page.wait_for_timeout(1000)

        # Click Next button
        await self._click_next_button(page)
        await page.wait_for_timeout(2000)

        # Handle password input
        await self._handle_password_input(page)
        await page.wait_for_timeout(2000)

        # Click Login button
        await self._click_login_button(page)
        await page.wait_for_timeout(4000)

    async def _click_next_button(self, page):
        """Click the Next button during login."""
        logger.info("Attempting to click Next button...")
        selectors = [
            'div[role="button"]:has-text("Next")',
            'div.css-146c3p1:has-text("Next")',
            'div[data-testid="nextButton"]',
            'div:has-text("Next")',
        ]
        
        for selector in selectors:
            try:
                logger.info(f"Trying selector: {selector}")
                next_button = await page.wait_for_selector(selector, timeout=2000)
                if next_button:
                    await next_button.click()
                    logger.info(f"Successfully clicked using selector: {selector}")
                    return
            except Exception as e:
                logger.info(f"Selector {selector} failed: {str(e)}")
        
        # Final attempt using JavaScript
        logger.info("Trying JavaScript click...")
        await page.evaluate('''() => {
            const buttons = Array.from(document.querySelectorAll('div[role="button"], button, div.css-146c3p1'));
            const nextButton = buttons.find(button => {
                const text = (button.textContent || '').toLowerCase();
                return text.includes('next');
            });
            if (nextButton) {
                nextButton.click();
            }
        }''')

    async def _handle_password_input(self, page):
        """Handle password input during login."""
        logger.info("Waiting for password input field...")
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[autocomplete="current-password"]',
            'input.r-30o5oe.r-1niwhzg'
        ]

        for selector in password_selectors:
            try:
                logger.info(f"Trying password selector: {selector}")
                password_input = await page.wait_for_selector(selector, timeout=3000)
                if password_input:
                    await password_input.fill(self.password)
                    logger.info(f"Successfully filled password using selector: {selector}")
                    return
            except Exception as e:
                logger.info(f"Password selector {selector} failed: {str(e)}")

        raise Exception("Could not fill password input")

    async def _click_login_button(self, page):
        """Click the Login button during login."""
        logger.info("Attempting to click Login button...")
        login_selectors = [
            'div[role="button"]:has-text("Log in")',
            'div.css-146c3p1:has-text("Log in")',
            'div[data-testid="LoginButton"]',
            'div:has-text("Log in")'
        ]

        for selector in login_selectors:
            try:
                logger.info(f"Trying login selector: {selector}")
                login_button = await page.wait_for_selector(selector, timeout=3000)
                if login_button:
                    await login_button.click()
                    logger.info(f"Successfully clicked login using selector: {selector}")
                    return
            except Exception as e:
                logger.info(f"Login selector {selector} failed: {str(e)}")

        # Final attempt using JavaScript
        logger.info("Trying JavaScript click for login...")
        await page.evaluate('''() => {
            const buttons = Array.from(document.querySelectorAll('div[role="button"], button, div.css-146c3p1'));
            const loginButton = buttons.find(button => {
                const text = (button.textContent || '').toLowerCase();
                return text.includes('log in');
            });
            if (loginButton) {
                loginButton.click();
            }
        }''')

    async def _navigate_to_compose(self, page):
        """Navigate to the tweet compose page."""
        logger.info("Navigating to tweet compose...")
        try:
            await page.goto('https://twitter.com/home', wait_until='domcontentloaded')
            await page.wait_for_timeout(3000)

            compose_selectors = [
                'a[href="/compose/tweet"]',
                'div[data-testid="SideNav_NewTweet_Button"]',
                'a[href="/compose/post"]'
            ]

            for selector in compose_selectors:
                try:
                    logger.info(f"Trying compose selector: {selector}")
                    compose_button = await page.wait_for_selector(selector, timeout=3000)
                    if compose_button:
                        await compose_button.click()
                        logger.info(f"Clicked compose button with selector: {selector}")
                        return
                except Exception as e:
                    logger.info(f"Compose selector {selector} failed: {str(e)}")

            # Fallback to direct URL
            logger.info("Falling back to direct URL...")
            await page.goto('https://twitter.com/compose/tweet', wait_until='domcontentloaded')

        except Exception as e:
            logger.info(f"Twitter navigation failed, trying X.com: {str(e)}")
            try:
                await page.goto('https://x.com/home', wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)
                
                for selector in compose_selectors:
                    try:
                        logger.info(f"Trying X.com compose selector: {selector}")
                        compose_button = await page.wait_for_selector(selector, timeout=3000)
                        if compose_button:
                            await compose_button.click()
                            logger.info(f"Clicked X.com compose button with selector: {selector}")
                            return
                    except Exception as e:
                        logger.info(f"X.com compose selector {selector} failed: {str(e)}")

                await page.goto('https://x.com/compose/tweet', wait_until='domcontentloaded')
            except Exception as e:
                logger.error(f"X.com navigation also failed: {str(e)}")
                raise

    async def _input_tweet_text(self, page, tweet_text):
        """Input tweet text into the compose dialog."""
        logger.info("Attempting to input tweet text...")
        selectors = [
            'div[data-testid="tweetTextarea_0"]',
            'div[data-testid="tweetTextarea_0RichTextInputContainer"]',
            'div[contenteditable="true"]',
            '.DraftEditor-root'
        ]

        for selector in selectors:
            try:
                logger.info(f"Trying selector: {selector}")
                tweet_box = await page.wait_for_selector(selector, timeout=3000)
                if tweet_box:
                    await tweet_box.click()
                    await page.wait_for_timeout(2000)
                    await page.keyboard.type(tweet_text, delay=50)
                    await page.wait_for_timeout(2000)
                    return
            except Exception as e:
                logger.info(f"Selector {selector} failed: {str(e)}")

        raise Exception("Could not find tweet input box")

    async def _click_post_button(self, page):
        """Click the post button to submit the tweet."""
        logger.info("Clicking post button...")
        try:
            # Try JavaScript click first to bypass any overlays
            logger.info("Attempting JavaScript click...")
            click_success = await page.evaluate('''() => {
                const button = document.querySelector('button[data-testid="tweetButton"]');
                if (button) {
                    // Try both click() and dispatchEvent
                    button.click();
                    button.dispatchEvent(new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }));
                    return true;
                }
                return false;
            }''')
            
            if not click_success:
                logger.warning("JavaScript click failed, trying direct click...")
                # If JavaScript click fails, try direct click
                post_button = await page.wait_for_selector('button[data-testid="tweetButton"]', timeout=3000)
                if post_button:
                    await post_button.click()
            
            await page.wait_for_timeout(2000)
            
            # Log state after first click
            dialog_still_open = await page.evaluate('''() => !!document.querySelector('div[data-testid="tweetTextarea_0"]')''')
            logger.info(f"Compose dialog still open after first click: {dialog_still_open}")
            
            # If still open, try form submission
            if dialog_still_open:
                logger.info("Still on compose page, trying form submission...")
                await page.evaluate('''() => {
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                        return true;
                    }
                    return false;
                }''')
                await page.wait_for_timeout(2000)
                
                # If still open, try clicking any visible post button
                dialog_still_open_final = await page.evaluate('''() => !!document.querySelector('div[data-testid="tweetTextarea_0"]')''')
                if dialog_still_open_final:
                    logger.info("Still on compose page, trying to find and click any visible post button...")
                    await page.evaluate('''() => {
                        const buttons = Array.from(document.querySelectorAll('button, div[role="button"]'));
                        const postButton = buttons.find(button => {
                            const text = (button.textContent || '').toLowerCase();
                            return text.includes('post') && 
                                   window.getComputedStyle(button).display !== 'none' &&
                                   window.getComputedStyle(button).visibility !== 'hidden';
                        });
                        if (postButton) {
                            postButton.click();
                            return true;
                        }
                        return false;
                    }''')
                    await page.wait_for_timeout(2000)
            
            # Wait for the compose dialog to disappear
            try:
                await page.wait_for_selector('div[data-testid="tweetTextarea_0"]', state='detached', timeout=15000)
                logger.info("Compose dialog closed (tweet likely posted)")
            except Exception as e:
                logger.error(f"Compose dialog did not close: {str(e)}")
                raise Exception("Tweet posting failed: Compose dialog did not close after all attempts")
                
        except Exception as e:
            logger.error(f"Error clicking post button: {str(e)}")
            raise

    async def post_tweet(self, tweet_text: str):
        """Post a tweet to Twitter."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Handle login
                await self._handle_login(page)
                
                # Navigate to compose page
                await self._navigate_to_compose(page)
                
                # Wait for compose dialog
                logger.info("Waiting for compose dialog...")
                await page.wait_for_selector('div[data-testid="tweetTextarea_0"], div[data-testid="tweetTextarea_0RichTextInputContainer"]', timeout=10000)
                await page.wait_for_timeout(2000)
                
                # Input tweet text
                await self._input_tweet_text(page, tweet_text)
                
                # Click post button
                await self._click_post_button(page)
                
                logger.info("Tweet posted successfully!")
                
            except Exception as e:
                logger.error(f"Error during tweet posting: {str(e)}")
                raise
            finally:
                await browser.close()

    async def like_blockchain_tweets(self, min_likes: int = 5, max_likes: int = 10):
        """Like a random number of blockchain-related tweets.
        
        Args:
            min_likes (int): Minimum number of tweets to like (default: 5)
            max_likes (int): Maximum number of tweets to like (default: 10)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Handle login first
                await self._handle_login(page)
                
                # Navigate to blockchain search with a shorter timeout
                logger.info("Navigating to blockchain search...")
                await page.goto('https://twitter.com/search?q=%23blockchain&src=typed_query', wait_until='domcontentloaded')
                await page.wait_for_timeout(3000)  # Give some time for initial load
                
                # Click Latest tab
                logger.info("Clicking Latest tab...")
                try:
                    latest_tab = await page.wait_for_selector('a[role="tab"][href*="f=live"]', timeout=5000)
                    if latest_tab:
                        await latest_tab.click()
                        logger.info("Successfully clicked Latest tab")
                    else:
                        raise Exception("Could not find Latest tab")
                except Exception as e:
                    logger.error(f"Failed to click Latest tab: {str(e)}")
                    raise
                
                await page.wait_for_timeout(3000)  # Wait for tweets to load
                
                # Determine random number of tweets to like
                num_tweets_to_like = random.randint(min_likes, max_likes)
                logger.info(f"Will attempt to like {num_tweets_to_like} tweets")
                
                # Find and like tweets
                liked_count = 0
                scroll_count = 0
                max_scrolls = 10  # Maximum number of scroll attempts
                
                while liked_count < num_tweets_to_like and scroll_count < max_scrolls:
                    try:
                        # Scroll to load more tweets
                        logger.info(f"Scrolling to load more tweets (scroll {scroll_count + 1}/{max_scrolls})...")
                        await page.evaluate('window.scrollBy(0, 1000)')
                        await page.wait_for_timeout(2000)
                        scroll_count += 1
                        
                        # Find like buttons that haven't been liked yet
                        like_buttons = await page.query_selector_all('button[data-testid="like"]')
                        logger.info(f"Found {len(like_buttons)} like buttons")
                        
                        if not like_buttons:
                            logger.info("No like buttons found, continuing to scroll...")
                            continue
                            
                        for button in like_buttons:
                            if liked_count >= num_tweets_to_like:
                                break
                                
                            try:
                                # Check if already liked by checking the SVG fill color
                                is_liked = await button.evaluate('''(button) => {
                                    const svg = button.querySelector('svg');
                                    return svg ? svg.getAttribute('fill') === 'rgb(249, 24, 128)' : false;
                                }''')
                                
                                if not is_liked:
                                    # Random delay before clicking
                                    delay = random.uniform(1.5, 3.5)
                                    await page.wait_for_timeout(int(delay * 1000))
                                    
                                    # Scroll the button into view
                                    await button.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(1000)
                                    
                                    # Click the button
                                    await button.click()
                                    liked_count += 1
                                    logger.info(f"Liked tweet {liked_count}/{num_tweets_to_like}")
                                    
                                    # Random delay after clicking
                                    delay = random.uniform(2.0, 4.0)
                                    await page.wait_for_timeout(int(delay * 1000))
                            except Exception as e:
                                logger.warning(f"Failed to like a tweet: {str(e)}")
                                continue
                                
                    except Exception as e:
                        logger.error(f"Error during tweet liking process: {str(e)}")
                        continue
                
                if liked_count < num_tweets_to_like:
                    logger.warning(f"Only managed to like {liked_count} out of {num_tweets_to_like} requested tweets")
                else:
                    logger.info(f"Successfully liked {liked_count} tweets")
                
            except Exception as e:
                logger.error(f"Error in like_blockchain_tweets: {str(e)}")
                raise
            finally:
                await browser.close()

# Optionally, keep the generate_tweets function for LLM integration

