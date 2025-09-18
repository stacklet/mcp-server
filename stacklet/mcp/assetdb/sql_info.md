## **Stacklet AssetDB SQL Overview**

Stacklet's centralized PostgreSQL 16 data warehouse containing all cloud resource data, relationships, and metadata for efficient large-scale analysis.

### **⚠️ Scale Warning**

Many AssetDB tables are extremely large. Always use LIMIT and indexed column filters to avoid table scans.

### **Key Tables**

| Table                                    | Purpose                             | Scale           | Usage Notes                          |
|------------------------------------------|-------------------------------------|-----------------|--------------------------------------|
| `resources`                              | Current resource JSON               | Very Large      | LIMIT + indexed filters required     |
| `resource_revisions`                     | Resource history JSON               | Extremely Large | Primary key access only              |
| `aws_ec2`, `gcp_gke_cluster`, etc.       | Provider-specific columns           | Large           | Preferred over raw JSON for analysis |
| `resource_tags`, `resource_tags_mapping` | Tag analysis                        | Large           | Start here for tag queries           |
| `account_cost`                           | Cost by date/service/account/region | Medium          | Best starting point for costs        |
| `resource_cost_summaries`                | Monthly avg cost per resource       | Large           | More granular, incomplete coverage   |
| `resource_cost`                          | Granular cost details               | Extremely Large | Individual resource lookups only     |

### **Special Considerations**

- Most table columns are commented. When investigating table structure, these are valuable.
- Foreign key constraints do not tell the whole story; there are many implicit foreign relations.

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
