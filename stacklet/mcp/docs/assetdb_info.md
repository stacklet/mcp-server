## **Stacklet AssetDB SQL Overview**

The AssetDB is Stacklet's centralized data warehouse containing all cloud resource data,
relationships, and metadata. It's designed for efficient querying and analysis of your
cloud estate at scale.

### **Database Structure**

The AssetDB follows a structured schema with these key principles:
- Resources are normalized across cloud providers
- Historical data is maintained for change tracking
- Relationships between resources are preserved
- Metadata includes tags, configurations, and compliance state

Always explore the schema first using the data source schema APIs to understand
available tables and columns before writing queries.

### **SQL Usage Principles**

**Query Efficiently:**
- Use LIMIT clauses for exploratory queries to avoid overwhelming results
- Index on commonly filtered columns (account_id, resource_type, region)
- Use time-based filters when analyzing historical data

**Common Patterns:**
- Filter by account_id to scope queries to specific accounts
- Use resource_type to focus on specific AWS/Azure/GCP services
- Join tables carefully - the schema preserves relationships but joins can be expensive
- Aggregate data when looking for trends or summaries

**Schema Exploration:**
- Start with DESCRIBE or SHOW TABLES to understand structure
- Use INFORMATION_SCHEMA queries to explore column metadata
- Look for tables with prefixes indicating data types (e.g., aws_, azure_, gcp_)

**Performance Tips:**
- Use specific column lists instead of SELECT *
- Apply filters early in WHERE clauses
- Consider using CTEs for complex multi-step analysis
- Be mindful of query timeout limits (typically 60 seconds)

### **Common Use Cases**

**Resource Inventory:**
- Count resources by type, account, or region
- Find resources with specific tags or configurations
- Identify orphaned or unused resources

**Compliance Analysis:**
- Query resource configurations against policy requirements
- Find resources missing required tags or settings
- Track compliance trends over time

**Cost Analysis:**
- Aggregate resource costs by various dimensions
- Identify cost anomalies or optimization opportunities
- Track spending trends and patterns

**Change Tracking:**
- Query historical data to understand resource lifecycle
- Find recently created, modified, or deleted resources
- Analyze configuration drift over time

### **Security Considerations**

The AssetDB contains sensitive information about your cloud infrastructure.
Queries should be:
- Purposeful and scoped appropriately
- Mindful of data sensitivity in results
- Used only for legitimate analysis and governance needs

### **Getting Help**

- Use the schema exploration tools to understand available data
- Start with simple queries and build complexity incrementally
- Consider the Stacklet documentation for data model explanations
- Remember that GraphQL tools may provide complementary analysis capabilities
