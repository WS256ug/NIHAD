# NIHAD School Management

A Django school management system being built in the verified phases defined in
[AGENTS.md](AGENTS.md). Phases 1–4 provide accounts, school configuration,
student/guardian records and enrollment history.
The guide was originally named `AGENTS(1).md` and is now named `AGENTS.md`.

## Stack

- Python 3.12+, Django 5.2
- SQLite for development; PostgreSQL for production
- Django templates, locally served Oat UI 0.8.0 and HTMX 2.0.10
- Django authentication, forms, ORM, migrations and admin

## Run locally on Windows

The current workspace already has `.venv`, installed dependencies, a generated
local `.env`, and a migrated SQLite database. Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in with the account you created. Administration
is at http://127.0.0.1:8000/admin/ for Super Admins. The account-management portal
is at http://127.0.0.1:8000/accounts/users/. No default passwords or accounts are seeded.

If PowerShell blocks activation, use the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

VS Code is configured to select `.venv/Scripts/python.exe`. All Python commands
and dependency installations should run inside this environment.

## Fresh checkout

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from secrets import token_urlsafe; print(token_urlsafe(64))"
```

Paste the generated value into `DJANGO_SECRET_KEY` in `.env`, then run:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

On macOS/Linux use `python3 -m venv .venv` and `source .venv/bin/activate`, then the
same `python -m pip` and `python manage.py` commands. Set environment values in
`.env` or in the process environment; process environment values take precedence.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pip check
```

The 123 tests cover all six roles, login/logout, role access and navigation,
account creation/editing/deactivation, privilege escalation attempts, CSRF,
password changes, reset expiry/reuse, session invalidation, HTMX responses,
database constraints, environment settings and school configuration rules. Tests
use a separate test database. School tests include period/date consistency, parent
relationships, activation, audit rollback and protected configuration routes.
Student tests cover permanent IDs, guardian registration/linking, enrollment
history, private photos, date and uniqueness constraints, role boundaries and CSRF.

## School setup

Sign in as a School Admin or Super Admin and open **School setup**, or visit
http://127.0.0.1:8000/school/.

1. Save the school profile, contact details and currency code (default: UGX).
2. Add sections, then classes within each section. Add streams only where needed.
3. Add academic years and terms with the school's actual names and dates.
4. Select the current academic year and, optionally, its current term.

No sections, classes or periods are hard-coded or seeded automatically. A class
may have no streams. Ranking and fee-clearance preferences are saved now for use
when reports and the guardian portal are implemented.

Years cannot overlap, and terms must fit inside their year without overlapping
other terms in that year. Date boundaries are inclusive. Terms are ordered by
start date within each year, without a separate sequence field. Term names
are unique within their year; section, class and stream names are unique within
their parent. A year cannot be shortened past an existing term.

Parent relationships remain fixed after creation to preserve history. Use a new
record to represent a different parent. Deactivate children before their parent,
and switch or clear the current period before deactivating a current year/term.
Reactivation requires active parents. Existing records are preserved.

The current year and term are stored together on the school profile. Configuration
writes are validated, transactional and audited. Django admin provides a read-only
view; use the School setup pages to make changes. The application supports one school.

## Students, guardians and enrollment

Open http://127.0.0.1:8000/students/ as School Admin or Super Admin. Headteachers
can search and view student profiles/history but cannot change records. Teacher,
Bursar and Guardian access will be added through their scoped domain modules.

1. Complete school configuration, including an active year and class.
2. Choose **Register student**. The permanent ID is generated, starting at
   `STD-000001`; an optional separate admission number must be unique.
3. Open **Guardians** and register an account/profile, or select **Use existing
   account** for an ordinary active Guardian account. Edit names and email through
   Accounts; phone/address are maintained on the guardian profile.
4. On the student profile, choose **Link a guardian**. A guardian can have multiple
   children and a student can have multiple guardians, with one active primary
   guardian. Deactivating a link preserves the relationship and clears its primary
   and emergency-contact flags. Account deactivation separately disables sign-in.
5. Choose **Add enrollment** and select the year, class and optional stream.
   The section is derived from the class. Use a completed status and completion
   date when entering past enrollment; referenced configuration must be active.
6. Close an enrollment before entering a later placement in the same year. Its
   dates cannot overlap the previous placement (both endpoints are inclusive).
   New years get new records; previous placements are preserved. Batch promotion
   is a later phase. A current enrollment means open in its year, and the profile
   separately identifies the school's selected current year.

