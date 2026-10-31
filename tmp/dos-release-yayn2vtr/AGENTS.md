# AGENTS.md
# School Management System — Django Development Guide

## Workspace execution notes

- Use the project virtual environment at `.venv` for every Python command and dependency installation.
- On Windows, activate with `.\.venv\Scripts\Activate.ps1` or invoke `.\.venv\Scripts\python.exe` directly.
- The Django project lives at the repository root; `manage.py` uses development settings by default.
- Track completed phases and the next milestone in `DEVELOPMENT_PLAN.md`.
- Keep `.env`, `.venv`, local databases, and uploaded media out of Git.
- Latest account requirement (2026-09-24): keep guardian contact details and
  student relationships, but do not provision separate guardian accounts.
- Parents use each child's student registration number and portal password.
  Separate Guardian sign-in is disabled by default; historical account links
  remain stored. This supersedes older independent Guardian account requirements
  elsewhere in this guide. Staff continue to use individual accounts.

## 1. Project Overview

Build a production-ready **School Management System (SMS)** using Django.

The system manages:

- School sections: Nursery and Primary
- Academic years and terms
- Academic classes and streams
- Student registration and profiles
- Student enrollment/history
- Student promotion between classes
- Teachers and teacher accounts
- Subject registration
- Teacher and subject allocation
- Class-teacher allocation
- Assessments: Mid-Term and End-Term
- Marks entry
- Grades, aggregates, divisions, averages and optional ranking
- Class-teacher comments
- Headteacher comments and report approval
- Individual student reports
- Guardian accounts and linked children
- Fees, invoices, payments, balances and receipts
- Guardian report-access control based on fees policy
- School expenses
- Income and financial summaries
- Role-based dashboards
- Audit-friendly historical records

The system must be modular, maintainable, secure, responsive and suitable for eventual deployment to a real school.

---

# 2. Core Development Principles

## 2.1 Build in small, verified phases

Never build the entire system at once.

Use this sequence:

1. Project foundation
2. Accounts and roles
3. School configuration
4. Academic structure
5. Students and guardians
6. Teachers and allocations
7. Assessments and grading
8. Marks entry
9. Reports and approval
10. Fees and payments
11. Guardian portal
12. Expenses and finance
13. Promotion
14. Dashboards and reporting
15. Testing and security
16. Deployment preparation

Each phase must be tested before moving to the next.

## 2.2 Do not break completed functionality

Before modifying an existing feature:

- Inspect the existing implementation.
- Understand its dependencies.
- Make the smallest safe change.
- Run tests.
- Run `python manage.py check`.
- Verify related workflows.

Do not rewrite functioning modules unnecessarily.

## 2.3 Prefer Django-native solutions

Use:

- Django ORM
- Django authentication
- Django permissions
- Django forms
- Django class-based or function-based views where appropriate
- Django templates
- Django admin where useful
- Django messages
- Django transactions
- Django management commands

Do not introduce unnecessary infrastructure.

Avoid adding:

- React
- Django REST Framework
- Celery
- Redis
- WebSockets
- microservices
- Kubernetes

unless a later requirement clearly justifies them.

---

# 3. Recommended Stack

## Backend

- Python 3.12+
- Django 5.x
- PostgreSQL for production
- SQLite for local development

## Frontend

- Django Templates
- HTML5
- CSS3
- Oat UI for styling and UI components
- HTMX for dynamic interactions and partial page updates
- Vanilla JavaScript when necessary

## Reports

Use a reliable server-side PDF generation approach.

Reports must also have an HTML/printable version so that PDF generation is not the only way to view them.

## Development Tools

Recommended:

- VS Code
- Git
- GitHub
- Python virtual environment
- SQLite for local development; PostgreSQL for production
- Django test framework

---

# 4. Project Structure

Use a modular Django project.

Recommended structure:

```text
school_management/
├── manage.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
├── AGENTS.md
│
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/
│   ├── schools/
│   ├── students/
│   ├── academics/
│   ├── reports/
│   ├── finance/
│   ├── expenses/
│   ├── promotions/
│   └── dashboard/
│
├── templates/
├── static/
├── media/
└── tests/
```

Do not create an app for every tiny feature. Keep related domain logic together.

---

# 5. Application Responsibilities

## `accounts`

Responsible for:

