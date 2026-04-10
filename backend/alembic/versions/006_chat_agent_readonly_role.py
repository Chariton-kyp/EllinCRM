"""Create read-only Postgres role for the chat agent tools.

Revision ID: 006
Revises: 005
Create Date: 2026-04-09

Defense in depth for the chat agent (v2): even if a bug in a tool allowed
SQL injection, the database itself refuses any write operations and caps
query time to prevent runaway scans.

What this migration does:
  1. Creates role `ellincrm_readonly` if it doesn't exist.
  2. Sets `statement_timeout = 3s` at the role level (overridable per-session).
  3. GRANTs SELECT on chat-relevant tables: extraction_records,
     document_embeddings, audit_logs.
  4. REVOKEs all write privileges (INSERT/UPDATE/DELETE/TRUNCATE).

Notes:
  - The password must be set out-of-band via `READONLY_DB_PASSWORD` env var
    consumed by `backend/app/db/readonly_session.py`. This migration creates
    the role WITHOUT a password; the DBA/operator sets it via:
        ALTER USER ellincrm_readonly WITH PASSWORD '<secret>';
  - In dev, if `READONLY_DB_PASSWORD` is unset, the backend falls back to the
    main DB user (also read-only by intent, less strict enforcement).
  - Idempotent: safe to run multiple times. Uses `DO $$` blocks with existence
    checks.
  - Downgrade drops the role entirely.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ellincrm_readonly role with SELECT-only access."""

    # 1. Create the role if it doesn't exist (idempotent)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ellincrm_readonly') THEN
                CREATE ROLE ellincrm_readonly WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )

    # 2. Per-role statement timeout (3s) — hard cap on any query from this role
    op.execute("ALTER ROLE ellincrm_readonly SET statement_timeout = '3s';")

    # 3. Per-role idle-in-transaction timeout (5s) — prevent held locks
    op.execute(
        "ALTER ROLE ellincrm_readonly SET idle_in_transaction_session_timeout = '5s';"
    )

    # 4. Grant schema usage (required for SELECT on tables in the schema)
    op.execute("GRANT USAGE ON SCHEMA public TO ellincrm_readonly;")

    # 5. Grant SELECT only on chat-relevant tables
    op.execute("GRANT SELECT ON extraction_records TO ellincrm_readonly;")
    op.execute("GRANT SELECT ON document_embeddings TO ellincrm_readonly;")
    op.execute("GRANT SELECT ON audit_logs TO ellincrm_readonly;")

    # 6. Also grant SELECT on future tables (nice-to-have for dev, explicit
    # future grants can be removed in prod hardening)
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT ON TABLES TO ellincrm_readonly;
        """
    )

    # 7. Belt-and-suspenders: explicitly revoke write privileges. CREATE ROLE
    # defaults NOCREATEDB/NOCREATEROLE but other grants depend on the table
    # owner's defaults, so we're explicit here.
    op.execute(
        """
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
        ON extraction_records FROM ellincrm_readonly;
        """
    )
    op.execute(
        """
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
        ON document_embeddings FROM ellincrm_readonly;
        """
    )
    op.execute(
        """
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
        ON audit_logs FROM ellincrm_readonly;
        """
    )


def downgrade() -> None:
    """Drop the ellincrm_readonly role and all its grants."""

    # Revoke grants before dropping (required by Postgres)
    op.execute("REVOKE ALL ON extraction_records FROM ellincrm_readonly;")
    op.execute("REVOKE ALL ON document_embeddings FROM ellincrm_readonly;")
    op.execute("REVOKE ALL ON audit_logs FROM ellincrm_readonly;")
    op.execute("REVOKE ALL ON SCHEMA public FROM ellincrm_readonly;")
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        REVOKE SELECT ON TABLES FROM ellincrm_readonly;
        """
    )

    # Drop the role (idempotent)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ellincrm_readonly') THEN
                DROP ROLE ellincrm_readonly;
            END IF;
        END
        $$;
        """
    )
