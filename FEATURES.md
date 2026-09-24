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
- School setup create/edit dialogs for sections, academic years, terms, classes
  and streams, with inline validation, filtered table refresh and unsaved-change
  confirmation; standard form pages remain available without JavaScript.
- Shared dialogs also cover school profile/current period, accounts/password
  changes, students/guardians/enrollments, academic records and individual marks,
  report actions, fees/payments, expenses and promotion steps. Photo uploads,
  confirmation forms, dependent selectors and existing server permissions remain
  supported. Saving refreshes the underlying workspace and provides a link to
  the saved result; promotion creation and decisions advance inside the dialog.
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


## Simplified grades interface

- Grades and divisions are managed directly by section, without scheme controls.
- Assessments automatically use ready section grades; incomplete grade setup
  does not block assessment creation. Report generation still requires grades.
- Grade changes create internal versions when necessary to preserve history.
- Removed the section setup messages and explanatory paragraph above the table.


## Whole-class marks entry and review

- Marks entry navigation lists accessible open assessments; teachers see only
  authorized subject assignments and student enrollments.
- Numeric scores or descriptive levels, explicit absence, saved grades, progress
  counts, partial saves, keyboard entry, and unsaved-change warnings.
- Draft/returned sheets can be edited. Submission requires a complete roster;
  submitted/approved sheets are locked, including the single-mark endpoint.
- School Admin and Headteacher can approve or return with a required reason.
- Closing assessments and report generation verify current approved snapshots.
- Atomic writes, signed roster checks, revision conflicts, and audited review.
- Absence never becomes zero or a ranked numeric overall result.


## Guardian contacts and student portal (2026-09-24)

This supersedes earlier independent guardian-account requirements. Guardian
names, phone numbers, NIN, email, addresses and student relationships remain.
Parents use each child's registration number and student portal password;
siblings require separate sign-ins. Staff manage access from the student profile.
Separate guardian login, sessions and account provisioning are disabled by default
(`GUARDIAN_ACCOUNTS_ENABLED = False`). Existing accounts and links are retained
for historical integrity. Registration creates contacts without login accounts.
Report publication, student isolation and fee-clearance checks remain enforced.