- Custom user model
- Login/logout
- Password management
- User roles
- Permissions
- Teacher accounts
- Guardian accounts
- Admin accounts
- Headteacher accounts
- Bursar/finance accounts

## `schools`

Responsible for:

- School profile
- Sections
- Academic years
- Terms
- Academic classes
- Streams
- School configuration
- Grading configuration where appropriate

## `students`

Responsible for:

- Student profiles
- Student IDs
- Guardians
- Student-guardian relationships
- Student enrollment
- Student academic history

## `academics`

Responsible for:

- Subjects
- Teachers
- Teacher-subject allocation
- Class/stream allocation
- Class teachers
- Assessments
- Marks
- Grades
- Aggregates
- Divisions
- Ranking configuration

## `reports`

Responsible for:

- Student reports
- Mid-Term reports
- End-Term reports
- Teacher comments
- Headteacher comments
- Report approval
- Report publication
- Report rendering
- PDF/print output

## `finance`

Responsible for:

- Fee structures
- Student fee assignments
- Invoices/charges
- Payments
- Receipts
- Balances
- Financial statements
- Guardian fee visibility
- Report access policy

## `expenses`

Responsible for:

- Expense categories
- Expenses
- Expense records
- Financial summaries

## `promotions`

Responsible for:

- Promotion batches
- Promotion decisions
- Repeat decisions
- Transfers
- Graduation/withdrawal status
- New enrollment creation

## `dashboard`

Responsible for:

- Admin dashboard
- Teacher dashboard
- Headteacher dashboard
- Bursar dashboard
- Guardian dashboard
- Role-specific navigation

---

# 6. User Roles

Implement role-based access.

Minimum roles:

1. Super Admin
2. School Admin
3. Headteacher
4. Teacher
5. Bursar/Finance
6. Guardian

A custom Django user model should be created at the beginning of the project.

Do NOT start with Django's default User model and later attempt to replace it.

---

# 7. Permissions

## Super Admin

Can manage everything.

## School Admin

Can manage:

- Students
- Guardians
- Teachers
- Classes
- Streams
- Subjects
- Academic years
- Terms
- Fees
- Promotions
- General school configuration

## Headteacher

Can:

- View academic data
- Review reports
- Enter headteacher comments
- Approve reports
- View students
- Manage/review promotion decisions
- View academic summaries

The headteacher should not automatically have permission to modify financial records.

## Teacher

Can:

- View assigned classes
- View assigned students
- View assigned subjects
- Enter/edit marks for authorized assignments
- Enter class-teacher comments where assigned
- View relevant academic information

Teachers must not see financial information unless explicitly granted permission.

## Bursar

Can:

- Manage fees
- Record payments
- Generate receipts
- View balances
- Record expenses if authorized
- View financial reports

Bursar should not modify academic marks.

## Guardian

Can:

- View own profile
- View linked children
- View child profile
- View fees
- View payments
- View balance
- View reports only when access conditions are satisfied

Guardians must never access another student's data.

---

# 8. School Structure

The system must support:

```text
School
├── Nursery
│   ├── Baby
│   ├── Middle
│   └── Top
│
└── Primary
    ├── P.1
    ├── P.2
    ├── P.3
    ├── P.4
    ├── P.5
    ├── P.6
    └── P.7
```

Do not hard-code these values.

Administrators must be able to create:

- Sections
- Academic classes
- Streams

Example:

```text
Section: Primary
Class: P.5
Stream: East
```

Another:

```text
Section: Primary
Class: P.5
Stream: West
```

A class may exist without streams if the school does not use streams.

---

# 9. Academic Year and Terms

Create an `AcademicYear` model.

Example:

```text
2026
```

Create a `Term` model.

Example:

```text
2026
├── Term 1
├── Term 2
└── Term 3
```

A term belongs to an academic year.

Order terms by start date within their academic year; do not ask administrators
for a separate sequence number. Keep dates non-overlapping and within the year.

The system must prevent conflicting active academic periods where appropriate.

---

# 10. Student Model

Student must have a permanent unique identifier.

Example:

```text
STD-000001
```

Student information:

- Student ID
- First name
- Middle name
- Last name
- Photo
- Gender
- Date of birth
- Admission date
- Admission number if separate
- Status
- Contact/address information where required

Do not use the current class as the student's permanent historical class.

---

# 11. Student Enrollment

This is a critical design rule.

Do NOT simply update:

```text
student.class = P5
```

