from itertools import chain
from textwrap import dedent
from typing import Any, Callable

from fastmcp import FastMCP
from fastmcp.tools import Tool

from . import __version__
from .assetdb.tools import tools as assetdb_tools
from .docs.tools import tools as docs_tools
from .lifespan import lifespan
from .platform.tools import tools as platform_tools


def make_server() -> FastMCP:
    """Create an MCP server.."""
    tool_sets = [
        assetdb_tools,
        docs_tools,
        platform_tools,
    ]
    tools: list[Tool | Callable[..., Any]] = list(chain(*(tool_set() for tool_set in tool_sets)))

    return FastMCP(
        name="Stacklet",
        version=__version__,
        instructions=dedent(
            """
            Stacklet provides comprehensive cloud governance and analytics capabilities through
            integrated toolsets. These enable you to understand, analyze, and govern your entire
            cloud estate at scale.

            ## Start Here: Critical Info Tools
            Always call these info tools first - they contain essential guidance and best practices:
            - "assetdb_sql_info" - For cloud asset analytics
            - "platform_graphql_info" - For governance operations
            - "platform_dataset_info" - For large-scale data exports
            - "docs_list" then "docs_read" - Live platform documentation

            ## Core Capabilities

            ### 🔍 Cloud Asset Discovery & Analytics
            Analyze your entire multi-cloud estate with a continuously-updated PostgreSQL warehouse:
            - Query resource inventories, costs, and relationships across AWS, GCP, Azure, Tencent
            - Perform complex analytics on resource usage patterns and cost optimization
            - Track resource changes and lifecycle management
            - Build custom reports with SQL

            ### 🛡️ Cloud Governance Operations
            Execute governance policies and manage compliance at scale:
            - Deploy and manage Cloud Custodian policies across accounts and regions
            - Monitor policy execution results and resource compliance
            - Configure account grouping and binding relationships
            - Export large governance datasets for analysis and reporting

            ### 📚 Platform Knowledge Access
            Access live Stacklet platform documentation and guidance:
            - Browse comprehensive how-to guides, reference docs, and runbooks
            - Get LLM-optimized documentation specifically designed for AI assistance
            - Access up-to-date platform configuration and troubleshooting information

            ## Workflow Patterns
            - **Exploration**: Start small with targeted queries, then scale to larger datasets
            - **Analysis**: Use SQL for complex analytics, GraphQL for governance operations
            - **Scale**: Export large datasets when working with 10K+ records
            - **Integration**: Combine asset data with governance results for comprehensive insights

            The info tools will guide you through each toolset's specific best practices.
            """
        ),
        tools=tools,
        lifespan=lifespan,
    )


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = make_server()
    mcp.run(show_banner=False)
