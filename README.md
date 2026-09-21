# NIHAD School Management

A Django school management system being built in the verified phases defined in
[AGENTS.md](AGENTS.md). Phase 1 provides the project and authentication foundation.
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
is at http://127.0.0.1:8000/admin/. No default passwords or accounts are seeded.

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

Tests cover all six role values, password hashing, login/logout, inactive users,
CSRF protection, safe redirects, HTMX responses, admin access, database role
constraints, and environment-specific settings. Tests use a separate test database.

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

Sign-in, POST sign-out, a protected personal workspace, and custom-user admin are
available. Role names are stored; they do not automatically grant Django staff or
superuser permissions. Domain permissions, password management, school records,
students, assessment, reports and finance follow in subsequent phases. There is
no public registration or password reset workflow yet.

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for progress and
[FEATURES.md](FEATURES.md) for implemented and planned functionality.