when a student is promoted.

Use an enrollment/history model.

Example:

```text
John Wasswa

2024 → P.3 → Completed
2025 → P.4 → Completed
2026 → P.5 → Current
```

An enrollment should reference:

- Student
- Academic year
- Section
- Academic class
- Stream
- Status
- Enrollment date
- Completion date where applicable

This preserves historical records.

---

# 12. Student Status

Support statuses such as:

- Active
- Promoted
- Repeating
- Transferred
- Withdrawn
- Graduated
- Inactive

Do not delete historical student records merely because a student leaves the school.

---

# 13. Guardians

A guardian is a user/account that can be linked to one or more students.

Example:

```text
Guardian
├── John
├── Sarah
└── David
```

Create a proper relationship model rather than storing only one guardian ID on the student.

Support:

- Guardian name
- Relationship
- Phone
- Email
- Address
- Primary guardian flag
- Emergency contact flag if required

---

# 14. Subjects

Subjects must be configurable.

Examples:

Primary:

- English
- Mathematics
- Science
- Social Studies
- Religious Education
- ICT

Nursery may use learning areas instead of the same primary subject structure.

Do not force nursery to use primary grading.

---

# 15. Teacher Registration

Teacher records should include:

- Teacher ID
- User account
- Full name
- Phone
- Email
- Employment status
- Date joined
- Optional specialization

Teachers should authenticate through their own accounts.

---

# 16. Teacher and Subject Allocation

Teacher allocation must be explicit.

Example:

```text
Teacher: Mr. John
Class: P.5 East
Subject: Mathematics
Academic Year: 2026
Term: Term 2
```

Another:

```text
Teacher: Mr. John
Class: P.6 West
Subject: Mathematics
Academic Year: 2026
Term: Term 2
```

This means one teacher may teach:

- Multiple classes
- Multiple streams
- Multiple subjects

Create a `TeachingAssignment` model.

A teaching assignment should reference:

- Teacher
- Academic year
- Term where applicable
- Section
- Academic class
- Stream
- Subject
- Active status

---

# 17. Class Teacher Allocation

Class teacher assignment is separate from subject teaching.

Example:

```text
P.5 East → Mr. John
P.5 West → Ms. Sarah
```

A `ClassTeacherAssignment` should reference:

- Teacher
- Academic year
- Term if required by school policy
- Section
- Academic class
- Stream
- Active status

Only the assigned class teacher should be able to enter the class-teacher comment unless an authorized administrator overrides it.

---

# 18. Assessments

The system must support at least:

- Mid-Term
- End-Term

Assessment structure:

```text
Academic Year
└── Term
    └── Assessment
        ├── Mid-Term
        └── End-Term
```

An assessment should be associated with the relevant academic period.

Do not overwrite previous assessment results.

---

# 19. Marks

A mark belongs to:

- Student enrollment
- Assessment
- Subject
- Teaching assignment where appropriate
- Score
- Metadata/audit fields

Teachers can only edit marks they are authorized to enter.

Validate score ranges.

For example, if maximum score is 100:

```text
0 <= score <= 100
```

Do not silently accept invalid values.

---

# 20. Grading System

Grading must be configurable.

Do not hard-code grading rules in views.

Create a grading configuration such as:

```text
Grade Rule
--------------------------------
Grade     Min     Max
D1        80      100
D2        75      79
D3        70      74
...
F9        0       39
```

The exact ranges must be configurable by the school.

Different sections may use different grading systems.

---

# 21. Nursery Assessment

Nursery should not be forced into the primary grading system.

Possible configurable levels:

```text
Emerging
Developing
Achieved
Excellent
```

The school should be able to define its own levels.

Nursery reports may therefore contain descriptive assessment rather than aggregates/divisions.

---

# 22. Aggregates

The system must support aggregate calculation.

Example:

```text
English       D1 → 1
Mathematics   D2 → 2
Science       D2 → 2
SST           D1 → 1
----------------------
Aggregate     6
```

Do not assume that every school uses the same aggregation rule.

Support configuration such as:

- Best N subjects
- Required subjects
- Specific subject combination
- All graded subjects
- Custom aggregation rule

Store the configuration rather than embedding it in Python conditionals.

---

# 23. Divisions

The system must support configurable division rules.

Example only:

```text
Division I
Aggregate 4–12

Division II
Aggregate 13–24

Division III
Aggregate 25–32

Division IV
Aggregate 33–36

Division U
Unclassified
```

