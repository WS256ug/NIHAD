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

## School configuration schema

| Model | Relationship and purpose |
| --- | --- |
| School | One profile (primary key 1), contact details, currency and report preferences |
| Section | Belongs to School; configurable name, description and display order |
| AcademicYear | Belongs to School; named date range |
| Term | Belongs to AcademicYear; name and contained date range; ordered by start date |
| AcademicClass | Belongs to Section; configurable name and display order |
| Stream | Belongs to AcademicClass; optional subdivision of a class |

The school profile holds nullable `current_academic_year` and `current_term`
foreign keys. This gives one current period without distributed current-status
flags. The term must be active and belong to the active current year. Both
pointers change in one transaction; previous year and term records remain intact.

All six models track creation/update timestamps and actors. Configuration records
use `is_active`. Parent foreign keys use `PROTECT`, and parent reassignment is
rejected after creation. The portal and Django admin expose no configuration
delete action; admin inspection is read-only.

Database constraints enforce the single profile, current-term/year presence,
date ordering and scoped case-insensitive name uniqueness. Terms are displayed
within each year by start date; no sequence column is stored. Model validation
additionally checks period overlaps, containment, parent immutability and
active-parent/child consistency.
Date comparisons include both endpoints, and inactive historical periods still
participate in date/overlap validation.

Use `apps.schools.services` for writes. Services validate after obtaining the
school row lock and record changes in `django_admin_log` within the transaction.
The lock serializes cross-record checks in PostgreSQL. Direct ORM bulk updates
bypass these application rules and are not a supported configuration workflow.
SQLite checks pass; PostgreSQL concurrency still requires deployment validation.

Ranking and fee-clearance preference fields are stored configuration only; the
report and guardian modules will enforce them when implemented.

## Student and guardian schema

| Model | Relationship and purpose |
| --- | --- |
| Student | School, permanent unique student ID, identity/admission details, required Male/Female gender, optional religion (100 characters), status and private photo |
| StudentNumber | One counter per school; allocates sequential permanent IDs inside the school transaction |
| Guardian | One-to-one protected User account, School, phone and address; name/email remain on User |
| StudentGuardian | Protected Student and Guardian, relationship, primary/emergency flags and active status |
| Enrollment | Protected Student, AcademicYear, Section, AcademicClass and optional Stream, dates and status |

All domain records carry audit timestamps and actors. Guardian accounts must retain
the Guardian role; account deactivation disables sign-in without deleting links.
StudentGuardian pairs are unique, and a partial unique constraint allows only one
active primary guardian per student. Deactivated links are retained for inspection.

IDs use `STD-000001` formatting with a unique, nonempty database field. Allocation
locks the school and increments StudentNumber atomically; failed creation rolls
back the increment. IDs and school/account identities cannot be reassigned.
Nonblank admission numbers are case-insensitively unique within the school.
Database checks enforce birth/admission date ordering and valid status/gender values.

Enrollment derives Section from AcademicClass and validates Stream against that
class. The year/class/section/stream must belong to the student's school and be
active for a new enrollment. A conditional database constraint allows one current
enrollment per student/year. Current records have no completion date; all closed
statuses require a completion date on or after enrollment. Date ranges must fit
the academic year and cannot overlap within that student's year, inclusive of
endpoints. Enrollment cannot predate admission.

Enrollment's student, year, section, class, stream and enrollment date are fixed
after creation. Closing changes only status/completion and audit metadata; closed
records are immutable. New placements create new records, including subsequent
placements in the same year after closure. The school current-year pointer is
independent of each year's open/closed enrollment status. Historic enrollment can
be entered with a closed status using active configuration. Parent dates and
deactivation checks now protect enrollment context too.

Use `apps.students.services` for all writes. Services authorize the actor, lock
the school/student and relevant guardian account, revalidate relations and create
audit entries atomically. PostgreSQL uses row locks; SQLite may reject competing
writes with a retryable error. Raw ORM bulk mutations bypass application checks
and are not a supported record-editing workflow. Django admin is read-only.

Photos use PrivatePhotoStorage rooted at PRIVATE_MEDIA_ROOT, never a public media
URL. Uploads are bounded, decoded and re-encoded without metadata. Authorized views
return private, noncached FileResponses. New files are cleaned on write failure;
old files are removed after successful replacement/removal commits. Filesystem and
database backups must be coordinated; a process crash can still leave an orphaned file.

## Environment behavior

- Development: SQLite in ignored `db.sqlite3`.
- Production: PostgreSQL configured through environment variables with psycopg.
- Automated tests: Django's isolated test database, not the local database.

Use ORM migrations and portable constraints. Production database integration tests
will be required before deployment; local SQLite tests cannot validate PostgreSQL
locking and concurrency behavior.

## Planned relationships

Enrollment → academic context, assessments, marks and reports.
Teaching assignment → teacher, subject, class/stream and academic period.
Fee charges → payments/receipts and calculated balance.
Promotion batch → individual decisions and new enrollment records.

Use `settings.AUTH_USER_MODEL` for user foreign keys, protect referenced history,
use `DecimalField` for money and wrap related financial or promotion writes in
transactions. Detailed domain schemas will be added in their implementation phases.


## Internal section grade versions

GradingScheme, GradeRule and DivisionRule remain unchanged in the database.
The newest scheme by primary key in a section is its current configuration,
including incomplete drafts. Workspace lists show only that version's rules.
Editing an active, used or assessment-linked version copies its grades, divisions,
aggregation settings and required subjects within the school transaction lock.
Older assessments keep their foreign keys. Incomplete unreferenced versions can
be edited directly; complete versions activate automatically. No schema migration
is required. New sections start without aggregates; adding divisions requires
points on every grade and enables all-subject aggregation. Existing aggregation
policies are preserved when copying versions.


## Marks sheet review and absence

Migration academics.0004 adds Mark.is_absent and updates the value constraint:
absent marks have neither score nor level; other marks have exactly one.
Assessment.requires_mark_review defaults to true for new assessments; migration
preserves false for existing records. Saving a sheet enables review for it.

MarkSubmission is unique by assessment and teaching assignment. It stores a
status (draft/submitted/approved/returned), optimistic revision, submitter/reviewer
and timestamps, review note, and a JSON snapshot of enrollment IDs and mark
revisions. Audit events preserve transitions. Approval and downstream report
checks compare the saved snapshot against the current eligible roster/results.
Report correction returns submitted/approved sheets while preserving prior report
snapshots. Absent numeric results do not contribute an overall result or ranking.


## Guardian contacts and student portal (2026-09-24)

This supersedes earlier independent guardian-account requirements. Guardian
names, phone numbers, NIN, email, addresses and student relationships remain.
Parents use each child's registration number and student portal password;
siblings require separate sign-ins. Staff manage access from the student profile.
Separate guardian login, sessions and account provisioning are disabled by default
(`GUARDIAN_ACCOUNTS_ENABLED = False`). Existing accounts and links are retained
for historical integrity. Registration creates contacts without login accounts.
Report publication, student isolation and fee-clearance checks remain enforced.
