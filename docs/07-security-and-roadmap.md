# Security and Production Roadmap

The MVP accepts only one parsed `SELECT`, rejects comments, DDL/DML, dangerous functions, system catalogs, and non-allow-listed tables, adds a bounded limit where appropriate, dry-runs before execution, and uses a read-only database identity in production. It never interpolates user text into SQL.

Production work includes OIDC/SSO, tenant isolation, per-metric policy, RLS/CLS, query cost and timeout controls, PII classification, prompt-injection defenses, secrets manager integration, tamper-evident audit logs, dependency/image scanning, backups, rate limiting, and incident runbooks.

Cloud deployment is intentionally deferred. Before using the known Tencent Cloud host, restrict security-group sources: SSH and 1Panel must not remain world-open; databases should be private; public ingress should normally be limited to 80/443 through a reverse proxy with TLS. No action is authorized against that server in this sprint step.