These values are examples and must be configurable.

Division calculation should happen after aggregate calculation.

---

# 24. Ranking

Student ranking must be configurable.

School setting:

```text
Enable ranking: Yes/No
```

If enabled, the report may show:

```text
Position: 4 / 52
```

If disabled, no student ranking should be displayed.

Do not expose ranking simply because the database calculated it.

---

# 25. Academic Result Pipeline

Use this sequence:

```text
Raw Marks
   ↓
Subject Score
   ↓
Grade
   ↓
Grade Points / Aggregate
   ↓
Total Aggregate
   ↓
Division
   ↓
Optional Position
```

Keep calculations deterministic and testable.

---

# 26. Student Report

Every student receives an individual report for an assessment period.

Example:

```text
School
Student: John Wasswa
ID: STD-000001
Class: P.5 East
Academic Year: 2026
Term: Term 2
Assessment: End-Term

Subject | Mark | Grade | Aggregate
-----------------------------------
English | 82   | D1    | 1
Math    | 76   | D2    | 2
Science | 71   | D2    | 2
SST     | 85   | D1    | 1

Total: 314
Average: 78.5%
Aggregate: 6
Division: I
Position: 4/52
```

Do not display fields that do not apply to the student's section or configured grading system.

---

# 27. Report Workflow

Use explicit report statuses.

Recommended:

```text
DRAFT
MARKS_COMPLETE
TEACHER_COMMENT_COMPLETE
HEADTEACHER_REVIEW
APPROVED
PUBLISHED
LOCKED
```

Typical flow:

```text
Marks entered
    ↓
Marks complete
    ↓
Class teacher comment
    ↓
Headteacher review
    ↓
Headteacher comment
    ↓
Approval
    ↓
Publication
```

Once published, prevent unauthorized modification.

If a published report must be changed, require an authorized correction workflow.

---

# 28. Class Teacher Comment

The class teacher can enter:

- Comment
- Optional conduct/attendance observations if later required

The comment belongs to the specific report.

It must not be a permanent comment on the student profile.

---

# 29. Headteacher Comment

The headteacher can:

- Review the report
- Enter headteacher comment
- Approve the report
- Reject/send back for correction if required

A rejected report should return to an appropriate earlier status.

---

# 30. Fees

Create configurable fee structures.

Example:

```text
2026
Term 2
P.5

Tuition:       500,000
Meals:          80,000
Development:    20,000
------------------------
Total:         600,000
```

Do not hard-code fees.

Fee structures may vary by:

- Section
- Class
- Term
- Academic year
- Student category

---

# 31. Student Fees

Track:

```text
Amount charged
Amount paid
Balance
```

Balance:

```text
Balance = Total Charges - Total Payments
```

If credits, discounts or adjustments are later supported, model them explicitly rather than altering payment records.

---

# 32. Payments

Every payment should record:

- Student
- Amount
- Date
- Payment method
- Reference/receipt number
- Recorded by
- Relevant fee charge/invoice
- Notes where required

Use database transactions for financial operations.

Do not partially save a payment and receipt operation.

---

# 33. Receipts

Generate a unique receipt number.

Example:

```text
REC-2026-000001
```

Receipt should show:

- School
- Receipt number
- Student
- Class
- Amount paid
- Payment date
- Payment method
- Previous balance
- New balance
- Recorded by

---

# 34. Guardian Report Access

Guardian access must be enforced on the server.

Rule:

```text
IF outstanding balance <= 0
    report access allowed
ELSE
    report access denied
```

But implement this through a configurable school policy.

Recommended setting:

```text
Require fee clearance before report access: Yes/No
```

When access is denied:

Guardian can still view:

- Student profile
- Class
- Academic history summary where permitted
- Fees charged
- Payments
- Outstanding balance

Guardian cannot view:

- Restricted report
- Restricted report PDF
- Restricted report print view
- Restricted report download endpoint

Do not merely hide the report button.

---

# 35. Guardian Security

Every guardian request must verify:

1. User is authenticated.
2. Student is linked to that guardian.
3. Student belongs to the relevant school.
4. Requested object belongs to that student.
5. Report access policy is satisfied.

Never trust a student ID supplied in a URL.

---

# 36. Expenses

Create expense categories such as:

