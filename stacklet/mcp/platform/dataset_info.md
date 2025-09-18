# Stacklet Platform Dataset Export Guide

This guide documents how to use the `platform_dataset_export` functionality to export large datasets from the Stacklet GraphQL API into CSV format.

## Overview

The platform dataset export tool allows you to:
- Export full datasets from GraphQL Connection fields
- Apply filters and parameters to scope the data
- Extract specific columns with custom names
- Use JMESPath expressions to transform JSON data
- Export from both root query connections and node-specific connections

## ⚠️ Scale Considerations

**While it's technically possible to export all resources, this is generally a terrible idea.** Resource datasets can be enormous and are far better handled with AssetDB SQL queries for analysis.

**Always test your query scope first:**
```python
# Test query scope before full export
mcp__stacklet__platform_graphql_query(
    query="""query {
      resources(first: 1, filterElement: {single: {name: "provider", value: "aws"}}) {
        pageInfo { total }
        edges { node { key resourceType } }
      }
    }"""
)
```

If `pageInfo.total` shows thousands or more records, consider:
1. **Adding more filters** (resource-type, region, account)
2. **Using AssetDB queries instead** for large-scale analysis
3. **Exporting incrementally** by region or resource type

**Better alternatives for large datasets:**
- Use `assetdb_sql_query` for complex analysis across millions of resources
- Export smaller, focused datasets (specific resource types, single regions)
- Start with accounts or policies which are typically much smaller

## Basic Usage

### Simple Root Query Export

Export all accounts with basic information:

```python
mcp__stacklet__platform_dataset_export(
    connection_field="accounts",
    columns=[
        {"name": "account_key", "path": "key"},
        {"name": "account_name", "path": "name"},
        {"name": "provider", "path": "provider"},
        {"name": "path", "path": "path"},
        {"name": "email", "path": "email"},
        {"name": "active", "path": "active"}
    ],
    timeout=30
)
```

## Column Configuration

Columns are defined with:
- `name`: Column header in the CSV
- `path`: Path to the data field (relative to the connection node)
- `subpath` (optional): JMESPath expression for JSON transformation

### Column Path Examples

| Path           | Description              |
|----------------|--------------------------|
| `key`          | Direct field on the node |
| `account.name` | Nested field access      |
| `data`         | Raw JSON field           |

### Subpath JSON Transformation Examples

```python
# Count array elements
{"name": "tag_count", "path": "data", "subpath": "length(Tags || `[]`)"}

# Extract first array element
{"name": "first_tag_key", "path": "data", "subpath": "Tags[0].Key || null"}

# Transform tag array to key-value pairs
{"name": "tags", "path": "tags", "subpath": "[].{key:key,value:value}"}
```

## Filtering Data

### Available Filter Operations

First, discover available filters for a connection:

```python
mcp__stacklet__platform_graphql_query(
    query="""query {
      resources(first: 1) {
        filterSchema {
          filters {
            name
            freeform
            operators
            defaultOperator
            suggestions
            docMarkdown
          }
        }
      }
    }"""
)
```

### Single Filter Example

```python
params=[
    {
        "name": "filterElement",
        "type": "FilterElementInput",
        "value": {
            "single": {
                "name": "provider",
                "operator": "equals",
                "value": "aws"
            }
        }
    }
]
```

### Multiple Filters with Boolean Logic

```python
params=[
    {
        "name": "filterElement",
        "type": "FilterElementInput",
        "value": {
            "multiple": {
                "operator": "AND",
                "operands": [
                    {"single": {"name": "provider", "operator": "equals", "value": "aws"}},
                    {"single": {"name": "active", "operator": "equals", "value": "true"}}
                ]
            }
        }
    }
]
```

### Common Filter Names by Connection

| Connection  | Common Filters                                                          |
|-------------|-------------------------------------------------------------------------|
| `accounts`  | `provider`, `active`, `name`, `path`, `email`, `tag`                    |
| `resources` | `provider`, `resource-type`, `account`, `region`, `resource-tag`, `key` |
| `policies`  | `provider`, `resource`, `category`, `severity`, `compliance`, `binding` |

### Scale Considerations for Filtering

⚠️ **Important**: Simple provider filtering (`provider:aws`) can return enormous datasets. Always test scope first:

```python
# ❌ Test this first - may be too broad
query = """query {
  resources(first: 1, filterElement: {single: {name: "provider", value: "aws"}}) {
    pageInfo { total }
  }
}"""
# If total > 10,000, add more filters

# ✅ Better - scoped to specific resource type and region
params=[
    {
        "name": "filterElement",
        "type": "FilterElementInput",
        "value": {
            "multiple": {
                "operator": "AND",
                "operands": [
                    {"single": {"name": "provider", "value": "aws"}},
                    {"single": {"name": "resource-type", "value": "aws.vpc"}},
                    {"single": {"name": "region", "value": "us-east-1"}}
                ]
            }
        }
    }
]
```

## Node-Based Exports

Export connections from specific GraphQL nodes by providing `node_id`:

### Get Node ID First

```python
# Get a specific account ID
mcp__stacklet__platform_graphql_query(
    query="""query {
      accounts(first: 1) {
        edges {
          node {
            id
            key
            name
          }
        }
      }
    }"""
)
```

### Export from Node

