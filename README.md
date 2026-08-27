# CHATBI Portfolio Sprint MVP

A four-day, portfolio-grade conversational BI MVP for business operators who need certified metrics without SQL. Day 1 provides a real thin vertical slice: Next.js UI → FastAPI → graph workflow → hybrid knowledge retrieval / Wren adapter → SQLGlot safety → PostgreSQL (plus SQLite local fallback).

## Day 1 status

- **Implemented:** synthetic commerce schema and seed data, four knowledge classes, keyword + hashed-vector hybrid retrieval with trace, deterministic graph workflow, replaceable Wren adapter, SQLGlot validation, read-only execution, one repair attempt, query API, replay fixture, three-page UI shell, tests.
- **Simplified:** embeddings are local deterministic feature hashing; the local Wren adapter plans certified metrics when no Wren endpoint is configured; chart and insight generation are deterministic.
- **Design-only:** production Wren deployment details, enterprise authorization/RLS, knowledge publishing/versioning, distributed tracing, cloud deployment.

These labels are kept in repository documentation and code comments only; the product UI does not expose delivery-status labels.

## One-command local development (tunneled Tencent Cloud PostgreSQL)

After the first setup, use the idempotent PowerShell launcher so the SSH tunnel, API, and frontend do not need to be configured repeatedly:

```powershell
.\scripts\start-local.ps1
```

The one-time setup is `.\scripts\setup-local.ps1`; diagnostics are `.\scripts\check-local.ps1`; stop everything with `.\scripts\stop-local.ps1`. See [`docs/09-local-environment.md`](docs/09-local-environment.md). The tunnel keeps PostgreSQL bound to the server loopback interface and never opens database port 5432 publicly.
## Run locally without Docker

Python 3.11–3.13 is recommended (the project also avoids version-specific features).

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r backend/requirements.txt
python -m backend.scripts.seed_sqlite
uvicorn backend.app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The default question is “最近 30 天 GMV 是多少？”.

## Run with Docker Compose

```bash
copy .env.example .env
docker compose up --build
```

Open <http://localhost:3000>; API health is <http://localhost:8000/api/health>.

## Static GitHub Pages replay

```bash
cd frontend
npm install
npm run build:replay
```

The static export is written to `frontend/out`. The replay mode reads checked-in fixtures and never attempts to deploy or call a real backend.

## Validation

```bash
pytest backend/tests -q
```

Architecture and delivery evidence live in [`docs/`](docs/); the Golden set lives in [`evals/golden_questions.json`](evals/golden_questions.json).

## Security

Only read-only `SELECT` statements over allow-listed schemas/tables pass the SQLGlot gate. Row limits, statement count, forbidden functions, comments, and DDL/DML are checked before dry-run and execution. No secret is stored in the repository. Before any later Tencent Cloud deployment, restrict security-group source ranges—do not leave database/application/admin ports open to all IPv4.