- Salaries
- Food
- Electricity
- Water
- Transport
- Maintenance
- Stationery
- Internet
- Equipment
- Rent
- Other

Expense record:

- Category
- Description
- Amount
- Date
- Payment method
- Reference
- Recorded by
- Optional attachment/receipt

---

# 37. Financial Summary

Dashboard should calculate:

```text
Total Fees Charged
Total Fees Collected
Outstanding Fees
Other Income
Total Expenses
Net Financial Balance
```

Example:

```text
Fees Collected       UGX 85,400,000
Other Income          UGX 2,500,000
-----------------------------------
Total Income         UGX 87,900,000

Expenses             UGX 61,200,000
-----------------------------------
Net Balance          UGX 26,700,000
```

For school terminology, prefer:

- Income
- Expenses
- Surplus/Deficit
- Outstanding Fees

rather than assuming the organization is a for-profit business.

---

# 38. Promotion

Promotion must preserve history.

Example:

```text
2025 → P.4
2026 → P.5
```

Never delete the old P.4 enrollment.

Promotion workflow:

```text
Select Academic Year
        ↓
Select Source Class
        ↓
Select Destination Class
        ↓
List Students
        ↓
Choose:
  Promote
  Repeat
  Transfer
  Withdraw
        ↓
Preview
        ↓
Confirm
        ↓
Create New Enrollment
```

Use database transactions when processing a batch promotion.

---

# 39. Promotion Batch

Create a promotion batch so that promotion can be audited.

Example:

```text
Promotion Batch
Academic Year: 2026
From: P.4
To: P.5
Created by: Admin
Date: ...
Status: Draft/Confirmed
```

Individual decisions belong to the batch.

---

# 40. Dashboard Design

## Admin Dashboard

Show:

- Total students
- Students by section
- Teachers
- Classes
- Current academic year
- Current term
- Fee collections
- Outstanding fees
- Expenses
- Financial balance
- Reports pending
- Promotion status

## Teacher Dashboard

Show:

- Assigned classes
- Assigned subjects
- Students
- Assessments
- Pending marks
- Comments pending
- Reports requiring action

Do not show finance unless permission is explicitly granted.

## Headteacher Dashboard

Show:

- Students
- Academic classes
- Reports awaiting review
- Approved reports
- Academic performance
- Promotion status

## Bursar Dashboard

Show:

- Fees collected
- Outstanding fees
- Recent payments
- Receipts
- Expenses
- Financial summary

## Guardian Dashboard

Show:

- Linked children
- Current class
- Student profile
- Fees
- Balance
- Report availability

---

# 41. Navigation

Use role-specific navigation.

Admin:

```text
Dashboard
Students
Guardians
Teachers
Classes
Streams
Subjects
Academic Years
Terms
Assessments
Reports
Fees
Payments
Expenses
Promotions
Settings
```

Teacher:

```text
Dashboard
My Classes
My Subjects
Students
Marks
Comments
Reports
```

Headteacher:

```text
Dashboard
Students
Academic Performance
Reports
Comments
Promotions
```

Bursar:

```text
Dashboard
Fees
Payments
Receipts
Outstanding Fees
Expenses
Finance Reports
```

Guardian:

```text
Dashboard
My Children
Student Profile
Fees
Reports
```

---

# 42. UI/UX Rules

Use a clean school-management interface.

Requirements:

- Responsive
- Mobile-friendly
- Desktop-friendly
- Clear navigation
- Consistent forms
- Searchable tables
- Pagination
- Filters
- Confirmation dialogs for destructive actions
- Success/error messages
- Empty states
- Loading states where HTMX is used
- Accessible labels
- Clear status badges

Avoid clutter.

Use cards for dashboard summaries and tables for operational data.

---

# 43. Forms

Use Django Forms or ModelForms.

Forms must:

- Validate input server-side
- Provide useful error messages
- Preserve entered data when validation fails
- Restrict queryset choices according to permissions
- Prevent unauthorized object selection

Never trust frontend restrictions as security.

---

# 44. Queryset Security

This is critical.

Teachers should receive filtered querysets.

Example concept:

```python
TeachingAssignment.objects.filter(
    teacher=request.user.teacher,
    active=True,
)
```

Do not fetch all students and merely hide unauthorized rows in the template.

Use authorization at the queryset/view/service level.

---

# 45. Financial Security

Financial records are sensitive.

Use:

