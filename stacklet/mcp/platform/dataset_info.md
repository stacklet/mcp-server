# Stacklet Platform Dataset Export Guide

Export GraphQL Connection data to CSV with filtering, custom columns, and JMESPath JSON transformations.

## ⚠️ Critical: Test Scale First

**Never export all resources** - use AssetDB for large-scale analysis instead.

**Always check scope:**
```python
# Test before full export
mcp__stacklet__platform_graphql_query(
    query="query { resources(first: 1, filterElement: {single: {name: \"provider\", value: \"aws\"}}) { pageInfo { total } } }"
)
```

**If total large or null**: Export likely slow; consider using `assetdb_sql_query`

## Basic Usage

```python
mcp__stacklet__platform_dataset_export(
    connection_field="accounts",
    columns=[
        {"name": "account_key", "path": "key"},
        {"name": "account_name", "path": "name"},
        {"name": "provider", "path": "provider"}
    ],
    timeout=30
)
```

## Column Configuration

- `name`: CSV column header
- `path`: Field path from connection node (`key`, `account.name`, `data`)
- `subpath`: JMESPath for JSON field transformation

### Common JMESPath Examples

```python
{"name": "tag_count", "path": "data", "subpath": "length(Tags || `[]`)"}
{"name": "env_tag", "path": "data", "subpath": "Tags[?Key=='Environment'].Value | [0]"}
```

## Filtering

**Discover filters:** Query `filterSchema { filters { name operators } }`

**Single filter:**
```python
params=[{"name": "filterElement", "type": "FilterElementInput",
         "value": {"single": {"name": "provider", "value": "aws"}}}]
```

**Multiple filters:**
```python
params=[{"name": "filterElement", "type": "FilterElementInput",
         "value": {"multiple": {"operator": "AND", "operands": [
             {"single": {"name": "provider", "value": "aws"}},
             {"single": {"name": "resource-type", "value": "aws.vpc"}}
         ]}}}]
```

**Common filters:** accounts (`provider`, `active`), resources (`provider`, `resource-type`, `region`), policies (`severity`, `compliance`)

## Node-Based Exports

**Get node ID:** Query `accounts(first: 1) { edges { node { id } } }`

**Export from node:**
```python
mcp__stacklet__platform_dataset_export(
    connection_field="groupMappings",
    node_id="WyJhY2NvdW50IiwgImdjcCIsICJzdGFja2xldC10ZXN0LXJ1bm5lciJd",
    columns=[{"name": "group_name", "path": "group.name"}]
)
```

**Node connections:** Account (`groupMappings`), Policy (`resources`, `bindings`), Binding (`executions`)

## Export Management

**Async export:** Use `timeout=0` to return immediately, then monitor with `platform_dataset_lookup(dataset_id, timeout=60)`

**Key status fields:** `dataset_id`, `success`, `download_url`, `available_until` (24hr expiry)

**Download:** `curl -L -o file.csv "download_url"` (follows S3 redirects)

## Quick Examples

**AWS VPC with tags:**
```python
mcp__stacklet__platform_dataset_export(
    connection_field="resources",
    columns=[
        {"name": "key", "path": "key"},
        {"name": "account", "path": "account.name"},
        {"name": "env_tag", "path": "data", "subpath": "Tags[?Key=='Environment'].Value | [0]"}
    ],
    params=[{"name": "filterElement", "type": "FilterElementInput",
             "value": {"multiple": {"operator": "AND", "operands": [
                 {"single": {"name": "resource-type", "value": "aws.vpc"}},
                 {"single": {"name": "region", "value": "us-east-1"}}
             ]}}}]
)
```

## Key Reminders

- Cannot use paging params (`first`, `after`) - export handles pagination
- `timeout=0` returns immediately; use `platform_dataset_lookup` to monitor
- Download URLs redirect to S3 - use `curl -L`
- Files expire after 24 hours
- Use GraphQL Node IDs for node-based exports
