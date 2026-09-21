# Development plan

Follow the detailed sequence in AGENTS.md section 54. Verify each phase before
starting the next. Always use `.venv` for Python and dependency commands.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Project foundation, custom user, settings, base layout | Complete |
| 2 | Accounts, password management, permission helpers, role navigation | Complete |
| 3 | School profile, sections, years, terms, classes and streams | Complete |
| 4 | Students, guardians, enrollment and history | Complete |
| 5 | Teachers, subjects and allocations | Next |
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

## Phase 2 deliverables and verification

- Six protected role workspaces, login redirects and role-specific navigation.
- Shared role checks, route decorators and scoped account querysets.
- Account list, search, role filter, pagination, creation and editing.
- Confirmed activation/deactivation, with no account deletion in the portal.
- School Admins manage ordinary Headteacher, Teacher, Bursar and Guardian accounts.
- Super Admins additionally provision School Admins; privileged accounts and
  Django permission editing are restricted to Super Admins in Django admin.
- Profile display, password change and email-token password recovery.
- Password reset tokens expire after one hour and cannot be reused.
- Database constraint and form validation keep Super Admin role, superuser and
  staff flags consistent.
- Account mutations create Django admin audit entries inside the same transaction.
- Development reset mail stays in the server console; production SMTP is configurable.
- All 48 tests pass, including the cross-role access matrix, forged privileges,
  scoped targets, CSRF, password validation, token expiry and session invalidation.
- Django system, migration drift and dependency checks pass.
- Migration 0002 is applied to local SQLite. Production deployment checks and
  static collection pass with temporary configuration values.
- Live HTTP checks pass for all six roles, account creation/editing/status changes,
  password changes, password reset and rejected token reuse. Temporary test
  accounts were removed, and the development server serves the updated routes.
- Browser visual checks and live PostgreSQL/SMTP integration remain outstanding.

## Phase 3 deliverables and verification

- School profile with contact details, currency, ranking preference and the future
  guardian report-access policy; the configured school name appears in the portal.
- Configurable sections, academic years, terms, classes and optional streams.
- Searchable, paginated lists and creation/editing/status confirmation forms.
- School Admin and Super Admin access checks on every configuration route.
- One current year and optional term, saved together on the single school profile.
- HTMX term choices restricted to the selected active academic year.
- Valid date ranges, non-overlapping periods, scoped unique names and term numbers.
- Parent relationships cannot be reassigned after creation. Referenced parents
  use protected foreign keys; configuration is deactivated instead of deleted.
- Active children and current periods prevent invalid parent deactivation.
- Transactional writes, audit fields and Django admin log entries; Django admin
  displays configuration read-only so edits use the validated portal.
- Both school migrations are applied to local SQLite.
- All 79 tests pass across Phases 1–3; system, migration and dependency checks pass.
- Live HTTP checks passed against an isolated SQLite database for first-time setup,
  record creation, current-period changes, date protection, activation, HTMX
  search and role restrictions. No sample school data was added to development.
- Production configuration and static collection checks pass. Browser visual
  checks and live PostgreSQL/SMTP integration remain outstanding.

## Phase 4 deliverables and verification

- Student registration, permanent sequential IDs, profiles, admission numbers,
  status changes and protected photos. Pillow validates and re-encodes uploads.
- Guardian account/profile registration and reuse of existing Guardian accounts.
- Multiple student/guardian links, relationship and emergency-contact details,
  one active primary guardian per student, and confirmed link deactivation.
- Enrollment by academic year, section, class and optional stream; historical
  entries, one current enrollment per student/year, and explicit closure.
- Enrollment context is immutable. Closed records cannot be reopened or changed.
  Dates must fit the year, follow admission and not overlap within the same year.
- Search, history-aware section/year/class/stream filters, pagination and HTMX
  stream choices with ordinary form fallback.
- School Admin/Super Admin management and Headteacher read-only student access.
  Teacher, Bursar and Guardian student access awaits the corresponding scoped modules.
- Transactions, audit entries, protected relationships and read-only Django admin.
  School date/status changes cannot invalidate enrollment history.
- The student migration is applied to development SQLite. All 122 tests pass;
  system, migration-drift and dependency checks pass.
- Production deployment checks and manifest static collection pass with temporary
  configuration values, without connecting to a live PostgreSQL database.
- Live HTTP checks passed against an isolated database for sign-in, registration,
  guardian linking, enrollment, overlap rejection, preserved history, HTMX and
  role restrictions. Verification data was cleared from that isolated database.
- No browser was connected; visual desktop/mobile checks remain pending. Live
  PostgreSQL concurrency and SMTP checks remain part of deployment verification.

## Next phase

Phase 5 adds teacher profiles/accounts, configurable subjects, teaching assignments,
class-teacher assignments and assignment validation. Test authorization against
the student's enrollment context before granting teachers access to student records.