- Transactions
- Permission checks
- Immutable payment records where practical
- Audit fields
- Unique receipt numbers
- Validation
- Decimal fields for money

Never use floating-point fields for currency.

Use:

```python
DecimalField
```

---

# 46. Money

Use UGX as the initial school currency if this system is intended for Uganda.

Do not store:

```python
FloatField
```

for financial amounts.

Use:

```python
DecimalField(max_digits=..., decimal_places=2)
```

Allow future currency configuration if multi-country expansion becomes a requirement.

---

# 47. Auditability

Important records should include:

- Created at
- Updated at
- Created by where relevant
- Updated by where relevant

Financial records and report approval should have stronger audit trails.

Never silently delete important historical records.

Prefer:

- Soft deactivation
- Status changes
- Reversal/adjustment records

where appropriate.

---

# 48. Deletion Rules

Avoid hard deletion of:

- Students with academic history
- Published reports
- Payments
- Fee charges
- Promotion history
- Important teacher assignments

Instead use:

- `is_active`
- status fields
- archive/deactivate operations

Hard deletion may be allowed for configuration records only when there are no dependencies.

---

# 49. Database Design Principles

Use proper foreign keys.

Use appropriate `on_delete` behavior.

Add:

- Unique constraints
- Check constraints
- Composite constraints
- Database indexes where useful

Examples:

A student ID must be unique.

A student should not have two current enrollments for the same academic year.

A teaching assignment should not be duplicated.

A receipt number must be unique.

---

# 50. Reports and Historical Data

Never calculate historical reports from today's current class.

A report should point to the relevant historical enrollment/academic context.

Example:

```text
2025 Term 3 Report
→ Student
→ 2025 Enrollment
→ P.4
→ Term 3
→ End-Term Assessment
```

Even if the student is currently in P.6, the old report must still show P.4.

---

# 51. Database Transaction Rules

Use transactions for operations involving multiple related writes.

Examples:

### Payment

```text
Create payment
+
Update/derive balance
+
Create receipt
```

### Promotion

```text
Create promotion batch
+
Create decisions
+
Create new enrollments
```

### Report publication

```text
Validate report
+
Finalize report
+
Publish report
```

If one critical operation fails, the related transaction should roll back.

---

# 52. Testing Strategy

Every major module must have tests.

## Accounts

Test:

- Login
- Logout
- Password
- Role permissions

## Students

Test:

- Registration
- Unique student ID
- Guardian linking
- Enrollment

## Academics

Test:

- Subject assignment
- Teacher assignment
- Mark entry authorization
- Score validation
- Grade calculation
- Aggregate calculation
- Division calculation

## Reports

Test:

- Report creation
- Comments
- Approval
- Publication
- Historical reports

## Finance

Test:

- Fee charges
- Payments
- Balance
- Receipt numbers
- Guardian access restriction

## Promotion

Test:

- Promotion
- Repeating
- Historical enrollment
- Batch promotion

---

# 53. Required Automated Tests

Before each milestone:

```bash
python manage.py check
python manage.py test
```

When practical:

```bash
python manage.py makemigrations --check
```

No milestone is complete if tests are failing.

---

# 54. Development Sequence

Follow this exact implementation order.

## Phase 1 — Project Foundation

Tasks:

1. Create repository.
2. Create virtual environment.
3. Install Django.
4. Create project.
5. Create custom user model.
6. Configure settings.
7. Configure environment variables.
8. Configure templates.
9. Configure static files.
10. Configure media.
11. Configure database.
12. Add base layout.
13. Run initial checks.

Deliverable:

A clean Django project with authentication foundation.

---

## Phase 2 — Accounts

Build:

1. Custom user
2. Roles
3. Login
4. Logout
5. Password management
6. Permission helpers
7. Role-based redirects
8. Role-based navigation

Test every role.

---

## Phase 3 — School Configuration

Build:

1. School profile
2. Sections
3. Academic years
4. Terms
5. Academic classes
6. Streams

Admin must be able to configure the school without editing code.

---

## Phase 4 — Students and Guardians

Build:

1. Student registration
2. Student ID generation
3. Student profile
4. Guardian registration
5. Guardian-student relationship
6. Enrollment
7. Student history
8. Search/filtering

Verify historical enrollment.

---

## Phase 5 — Teachers and Subjects

Build:

1. Teacher profiles
2. Teacher accounts
3. Subjects
4. Teaching assignments
5. Class-teacher assignments
6. Assignment validation

