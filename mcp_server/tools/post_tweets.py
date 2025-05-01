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

    async def post_tweet(self, tweet_text: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Go to Twitter login
                logger.info("Navigating to Twitter login...")
                await page.goto('https://twitter.com/i/flow/login', wait_until='networkidle')
                await page.wait_for_timeout(2000)
                
                # Handle username input
                logger.info("Filling username...")
                await page.wait_for_selector('input[autocomplete="username"][name="text"]', timeout=10000)
                await page.fill('input[autocomplete="username"][name="text"]', self.username)
                await page.wait_for_timeout(1000)  # Wait for the button to become enabled

                # Debug: Log all buttons and their text content
                logger.info("Debugging available buttons...")
                await page.evaluate('''() => {
                    const allButtons = Array.from(document.querySelectorAll('div[role="button"], button, div.css-146c3p1'));
                    console.log('Available buttons:', allButtons.map(b => ({
                        text: b.textContent,
                        role: b.getAttribute('role'),
                        class: b.getAttribute('class')
                    })));
                }''')

                # Click Next using multiple approaches
                logger.info("Attempting to click Next button...")
                try:
                    # Try multiple selectors in sequence
                    selectors = [
                        'div[role="button"]:has-text("Next")',
                        'div.css-146c3p1:has-text("Next")',
                        'div[data-testid="nextButton"]',
                        'div:has-text("Next")',
                    ]
                    
                    clicked = False
                    for selector in selectors:
                        try:
                            logger.info(f"Trying selector: {selector}")
                            next_button = await page.wait_for_selector(selector, timeout=2000)
                            if next_button:
                                await next_button.click()
                                clicked = True
                                logger.info(f"Successfully clicked using selector: {selector}")
                                break
                        except Exception as e:
                            logger.info(f"Selector {selector} failed: {str(e)}")
                    
                    if not clicked:
                        # Final attempt using JavaScript
                        logger.info("Trying JavaScript click...")
                        await page.evaluate('''() => {
                            function findButtonByText(text) {
                                const elements = Array.from(document.querySelectorAll('div[role="button"], button, div.css-146c3p1'));
                                return elements.find(el => {
                                    const content = (el.textContent || '').toLowerCase();
                                    return content.includes(text.toLowerCase());
                                });
                            }
                            
                            const nextButton = findButtonByText('Next');
                            if (nextButton) {
                                nextButton.click();
                            } else {
                                throw new Error('Next button not found after all attempts');
                            }
                        }''')
                        
                except Exception as e:
                    logger.error(f"Failed to click Next button: {str(e)}")
                    raise Exception("Could not click Next button after all attempts")

                await page.wait_for_timeout(2000)  # Wait for navigation

                # Now wait for password input with multiple attempts
                logger.info("Waiting for password input field...")
                await page.wait_for_timeout(2000)  # Give time for password field to appear
                
                try:
                    # Debug: Log form elements
                    logger.info("Debugging form elements...")
                    await page.evaluate('''() => {
                        const inputs = Array.from(document.querySelectorAll('input'));
                        console.log('Available inputs:', inputs.map(i => ({
                            type: i.type,
                            name: i.name,
                            id: i.id,
                            class: i.getAttribute('class')
                        })));
                    }''')

                    # Try multiple selectors for password input
                    password_selectors = [
                        'input[type="password"]',
                        'input[name="password"]',
                        'input[autocomplete="current-password"]',
                        'input.r-30o5oe.r-1niwhzg'  # Common Twitter password input class
                    ]

                    password_filled = False
                    for selector in password_selectors:
                        try:
                            logger.info(f"Trying password selector: {selector}")
                            password_input = await page.wait_for_selector(selector, timeout=3000)
                            if password_input:
                                await password_input.fill(self.password)
                                password_filled = True
                                logger.info(f"Successfully filled password using selector: {selector}")
                                break
                        except Exception as e:
                            logger.info(f"Password selector {selector} failed: {str(e)}")

                    if not password_filled:
                        raise Exception("Could not fill password input")

                    # Try to click the Login button
                    logger.info("Attempting to click Login button...")
                    login_selectors = [
                        'div[role="button"]:has-text("Log in")',
                        'div.css-146c3p1:has-text("Log in")',
                        'div[data-testid="LoginButton"]',
                        'div:has-text("Log in")'
                    ]

                    login_clicked = False
                    for selector in login_selectors:
                        try:
                            logger.info(f"Trying login selector: {selector}")
                            login_button = await page.wait_for_selector(selector, timeout=3000)
                            if login_button:
                                await login_button.click()
                                login_clicked = True
                                logger.info(f"Successfully clicked login using selector: {selector}")
                                break
                        except Exception as e:
                            logger.info(f"Login selector {selector} failed: {str(e)}")

                    if not login_clicked:
                        # Final attempt using JavaScript
                        logger.info("Trying JavaScript click for login...")
                        await page.evaluate('''() => {
                            function findButtonByText(text) {
                                const elements = Array.from(document.querySelectorAll('div[role="button"], button, div.css-146c3p1'));
                                return elements.find(el => {
                                    const content = (el.textContent || '').toLowerCase();
                                    return content.includes(text.toLowerCase());
                                });
                            }
                            
                            const loginButton = findButtonByText('Log in');
                            if (loginButton) {
                                loginButton.click();
                            } else {
                                throw new Error('Login button not found after all attempts');
                            }
                        }''')

                    # Wait for login to complete and verify we're logged in
                    logger.info("Waiting for login to complete...")
                    await page.wait_for_timeout(5000)
                    
                    # Verify we're logged in by checking for home page indicators
                    logger.info("Verifying login success...")
                    try:
                        # Try multiple home page indicators
                        home_indicators = [
                            'a[href="/compose/tweet"]',
                            'a[href="/home"]',
                            'div[data-testid="SideNav_NewTweet_Button"]'
                        ]
                        
                        for indicator in home_indicators:
                            try:
                                await page.wait_for_selector(indicator, timeout=3000)
                                logger.info(f"Login verified with indicator: {indicator}")
                                break
                            except Exception:
                                continue
                        
                        # Go to compose tweet page
                        logger.info("Navigating to tweet compose...")
                        try:
                            # First try the home page and click the compose button
                            logger.info("Navigating to home page first...")
                            await page.goto('https://twitter.com/home', wait_until='domcontentloaded')
                            await page.wait_for_timeout(3000)

                            # Try to find and click the compose button
                            logger.info("Looking for compose button...")
                            compose_selectors = [
                                'a[href="/compose/tweet"]',
                                'div[data-testid="SideNav_NewTweet_Button"]',
                                'a[href="/compose/post"]'
                            ]

                            compose_clicked = False
                            for selector in compose_selectors:
                                try:
                                    logger.info(f"Trying compose selector: {selector}")
                                    compose_button = await page.wait_for_selector(selector, timeout=3000)
                                    if compose_button:
                                        await compose_button.click()
                                        compose_clicked = True
                                        logger.info(f"Clicked compose button with selector: {selector}")
                                        break
                                except Exception as e:
                                    logger.info(f"Compose selector {selector} failed: {str(e)}")

                            if not compose_clicked:
                                # Fallback to direct URL
                                logger.info("Falling back to direct URL...")
                                await page.goto('https://twitter.com/compose/tweet', wait_until='domcontentloaded')

                        except Exception as e:
                            logger.info(f"Twitter navigation failed, trying X.com: {str(e)}")
                            try:
                                await page.goto('https://x.com/home', wait_until='domcontentloaded')
                                await page.wait_for_timeout(3000)
                                
                                # Try the same compose button selectors
                                compose_clicked = False
                                for selector in compose_selectors:
                                    try:
                                        logger.info(f"Trying X.com compose selector: {selector}")
                                        compose_button = await page.wait_for_selector(selector, timeout=3000)
                                        if compose_button:
                                            await compose_button.click()
                                            compose_clicked = True
                                            logger.info(f"Clicked X.com compose button with selector: {selector}")
                                            break
                                    except Exception as e:
                                        logger.info(f"X.com compose selector {selector} failed: {str(e)}")

                                if not compose_clicked:
                                    await page.goto('https://x.com/compose/tweet', wait_until='domcontentloaded')
                            except Exception as e:
                                logger.error(f"X.com navigation also failed: {str(e)}")
                                raise

                        # Wait for the compose dialog
                        logger.info("Waiting for compose dialog...")
                        await page.wait_for_selector('div[data-testid="tweetTextarea_0"], div[data-testid="tweetTextarea_0RichTextInputContainer"]', timeout=10000)
                        await page.wait_for_timeout(2000)

                        # Debug: Log all elements with data-testid
                        logger.info("Analyzing page structure...")
                        structure = await page.evaluate('''() => {
                            const elements = document.querySelectorAll('[data-testid]');
                            return Array.from(elements).map(el => ({
                                testid: el.getAttribute('data-testid'),
                                tag: el.tagName,
                                class: el.className,
                                contentEditable: el.contentEditable,
                                role: el.getAttribute('role')
                            }));
                        }''')
                        logger.info(f"Found elements: {structure}")

                        # Try to input text
                        logger.info("Attempting to input tweet text...")
                        try:
                            # Try multiple selectors for the tweet box
                            selectors = [
                                'div[data-testid="tweetTextarea_0"]',
                                'div[data-testid="tweetTextarea_0RichTextInputContainer"]',
                                'div[contenteditable="true"]',
                                '.DraftEditor-root'
                            ]

                            tweet_box = None
                            for selector in selectors:
                                try:
                                    logger.info(f"Trying selector: {selector}")
                                    tweet_box = await page.wait_for_selector(selector, timeout=3000)
                                    if tweet_box:
                                        logger.info(f"Found tweet box with selector: {selector}")
                                        break
                                except Exception as e:
                                    logger.info(f"Selector {selector} failed: {str(e)}")

                            if not tweet_box:
                                raise Exception("Could not find tweet input box")

                            # Click the tweet box
                            logger.info("Clicking tweet box...")
                            await tweet_box.click()
                            await page.wait_for_timeout(2000)

                            # Try to input text
                            logger.info("Attempting keyboard input...")
                            await page.keyboard.type(tweet_text, delay=50)
                            await page.wait_for_timeout(2000)

                            # Verify text was entered
                            content = await page.evaluate('''() => {
                                const selectors = [
                                    'div[data-testid="tweetTextarea_0"]',
                                    'div[data-testid="tweetTextarea_0RichTextInputContainer"]',
                                    'div[contenteditable="true"]',
                                    '.DraftEditor-root'
                                ];
                                
                                for (const selector of selectors) {
                                    const element = document.querySelector(selector);
                                    if (element && element.textContent) {
                                        return element.textContent;
                                    }
                                }
                                return '';
                            }''')
                            
                            logger.info(f"Current tweet content: {content}")
                            if not content:
                                raise Exception("Failed to input text into tweet box")

                        except Exception as e:
                            logger.error(f"Failed to input text: {str(e)}")
                            raise

                        # Click post button using multiple approaches
                        logger.info("Looking for post button...")
                        post_button = None
                        
                        # Try multiple selectors for the post button
                        post_button_selectors = [
                            'button[data-testid="tweetButton"]',
                            'div[role="button"]:has-text("Post")',
                            'div:has(span:text-is("Post"))',
                            'div.css-1jxf684:has-text("Post")',
                            'div[data-testid="tweetButtonInline"]'
                        ]
                        
                        for selector in post_button_selectors:
                            try:
                                logger.info(f"Trying post button selector: {selector}")
                                post_button = await page.wait_for_selector(selector, timeout=3000)
                                if post_button:
                                    logger.info(f"Found post button with selector: {selector}")
                                    break
                            except Exception as e:
                                logger.info(f"Selector {selector} failed: {str(e)}")
                        
                        if post_button:
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
                            
                            logger.info("Post button click attempts complete. Waiting for post to complete...")
                            # Wait for the compose dialog to disappear (dialog closes = tweet posted or failed)
                            try:
                                await page.wait_for_selector('div[data-testid="tweetTextarea_0"]', state='detached', timeout=15000)
                                logger.info("Compose dialog closed (tweet likely posted or failed)")
                            except Exception as e:
                                logger.error(f"Post completion wait failed: {str(e)}")
                                raise Exception("Tweet posting failed: Compose dialog did not close after post attempts.")
                        else:
                            # Try JavaScript click as last resort
                            logger.info("Trying JavaScript click for post button...")
                            await page.evaluate('''() => {
                                const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
                                const postButton = buttons.find(button => {
                                    const text = button.textContent || '';
                                    return text.toLowerCase().includes('post');
                                });
                                if (postButton) {
                                    postButton.click();
                                    return true;
                                }
                                return false;
                            }''')
                            
                        # Wait for post to complete
                        logger.info("Waiting for post to complete...")
                        await page.wait_for_timeout(5000)
                            
                    except Exception as e:
                        logger.error(f"Failed to post tweet: {str(e)}")
                        raise Exception(f"Tweet posting failed: {str(e)}")

                except Exception as e:
                    logger.error(f"Login process failed: {str(e)}")
                    raise

            except Exception as e:
                logger.error(f"Error during tweet posting: {str(e)}")
                raise
            finally:
                await browser.close()

    async def like_blockchain_tweets(self, like_count: int = 5):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto('https://twitter.com/login')
            await page.fill('input[name="text"]', self.username)
            await page.click('div[role="button"][data-testid="LoginForm_Login_Button"]')
            await page.wait_for_timeout(2000)
            await page.fill('input[name="password"]', self.password)
            await page.click('div[role="button"][data-testid="LoginForm_Login_Button"]')
            await page.wait_for_timeout(4000)
            await page.goto('https://twitter.com/search?q=%23blockchain&src=typed_query')
            await page.wait_for_selector('nav[role="navigation"]')
            # Click 'Latest' tab
            await page.click('a[role="tab"][href*="f=live"]')
            await page.wait_for_timeout(2000)
            # Like tweets
            like_buttons = await page.query_selector_all('div[data-testid="like"]')
            for i, btn in enumerate(like_buttons[:like_count]):
                await btn.click()
                sleep_time = random.uniform(2, 5)
                await page.wait_for_timeout(int(sleep_time * 1000))
            await browser.close()

# Optionally, keep the generate_tweets function for LLM integration

