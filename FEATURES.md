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

Phase 3 starts school configuration. Subsequent phases add
students/guardians, enrollment history, teachers/subjects,
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
