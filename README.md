# Social MCP: Multi-Agent Social Media Automation

## Overview
Social MCP is a multi-agent system for automating content extraction, tweet generation, posting, and engagement on platforms like Twitter and Bluesky. It uses LLMs for content generation, Playwright for browser automation, and APIs for platform integration.

## Architecture
- **MCP Server**: Hosts tool endpoints for:
  - Content extraction
  - Tweet generation using LLMs
  - Browser automation for Twitter (using Playwright)
  - Social media engagement
  - Content scheduling
- **MCP Client**: Orchestrates workflow, runs agents, manages LLM, and coordinates tool calls
- **Common**: Shared utilities for Google Sheets integration, retry logic, and secrets management

## Core Features
1. **Twitter Automation**
   - Persistent session management
   - Robust login detection
   - Tweet posting with retry logic
   - Search and engagement automation
   - Hashtag-based content discovery

2. **Content Generation**
   - LLM-powered tweet generation
   - Content scheduling
   - Multi-platform support

3. **Browser Automation**
   - Persistent session handling
   - Robust page state verification
   - Automatic recovery from navigation issues
   - URL encoding and proper page loading

## Directory Structure
```
social_mcp/
├── mcp_server/
│   ├── tools/
│   │   ├── post_tweets.py      # Twitter automation
│   │   ├── generate_tweets.py  # LLM tweet generation
│   │   └── engage_posts.py     # Social engagement
│   ├── server.py
│   └── config.py
├── mcp_client/
│   ├── agents/
│   ├── llm_orchestrator.py
│   ├── workflow_graph.py
│   └── client.py
├── common/
│   ├── google_sheets.py
│   ├── retry_utils.py
│   └── secrets.py
├── .env
├── requirements.txt
├── README.md
└── setup.sh
```

## Implementation Details

### Twitter Automation (post_tweets.py)
- **Session Management**
  - Persistent browser sessions
  - Automatic login detection
  - Session recovery

- **Robust Page Handling**
  - URL encoding for search terms
  - Continuous page state verification
  - Automatic navigation recovery
  - Retry logic for failed operations

- **Engagement Features**
  - Hashtag-based search
  - Tweet liking automation
  - Content discovery

### Browser Automation Best Practices
1. **Page Loading**
   - Use `domcontentloaded` for initial load
   - Wait for specific elements
   - Verify page state

2. **Error Handling**
   - Retry logic for failed operations
   - Graceful recovery from errors
   - Detailed logging

3. **Session Management**
   - Persistent context
   - Login state verification
   - Automatic session recovery

## Setup
1. Clone the repo and enter the directory:
   ```bash
   git clone <repository-url>
   cd social_mcp
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install
   ```

3. Configure your `.env` file with:
   ```
   TWITTER_USERNAME=your_username
   TWITTER_PASSWORD=your_password
   PLAYWRIGHT_SESSION_DIR=./playwright_session
   HEADLESS=false  # Set to true for headless operation
   ```

4. Set up Google Sheets API and OAuth credentials

## Usage
1. Start the MCP server from /social_mcp:
   ```bash
   python mcp_server/server.py
   ```

2. Run the MCP client from /social_mcp:
   ```bash
   python mcp_client/client.py
   ```


## Adding New Features
- **New Tools**: Add to `mcp_server/tools/` and register in `server.py`
- **New Agents**: Add to `mcp_client/agents/` and update `workflow_graph.py`
- **Browser Automation**: Follow the patterns in `post_tweets.py` for robust implementation

## Security
- Store all secrets in `.env`
- Use OAuth scopes for Google Sheets and Bluesky
- Playwright scripts handle MFA/CAPTCHA gracefully
- Session data stored securely in `playwright_session` directory

## Best Practices
1. **Browser Automation**
   - Always verify page state
   - Use proper URL encoding
   - Implement retry logic
   - Handle navigation issues

2. **Error Handling**
   - Log all operations
   - Implement graceful recovery
   - Use appropriate timeouts

3. **Session Management**
   - Verify login state
   - Handle session recovery
   - Clean up resources properly 


** To do
1. Get content from tweet and bsky, use LLM to get response and post it
2. Incorporate second twitter account to post and like