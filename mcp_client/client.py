import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from workflow_graph import WorkflowGraph

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def main():
    print("MCP Client starting. Connecting to MCP server and running workflow...")

    async def run_workflow():
        server_params = StdioServerParameters(
            command="python",
            args=[os.path.join(project_root, "mcp_server/server.py")],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                
                # Create and run the workflow graph
                workflow = WorkflowGraph()
                graph = workflow.build_workflow_graph()
                
                # Run the workflow
                result = await graph.ainvoke({})
                print("Workflow completed with result:", result)

    asyncio.run(run_workflow())

if __name__ == "__main__":
    main() 