Test authorization.

---

## Phase 6 — Academic Assessment

Build:

1. Assessment types
2. Mid-Term
3. End-Term
4. Assessment configuration
5. Mark entry
6. Mark editing
7. Mark validation

Teachers must only see authorized classes/subjects.

---

## Phase 7 — Grading

Build:

1. Grading systems
2. Grade rules
3. Aggregate rules
4. Division rules
5. Optional ranking
6. Nursery assessment configuration

Write unit tests for calculations.

---

## Phase 8 — Reports

Build:

1. Student report model
2. Report generation
3. Subject results
4. Aggregate
5. Division
6. Position if enabled
7. Class-teacher comments
8. Headteacher comments
9. Approval
10. Publishing
11. Print view
12. PDF

Test historical reports.

---

## Phase 9 — Fees

Build:

1. Fee structures
2. Student charges
3. Payments
4. Balances
5. Receipts
6. Fee statements
7. Outstanding-fee reports

Use database transactions.

---

## Phase 10 — Guardian Portal

Build:

1. Guardian dashboard
2. Children list
3. Student profile
4. Fees
5. Payment history
6. Report access control

Test unauthorized access carefully.

---

## Phase 11 — Expenses and Finance

Build:

1. Expense categories
2. Expenses
3. Income summary
4. Expense summary
5. Outstanding fees
6. Financial balance
7. Financial dashboard

---

## Phase 12 — Promotion

Build:

1. Promotion batches
2. Student selection
3. Promote
4. Repeat
5. Transfer
6. Withdraw
7. New enrollment creation
8. Historical preservation
9. Promotion reports

Test batch transactions.

---

## Phase 13 — Dashboards

Polish:

- Admin dashboard
- Teacher dashboard
- Headteacher dashboard
- Bursar dashboard
- Guardian dashboard

Only show information appropriate to each role.

---

## Phase 14 — Security

Review:

- Authentication
- Authorization
- Object-level permissions
- CSRF
- XSS
- SQL injection protection
- File upload validation
- Session security
- Password security
- Guardian isolation
- Financial isolation
- Report access
- IDOR protection

Pay special attention to URLs such as:

```text
/students/123/
/reports/456/
/fees/789/
```

A user must not gain access simply by changing the numeric ID.

---

## Phase 15 — Production Preparation

Configure:

- PostgreSQL
- Environment variables
- `DEBUG=False`
- Allowed hosts
- CSRF trusted origins
- Static files
- Media files
- Secure cookies
- HTTPS
- Logging
- Backups
- Error handling

Run:

```bash
python manage.py check --deploy
```

---

# 55. Git Strategy

Use small commits.

Examples:

```text
chore: initialize django project
feat: add custom user model
feat: add school sections and academic years
feat: add classes and streams
feat: add student enrollment
feat: add guardian management
feat: add teacher subject allocation
feat: add assessment management
feat: add marks entry
feat: add grading and aggregates
feat: add student reports
feat: add fees management
feat: add guardian portal
feat: add expense tracking
feat: add promotion workflow
test: add academic calculation tests
fix: enforce guardian report access
```

Do not create huge commits containing unrelated changes.

---

# 56. Development Documentation

Maintain:

```text
AGENTS.md
PRODUCT_REQUIREMENTS.md
DATABASE_DESIGN.md
FEATURES.md
DEVELOPMENT_PLAN.md
README.md
```

Keep documentation synchronized with implementation.

If a requirement changes, update the relevant document.

---

# 57. Seed/Demo Data

Create a development management command such as:

```bash
python manage.py seed_demo
```

Demo data should include:

- One school
- Nursery
- Primary
- Several classes
- Streams
- Academic year
- Terms
- Subjects
- Teachers
- Class teachers
- Students
- Guardians
- Teaching assignments
- Assessments
- Marks
- Reports
- Fees
- Payments
- Expenses

This makes testing the complete workflow easier.

---

# 58. End-to-End Test Scenario

The complete system must support this scenario:

