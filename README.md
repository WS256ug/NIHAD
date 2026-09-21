# NIHAD School Management

A Django school management system being built in the verified phases defined in
[AGENTS.md](AGENTS.md). Phases 1 and 2 provide the project foundation and accounts.
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

The 48 tests cover all six roles, login/logout, role access and navigation,
account creation/editing/deactivation, privilege escalation attempts, CSRF,
password changes, reset expiry/reuse, session invalidation, HTMX responses,
database constraints and environment settings. Tests use a separate test database.

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
checks for students, teaching assignments and finance will be added with those
modules; the current project represents one school.

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

Accounts, password management, role workspaces and role-based navigation are
available. School records, students, assessments, reports, finance and populated
domain dashboards follow in subsequent phases. There is no public registration.

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for progress and
[FEATURES.md](FEATURES.md) for implemented and planned functionality.
