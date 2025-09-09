#!/usr/bin/env python3


from typing import Any, Dict

import requests

from .stacklet_auth import StackletCredentials


def query_stacklet_graphql(
    creds: StackletCredentials,
    query: str,
    variables: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the Stacklet API.

    Args:
        creds: Stacklet credentials (endpoint and access token)
        query: The GraphQL query string
        variables: Optional variables for the query

    Returns:
        Query result as dict
    """

    # Prepare the GraphQL request
    request_data = {"query": query}
    if variables:
        request_data["variables"] = variables

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {creds.access_token}",
    }

    response = requests.post(creds.endpoint, json=request_data, headers=headers, timeout=30)
    # 400s and 500s may still contain response data, don't raise.
    return response.json()
