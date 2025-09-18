## **Stacklet GraphQL API Overview**

The Platform GraphQL API enables interaction with the Stacklet Platform, equivalent to console UI capabilities and more.

### **Critical Requirements**

- **Always look up schema types before querying**
- If you're not certain what a field means, use the docs toolset for context
- **Always query for "problems" alongside results** - problems contain critical information
- Use Stacklet documentation (especially glossary) for concept details

### **Connection Query Best Practices**

- Use small pages (5-10 items) to keep context compact
- Use "PageInfo" for total counts, never count by paging
- Query "filterSchema" to compose "FilterElementInput" values
- For large datasets: test with small queries first, then use `platform_dataset_export`
- Avoid nested connections (causes timeouts)

### **Entity Guidelines**

- "system" field = true means entity cannot be mutated
- Use "HasACL" interface for ownership/permissions
- When updating "description" fields: document your LLM identity and context, append (don't replace)
- Prefer updating entities you created or were asked to modify

### **Management Operations**

**Accounts**: Rarely add/update directly; prefer organization-level account discovery (requires human support).

**Policies**: LLMs excel at policy writing. Get examples via "sourceYAML" field, especially from system collections. New policies require external SCM (GitHub/Bitbucket) - check documentation for RepositoryConfig/DPC details.

**Core Entities**:
- Account groups, policy collections, and bindings are the main manipulation targets
- Notifications via report groups (never alter UUID-named groups; use human-readable names)
- Jinja2 templates can be created/updated via API - always use "previewTemplate" to validate

### **Data Analysis**

**Scale Strategy**: Small pages for exploration → `platform_dataset_export` for complete datasets → local analysis tools for large-scale work. Use AssetDB tools for massive analysis.

**Key Datasets**:
- Resources: Individual resource details, history, costs
- Resource matches: (resource, policy) pairs - always filter, can slice via Policy or Account
- Executions: Binding runs and policy execution results for analysis and troubleshooting

**Related Tools**: `platform_dataset_info` for export guidance, AssetDB tools for warehouse queries