```text
1. Admin creates 2026 academic year.

2. Admin creates Term 1.

3. Admin creates Primary section.

4. Admin creates P.5.

5. Admin creates P.5 East stream.

6. Admin registers teacher John.

7. Admin registers Mathematics.

8. Admin assigns John to P.5 East Mathematics.

9. Admin assigns John as P.5 East class teacher.

10. Admin registers student Mary.

11. Mary is enrolled in P.5 East.

12. Admin links Mary's guardian.

13. Admin creates Term 1 Mid-Term assessment.

14. Teacher John enters Mary's Mathematics mark.

15. Other assigned subject teachers enter their marks.

16. System calculates grades.

17. System calculates aggregate where applicable.

18. System calculates division where applicable.

19. System calculates position if enabled.

20. Class teacher enters Mary's comment.

21. Headteacher reviews the report.

22. Headteacher enters a comment.

23. Headteacher approves the report.

24. Admin/Bursar assigns fees.

25. Guardian pays the full balance.

26. Guardian logs in.

27. Guardian views Mary's profile.

28. Guardian views fees and payment history.

29. Guardian views Mary's report.

30. End of academic year arrives.

31. Admin starts promotion.

32. Mary is promoted from P.5 to P.6.

33. System creates a new P.6 enrollment.

34. Mary's P.5 history remains unchanged.

35. Previous report remains accessible according to school policy.
```

This scenario should eventually be automated as an integration test.

---

# 59. Important Non-Functional Requirements

The system should be:

- Secure
- Maintainable
- Responsive
- Fast for normal school operations
- Accessible
- Auditable
- Mobile-friendly
- Database-consistent
- Easy for non-technical school staff
- Scalable to additional classes/students
- Configurable without code changes

---

# 60. Future Extensions

Do not build these into the MVP unless required.

Possible future modules:

- Attendance
- Timetable
- School calendar
- SMS notifications
- Email notifications
- WhatsApp notifications
- Online fee payment
- Student ID cards
- Teacher attendance
- Payroll
- Library
- Transport
- Inventory
- Hostel/boarding
- Discipline
- Health records
- Parent announcements
- Mobile application
- Multi-school SaaS architecture

The initial architecture should avoid blocking these future additions.

---

# 61. Final Architecture Principle

The most important relationship in this system is:

```text
STUDENT
   ↓
ENROLLMENT
   ↓
ACADEMIC YEAR + TERM + CLASS + STREAM
   ↓
TEACHER/SUBJECT ASSIGNMENT
   ↓
ASSESSMENT
   ↓
MARKS
   ↓
GRADING
   ↓
AGGREGATE
   ↓
DIVISION
   ↓
REPORT
   ↓
TEACHER COMMENT
   ↓
HEADTEACHER COMMENT
   ↓
APPROVAL
   ↓
GUARDIAN ACCESS
```

Financially:

```text
STUDENT
   ↓
FEE CHARGES
   ↓
PAYMENTS
   ↓
BALANCE
   ↓
REPORT ACCESS POLICY
```

At year-end:

```text
CURRENT ENROLLMENT
        ↓
PROMOTION DECISION
        ↓
NEW ENROLLMENT
        ↓
NEW CLASS
```

Never destroy the previous enrollment.

---

# 62. Definition of Done

A feature is not complete merely because its page exists.

A feature is complete when:

- Model is implemented
- Migration is created
- Forms are validated
- Views are implemented
- URLs are implemented
- Templates are implemented
- Permissions are enforced
- Error handling exists
- Relevant tests pass
- `python manage.py check` passes
- Related workflows have been manually verified
- Documentation is updated

---

# 63. Golden Rules for Agents

1. Read `AGENTS.md` before making changes.
2. Inspect existing code before modifying it.
3. Do not overwrite working features unnecessarily.
4. Follow the defined architecture.
5. Keep business logic out of templates.
6. Do not duplicate business rules in multiple views.
7. Prefer reusable services/helpers for complex calculations.
8. Keep financial operations transactional.
9. Keep academic history immutable.
10. Never expose unauthorized student data.
11. Never rely on frontend hiding for security.
12. Test grading, aggregate and division calculations.
13. Test guardian report restrictions.
14. Test promotion history.
15. Use `DecimalField` for money.
16. Do not hard-code classes, subjects, fees or grading rules.
17. Use migrations for database changes.
18. Do not manually edit production databases.
19. Keep commits focused.
20. Run checks and tests after meaningful changes.
21. Update documentation when architecture or requirements change.
22. Prefer the simplest Django-native solution.
23. Do not add dependencies without a clear reason.
24. Preserve historical reports and financial records.
25. Treat student, guardian and financial data as sensitive.
