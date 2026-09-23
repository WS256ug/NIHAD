# Feature status

## Implemented in the foundation

- Python virtual environment, dependency pins and VS Code interpreter selection
- Django project with SQLite development and PostgreSQL production settings
- Custom user, six stored school roles and Django admin integration
- Sign-in with HTMX validation and standard HTML form fallback
- Authentication-required workspace containing only the current user's profile
- CSRF-protected POST sign-out and safe post-login redirects
- Responsive Oat UI layout, local frontend assets and request feedback
- Tests for authentication, privilege boundaries and settings

## Planned

Phase 5 starts teachers, subjects and assignments. Subsequent phases add
assessments, grading, reports, fees, guardian access policies, expenses, promotion,
dashboards, security review and deployment preparation. See DEVELOPMENT_PLAN.md.

## Implemented in Phase 2

- Separate protected workspaces and navigation for all six roles
- Shared role permissions and scoped account-management querysets
- Searchable, paginated account directory with HTMX search
- Authorized account creation, editing and confirmed activation/deactivation
- Server-side prevention of privilege changes through ordinary account forms
- Super Admin-only Django administration and consistent superuser/role flags
- Account-change audit entries in Django admin's log
- Own profile display, password change and email-token password reset
- One-hour reset expiry, single-use tokens and session invalidation
- Console email for development; production SMTP configuration
- 48 passing automated tests across the foundation and account workflows

## Implemented in Phase 3

- School profile, configurable contact/currency details and saved report preferences
- School name displayed throughout the main portal layout
- Sections, academic years, terms, classes and optional streams
- Admin-only setup with searchable lists, pagination and confirmed status changes
- One current academic year and optional term, with HTMX term selection
- Scoped duplicate-name checks, date-based term ordering and date/overlap validation
- Protected parent relationships, active-parent checks and historical preservation
- Audit fields and transactional configuration logs
- Read-only configuration inspection in Django admin
- 79 passing tests across Phases 1–3 plus isolated live HTTP workflow checks

## Implemented in Phase 4

- Student registration/profiles with required Male/Female gender and optional religion, permanent sequential IDs, admission numbers and statuses
- Validated private photo uploads and authorized delivery
- Guardian account/profile registration and reuse of existing Guardian accounts
- Multiple guardian links, primary/emergency contacts and preserved inactive links
- Enrollment with optional streams, closure, immutable context and historical entries
- Date, status, duplicate, parent and overlap validation with database constraints
- Student search, history-aware year/section/class/stream filters and pagination
- HTMX search/stream choices and ordinary HTML form fallback
- Administrator management, Headteacher read-only student access and audited writes
- Read-only domain inspection in Django admin and protected account relationships
- 123 tests across Phases 1–4, plus isolated live HTTP workflow verification
