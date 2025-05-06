import requests
import os
import logging
import webbrowser
from dotenv import load_dotenv, find_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse
import time
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the query parameters
        query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = query_components.get('code', [None])[0]
        
        if code:
            # Store the authorization code
            self.server.auth_code = code
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authorization successful! You can close this window.")
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authorization failed. No code received.")
        
        # Stop the server after handling the request
        threading.Thread(target=self.server.shutdown).start()

def get_authorization_code():
    """Get the authorization code from LinkedIn OAuth.
    
    Returns:
        str: The authorization code if successful, None otherwise
    """
    try:
        # Find and load .env file
        dotenv_path = find_dotenv()
        if not dotenv_path:
            logger.error("No .env file found")
            return None
            
        load_dotenv(dotenv_path)
        logger.info(f"Loaded .env from: {dotenv_path}")
        
        # Retrieve values from environment
        CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID')
        REDIRECT_URI = os.getenv('LINKEDIN_REDIRECT_URI', 'http://localhost:8000/callback')
        
        if not CLIENT_ID:
            logger.error("Missing required environment variable: LINKEDIN_CLIENT_ID")
            return None
        
        # Start a local server to handle the callback
        server = HTTPServer(('localhost', 8000), OAuthCallbackHandler)
        server.auth_code = None
        
        # Start the server in a separate thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Construct the authorization URL with only w_member_social scope
        auth_url = (
            'https://www.linkedin.com/oauth/v2/authorization'
            f'?response_type=code'
            f'&client_id={CLIENT_ID}'
            f'&redirect_uri={REDIRECT_URI}'
            f'&state=random'
            f'&scope=w_member_social'  # Only requesting w_member_social
        )
        
        # Print the authorization URL instead of opening it
        logger.info("Please open this URL in your browser:")
        logger.info(auth_url)
        logger.info("IMPORTANT: Please make sure to authorize this permission:")
        logger.info("- Share and Comment (w_member_social)")
        
        # Wait for the authorization code
        logger.info("Waiting for authorization...")
        while server.auth_code is None:
            time.sleep(1)
        
        # Clean up
        server.shutdown()
        server.server_close()
        
        return server.auth_code
        
    except Exception as e:
        logger.error(f"An error occurred while getting authorization code: {str(e)}")
        return None

