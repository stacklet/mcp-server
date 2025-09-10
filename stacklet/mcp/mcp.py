import json
import re

from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from graphql import print_type

from .docs_handler import list_documentation_files, read_documentation_file
from .models import DocContent, DocsList
from .stacklet_auth import load_stacklet_auth
from .stacklet_query import query_stacklet_graphql
from .stacklet_schema import get_stacklet_schema


mcp = FastMCP("Stacklet")


class Error(ToolError):
    """An error from the tool."""

    def __init__(self, message: str, suggestion: str | None = None):
        if suggestion:
            message += f". *Suggestion*: {suggestion}."
        super().__init__(message)


@mcp.tool()
def docs_list() -> DocsList:
    """
    List all available Stacklet user documentation files.

    Returns:
        Available documentation files
    Note:
        This information is most valuable when "index_llms.md" has already been
        seen via the docs_read tool.
    """
    return DocsList(
        available_files=list_documentation_files(),
        note="Use docs_read with any of these file paths to read the content",
    )


@mcp.tool()
def docs_read(file_path: Path) -> DocContent:
    """
    Read a Stacklet documentation file.

    Args:
        file_path: Relative path to the documentation file (e.g., "index_llms.md")

    Returns:
        The content of the file

    Note:
        The best starting point is "index_llms.md" which provides an overview
        of all available documentation.
    """
    content = read_documentation_file(file_path)
    if content is None:
        raise Error(
            f"File '{file_path}' not found or not accessible",
            suggestion="Try 'index_llms.md' as a starting point, or check docs_list",
        )

    return DocContent(file_path=file_path, content=content)


@mcp.tool()
def platform_graphql_info() -> str:
    """
    Key information for LLMs using the platform_graphql_ tools; call this first.

    Returns:
        Text to guide correct and effective use of the toolset.
    """
    return """
## **Stacklet GraphQL API Overview**

The Platform GraphQL API is a mechanism for interacting with the Stacklet Platform.
It enables a client to do anything a user could do in the console UI, and sometimes
offers additional capabilities.

The Stacklet documentation (especially the glossary) explains the core concepts and
the relations between them; always remember that concepts from the API will often be
decribed with more nuance in the documentation for Stacklet as a whole, and that the
docs exist to help you make correct and effective requests. Make use of them.

### **API Principles**

When composing a query, always look up the types you're using in the schema first.

Whenever a result type includes "problems", ALWAYS query for problems alongside other
results. Anything mentioned in problems is always very important.

Many investigative queries will require that you use the Relay-style Connection types
defined in the schema. When querying connections, always remember to:

- Request small pages, to keep context compact; consider 5 or 10 a reasonable default.
- Take advantage of the "PageInfo" type for total count queries. Do not attempt to
  count by paging.
- When you need to search or refine results, query the Connection's "filterSchema",
  and use that to compose "FilterElementInput" values.
- When you need a large result set, make small first queries to confirm the shape and
  value of the data first; only then, use the "exportConnection" mutation to generate
  a CSV which can be downloaded locally for analysis with more suitable tools.

Try to avoid nesting connection queries. With small page sizes, a single nested
connection is probably fine; deeper nesting can be very inefficient, and may cause
the query to time out.

There are many valid example queries in the API section of the Stacklet documentation.

Some entities have a "system" field; when true, this indicates that the entity cannot
be mutated by a client at all.

Many entities support the "HasACL" interface, which can be used to determine ownership
and permissions.

Whenever creating or updating entities with a "description" field, use it to document
your identity as an LLM, and the context in which you decided to take the action. Be
concise, and append to existing descriptions without replacing them.

In general, prefer to update entities you created yourself, and/or entities that you
have been specifically requested to alter.

### **Accounts and Policies**

Accounts should only rarely be added to the platform, or updated directly; prefer to
configure account discovery at the organization level instead. This is likely to
require human support.

As an LLM, you're well suited to writing policies, and can get many examples via the
"sourceYAML" field; especially policies in system collections, which are often examples
of best practices.

However, adding new policies to the platform is complicated and must be mediated via an
external SCM provider, such as GitHub or Bitbucket. You'll need some access to these
tools, and may need some steps to be taken by a human; check the documentation for full
details and make a plan before attempting to take action. Be aware that pages which
mention RepositoryConfig, or DPCs, are more authoritative than pages which don't; pages
referencing repositories without mentioning these concepts are more likely to be
outdated.

### **Controlling Stacklet**

https://registry.terraform.io/providers/stacklet/stacklet/latest/docs is often the
ideal way to manage Stacklet, for all the usual reasons that IaC is superior to ad-
hoc intervention. If that's not possible, mutations via the GraphQL API are always
possible.

Account groups, policy collections, and bindings (which link the two) are the main
entities suited to manipulation, because they define the sets of policies applied to
sets of accounts.

Notifications can be configured by creating report groups, which can be associated
with bindings to report their results. Never attempt to alter report groups named
after binding UUIDs; always name report groups clearly and human-readably.

The notifications use jinja2 templates, which can be created and updated over the
API if the existing ones don't suit your needs; always use the "previewTemplate"
functionality to validate your work.

### **Analyzing findings**

Remember to explore these datasets with few small pages, and capture complete datasets
by exporting the full connection once you've determined the fields you need. This can
get you large datasets for local analysis with dedicated tools, without overwhelming an
LLM's context window.

Resources are a direct window into the contents of your cloud estate, and are useful
for inspecting individual resources (including their change history and coarse-grained
costs). Larger-scale analysis is better performed via the AssetDB tools.

Resource matches are a flattened representation of pairs of (resource, policy) where
the policy currently matches the resource. There's almost no point querying it without
any filters applied, but it lets you slice that relation in either dimension. If you
already know the policy, or account, you can look up matches via that node in GraphQL.

Examining the validation status of accounts, and the results of binding runs and
individual policy executions, can help you track down problems. The "executionProblems"
API is not currently a useful tool, except perhaps in estimating raw error rates across
all executions.
"""


@mcp.tool()
def platform_graphql_list_types(match: str | None = None) -> list[str]:
    """
    List the types available in the Stacklet Platform GraphQL API.

    Args:
        match: Optional regular expression filter

    Returns:
        List of type names
    """
    creds = load_stacklet_auth()
    schema = get_stacklet_schema(creds)
    names = schema.type_map.keys()
    if match:
        f = re.compile(match)
        names = filter(f.search, names)

    return sorted(names)


@mcp.tool()
def platform_graphql_get_types(type_names: list[str]) -> str:
    """
    Retrieve information about types in the Stacklet Platform GraphQL API.

    Args:
        type_names: Names of requested types.

    Returns:
        JSON string mapping valid type names to GraphQL SDL definitions.
    """
    creds = load_stacklet_auth()
    schema = get_stacklet_schema(creds)
    found = {}
    for type_name in type_names:
        if match := schema.type_map.get(type_name):
            found[type_name] = print_type(match)

    return json.dumps(found)


@mcp.tool()
def platform_graphql_query(query: str, variables: dict[str, Any] | None = None) -> str:
    """
    Execute a GraphQL query against the Stacklet API.

    Only call this tool when you understand the principles outlined in the
    platform_graphql_info tool. Always remember to check input and output
    types before you use them.

    Args:
        query: The GraphQL query string
        variables: Variables dict for the query

    Returns:
        JSON string of the query result
    """

    # Execute the query
    creds = load_stacklet_auth()
    result = query_stacklet_graphql(creds, query, variables or {})
    return json.dumps(result, indent=2)


def main() -> None:
    """Main entry point for the MCP server"""
    mcp.run()
