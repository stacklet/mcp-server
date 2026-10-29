## **Stacklet AssetDB SQL Overview**

Stacklet's centralized PostgreSQL 16 data warehouse containing all cloud resource data, relationships, and metadata for efficient large-scale analysis.

### **⚠️ Scale Warning**

Many AssetDB tables are extremely large. Always use LIMIT and indexed column filters to avoid table scans.

### **Key Tables**

| Table                                    | Purpose                               | Scale           | Usage Notes                                            |
| ---------------------------------------- | ------------------------------------- | --------------- | ------------------------------------------------------ |
| `resources`                              | Current resource JSON                 | Very Large      | LIMIT + indexed filters required                       |
| `resource_revisions`                     | Resource history JSON                 | Extremely Large | Primary key access only                                |
| `aws_s3`, `gcp_gke_cluster`, etc.        | Provider-specific columns             | Large           | Preferred over raw JSON for analysis                   |
| `resource_tags`, `resource_tags_mapping` | Tag analysis                          | Large           | Start here for tag queries                             |
| `account_cost_monthly`                   | Cost per month/service/account/region | Medium          | Best starting point for costs                          |
| `account_focus_cost`                     | Cost per day/service/account/region   | Large           | `account_cost_monthly` with daily detail               |
| `resource_cost_monthly`                  | Cost per month/resource               | Large           | Best starting point for resource-level costs           |
| `resource_focus_cost`                    | Cost per day/service/resource         | Very Large      | `resource_cost_monthly` with daily detail              |
| `cost_source`                            | Lookup table for cost sources         | Very Small      | Sources of ingested cost data                          |
| `account_id`                             | Lookup table for accounts             | Small           | Bridge between cost tables and account/provider detail |
| `resource_id`                            | Lookup table for resources            | Medium          | Bridge between cost tables and resource detail         |
| `cloud_service`                          | Lookup table for services             | Small           | Bridge between cost tables and service/provider names  |
| `cloud_region`                           | Lookup table for regions              | Small           | Bridge between cost tables and region names            |

### **Special Considerations**

- Most table columns are commented. When investigating table structure, these are valuable.
- Foreign key constraints do not tell the whole story; there are many implicit foreign relations.

### **Cost Data**

- Do not filter on `current` to pick a month; filter on `date`. `current` marks each account's (`account_cost_monthly`) or resource's (`resource_cost_monthly`) own latest month, not the latest calendar month, and a resource that has stopped costing has no current row. Rows are never superseded, so filtering `current = true` silently drops past months, and any account or resource whose latest data is older.
- A month's row may be partial while its data is still arriving: compare `source_date` or `last_date` with the month end.
- Filter on `account_id.provider`, through the cost row's `account`, not by matching service names: every cost table has `account`, and a provider's services need not contain its name. Some deployments have non-cloud providers (e.g. `anthropic`, in preview, whose services are model names); `SELECT DISTINCT provider FROM account_id` lists them.
- `account_cost_monthly.account`, `.service` and `.region` are integer ids; join them to `account_id`, `cloud_service` and `cloud_region` on `id`. `resource_cost_monthly` has only `account` and `resource_id`, with no service or region.
- `resource_focus_cost` and `resource_cost_monthly` have `tags`, an array of `resource_tags.id`s: unnest and join them to see whose cost it is, even for resources that aren't in `resources`. They are the tags the cost source reported, so for cloud resources they can be empty (AWS legacy CUR) or have `user_`-prefixed keys (AWS CUR 2.0: `team` is `user_team`); `resources._tags` has the inventory tags. Only `resource_focus_cost` has `sku`: join it to `sku.id` for `sku_id`, which encodes the pricing dimensions.
- Anthropic (preview): the cost row's `resource_id` joins `resource_id.id`, whose `r_id` is a user (`user_…`, Claude Code usage included), an API key (`apikey_…`) or a service account (untagged). Users are tagged `anthropic:user_email`/`anthropic:user_name` (or `anthropic:claude_code_user` for users who've left), keys `anthropic:api_key_name`/`anthropic:owner_*`. `sku_id` is `model:token_type:context_window:service_tier:inference_geo:speed` (e.g. `…:200k-1M:…` for long context), or `web_search`. Some cost (Console usage, code execution, small shares) has no principal, so is only in account-level cost; resource rows sum to less.

