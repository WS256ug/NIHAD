# Product requirements

The complete requirements and rules are maintained in [AGENTS.md](AGENTS.md).
This summary identifies the scope and constraints for implementation.

Build a school management system for nursery and primary sections with academic
periods, configurable classes/streams, students, guardians, teachers, assessments,
reports, fees, expenses, promotions and role-specific dashboards.

Use Django templates with Oat UI and HTMX; use SQLite in development and
PostgreSQL in production. Develop inside a Python virtual environment.

Roles: Super Admin, School Admin, Headteacher, Teacher, Bursar/Finance and Guardian.
Use server-side permissions. Guardians may access only their linked children;
teachers may access only authorized assignments. Financial access is separate
from academic access.

Preserve academic history through enrollment records. Configure grading, fees,
school structure and guardian report-access policy. Use Decimal values for money,
atomic financial/promotion operations and protected historical records.

Phases 1–4 provide authentication, role/account management, school configuration,
academic structure, student/guardian records and enrollment history. Student IDs
are permanent. Term ordering follows start dates without a manually entered sequence.
Enrollment context and closed history cannot be overwritten.
School Admins manage records, and Headteachers have read-only student access.
Teacher/student scope follows assignments in Phase 5, and the guardian-facing
portal follows in Phase 10. Remaining workflows follow the guide's verified phases.


## Simplified grade management

Users manage Grades and Divisions by school section. Grading schemes remain
internal; assessment forms do not ask users to select one. Numeric grade ranges
cover 0-100 without overlaps; descriptive levels use labels without percentages.
Assessments can be created before grades are complete. Ready grades are selected
automatically on creation, editing an unconfigured assessment, opening marks, or
generating reports for an unconfigured assessment. Reports require complete
grading. Existing configured assessments retain their original version.


## Marks entry workflow refinement

Teachers enter marks on a whole-class sheet per authorized assessment, subject,
and stream. Save progress permits missing results. Submit for review requires
all eligible students to have a valid score, descriptive level, or explicit
absence. Zero remains valid and differs from blank and absence.

Submitted sheets are locked. School Admin/Headteacher reviews each sheet and
approves it or returns it with a reason. Closing a new assessment and generating
reports require complete, current approved sheets. Existing assessments retain
compatibility until a sheet is saved. Corrections follow the audited report
correction workflow. Numeric reports with absence omit overall results/ranking.


## Guardian contacts and student portal (2026-09-24)

This supersedes earlier independent guardian-account requirements. Guardian
names, phone numbers, NIN, email, addresses and student relationships remain.
Parents use each child's registration number and student portal password;
siblings require separate sign-ins. Staff manage access from the student profile.
Separate guardian login, sessions and account provisioning are disabled by default
(`GUARDIAN_ACCOUNTS_ENABLED = False`). Existing accounts and links are retained
for historical integrity. Registration creates contacts without login accounts.
Report publication, student isolation and fee-clearance checks remain enforced.
