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

Phases 1–3 provide authentication, role/account management, school configuration
and academic structure. Student/guardian records and enrollment begin in Phase 4;
remaining domain workflows follow the guide's verified phases.
