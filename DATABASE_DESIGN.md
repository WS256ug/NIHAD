# Database design

## Implemented schema

`accounts.User` extends Django `AbstractUser` and is configured as `AUTH_USER_MODEL`
before the first migration. It retains username authentication, hashed passwords,
name/email, active/staff/superuser flags, groups, permissions, date joined and last
login. It adds `role` and `updated_at`.

Role values are `super_admin`, `school_admin`, `headteacher`, `teacher`, `bursar`
and `guardian`; a database check rejects any other value. New ordinary users
default to Guardian without staff/superuser privileges. `createsuperuser` assigns
Super Admin. The `accounts_superuser_role_consistent` constraint requires Super
Admin role exactly when `is_superuser=True`, and requires staff status for a
superuser. Model validation reports mismatches in admin forms. Other role labels
never grant staff/superuser flags or Django group/model permissions automatically.

Phase 2 uses shared role helpers to authorize workspaces and account-management
views, plus restricted querysets for account targets. It does not seed broad Django
permissions into role groups. School Admins may manage ordinary Headteacher,
Teacher, Bursar and Guardian accounts; only Super Admins may manage School Admins.
Staff, superusers and accounts with groups or direct Django permissions are excluded
from portal management and handled only through the Super Admin-only Django admin.

Portal creation, edits and activation/deactivation are recorded in the existing
`django_admin_log` table in the same transaction as the account change. Records
include the actor, target and changed field names; passwords are never logged.
Status changes preserve the account row. There is no account-delete portal endpoint.

Password recovery uses Django's signed, time-limited tokens and existing password,
email and last-login fields, without a new token table. The token timeout is one
hour. Password changes invalidate older session authentication hashes; the current
password-change session is retained by Django's built-in view.

Django manages the auth, content type, session and admin log tables. The accounts
initial migration is applied before admin log migrations so foreign keys reference
the custom user from the start.

## Environment behavior

- Development: SQLite in ignored `db.sqlite3`.
- Production: PostgreSQL configured through environment variables with psycopg.
- Automated tests: Django's isolated test database, not the local database.

Use ORM migrations and portable constraints. Production database integration tests
will be required before deployment; local SQLite tests cannot validate PostgreSQL
locking and concurrency behavior.

## Planned relationships

School → sections, academic years, terms, academic classes and streams.
Student → guardians and immutable enrollment history.
Enrollment → academic context, assessments, marks and reports.
Teaching assignment → teacher, subject, class/stream and academic period.
Fee charges → payments/receipts and calculated balance.
Promotion batch → individual decisions and new enrollment records.

Use `settings.AUTH_USER_MODEL` for user foreign keys, protect referenced history,
use `DecimalField` for money and wrap related financial or promotion writes in
transactions. Detailed domain schemas will be added in their implementation phases.
