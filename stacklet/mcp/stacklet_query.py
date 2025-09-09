#!/usr/bin/env python3


from typing import Any, Dict

import requests

from .stacklet_auth import load_stacklet_auth


def query_stacklet_graphql(
    query: str,
    variables: Dict[str, Any] | None = None,
    endpoint: str | None = None,
    access_token: str | None = None,
) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the Stacklet API.

    Args:
        query: The GraphQL query string
        variables: Optional variables for the query
        endpoint: Optional direct endpoint configuration
        access_token: Optional direct access token configuration

    Returns:
        Query result as dict
    """
    # Load credentials using the same logic as Stacklet Terraform provider
    creds = load_stacklet_auth(endpoint=endpoint, access_token=access_token)

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
