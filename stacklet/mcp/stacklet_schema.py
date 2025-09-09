#!/usr/bin/env python3


import requests

from graphql import GraphQLSchema, build_client_schema, get_introspection_query

from .stacklet_auth import StackletCredentials


# Global cache for schema data
_schema_cache = None


def get_stacklet_schema(creds: StackletCredentials) -> GraphQLSchema:
    """
    Retrieve the GraphQL schema from a Stacklet endpoint.
    Uses caching to avoid repeated introspection queries.

    Args:
        creds: Stacklet credentials

    Returns:
        GraphQL schema
    """
    global _schema_cache

    # Return a deep copy of cached schema if available
    if _schema_cache is not None:
        return _schema_cache

    # Use the standard GraphQL introspection query from graphql-core
    introspection_query = {"query": get_introspection_query()}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {creds.access_token}",
    }

    response = requests.post(creds.endpoint, json=introspection_query, headers=headers, timeout=30)
    response.raise_for_status()

    result = response.json()
    if errors := result.get("errors"):
        raise Exception(f"GraphQL introspection errors: {errors}")

    schema = result.get("data", {}).get("__schema")
    if not schema:
        raise Exception("GraphQL introspection returned no schema data")

    # Cache the schema for future requests
    _schema_cache = build_client_schema({"__schema": schema})
    return _schema_cache
