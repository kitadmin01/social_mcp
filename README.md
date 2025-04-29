# Social MCP: Multi-Agent Social Media Automation

## Overview
Social MCP is a multi-agent system for automating content extraction, tweet generation, posting, and engagement on platforms like Twitter and Bluesky. It uses LLMs for content generation, Playwright for browser automation, and APIs for platform integration.

## Architecture
- **MCP Server**: Hosts tool endpoints (content extraction, tweet generation, posting, engagement, scheduling).
- **MCP Client**: Orchestrates workflow, runs agents, manages LLM, and coordinates tool calls.
- **Common**: Shared utilities (Google Sheets, retry logic, secrets management).

## Directory Structure
```
social_mcp/
├── mcp_server/
│   ├── tools/
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

## Setup
1. Clone the repo and enter the directory.
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install
   ```
3. Configure your `.env` file with API keys and credentials.
4. Set up Google Sheets API and OAuth credentials.

## Usage
- Start the MCP server: `python mcp_server/server.py`
- Run the MCP client: `python mcp_client/client.py`

## Adding New Agents/Tools
- Add new tools in `mcp_server/tools/` and register them in `server.py`.
- Add new agents in `mcp_client/agents/` and update the workflow in `workflow_graph.py`.

## Security
- Store all secrets in `.env`.
- Use OAuth scopes for Google Sheets and Bluesky.
- Playwright scripts should handle MFA/CAPTCHA gracefully. 