Enrollment identity, dates of entry and academic context cannot be reassigned;
closed records cannot be reopened or overwritten. Close all current enrollments
before marking a student transferred, withdrawn, graduated or inactive. A year
cannot be shortened past enrollment dates, and configuration with current
enrollments cannot be deactivated. There are no student or enrollment delete actions.

Search accepts names, student IDs and admission numbers. Year, section, class and
stream filters include past enrollment and must match the same enrollment record.

Optional student photos accept JPEG, PNG and WebP up to 5 MB and 16 million pixels.
Pillow re-encodes them as JPEG without original metadata. They are stored under
ignored `private_media/`, outside public `/media/`, and served only through the
authorized student-photo route. Keep this directory private and include it in
encrypted backups; never configure a public web-server alias for it. Deployment
must enforce upload request limits as well. Replacement/removal cleans the prior
file after the database commit; failed writes clean the new file.

## Accounts and roles

After signing in, each user is redirected to their role workspace. A safe local
`next` destination is preserved, and the destination still checks authorization.
Users can view their own account and change their password from **My account**.

| Role | Account administration |
| --- | --- |
| Super Admin | Manage ordinary accounts and School Admins; use Django admin for privileged accounts |
| School Admin | Create/edit/activate/deactivate ordinary Headteacher, Teacher, Bursar and Guardian accounts |
| Headteacher, Teacher, Bursar, Guardian | Own profile and password only |

School Admins cannot manage themselves, other School Admins, Super Admins, or
accounts with staff status, groups or explicit Django permissions. Portal forms
cannot grant staff/superuser flags, groups or Django permissions. Django admin is
restricted to active Super Admins, including its user/group permission editors.
New Super Admins can be created with `createsuperuser`; an existing Super Admin
can also assign the matching role, staff and superuser flags together in admin.

Account creation, edits and status changes are recorded in Django admin's log.
Deactivate accounts to remove access while retaining records. Domain permission
checks for students are implemented; teaching-assignment and finance scopes follow
with those modules. Accounts with guardian profiles retain the Guardian role to
preserve their relationships. The current project represents one school.

## Password recovery

**Forgot your password?** uses Django's reset tokens. Links expire in one hour and
are single use. Unknown, inactive or unusable-password accounts receive the same
public confirmation, without sending a reset email. An account needs an email
address for recovery; portal account forms require one. Accounts without an email
can be updated by an authorized administrator.

In development, reset emails appear in the `runserver` console. When the server is
started in the background by the development agent, they appear in the ignored
`artifacts/server.stdout.log`. These links contain private recovery tokens.

In production, set `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` and `EMAIL_USE_SSL` in the
environment. Use either TLS or SSL, not both. SMTP delivery requires a configured
mail service; tests use Django's in-memory email backend and send no external mail.

Changing a password preserves the current session and invalidates other sessions.
Resetting a password requires signing in again with the new password.

## Production configuration

Select `config.settings.production` with the **process** environment variable
`DJANGO_SETTINGS_MODULE`, or pass `--settings=config.settings.production` to
management commands. WSGI and ASGI default to production; `manage.py` defaults to
development. Do not select settings through `.env`, which loads after selection.

Production requires a strong `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`,
and `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`.
Configure `POSTGRES_PORT`, `POSTGRES_SSLMODE` and HTTPS
`DJANGO_CSRF_TRUSTED_ORIGINS` for the actual deployment.

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.production'
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
```

Production enforces HTTPS, secure cookies and HSTS. Configure an application
server, TLS, static file serving from `staticfiles/`, protected media delivery,
logging, backups and the trusted proxy boundary during Phase 15. Proxy headers
are deliberately not trusted without deployment-specific configuration.

PostgreSQL settings are present and checked without opening a connection. A live
PostgreSQL server and deployment have not been provisioned or tested. SQLite data
does not automatically transfer when switching settings. Sensitive uploaded files
must use authorized download views when their modules are added.

## Current scope

Accounts, password management, role workspaces, school configuration, student and
guardian records, enrollment history and role-based navigation are available.
Teachers/subjects, assessments, reports, finance, the guardian portal, batch
promotion and populated domain dashboards follow in subsequent phases.
There is no public registration.

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for progress and
[FEATURES.md](FEATURES.md) for implemented and planned functionality.