```python
mcp__stacklet__platform_dataset_export(
    connection_field="groupMappings",
    node_id="WyJhY2NvdW50IiwgImdjcCIsICJzdGFja2xldC10ZXN0LXJ1bm5lciJd",
    columns=[
        {"name": "mapping_id", "path": "id"},
        {"name": "account_name", "path": "account.name"},
        {"name": "group_name", "path": "group.name"},
        {"name": "dynamic", "path": "dynamic"}
    ]
)
```

### Available Node Connections

| Node Type      | Available Connections                                       |
|----------------|-------------------------------------------------------------|
| `Account`      | `groupMappings`                                             |
| `Policy`       | `resources`, `executions`, `collectionMappings`, `bindings` |
| `Binding`      | `executions`, `runs`                                        |
| `AccountGroup` | `accountMappings`                                           |

## Export Management

### Asynchronous Export with Monitoring

```python
# Start export without waiting (using filtered data for manageable size)
dataset_result = mcp__stacklet__platform_dataset_export(
    connection_field="policies",
    columns=[
        {"name": "policy_name", "path": "name"},
        {"name": "resource_type", "path": "resourceType"},
        {"name": "provider", "path": "provider"}
    ],
    timeout=0  # Return immediately
)

# Monitor progress with timeout
final_result = mcp__stacklet__platform_dataset_lookup(
    dataset_id=dataset_result["dataset_id"],
    timeout=60  # Wait up to 60 seconds for completion
)
```

### Export Status Fields

| Field             | Description                                                |
|-------------------|------------------------------------------------------------|
| `dataset_id`      | Unique identifier for the export                           |
| `started`         | ISO timestamp when export began                            |
| `processed_rows`  | Number of rows processed so far                            |
| `completed`       | ISO timestamp when export finished (null if still running) |
| `success`         | Boolean indicating success (null if still running)         |
| `message`         | Status message ("Exporting…", "Succeeded", etc.)           |
| `download_url`    | URL to download CSV (null if not complete)                 |
| `available_until` | ISO timestamp when download expires                        |

### Downloading the CSV File

The `download_url` will redirect to a signed S3 URL. Use tools that follow redirects:

```bash
# Download with curl (note the -L flag for redirects)
curl -L -o accounts.csv "https://console.william.sandbox.stacklet.dev/export/abc123/accounts.csv"

# Or with wget
wget --trust-server-names "https://console.william.sandbox.stacklet.dev/export/abc123/accounts.csv"
```

## Practical Examples

### Export AWS VPC Resources with Tag Analysis

```python
mcp__stacklet__platform_dataset_export(
    connection_field="resources",
    columns=[
        {"name": "resource_key", "path": "key"},
        {"name": "resource_type", "path": "resourceType"},
        {"name": "account_name", "path": "account.name"},
        {"name": "region", "path": "region"},
        {"name": "tag_count", "path": "data", "subpath": "length(Tags || `[]`)"},
        {"name": "environment_tag", "path": "data", "subpath": "Tags[?Key=='Environment'].Value | [0]"},
        {"name": "cost_center", "path": "data", "subpath": "Tags[?Key=='CostCenter'].Value | [0]"}
    ],
    params=[
        {
            "name": "filterElement",
            "type": "FilterElementInput",
            "value": {
                "multiple": {
                    "operator": "AND",
                    "operands": [
                        {"single": {"name": "resource-type", "operator": "equals", "value": "aws.vpc"}},
                        {"single": {"name": "region", "operator": "equals", "value": "us-east-1"}}
                    ]
                }
            }
        }
    ],
    timeout=30
)
```

### Export Policy Compliance Data

```python
mcp__stacklet__platform_dataset_export(
    connection_field="policies",
    columns=[
        {"name": "policy_name", "path": "name"},
        {"name": "resource_type", "path": "resourceType"},
        {"name": "provider", "path": "provider"},
        {"name": "severity", "path": "severity"},
        {"name": "compliance_frameworks", "path": "compliance"},
        {"name": "categories", "path": "category"},
        {"name": "system_policy", "path": "system"}
    ],
    params=[
        {
            "name": "filterElement",
            "type": "FilterElementInput",
            "value": {
                "multiple": {
                    "operator": "AND",
                    "operands": [
                        {"single": {"name": "severity", "value": "high"}},
                        {"single": {"name": "provider", "value": "aws"}}
                    ]
                }
            }
        }
    ]
)
```

## Important Notes

- **Paging Parameters**: Cannot use `first`, `after`, `last`, `before` in params - the export automatically handles pagination
- **Download Expiration**: CSV files are available for 24 hours after completion
- **Download URLs**: The `download_url` will redirect (HTTP 307) to a signed S3 URL - this is expected behavior. Use `curl -L` or similar redirect-following tools to download files.
- **Timeout Behavior**: Setting `timeout=0` returns immediately; setting a timeout waits for completion or timeout
- **JMESPath**: Use subpath for complex JSON transformations from the `data` field
- **Filter Discovery**: Always check `filterSchema` to understand available filters for each connection
- **Node IDs**: Use GraphQL Node IDs for node-based exports, not human-readable identifiers

## Troubleshooting

### Common Errors

1. **"Cannot query field X on type Y"**: Check that the connection exists on the specified node type
2. **"unknown filter name"**: Verify filter names using the `filterSchema` query
3. **"params must not set paging parameters"**: Remove `first`, `after`, `last`, `before` from params
4. **Invalid FilterElementInput**: Ensure filter structure uses `single` or `multiple` at top level

### Performance Tips

- Use specific filters to reduce dataset size
- Start with small test exports to verify column paths
- Use `timeout=0` for very large exports and monitor with lookup tool
- Consider the 24-hour download window when planning exports
