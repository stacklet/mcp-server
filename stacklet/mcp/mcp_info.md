Stacklet provides comprehensive cloud governance and analytics capabilities through
integrated toolsets. These enable you to understand, analyze, and govern your entire
cloud estate at scale.

## Start Here: Critical Info Tools
Always call these info tools first - they contain essential guidance and best practices:
- "assetdb_sql_info" - For cloud asset analytics
- "platform_graphql_info" - For governance operations
- "platform_dataset_info" - For large-scale data exports
- "docs_list" then "docs_read" - Live documentation for the platform and for IaC Governance (Sinistral)

## Core Capabilities

### 🔍 Cloud Asset Discovery & Analytics
Analyze your entire multi-cloud estate with a continuously-updated PostgreSQL warehouse:
- Query resource inventories, costs, and relationships across AWS, GCP, Azure, Tencent
- Perform complex analytics on resource usage patterns and cost optimization
- Track resource changes and lifecycle management
- Build custom reports with SQL

### 🛡️ Cloud Governance Operations
Execute governance policies and manage compliance at scale:
- Deploy and manage Cloud Custodian policies across accounts and regions
- Monitor policy execution results and resource compliance
- Configure account grouping and binding relationships
- Export large governance datasets for analysis and reporting

### 🏗️ IaC Governance (Sinistral)
Govern infrastructure-as-code before it is deployed, rather than resources after:
- Scan Terraform HCL against YAML policy, from CI or a developer machine
- Understand policy sources, policy collections, projects, scans, and scan results
- Documented under "iac/". Start at "iac/index.md" via docs_read

**"IaC Governance" and "Sinistral" name the same product.** The docs use both names.

Its vocabulary overlaps the platform's, and the meanings differ. A Sinistral policy is
YAML evaluated against Terraform. A Cloud Custodian policy is evaluated against live
cloud resources. Sinistral policy collections and projects are its own. Read
"reference/glossary.md" before reasoning across the two.

Sinistral has no tools of its own. Reach it through the documentation tools. Questions
about scanning Terraform, shift-left policy, or the Sinistral API are answered from
"iac/", not from AssetDB or the Platform GraphQL API.

### 📚 Platform Knowledge Access
Access live Stacklet platform documentation and guidance:
- Browse comprehensive how-to guides, reference docs, and runbooks
- Get LLM-optimized documentation specifically designed for AI assistance
- Access up-to-date platform configuration and troubleshooting information
- Covers both the core platform and IaC Governance (Sinistral)

## Workflow Patterns
- **Exploration**: Start small with targeted queries, then scale to larger datasets
- **Analysis**: Use SQL for complex analytics, GraphQL for governance operations
- **Scale**: Export large datasets when working with 10K+ records
- **Integration**: Combine asset data with governance results for comprehensive insights

The info tools will guide you through each toolset's specific best practices.
