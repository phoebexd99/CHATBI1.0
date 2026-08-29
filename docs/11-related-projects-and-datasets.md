# Related Intelligent Query and Text-to-SQL Projects

Research snapshot: 2026-08-28. This note records official project documentation and benchmark pages rather than third-party summaries.

## CHATBI baseline

- Data: a synthetic commerce analytics model with orders/items/customers/products plus campaign daily performance and inventory snapshots; SQLite is used for deterministic local evaluation and PostgreSQL is supported in Live mode.
- Certified metrics: 16 catalog-driven metrics spanning transaction health, customer reach, marketing acquisition, and inventory operations.
- Knowledge: versioned schema, metric, business-term, and verified NL–SQL documents for all three analysis domains.
- Golden questions: 45 Chinese cases spanning scalar metrics, grouping, dynamic filters, arbitrary rolling windows, trends, comparisons, knowledge answers, clarification, unsafe requests, PII export, and off-domain rejection.

## Comparable open-source systems

| Project | Data used in official examples | Context / knowledge strategy | Representative business questions | Relevance to CHATBI |
|---|---|---|---|---|
| [WrenAI](https://github.com/Canner/WrenAI) | dbt Labs `jaffle_shop`: fictional ecommerce customers, orders, and payments, built into customer and order analytics tables | Git-versioned MDL models, views/cubes, relationships, column descriptions, business rules, and confirmed NL–SQL pairs; indexed memory retrieves schema and prior examples | Customers with more than one order; top five customers by lifetime value; monthly order-count trend | Closest match to CHATBI's semantic-adapter direction. The main lesson is to make metric rules and relationships first-class, reviewable artifacts. |
| [Vanna](https://github.com/vanna-ai/vanna) | Official legacy material demonstrates a Cybersyn SEC dataset and supports user databases; examples also use customer/sales schemas | The 0.x/legacy retrieval pattern stores DDL, business documentation, and question/SQL examples in a vector store, then selects relevant context before SQL generation | Top customers by sales; dataset-specific SEC questions; follow-up questions generated from prior results | Its three-part context split maps directly to CHATBI's Schema, metric/term, and verified NL–SQL classes. API details differ in Vanna 2.x, so the pattern matters more than copying old calls. |
| [SQLBot](https://github.com/dataease/SQLBot) | Bring-your-own database or file-based source, organized by workspace and data source | Custom prompts, terminology, SQL examples, sample values, metric/dimension constraints, and row-level permission configuration | “本周销售额是多少”; multi-turn follow-up “继续按地区拆分” | Strong reference for Chinese product interaction, workspace governance, follow-up questions, and operational knowledge management. |
| [Dataherald](https://github.com/Dataherald/dataherald) | Connected relational databases; its engine and admin console are designed around enterprise data sources | Database scans, table/column descriptions, low-cardinality values, recent query history, and verified Golden NL–SQL records retrieved as few-shot context | Most expensive rental ZIP code in Los Angeles County for a specified month | Shows why schema-only RAG is insufficient: values, query logs, descriptions, and approved examples all improve grounding. |
| [MindsDB](https://github.com/mindsdb/mindsdb) | Official agent examples include a PostgreSQL `car_sales` table; broader examples join Salesforce opportunities, MongoDB tickets, files, and other sources | Text-to-SQL skills plus vectorized knowledge bases over text/PDF/HTML, with metadata filters; agents are scoped to specific tables and knowledge bases | Average car price by year; max mileage; transmission mix; most common model; open sales pipeline and risky renewals | Useful longer-term reference for combining structured metrics with unstructured support/customer context. It is broader than the four-day CHATBI scope. |
| [LangChain DeepAgents Text-to-SQL](https://github.com/langchain-ai/deepagents/tree/main/examples/text-to-sql-agent) | SQLite Chinook digital-media store: artists, albums, tracks, customers, invoices, and employees | Runtime schema exploration plus explicit agent instructions; no semantic RAG layer in the example | Count Canadian customers; find the employee generating the most revenue and the contributing countries | A compact control example for iterative schema inspection, query execution, repair, row limits, and read-only safety. |

## Training and evaluation resources

| Resource | Data and question coverage | Best use for CHATBI |
|---|---|---|
| [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) | Uses Spider as the primary example and documents WikiSQL, BIRD, and the Chinese multi-turn CHASE dataset. Spider contributes 10,181 questions over 200 databases; CHASE contributes 17,940 question/SQL pairs in 5,459 multi-turn sequences over 280 databases. | Source patterns for fine-tuning experiments and Chinese multi-turn evaluation design; do not mix benchmark test examples into CHATBI's holdout set. |
| [Defog SQLCoder](https://github.com/defog-ai/sqlcoder) | More than 20,000 human-curated questions over 10 training schemas; evaluation categories include date, grouping, ordering, ratio, joins, and filters. An official example compares revenue from New York and San Francisco. | Borrow the category taxonomy to balance the Golden set and expose weak SQL operations. |
| [Spider 1.0](https://yale-lily.github.io/spider) | 10,181 questions and 5,693 unique SQL queries over 200 multi-table databases in 138 domains. | Cross-schema generalization and SQL-complexity reference; less representative of enterprise metric governance. |
| [BIRD-SQL](https://bird-bench.github.io/) | 12,751 question/SQL pairs, 95 databases totaling 33.4 GB, and more than 37 domains including healthcare, education, blockchain, and sports; each case includes external evidence. | Best public reference for testing value grounding and external business evidence alongside large database contents. |
| [Spider 2.0](https://spider2-sql.github.io/) | 632 enterprise workflow problems over real application schemas, often with more than 1,000 columns, using systems such as BigQuery and Snowflake; tasks may require multiple SQL statements and repository context. | Long-term production benchmark for schema scale, dialects, multi-step workflows, and execution feedback—not a Day-4 MVP target. |

## Recommended dataset and knowledge expansion for CHATBI

1. Continue the implemented campaign/inventory expansion with payment/refund events, traffic sessions, and a date dimension. Keep a curated metric catalog rather than exposing every column.
2. Turn knowledge into versioned assets: table/column dictionary, metric formulas and owners, allowed dimensions, enum/value dictionaries, canonical joins, time semantics, PII classification, and verified NL–SQL pairs.
3. Add question families that reflect actual operations work: conversion funnel, repeat purchase, cohort retention, refund rate, contribution margin, inventory risk, campaign ROI, region/channel mix, and anomaly/root-cause drill-down.
4. Grow evaluation in two layers: a visible curated Golden set for regression and a separate holdout set for honest generalization. Measure execution accuracy, semantic correctness, clarification precision, unsafe/PII rejection, evidence recall, and latency.
5. Keep the current safety boundary. Retrieval or a semantic engine may propose SQL, but only a read-only allow-listed query should reach dry-run and execution.

## Source details

- WrenAI quickstart and context layout: <https://github.com/Canner/WrenAI/blob/main/docs/core/get_started/quickstart.md>
- Vanna legacy context pattern: <https://github.com/vanna-ai/vanna/blob/main/README_LEGACY.md>
- SQLBot overview and operational context: <https://github.com/dataease/SQLBot>
- Dataherald context store: <https://dataherald.readthedocs.io/en/latest/context_store.html>
- MindsDB query engine and knowledge-base examples: <https://github.com/mindsdb/mindsdb>
- LangChain DeepAgents example instructions: <https://github.com/langchain-ai/deepagents/blob/main/examples/text-to-sql-agent/AGENTS.md>
- Spider 1.0: <https://yale-lily.github.io/spider>
- BIRD-SQL: <https://bird-bench.github.io/>
- Spider 2.0: <https://spider2-sql.github.io/>