def get_linkedin_token():
    """Request an access token from LinkedIn OAuth API.
    
    Returns:
        str: The access token if successful, None otherwise
    """
    try:
        # First get the authorization code
        auth_code = get_authorization_code()
        if not auth_code:
            return None
            
        # Find and load .env file
        dotenv_path = find_dotenv()
        if not dotenv_path:
            logger.error("No .env file found")
            return None
            
        load_dotenv(dotenv_path)
        logger.info(f"Loaded .env from: {dotenv_path}")

        # Retrieve values from environment
        CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID')
        CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET')
        REDIRECT_URI = os.getenv('LINKEDIN_REDIRECT_URI', 'http://localhost:8000/callback')
        
        # Validate required environment variables
        if not all([CLIENT_ID, CLIENT_SECRET]):
            missing_vars = []
            if not CLIENT_ID:
                missing_vars.append('LINKEDIN_CLIENT_ID')
            if not CLIENT_SECRET:
                missing_vars.append('LINKEDIN_CLIENT_SECRET')
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return None
        
        # Prepare token request
        token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }

        # Make the request
        logger.info("Requesting access token from LinkedIn...")
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        # Extract and return the access token
        token_data = response.json()
        access_token = token_data.get('access_token')
        if access_token:
            logger.info("Successfully obtained access token")
            logger.info(f"Token scopes: {token_data.get('scope', 'No scopes returned')}")
            logger.info(f"Token expires in: {token_data.get('expires_in', 'Unknown')} seconds")
            return access_token
        else:
            logger.error("No access token in response")
            logger.error(f"Response: {token_data}")
            return None
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {str(e)}")
        if e.response:
            logger.error(f"Response: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return None

def get_linkedin_person_urn(access_token: str) -> str:
    """Get the LinkedIn Person URN using the access token.
    
    Args:
        access_token (str): The LinkedIn access token
        
    Returns:
        str: The Person URN if successful, None otherwise
    """
    try:
        # Try to get the Person URN from the access token first
        logger.info("Trying to get Person URN from access token...")
        token_parts = access_token.split('.')
        if len(token_parts) > 1:
            try:
                # Decode the JWT payload
                import base64
                import json
                payload = json.loads(base64.urlsafe_b64decode(token_parts[1] + '=' * (-len(token_parts[1]) % 4)).decode())
                person_id = payload.get('sub', '').split(':')[-1]
                if person_id:
                    logger.info(f"Successfully retrieved Person ID from access token: {person_id}")
                    return person_id
            except Exception as e:
                logger.error(f"Error decoding access token: {str(e)}")
        
        # If that fails, try to get the Person URN using the profile endpoint
        logger.info("Trying to get Person URN from profile endpoint...")
        url = 'https://api.linkedin.com/v2/me'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'X-Restli-Protocol-Version': '2.0.0'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        profile_data = response.json()
        person_id = profile_data.get('id')
        if person_id:
            logger.info(f"Successfully retrieved Person ID from profile: {person_id}")
            return person_id
        
        logger.error("Could not retrieve Person ID")
        logger.error(f"Response: {response.json()}")
        return None
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {str(e)}")
        if e.response:
            logger.error(f"Response: {e.response.text}")
            logger.error(f"Response headers: {e.response.headers}")
        return None
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return None

def update_env_file(access_token: str, person_urn: str):
    """Update the .env file with the access token and person URN.
    
    Args:
        access_token (str): The LinkedIn access token
        person_urn (str): The LinkedIn Person URN
    """
    try:
        # Create .env file in the project root directory
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
        logger.info(f"Updating .env file at: {dotenv_path}")
        
        # Read existing .env file if it exists
        existing_vars = {}
        if os.path.exists(dotenv_path):
            with open(dotenv_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        existing_vars[key] = value
        
        # Update LinkedIn-specific variables
        existing_vars['LINKEDIN_ACCESS_TOKEN'] = access_token
        existing_vars['LINKEDIN_PERSON_URN'] = person_urn
        
        # Write back all variables
        with open(dotenv_path, 'w') as f:
            for key, value in existing_vars.items():
                f.write(f'{key}={value}\n')
            
        logger.info("Successfully updated .env file")
        logger.info(f"Updated access token: {access_token[:10]}...")
        logger.info(f"Updated person URN: {person_urn}")
        
        # Verify the file was updated correctly
        if os.path.exists(dotenv_path):
            with open(dotenv_path, 'r') as f:
                content = f.read()
                logger.info(f"Current .env content:\n{content}")
        else:
            logger.error("Failed to update .env file")
        
    except Exception as e:
        logger.error(f"Error updating .env file: {str(e)}")

if __name__ == "__main__":
    access_token = get_linkedin_token()
    if access_token:
        print(f"Access Token: {access_token}")
        
        # Get Person URN
        person_urn = get_linkedin_person_urn(access_token)
        if person_urn:
            print(f"Person URN: {person_urn}")
            
            # Update .env file
            update_env_file(access_token, person_urn)
            print("Successfully updated .env file")
        else:
            print("Failed to get Person URN. Check the logs for details.")
            print("Please provide your LinkedIn Person URN manually:")
            print("1. Go to your LinkedIn profile")
            print("2. Copy the URL (it should look like https://www.linkedin.com/in/your-name-123456789/)")
            print("3. The number at the end is your Person URN")
            person_urn = input("Enter your Person URN: ")
            if person_urn:
                update_env_file(access_token, person_urn)
                print("Successfully updated .env file with manual Person URN")
                
                # Verify the update
                dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
                if os.path.exists(dotenv_path):
                    with open(dotenv_path, 'r') as f:
                        content = f.read()
                        print(f"Current .env content:\n{content}")
                else:
                    print("Error: .env file was not created")
    else:
        print("Failed to obtain access token. Check the logs for details.")