### **Safe Querying Process**

1. **Query table sizes:**
   ```sql
   SELECT
     schemaname,
     tablename,
     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
   FROM pg_tables
   WHERE schemaname = 'public' AND tablename = 'your_table_name';
   ```

2. **Check indexes on a table:**
   ```sql
   SELECT
     indexname,
     indexdef
   FROM pg_indexes
   WHERE schemaname = 'public' AND tablename = 'your_table_name'
   ORDER BY indexname;
   ```

3. **Use EXPLAIN to verify index usage**
4. **LIMIT results to manageable sizes**
5. **Use provider-specific tables over raw JSON when possible**

### **Parameterized Queries**

AssetDB supports parameterized queries using `{{parameter_name}}` syntax for dynamic values.

**Basic Example:**
```sql
SELECT {{value}} as result, _type, _account_id
FROM resources
LIMIT {{limit}}
```

**Parameter Definition:**
```json
{
  "parameters": [
    {
      "name": "value",
      "title": "Value",
      "type": "text",
      "value": "'Hello World'"
    },
    {
      "name": "limit",
      "title": "Limit",
      "type": "number",
      "value": 10
    }
  ]
}
```

**Parameter Types:** `text`, `number`, `date`, `datetime-local`, `query` (dropdown)

**Security Note:** Queries with `text` parameters are marked as "unsafe" because parameters use template substitution (not prepared statements), making them potentially vulnerable to SQL injection. Prefer validated parameter types (`number`, `date`, `query`) when possible.

**Usage:** Call `assetdb_query_result(query_id, parameters={"value": "'Test'", "limit": 5})`

### **Dropdown Parameters**

Dropdown parameters use `"type": "query"` and reference another query for options:

```json
{
  "name": "account_filter",
  "title": "Account",
  "type": "query",
  "queryId": 42
}
```

Query 42 must return `name` and `value` columns:
```sql
-- Query 42: Account options
SELECT account_name as name, account_id as value FROM accounts
-- Returns: [{"name": "Production", "value": "123456"}, {"name": "Staging", "value": "789012"}]
```

**Usage:** The parameter gets the `value` from the selected option:
```python
assetdb_query_result(query_id, parameters={"account_filter": "123456"})
# User saw "Production" but parameter receives "123456"
```

**🤖 LLM Parameter Discovery Workflow:**

1. **Check query definition:** `assetdb_query_get(query_id)` to see parameter structure
2. **For dropdown parameters with `"queryId"`:** Execute the source query first: `assetdb_query_result(query_id=dropdown_source_id)`
3. **Use the `value` field** from dropdown results, never the `name` field
4. **400 errors usually mean** invalid parameter values - re-check the dropdown source query for valid options
5. **Always run the source query first** for query-type parameters to get valid dropdown values before executing the main query

**Example:**
```python
# Query 74 has parameter: {"name": "resource_type_filter", "type": "query", "queryId": 73}
# Step 1: Get valid dropdown values
options = assetdb_query_result(query_id=73)
valid_values = [row['value'] for row in options['some_rows']]  # ["aws.s3", "aws.account", ...]

# Step 2: Use discovered value
result = assetdb_query_result(
    query_id=74,
    parameters={"resource_type_filter": "aws.s3"}  # ← from options above
)
```

### **Query Execution Behavior**

**Result Format Availability:**
- All result formats (CSV, JSON, TSV, XLSX) are available for any successfully executed query
- Empty result sets (0 rows) still provide all download formats - the format availability depends on query success, not data presence
- Only invalid parameters or malformed queries cause 400 errors and prevent format generation

**Parameterized Query Validation:**
- Invalid parameter values that don't match dropdown options cause 400 BAD REQUEST errors
- Valid parameters that return empty results execute successfully and provide all formats
- Template substitution means parameter validation happens at execution time, not submission time
