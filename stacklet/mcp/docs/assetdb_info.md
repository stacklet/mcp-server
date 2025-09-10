## **Stacklet AssetDB SQL Overview**

The AssetDB is Stacklet's centralized data warehouse containing all cloud resource data,
relationships, and metadata. It's designed for efficient querying and analysis of your
cloud estate at scale.

### **Database Structure**

AssetDB runs on PostgreSQL 16.

All AssetDB data is contained in the "public" schema. The most important tables are:

- "resources" contains raw JSON representations of every current resource in your estate
  - this table is very large
  - if you must query it, ensure you use LIMITs and/or filters on indexed columns

- "resource_revisions" contains coarse-grained resource configuration history raw JSON as in "resources"
  - this table is very very large
  - ideally, ONLY look into this table via primary key
  - if you must query it, ensure you use LIMITs and/or filters on indexed columns

- The many tables named by provider and resource type, e.g. "aws_ec2" and "gcp_gke_cluster",
are ideal when you want to know details of a specific resource type – they have SQL columns
with resource attributes
  - these tables are for some purposes a superior representation to that in the "resources"
  table
  - anything in a provider-type table should also be represented in "resources", and vice
  versa

- "resource_tags" and "resource_tags_mapping" must be the starting point for any potentially
large-scale tagging query

- "account_cost" (if configured) contains complete costs by date/service/account/region
  - the granularity is coarse but this is usually the best starting point for cost queries

- "resource_cost_summaries" contains the average daily cost that could be attributed to a given resource over the last month
  - this is much more granular than "account_cost", but not all cost data can be mapped to a
  specific resource, so it may not give a full picture.

- "resource_cost" is an unreasonably huge table and has the same completeness issues as the
summary table
  - it may be helpful in looking up granular costs for a few specific resources

This tool also has access to the "platform" schema, but it is often wiser to use platform
graphql tools to access the information you'd find there.


### Querying Advice

Many tables in AssetDB can be very large; always follow a process where you:
- Query for the sizes on disk of relevant tables
- Discover which indexes are available for large tables
- Structure the query to take advantage of indexes and avoid table scans
- EXPLAIN the query before executing it for results, and rework the query if the plan reveals table scans
- LIMIT the results to avoid overwhelming your context
