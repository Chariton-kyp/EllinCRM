# Security Policy

## Supported versions

EllinCRM is a portfolio / showcase project, so only the **current `main`
branch** receives security updates. Previous tags and forks are not
actively maintained.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security problems.**

Instead, email the author directly:

- **Chariton Kypraios** — [haritos19@gmail.com](mailto:haritos19@gmail.com)

Include, if possible:

1. A clear description of the issue and where it lives in the code
   (file path, function, line numbers).
2. Steps to reproduce — a minimal script, payload, or request.
3. The impact you observed or expect (data exposure, privilege
   escalation, denial of service, supply-chain concern, etc.).
4. Any suggested remediation, if you have one.

You can expect:

- An acknowledgement within **72 hours**.
- A triage response (confirmed / duplicate / out-of-scope / needs more
  info) within **7 days**.
- Credit in the release notes if you wish, once the fix ships.

## Scope

In scope for reports:

- The application code under `backend/app/` and `frontend/` on `main`.
- The `docker-compose.yml` and Dockerfiles shipped with the repo.
- The GitHub Actions workflow under `.github/workflows/`.
- Any exposed configuration defaults (e.g. dev DB credentials baked
  into compose files) that would unsafely leak into production.

Out of scope (not vulnerabilities for this project):

- Third-party dependencies whose CVEs have not yet been released. If
  you find one, please report upstream first.
- Dev defaults that are intentionally weak and clearly documented as
  "development only" (e.g. `ellincrm_dev_password` in the compose
  file). Running these in production is a deployment misconfiguration,
  not a repo vulnerability.
- Social-engineering attacks against the author.
- Denial-of-service by overwhelming a local deployment the user
  themselves exposes to the internet.

## Known-safe posture

For transparency, the repository already does the following:

- Secrets are `.env`-only and `.gitignored`. `.env.example` ships
  placeholders; real credentials never enter git history. See
  `.gitignore` at the repo root.
- API keys loaded via `Settings` are stored as pydantic `SecretStr`,
  so `repr(settings)` and stack traces never leak raw tokens.
- Third-party GitHub Actions are pinned to release tags, not `@master`.
- The chat agent uses a dedicated `ellincrm_readonly` Postgres role
  with a statement timeout, not the application's read-write user.
- CORS origins are an explicit allow-list, not `*`.

Thank you for helping keep the project and its users safe.
