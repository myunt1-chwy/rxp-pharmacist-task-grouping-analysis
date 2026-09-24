---
name: rxp-sql
description: Run and adapt read-only Snowflake SQL for Chewy prescription, approval, and pharmacy-operations analysis. Use when a request concerns RxP metrics, prescription workflows, clinics, approval outcomes, or the associated HDE views.
---

# RxP SQL

Use this skill for prescription-domain analysis in Snowflake. The skill runs Snowflake SQL through DuckDB using interactive browser SSO; it does not create, update, or delete Snowflake data.

## Workflow

1. Read [the data model](references/prescriptions-data-model.md) before selecting tables or joins.
2. For task-lifecycle or employee-role analysis, read [the task and employee schemas](references/task-employee-schemas.md).
3. For a known KPI, read [the query catalog](references/query-catalog.md) and start from its source query.
4. Prefer certified `BT_HCA_*` views for new work. Catalog queries that use `PET_HEALTH_ANALYTICS_SANDBOX` are legacy examples: do not silently translate them when no documented replacement exists.
5. Confirm the requested metric grain, reporting window, time zone, and exclusion rules. State any changes to a catalog query.
6. Run read-only SQL with `scripts/run_snowflake_query.py`; review the returned rows and report the SQL used, result grain, and limitations.

## Execution

Run `uv sync` once at the repository root, then set the required Snowflake settings in `.env` using `.env.example` as the template. The runner uses DuckDB 1.5.3 or newer from the uv environment, DuckDB's Snowflake community extension, and the Snowflake ADBC driver. It launches browser SSO on the first authenticated query.

```bash
uv run python skills/rxp-sql/scripts/run_snowflake_query.py path/to/query.sql
uv run python skills/rxp-sql/scripts/run_snowflake_query.py --query 'SELECT 1'
```

The runner accepts one read-only statement beginning with `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, or `EXPLAIN`. It blocks multiple statements and write/DDL statements; Snowflake roles remain the final authorization boundary.

## References

- Read [the data model](references/prescriptions-data-model.md) for table purpose, grain, approved joins, and migration guidance.
- Read [the task and employee schemas](references/task-employee-schemas.md) for lifecycle fields, employee attributes, and their approved Kyrios-user join.
- Read [the query catalog](references/query-catalog.md) for KPI definitions and source SQL from the Pet Health Analytics KPI Catalog.
