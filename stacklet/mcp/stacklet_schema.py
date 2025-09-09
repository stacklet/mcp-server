#!/usr/bin/env python3

import json

import requests

from graphql import GraphQLSchema, build_client_schema, get_introspection_query

from .stacklet_auth import load_stacklet_auth


# Global cache for schema data
_schema_cache = None


def get_stacklet_schema(
    endpoint: str | None = None, api_key: str | None = None
) -> GraphQLSchema | None:
    """
    Retrieve the GraphQL schema from a Stacklet endpoint.
    Uses caching to avoid repeated introspection queries.

    Args:
        endpoint: Optional direct endpoint configuration
        api_key: Optional direct API key configuration

    Returns:
        GraphQL schema as dict if successful, None otherwise
    """
    global _schema_cache

    # Return a deep copy of cached schema if available
    if _schema_cache is not None:
        return _schema_cache

    # Load credentials using the same logic as Stacklet Terraform provider
    creds = load_stacklet_auth(endpoint=endpoint, api_key=api_key)
    if not creds:
        return None

    # Use the standard GraphQL introspection query from graphql-core
    introspection_query = {"query": get_introspection_query()}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {creds.api_key}",
    }

    try:
        response = requests.post(
            creds.endpoint, json=introspection_query, headers=headers, timeout=30
        )
        response.raise_for_status()

        result = response.json()
        if errors := result.get("errors"):
            print(f"GraphQL errors: {errors}")
            return None

        schema = result.get("data", {}).get("__schema")

        # Cache the schema for future requests
        if schema:
            _schema_cache = build_client_schema({"__schema": schema})

        return _schema_cache

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        return None
