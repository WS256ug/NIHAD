# Development plan

Follow the detailed sequence in AGENTS.md section 54. Verify each phase before
starting the next. Always use `.venv` for Python and dependency commands.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Project foundation, custom user, settings, base layout | Complete |
| 2 | Accounts, password management, permission helpers, role navigation | Next; basic sign-in/out already available |
| 3 | School profile, sections, years, terms, classes and streams | Planned |
| 4 | Students, guardians, enrollment and history | Planned |
| 5 | Teachers, subjects and allocations | Planned |
| 6 | Assessments and marks | Planned |
| 7 | Configurable grading, aggregates and divisions | Planned |
| 8 | Reports, review, publication and PDF/print | Planned |
| 9 | Fees, payments, balances and receipts | Planned |
| 10 | Guardian portal and report-access policy | Planned |
| 11 | Expenses and financial summaries | Planned |
| 12 | Promotion and preserved enrollment history | Planned |
| 13 | Role dashboards | Planned |
| 14 | Security review | Planned |
| 15 | Production preparation | Planned |

## Phase 1 deliverables

- Repository and canonical AGENTS.md
- Python virtual environment and pinned dependencies
- Separate base, development (SQLite) and production (PostgreSQL) settings
- Ignored local `.env`, random local secret, and documented `.env.example`
- Custom user model installed in the initial migration
- Six stored role values, password hashing and Django custom-user administration
- Responsive Oat UI base layout and HTMX sign-in with ordinary form fallback
- Protected workspace and CSRF-protected POST logout
- Static/media configuration and local vendor assets with licenses
- Authentication and configuration tests

## Phase 1 verification

- 21 automated tests pass on SQLite.
- Django system check, migration drift check and dependency check pass.
- Production deployment checks and manifest static collection pass with temporary
  configuration values, without connecting to a PostgreSQL database.
- Local server responds to the sign-in page and all frontend assets.
- Live HTTP checks pass for HTMX and ordinary sign-in, the protected workspace,
  admin pages and POST sign-out. The temporary verification account was removed.
- No connected browser was available; visual desktop/mobile verification remains
  outstanding. A live PostgreSQL integration check remains part of deployment work.

## Next phase

Build password change/reset, role permission helpers and role navigation. Enforce
authorization in views and querysets as modules become available. Role labels
alone must never confer administrative access. Test each role before Phase 3.
