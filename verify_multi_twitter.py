#!/usr/bin/env python3
"""
Verification script for multi-account Twitter functionality
"""

import os
import sys
from dotenv import load_dotenv, find_dotenv

def verify_environment():
    """Verify that all required environment variables are set."""
    print("🔍 Verifying environment variables...")
    
    # Load .env file
    dotenv_path = find_dotenv()
    if not dotenv_path:
        print("❌ No .env file found")
        return False
    
    load_dotenv(dotenv_path)
    print(f"✅ Loaded .env from: {dotenv_path}")
    
    # Check required variables
    required_vars = {
        'TWITTER_USERNAME': 'Primary Twitter username',
        'TWITTER_PASSWORD': 'Primary Twitter password',
        'TWITTER_USERNAME_2': 'Secondary Twitter username',
        'TWITTER_PASSWORD_2': 'Secondary Twitter password',
        'GOOGLE_SHEET_ID': 'Google Sheet ID',
        'TELEGRAM_BOT_TOKEN': 'Telegram Bot Token',
        'TELEGRAM_CHANNEL': 'Telegram Channel'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f"{var} ({description})")
        else:
            # Mask sensitive values
            if 'PASSWORD' in var or 'TOKEN' in var:
                masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '***'
                print(f"✅ {var}: {masked_value}")
            else:
                print(f"✅ {var}: {value}")
    
    if missing_vars:
        print(f"\n❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    
    print("\n✅ All required environment variables are set!")
    return True

def verify_imports():
    """Verify that all required modules can be imported."""
    print("\n🔍 Verifying imports...")
    
    try:
        from mcp_server.tools.multi_twitter import MultiTwitterPlaywright
        print("✅ MultiTwitterPlaywright import successful")
    except ImportError as e:
        print(f"❌ Failed to import MultiTwitterPlaywright: {e}")
        return False
    
    try:
        from mcp_client.workflow_graph import WorkflowGraph
        print("✅ WorkflowGraph import successful")
    except ImportError as e:
        print(f"❌ Failed to import WorkflowGraph: {e}")
        return False
    
    print("✅ All imports successful!")
    return True

def verify_account_configuration():
    """Verify the Twitter account configuration."""
    print("\n🔍 Verifying Twitter account configuration...")
    
    primary_username = os.getenv('TWITTER_USERNAME')
    secondary_username = os.getenv('TWITTER_USERNAME_2')
    
    print(f"Primary account: {primary_username}")
    print(f"Secondary account: {secondary_username}")
    
    if primary_username == secondary_username:
        print("⚠️  Warning: Both accounts have the same username!")
        return False
    
    print("✅ Account configuration looks good!")
    return True

def main():
    """Main verification function."""
    print("🚀 Multi-Account Twitter Setup Verification")
    print("=" * 50)
    
    # Verify environment
    if not verify_environment():
        print("\n❌ Environment verification failed!")
        return False
    
    # Verify imports
    if not verify_imports():
        print("\n❌ Import verification failed!")
        return False
    
    # Verify account configuration
    if not verify_account_configuration():
        print("\n❌ Account configuration verification failed!")
        return False
    
    print("\n" + "=" * 50)
    print("✅ All verifications passed!")
    print("\n📋 Next steps:")
    print("1. Run the test script: python mcp_server/test/test_multi_twitter.py")
    print("2. Start the workflow: python mcp_client/client.py")
    print("3. Monitor the logs for both Twitter accounts")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 