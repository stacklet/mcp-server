#!/usr/bin/env python3

import json

from typing import Any, Dict

import requests

from .stacklet_auth import load_stacklet_auth


def query_stacklet_graphql(
    query: str,
    variables: Dict[str, Any] | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> Dict[str, Any] | None:
    """
    Execute a GraphQL query against the Stacklet API.

    Args:
        query: The GraphQL query string
        variables: Optional variables for the query
        endpoint: Optional direct endpoint configuration
        api_key: Optional direct API key configuration

    Returns:
        Query result as dict if successful, None otherwise
    """
    # Load credentials using the same logic as Stacklet Terraform provider
    creds = load_stacklet_auth(endpoint=endpoint, api_key=api_key)
    if not creds:
        return None

    # Prepare the GraphQL request
    request_data = {"query": query}
    if variables:
        request_data["variables"] = variables

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {creds.api_key}",
    }

    try:
        response = requests.post(creds.endpoint, json=request_data, headers=headers, timeout=30)
        # 400s and 500s may still contain response data, don't raise.
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        return None
