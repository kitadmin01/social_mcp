import asyncio
import os
import sys
import logging
import signal
import random
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
# Global Twitter instance to keep sessions open
global_twitter = None

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global running, global_twitter
    logger.info("Received shutdown signal. Gracefully stopping...")
    running = False
    # Close Twitter sessions on shutdown
    if global_twitter:
        asyncio.create_task(global_twitter.close_session())

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
            'WORKFLOW_INTERVAL_MINUTES',
            'TWITTER_LIKE_COUNT',
            'BLUESKY_LIKE_COUNT',
            'LINKEDIN_LIKE_COUNT'
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
    global global_twitter
    session = None
    try:
        # Initialize server parameters
        server_params = StdioServerParameters(
            command="python",
            args=[os.path.join(project_root, "mcp_server/server.py")],
            env={
                **os.environ,  # Pass through all environment variables
                "HEADLESS": os.getenv("HEADLESS", "true")  # Ensure HEADLESS is set
            }
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
                    if platform.startswith('twitter_'):
                        account_name = platform.replace('twitter_', '')
                        status_text = 'Ready' if platform_status else 'Not Available'
                        logger.info(f"  Twitter ({account_name}): {status_text}")
                    else:
                        logger.info(f"  {platform}: {'Ready' if platform_status else 'Not Available'}")
                
                graph = workflow.build_workflow_graph()
                
                # Get workflow interval from environment
                interval_minutes = int(os.getenv('WORKFLOW_INTERVAL_MINUTES', '60'))
                logger.info(f"Workflow will run every {interval_minutes} minutes")
                
                # Initialize global Twitter instance once
                from mcp_server.tools.multi_twitter import MultiTwitterPlaywright
                global_twitter = MultiTwitterPlaywright()
                logger.info("Initialized global Twitter instance with persistent sessions")
                
                while running:
                    try:
                        # Run the workflow
                        logger.info("Starting workflow execution...")
                        start_time = datetime.now()
                        
                        # First try to process content
                        result = await graph.ainvoke({})
                        
                        # Always run engagement tasks (not just when no content)
                        logger.info("Running engagement tasks...")
                        
                        # Run Twitter engagement with both accounts using persistent sessions
                        try:
                            logger.info("Running Twitter engagement with both accounts using persistent sessions...")
                            
                            # Get search terms for each account
                            search_terms_primary = os.getenv('SEARCH_TERMS_PRIMARY', '#blockchain,#crypto,#web3,#defi,#nft')
                            search_terms_secondary = os.getenv('SEARCH_TERMS_SECONDARY', '#cryptotrading,#bitcoin,#ethereum,#altcoin')
                            
                            search_terms_primary_list = [term.strip() for term in search_terms_primary.split(',')]
                            search_terms_secondary_list = [term.strip() for term in search_terms_secondary.split(',')]
                            
                            # Select random search terms for each account
                            primary_search_term = random.choice(search_terms_primary_list)
                            secondary_search_term = random.choice(search_terms_secondary_list)
                            
                            twitter_like_count = int(os.getenv('TWITTER_LIKE_COUNT', '10'))
                            likes_per_account = twitter_like_count // 2
                            
                            # Engage with primary account using primary search terms
                            logger.info(f"Primary account using search term: {primary_search_term}")
                            primary_success = await global_twitter.search_and_like_tweets(
                                search_term=primary_search_term, 
                                max_likes=likes_per_account, 
                                account_name='primary'
                            )
                            
                            # Engage with secondary account using secondary search terms
                            logger.info(f"Secondary account using search term: {secondary_search_term}")
                            secondary_success = await global_twitter.search_and_like_tweets(
                                search_term=secondary_search_term, 
                                max_likes=likes_per_account, 
                                account_name='secondary'
                            )
                            
                            if primary_success:
                                logger.info(f"Primary Twitter account engagement completed with {likes_per_account} likes")
                            else:
                                logger.warning("Primary Twitter account engagement failed")
                                
                            if secondary_success:
                                logger.info(f"Secondary Twitter account engagement completed with {likes_per_account} likes")
                            else:
                                logger.warning("Secondary Twitter account engagement failed")
                            
                            # Don't close sessions - keep them open for next cycle
                            logger.info("Keeping Twitter browser sessions open for next cycle")
                            
                        except Exception as e:
                            logger.error(f"Error in Twitter engagement: {str(e)}")
                        
                        # Run Bluesky engagement
                        # COMMENTED OUT: Bluesky like feature disabled
                        # try:
                        #     logger.info("Running Bluesky engagement...")
                        #     bsky_tool = next((tool for tool in tools if tool.name == "engage_bsky"), None)
                        #     if bsky_tool:
                        #         bsky_like_count = int(os.getenv('BLUESKY_LIKE_COUNT', '10'))
                        #         await bsky_tool.ainvoke({"count": bsky_like_count})
                        #         logger.info(f"Bluesky engagement completed with {bsky_like_count} likes")
                        #     else:
                        #         logger.error("Bluesky engagement tool not found")
                        # except Exception as e:
                        #     logger.error(f"Error in Bluesky engagement: {str(e)}")
                        
                        # Run LinkedIn engagement
                        try:
                            logger.info("Running LinkedIn engagement...")
                            linkedin_tool = next((tool for tool in tools if tool.name == "engage_linkedin"), None)
                            if linkedin_tool:
                                linkedin_like_count = int(os.getenv('LINKEDIN_LIKE_COUNT', '5'))
                                await linkedin_tool.ainvoke({"count": linkedin_like_count})
                                logger.info(f"LinkedIn engagement completed with {linkedin_like_count} likes")
                            else:
                                logger.error("LinkedIn engagement tool not found")
                        except Exception as e:
                            logger.error(f"Error in LinkedIn engagement: {str(e)}")
                        
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
        # Close Twitter sessions on final cleanup
        if global_twitter:
            try:
                await global_twitter.close_session()
                logger.info("Closed Twitter sessions on final cleanup")
            except Exception as e:
                logger.error(f"Error closing Twitter sessions: {str(e)}")
        
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