# Business Semantic Expansion

## Outcome

CHATBI no longer maps a small list of exact questions to handwritten SQL branches. The local Live path now composes a query from a versioned semantic catalog:

`question → metric alias → time window → dimensions → database-discovered filters → certified expression → SQL safety → execution`

This keeps local development deterministic while preserving the Wren adapter boundary for a later production semantic engine.

## Business domains

### Transaction health

- GMV, net revenue, valid orders, AOV, refund amount, refund rate, discount rate, units sold, and purchasing customers.
- Dimensions: date, region, channel, category, and product where the metric grain permits it.
- Questions: “最近 45 天各渠道退款率”, “本季度各区域净收入”, “最近 30 天各品类销量排行”.

### Marketing acquisition

- Advertising spend, attributed revenue, purchase conversion rate, and ROAS.
- Dimensions: date, channel, and campaign.
- Questions: “最近 30 天各活动 ROAS 排名”, “开学季最近 30 天下单转化率”, “最近 90 天按渠道看广告花费”.

### Inventory operations

- Available inventory, stockout product count, and stockout rate.
- Dimensions: date, category, and product where supported.
- Questions: “今天各品类可用库存”, “今天缺货商品数”, “最近 14 天缺货率趋势”.

## What makes the system extensible

1. `data/metrics.json` is the source of truth for aliases, formulas, base tables, date fields, joins, dimensions, filter columns, units, owners, and certification status.
2. `data/dimensions.json` holds reusable Chinese dimension aliases.
3. `backend/app/semantic.py` loads and validates the catalog and performs longest-alias matching.
4. `backend/app/workflow.py` parses arbitrary rolling windows such as 45 or 90 days and discovers low-cardinality filter values from the active database. A newly added region, channel, campaign, category, or product can therefore be recognized without adding a Python `if` branch.
5. `backend/app/wren.py` composes SQL from certified catalog fields. Production Wren can replace this planner through the existing adapter without bypassing SQLGlot, dry-run, or read-only execution.
6. Knowledge documents and Golden questions provide evidence and regression coverage for every published metric.

## Add a metric without adding a fixed question

1. Add a certified metric entry to `data/metrics.json` with a unique name, aliases, expression, grain/base table, date field, supported dimensions, filter columns, unit, and owner.
2. Add a `metric.<name>` knowledge document to `data/knowledge.json` explaining the business definition, inclusions/exclusions, and caveats.
3. Add at least three evaluation cases: scalar, grouped, and filtered/time-bound. Add a knowledge-definition case for business-critical metrics.
4. Run backend tests and the full evaluation. Do not publish the metric if execution accuracy, evidence retrieval, or safety regresses.

No parser code change is required when the new metric uses existing catalog capabilities.

## Add a data domain

1. Create a curated analytics fact or snapshot table rather than exposing raw OLTP tables directly.
2. Add equivalent SQLite fixture and PostgreSQL DDL/seed or migration coverage.
3. Add the table to the SQL safety allow-list only after deciding which columns and joins are permitted.
4. Register certified metrics and supported dimensions in the catalog.
5. Add Schema, metric, term, and verified NL–SQL knowledge.
6. Add domain-specific Golden cases, boundary cases, and a separate real-data holdout before production use.

## Remaining production gap

The expansion improves breadth and maintainability, but it does not claim unrestricted natural-language understanding. The local parser is deterministic and catalog-governed. Production breadth still requires schema/metric ingestion, model-assisted entity extraction, pgvector or equivalent hybrid retrieval, a private Wren deployment, identity/RLS, real business data, and holdout evaluation. Generated SQL must continue through the current safety and dry-run gates.
