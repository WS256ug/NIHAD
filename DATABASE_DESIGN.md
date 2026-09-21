# Database design

## Implemented schema

`accounts.User` extends Django `AbstractUser` and is configured as `AUTH_USER_MODEL`
before the first migration. It retains username authentication, hashed passwords,
name/email, active/staff/superuser flags, groups, permissions, date joined and last
login. It adds `role` and `updated_at`.

Role values are `super_admin`, `school_admin`, `headteacher`, `teacher`, `bursar`
and `guardian`; a database check rejects any other value. New ordinary users
default to Guardian without staff/superuser privileges. `createsuperuser` assigns
Super Admin. School role labels do not automatically grant Django permissions.
Account role consistency and domain permission assignment are part of Phase 2.

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
