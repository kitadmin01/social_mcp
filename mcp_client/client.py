import asyncio
import os
import sys
import logging
import signal
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from workflow_graph import WorkflowGraph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Global flag for graceful shutdown
running = True

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global running
    logger.info("Received shutdown signal. Gracefully stopping...")
    running = False

def load_config():
    """Load configuration from environment variables."""
    try:
        # Load .env file
        dotenv_path = find_dotenv()
        if not dotenv_path:
            logger.error("No .env file found")
            raise ValueError("No .env file found")
            
        load_dotenv(dotenv_path)
        logger.info(f"Loaded .env from: {dotenv_path}")
        
        # Verify required environment variables
        required_vars = [
            'GOOGLE_SHEET_ID',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHANNEL',
            'WORKFLOW_INTERVAL_MINUTES'
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
        logger.info("Configuration loaded successfully")
        
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise

async def run_workflow():
    """Run the social media workflow."""
    session = None
    try:
        # Initialize server parameters
        server_params = StdioServerParameters(
            command="python",
            args=[os.path.join(project_root, "mcp_server/server.py")],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                logger.info("Initializing MCP session...")
                await session.initialize()
                
                logger.info("Loading MCP tools...")
                tools = await load_mcp_tools(session)
                
                # Create and run the workflow graph
                logger.info("Initializing workflow graph...")
                workflow = WorkflowGraph(batch_size=5)  # Configure batch size
                
                # Check platform status before starting
                status = workflow.get_status()
                logger.info("Platform Status:")
                for platform, platform_status in status.items():
                    logger.info(f"  {platform}: {'Ready' if platform_status else 'Not Available'}")
                
                graph = workflow.build_workflow_graph()
                
                # Get workflow interval from environment
                interval_minutes = int(os.getenv('WORKFLOW_INTERVAL_MINUTES', '60'))
                logger.info(f"Workflow will run every {interval_minutes} minutes")
                
                while running:
                    try:
                        # Run the workflow
                        logger.info("Starting workflow execution...")
                        start_time = datetime.now()
                        
                        # First try to process content
                        result = await graph.ainvoke({})
                        
                        # If no content, run engagement tasks
                        if result.get('error') and "No content available" in result['error']:
                            logger.info("No content to process, running engagement tasks...")
                            
                            # Run Twitter engagement
                            try:
                                logger.info("Running Twitter engagement...")
                                twitter_tool = next((tool for tool in tools if tool.name == "engage_twitter"), None)
                                if twitter_tool:
                                    await twitter_tool.ainvoke({"count": 5})
                                    logger.info("Twitter engagement completed")
                                else:
                                    logger.error("Twitter engagement tool not found")
                            except Exception as e:
                                logger.error(f"Error in Twitter engagement: {str(e)}")
                            
                            # Run Bluesky engagement
                            try:
                                logger.info("Running Bluesky engagement...")
                                bsky_tool = next((tool for tool in tools if tool.name == "engage_bsky"), None)
                                if bsky_tool:
                                    await bsky_tool.ainvoke({"count": 5})
                                    logger.info("Bluesky engagement completed")
                                else:
                                    logger.error("Bluesky engagement tool not found")
                            except Exception as e:
                                logger.error(f"Error in Bluesky engagement: {str(e)}")
                            
                            result = {"status": "engagement_completed"}
                        
                        end_time = datetime.now()
                        
                        # Log results
                        duration = (end_time - start_time).total_seconds()
                        logger.info(f"Workflow completed in {duration:.2f} seconds")
                        
                        if result.get('error'):
                            if "No content available" in result['error']:
                                logger.info("No content to process, continuing with engagement")
                            else:
                                logger.error(f"Workflow completed with error: {result['error']}")
                        else:
                            logger.info("Workflow completed successfully")
                            if result.get('rows'):
                                logger.info(f"Processed {len(result['rows'])} items")
                                for row in result['rows']:
                                    logger.info(f"  - {row.get('title', 'Untitled')}: {row.get('status', 'Unknown')}")
                        
                        # Calculate next run time
                        next_run = datetime.now() + timedelta(minutes=interval_minutes)
                        logger.info(f"Next workflow run scheduled for: {next_run}")
                        
                        # Wait until next run time or until shutdown signal
                        while running and datetime.now() < next_run:
                            await asyncio.sleep(1)
                            
                    except Exception as e:
                        logger.error(f"Error in workflow iteration: {str(e)}", exc_info=True)
                        # Wait a bit before retrying
                        await asyncio.sleep(60)
                
                # Cleanup
                if workflow:
                    await workflow.cleanup()
                
    except Exception as e:
        logger.error(f"Error running workflow: {str(e)}", exc_info=True)
        raise
    finally:
        if session:
            try:
                # Don't try to close the session, just let it be cleaned up by the context manager
                pass
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

def main():
    """Main entry point."""
    try:
        logger.info("MCP Client starting...")
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Load configuration
        load_config()
        
        # Run the workflow
        asyncio.run(run_workflow())
        
        logger.info("MCP Client stopped gracefully")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 