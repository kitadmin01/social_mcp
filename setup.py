from setuptools import setup, find_packages

setup(
    name="social_mcp",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "gspread",
        "python-dotenv",
        "mcp",
        "langchain",
        "langchain-openai",
        "langgraph",
        "langchain-mcp-adapters",
    ],
) 