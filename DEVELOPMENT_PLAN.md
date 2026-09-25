# Development plan

Action links across school, academic, student, account, report and finance pages
use compact Oat outline buttons. Navigation and record-name links stay as links;
table actions wrap to fit narrow screens.

Shared footer stays at the bottom of short pages and follows content on longer
pages without covering forms or tables. It remains hidden in printed reports.

Sidebar refined to 220px wide, with only a centered 80px school logo in the
gold header. The logo link retains an accessible school-name label.

The sidebar logo header uses the logo-inspired golden yellow with dark text
and a circular white logo image above the burgundy navigation.

Visual theme refinement: burgundy sidebar with white text and gold active-link
indicator, white logo panel, warm cream page background, solid primary quick
action and category-colored stat icons/borders (school, academics, finance).

Dashboard refinement: wider content, compact cards grouped into School overview,
Academic tasks and Finance, role-specific quick actions, and an actionable
academic-period setup notice. Repeated Live badges and the duplicate role badge
were removed; figures continue to update on page load.

NIHAD theme: Oat color tokens in static/css/app.css define deep red primary
controls, gold accents, white cards and warm neutral backgrounds. Custom
components share these tokens; success and error states retain semantic colors.

The supplied Nihad school logo is stored locally in static/img/nihad-logo.jpg
and used in the sidebar, sign-in header and browser tab.

All staff roles use Dashboard as their sidebar link and page title. Role-specific
content and the role shown beside the sidebar account name remain unchanged.

Reusable avatars identify the signed-in account and students in lists/profiles.
Student photos use existing authorized image routes; initials are shown when
no photo is available. No external avatar service is used.

Mobile navigation uses an accessible SVG hamburger button with a 44-pixel
touch target, theme colors, visible keyboard focus and wrapping school names.
The sidebar has no close button; tapping outside it or pressing Escape closes it.

Personal account information is accessed by clicking the user's name in the
sidebar footer; the separate My account navigation item has been removed.

Reports and Promotions are nested under the collapsible Academics sidebar menu,
alongside Overview. The menu opens on academic, report and promotion pages;
Promotions remains visible only to roles authorized to manage promotions.

Sidebar organization: Guardians is nested in the collapsible Students menu.
A single Finance link opens the financial overview, which links to fees,
expenses, other income and expense categories. Existing role permissions apply.

Dashboard grid correction: removed Oat's `col-3` span from stat cards because
the dashboard already defines its own four-column grid. Cards now occupy one
track each, with two-column tablet and single-column phone layouts.

Dashboard statistics use responsive Oat UI cards with live values, badges and
detail links. Published report averages include a percentage progress bar;
counts and financial totals do not imply unrecorded targets or monthly trends.

Signed-in navigation now uses the local Oat UI sidebar component, with role-scoped
links, active-page highlighting, POST sign-out, a mobile menu toggle and Escape
to close. Sidebar navigation is excluded from printed reports. The 30 account
and dashboard tests pass after this layout change.

UI correction: the shared request-error banner now stays hidden until an HTMX
failure. An application CSS rule overrides Oat's alert display styling when the
banner has the `hidden` attribute.

Guardian registration refinement: capture an optional National Identification
Number (NIN) when registering a student or adding a guardian contact. Authorized
staff can view and update it on the guardian profile; existing records may remain blank.

Follow the detailed sequence in AGENTS.md section 54. Verify each phase before
starting the next. Always use `.venv` for Python and dependency commands.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Project foundation, custom user, settings, base layout | Complete |
| 2 | Accounts, password management, permission helpers, role navigation | Complete |
| 3 | School profile, sections, years, terms, classes and streams | Complete |
| 4 | Students, guardians, enrollment and history | Complete |
| 5 | Teachers, subjects and allocations | Complete |
| 6 | Assessments and marks | Complete |
| 7 | Configurable grading, aggregates and divisions | Complete |
| 8 | Reports, review, publication and PDF/print | Complete |
| 9 | Fees, payments, balances and receipts | Complete |
| 10 | Independent Guardian accounts, family portal and report-access policy | In progress |
| 11 | Expenses and financial summaries | Planned |
| 12 | Promotion and preserved enrollment history | Planned |
| 13 | Role dashboards | Planned |
| 14 | Security review | Planned |
| 15 | Production preparation | Planned |

## Phase 1 deliverables

- Repository and canonical AGENTS.md
- Python virtual environment and pinned dependencies
- Separate base, development (SQLite) and production (PostgreSQL) settings
- Ignored local `.env`, random local secret, and documented `.env.example`
- Custom user model installed in the initial migration
- Six stored role values, password hashing and Django custom-user administration
- Responsive Oat UI base layout and HTMX sign-in with ordinary form fallback
- Protected workspace and CSRF-protected POST logout
- Static/media configuration and local vendor assets with licenses
- Authentication and configuration tests

## Phase 1 verification

- 21 automated tests pass on SQLite.
- Django system check, migration drift check and dependency check pass.
- Production deployment checks and manifest static collection pass with temporary
  configuration values, without connecting to a PostgreSQL database.
- Local server responds to the sign-in page and all frontend assets.
- Live HTTP checks pass for HTMX and ordinary sign-in, the protected workspace,
  admin pages and POST sign-out. The temporary verification account was removed.
- No connected browser was available; visual desktop/mobile verification remains
  outstanding. A live PostgreSQL integration check remains part of deployment work.

## Phase 2 deliverables and verification

- Six protected role workspaces, login redirects and role-specific navigation.
- Shared role checks, route decorators and scoped account querysets.
- Account list, search, role filter, pagination, creation and editing.
- Confirmed activation/deactivation, with no account deletion in the portal.
- School Admins manage ordinary Headteacher, Teacher, Bursar and Guardian accounts.
- Super Admins additionally provision School Admins; privileged accounts and
  Django permission editing are restricted to Super Admins in Django admin.
- Profile display, password change and email-token password recovery.
- Password reset tokens expire after one hour and cannot be reused.
- Database constraint and form validation keep Super Admin role, superuser and
  staff flags consistent.
- Account mutations create Django admin audit entries inside the same transaction.
- Development reset mail stays in the server console; production SMTP is configurable.
- All 48 tests pass, including the cross-role access matrix, forged privileges,
  scoped targets, CSRF, password validation, token expiry and session invalidation.
- Django system, migration drift and dependency checks pass.
- Migration 0002 is applied to local SQLite. Production deployment checks and
  static collection pass with temporary configuration values.
- Live HTTP checks pass for all six roles, account creation/editing/status changes,
  password changes, password reset and rejected token reuse. Temporary test
  accounts were removed, and the development server serves the updated routes.
- Browser visual checks and live PostgreSQL/SMTP integration remain outstanding.

## Phase 3 deliverables and verification

- School profile with contact details, currency, ranking preference and the future
  guardian report-access policy; the configured school name appears in the portal.
- Configurable sections, academic years, terms, classes and optional streams.
- Searchable, paginated lists and creation/editing/status confirmation forms.
- School Admin and Super Admin access checks on every configuration route.
- One current year and optional term, saved together on the single school profile.
- HTMX term choices restricted to the selected active academic year.
- Valid date ranges, non-overlapping periods, scoped unique names and date-based term ordering.
- Parent relationships cannot be reassigned after creation. Referenced parents
  use protected foreign keys; configuration is deactivated instead of deleted.
- Active children and current periods prevent invalid parent deactivation.
- Transactional writes, audit fields and Django admin log entries; Django admin
  displays configuration read-only so edits use the validated portal.
- Both school migrations are applied to local SQLite.
- All 79 tests pass across Phases 1–3; system, migration and dependency checks pass.
- Live HTTP checks passed against an isolated SQLite database for first-time setup,
  record creation, current-period changes, date protection, activation, HTMX
  search and role restrictions. No sample school data was added to development.
- Production configuration and static collection checks pass. Browser visual
  checks and live PostgreSQL/SMTP integration remain outstanding.

## Phase 4 deliverables and verification

- Student registration, permanent sequential IDs, profiles, admission numbers,
  status changes and protected photos. Pillow validates and re-encodes uploads.
- Guardian account/profile registration and reuse of existing Guardian accounts.
- Multiple student/guardian links, relationship and emergency-contact details,
  one active primary guardian per student, and confirmed link deactivation.
- Enrollment by academic year, section, class and optional stream; historical
  entries, one current enrollment per student/year, and explicit closure.
- Enrollment context is immutable. Closed records cannot be reopened or changed.
  Dates must fit the year, follow admission and not overlap within the same year.
- Search, history-aware section/year/class/stream filters, pagination and HTMX
  stream choices with ordinary form fallback.
- School Admin/Super Admin management and Headteacher read-only student access.
  Teacher, Bursar and Guardian student access awaits the corresponding scoped modules.
- Transactions, audit entries, protected relationships and read-only Django admin.
  School date/status changes cannot invalidate enrollment history.
- The student migration is applied to development SQLite. All 123 tests pass;
  system, migration-drift and dependency checks pass.
- Production deployment checks and manifest static collection pass with temporary
  configuration values, without connecting to a live PostgreSQL database.
- Live HTTP checks passed against an isolated database for sign-in, registration,
  guardian linking, enrollment, overlap rejection, preserved history, HTMX and
  role restrictions. Verification data was cleared from that isolated database.
- No browser was connected; visual desktop/mobile checks remain pending. Live
  PostgreSQL concurrency and SMTP checks remain part of deployment verification.

## Term ordering refinement

- Removed the Sequence form field, database column and sequence constraints.
- Terms are ordered by start date within each academic year, including current-period choices.
- Names, dates, active status and current-period relationships are retained.
- Migration `schools.0003_terms_order_by_start_date` is applied to development SQLite.
- Creation, date editing, list order and HTMX term choices are covered by the test suite.

## Next phase

Phase 5 adds teacher profiles/accounts, configurable subjects, teaching assignments,
class-teacher assignments and assignment validation. Test authorization against
the student's enrollment context before granting teachers access to student records.

## Approved scope revision and remaining work

The user requested completion of all remaining phases. Guardian contacts are
captured during student registration; guardians no longer have separate accounts.
The student portal uses the permanent student registration number and a password.
Existing guardian contact data is migrated before old logins are retired. Portal
passwords are issued/reset by administrators and must be changed on first use.

Work proceeds through teacher/subject assignments, assessments and marks, grading,
report review/publication/PDF, fee charges/payments/receipts, portal fee/report
access, expenses, promotion, dashboards, security and production preparation.
Each milestone is verified before proceeding; deployment credentials and external
infrastructure are not assumed to exist.

## Phases 5–6 verification

Teacher profiles, subjects, teaching and class-teacher assignments are implemented.
Teachers see assigned students and enrollment history. Assessment types, class/stream
assessments, open/close controls, and audited marks entry enforce assignment scope,
score limits and revision checks. All 151 tests passed after Phase 6; migrations are
applied to development SQLite.

## Latest role clarification

The user subsequently specified individual accounts for Super Admin, School Admin,
Headteacher, Teacher, Bursar/Finance and Guardian. This supersedes the earlier
removal of independent Guardian logins. Guardian contacts remain part of student
registration, with account provisioning/linking from the guardian profile. Existing
student-number portal access remains separately supported.

## Phases 7–9 verification

Configurable numeric/descriptive grading, grade boundaries, required/best-N/all
aggregates, divisions and optional tied ranking are implemented. Used grading is
protected. Reports support immutable snapshots, class-teacher comments, headteacher
review, approval, publication and versioned correction. HTML/print and PDF access
share server checks; a rendered sample PDF was visually verified. All 168 tests
passed after Phase 8. Phase 9 adds fee templates, immutable student charges, Decimal
payments, idempotent submission, receipts, statements, outstanding balances and
explicit payment/charge reversals; its ten targeted tests pass.

## Student religion field

- Replaced student address with optional free-text religion (up to 100 characters)
  in registration, editing and profiles; guardian addresses remain unchanged.
- Migration students.0005 removes student address and adds religion; applied locally.
- All 214 tests pass; Django system and migration-drift checks pass.
- Next milestone: continue the remaining planned application phases.

## Student gender and address label refinement

- Student gender now requires Male or Female, enforced by forms and a database
  constraint, without an automatic default. Existing local records already comply.
- Guardian contact forms label the address field simply Address.
- Migration students.0006 applied; all 214 tests, system checks and migration-drift
  checks pass. Next milestone: continue the remaining planned application phases.

## Action link styling

- Applied Oat button, outline and small classes to action links across the workspace,
  including account creation, editing, marks, fees, reports and account recovery.
- Added the required button class: role="button" alone does not activate Oat styling.
- All 214 tests and Django system checks pass; template audit confirms consistent
  classes on button links. Next milestone: desktop/mobile visual verification.

## Visible checkbox controls

- Shared form checkboxes use explicit 20px controls beside clickable labels, with
  keyboard focus outlines on the checkbox. No surrounding border or highlight.
- Excluded checkboxes/radios from text-input styling that hid checked backgrounds
  and collapsed checkbox widths. This includes the emergency-contact control.
- All 214 tests and Django system checks pass. Next milestone: browser visual QA.

## Back navigation styling

- Standardized 22 back links with a shared decorative arrow, quiet text styling,
  44px minimum click target, hover feedback and visible keyboard focus.
- Refined after screenshot feedback: removed the box, softened the text color,
  added heading spacing and removed the repeated School setup eyebrow on lists.
- Kept native link semantics and explicit destinations; back links are hidden
  when printing and long labels wrap on narrow screens.
- All 214 tests, Django system checks and migration-drift checks pass.
- Next milestone: desktop/mobile browser visual QA.

## School setup form dialogs

- Added native Oat-styled dialogs with HTMX loading and saving for section,
  academic year, term, class and stream create/edit actions.
- Reused Django forms, authorization, CSRF checks and transactional services.
  Validation preserves input; saving refreshes the current filtered/paginated list.
- Added loading/error feedback, duplicate-submit prevention, focus management,
  unsaved-change confirmation and mobile-sized scrollable dialogs. Full-page
  form links remain available as a fallback.
- All 218 tests pass, including four new dialog tests; system checks,
  migration-drift checks and JavaScript syntax checks pass.
- Next milestone: desktop/mobile interactive browser QA. No browser connection
  was available during implementation.

## Direct school setup popup follow-up

- Create/edit links now declare their HTMX dialog target directly. The request
  handler opens the dialog immediately while the form loads, without navigating.
- Versioned the application script URL to refresh previously cached handlers.
- Added coverage for the Create academic year link and a JavaScript regression
  test for popup opening, repeated requests and preserving entered form data.
- All 219 Django tests and the JavaScript regression test pass; system,
  migration-drift and JavaScript syntax checks pass.
- Next milestone: browser click-through verification; no browser is connected.

## Dialog error visibility fix

- Extended the existing Oat alert visibility override to dialog error messages:
  hidden alerts stay hidden until a request fails. Versioned the stylesheet URL
  so refreshing the page loads the correction.
- All 219 Django tests, the JavaScript regression test and system checks pass.
- Next milestone: browser visual verification of dialog loading and error states.

## Remaining workspace forms in dialogs

- Extended the shared dialog to account management/password changes, school
  profile/current period/status, student registration/editing, guardian access
  and links, enrollment, academic configuration, marks, report actions, fee
  structures/charges/payments/reversals, expenses and promotions.
- Shared template context and success responses reuse existing forms, service
  transactions and permissions. Multipart requests preserve photo upload support.
  Confirmations retain record names; form errors stay inside the dialog.
- Saving refreshes the workspace with its existing query filters and provides a
  saved-result link. Promotion creation and decisions continue inside the dialog.
  Dashboard form shortcuts use the same behavior; direct URLs remain available.
- Long forms and decision tables get wider responsive dialogs; closing protects
  unsaved input and loading/error feedback is shared across forms.
- All 228 Django tests and four JavaScript tests pass. System, migration-drift
  and JavaScript syntax checks pass.
- Next milestone: interactive desktop/mobile browser verification, unavailable
  in this session because no browser is connected.


## Simplified section grades

- Removed scheme management from the workspace and scheme selection from
  assessments. Grades and divisions now use section selectors. Legacy scheme
  list/form links redirect to Grades.
- Added automatic internal versions and readiness checking. Transactions preserve
  historical grades, division rules and existing aggregation policies.
- Assessments can be created with incomplete grading; ready grades are selected
  automatically for unconfigured assessments. Reports still require ready grades.
- Removed the section status messages and explanatory paragraph per screenshot.
- Verification: all 237 Django tests and four JavaScript tests pass, along with
  system and migration-drift checks. No database migration required.
  Next milestone: browser verification of simplified
  grade entry and assessment creation.


## Whole-class marks workflow

- Completed editable subject/stream sheets, partial saves, complete submission,
  reviewer approval/return, explicit absence, saved grades and progress counts.
- Added keyboard navigation, unsaved-change protection, duplicate-submit guard,
  roster/revision checks, atomic saves, and audit records.
- New assessments require approved current sheets before closing/report creation.
  Historical assessments and report snapshots remain compatible; report
  correction returns sheets for editing and renewed approval.
- Added reviewer dashboard tasks, Marks entry navigation, read-only submission
  administration, and reviewed sheets in the demo seed workflow.
- Applied academics.0004 locally. All 254 Django tests and seven JavaScript
  interaction tests pass, along with system and migration-drift checks.
- Next milestone: desktop/mobile browser verification of marks entry and review;
  no browser is connected in this session.

## Marks subject selection follow-up

- Confirmed the current assessment has only an eligible English assignment.
- Marks sheets now explain missing subject assignments and link administrators to teaching assignments; teacher permissions remain enforced.
- Explicit sheet selection takes precedence over legacy subject URL filters.
- Verification: all 18 marks-sheet tests and Django system checks pass.
- Next milestone: configure the remaining subject assignments and verify the workflow in a browser.

## Simplified close-marks confirmation

- Removed the checkbox from closing marks; the confirmation names the assessment and explains that all subjects will be locked.
- Replaced Save changes with Close marks entry. The marks-page action appears only when every eligible subject sheet is approved and current.
- Direct close requests also check sheet readiness; cancellation and dialog responses are preserved.
- Targeted marks-sheet tests (19) and Django system checks pass. Next milestone: browser verification of the confirmation.
- Final verification: all 256 Django tests pass; system, migration-drift and diff checks pass.

## Assessment action placement

- Moved the marks link from the record name to Actions beside Edit. Open assessments offer Enter marks to admins/teachers; other states and reviewers show View marks.
- Teachers and headteachers retain the Actions column without gaining editing controls.
- Verification: 10 assessment tests and Django system checks pass. Next milestone: visual browser verification.

## Whole-number grade ranges

- Validation and calculation now share effective boundaries for consecutive integer bands, preserving shared-boundary grading and rejecting real gaps/overlaps.
- Report generation refreshes readiness for previously rejected, unused integer-band configurations with an audit entry. Existing report snapshots are preserved.
- Updated field help and checked the saved Primary ranges at decimal boundaries. Next milestone: retry report generation in the workspace.
- Verification: all 257 Django tests pass; system and migration-drift checks pass. No schema migration required.

## Clear stale sign-in feedback

- Request errors can be dismissed and clear when sign-in fields are edited or another request starts. Removed the unsupported connection diagnosis from the banner.
- Refreshed static asset versions so browsers fetch the update. Django checks and seven JavaScript tests pass.
- Next milestone: browser verification of sign-in feedback.

## Guardian contacts without separate accounts

- Kept contact details and student links; guardian profiles now direct staff to student portal access.
- Disabled guardian sign-in, existing guardian sessions, provisioning endpoints/services and role selection by default. Historical users and links are retained; opt-in legacy behavior remains tested.
- Demo seeding follows the contact-only default. Updated current requirements in AGENTS.md and product/schema/user documentation.
- Verification: all 259 Django tests pass, with system and migration-drift checks clean. No data deletion or schema migration required.
- Next milestone: browser verification of registration, contact editing and student portal sign-in.

## Report number display

- HTML, print and PDF reports remove trailing decimal zeros from scores, totals, averages and maximum scores, without rounding or changing stored snapshots.
- Verified 80.00 to 80, 80.50 to 80.5, fractional precision, zero and absent values. All nine report tests and Django checks pass.
- Next milestone: visual report verification in the browser.

## Sign-in school logo

- Replaced the welcome panel's promotional text and school illustration with the existing school logo, centered and scaled responsively.
- Updated static asset versions. Django system checks pass. Next milestone: visual browser verification of desktop/mobile sign-in.

## Transparent school logo

- Added a transparent PNG of the school logo and updated sign-in, header/sidebar and favicon references.
- Verified an RGBA alpha channel with transparent pixels; Django system checks pass. Original JPEG retained.
- Next milestone: visual browser verification against the sign-in background.

## Consistent login pages

- Staff and student login now share the transparent school-logo panel and responsive two-column layout.
- Login views suppress desktop and mobile navigation; the normal workspace layout is unchanged.
- Preserved student registration-number fields, validation, HTMX form targets and staff/student switching links.
- Verified both login responses render the shared layout without navigation; Django checks pass. Next milestone: desktop/mobile browser review.

## Superuser configuration administration

- Removed Administration navigation and dashboard shortcut from the user workspace. Django admin remains available directly at /admin/.
- Enabled audited superuser create/update operations for school structure, subjects, assessment types and guardian contact details. Model validation still runs.
- Delete is limited to unused configuration; school deletion and records with dependencies are blocked. Workflow/financial/history models remain read-only. Guardian account links cannot be edited here.
- Added tests for real admin create/update/delete, audit ownership and protected permissions. Next milestone: browser verification of admin forms.


## Full superuser CRUD administration

- Enabled active superusers to create, view, update and delete all registered domain records at `/admin/`, including financial and historical records, as requested. Bulk deletion uses Django's confirmation and audit logging.
- Superuser admin corrections may change previously immutable fields; ordinary workspace services retain their existing history and financial restrictions. Field validation, database constraints, protected relationships and the single-school rule still apply.
- Admin student creation allocates unique registration numbers transactionally; assignment sections and new expense/income metadata are populated automatically. Guardian account provisioning stays disabled and student photos remain managed through the student workspace.
- Verification: all 263 Django tests pass, including actual financial CRUD, student number allocation and superuser/non-superuser permissions. Django system and migration-drift checks pass.
- Next milestone: browser verification of the expanded admin forms and correction workflows.


## Optional marks review, generated references and forward promotions

- Marks review is off by default and disabled for existing assessments by migration 0005. Administrators can enable Require marks review when editing an assessment. Saving marks no longer enables review automatically; disabled review hides submission/review actions and rejects forged review requests. Completed sheets can close and generate reports without approval while review is off.
- Payment recording generates sequential PAY-year-number references transactionally alongside receipts. References are no longer entered on the payment form; repeated requests return the same payment/reference.
- Promotion destination choices include only later active academic years and higher configured classes. Section order followed by class order defines progression, with form/model/service enforcement. Repetition continues in the source class in a later year. Dependent choices refresh inside both full-page and dialog forms.
- Configured the existing local PRIMARY ONE and PRIMARY TWO class orders as 1 and 2; both were previously 0.
- Numeric inputs, financial displays and report/receipt output trim unnecessary decimal zeros without changing stored Decimal values or removing fractional precision.
- Applied the review-default migration locally. Browser verification could not run because no browser is connected; automated tests cover form refresh responses and preserved dialog submission attributes.
- Next milestone: browser verification of promotion dropdown changes and the optional review checkbox when a browser is connected.
- Final verification: all 270 Django tests pass; system checks, migration-drift check and diff check pass.


## Student religion choices

- Religion now uses an optional dropdown with Moslem, Christian and Other in registration, editing and Django admin. Django model/form validation rejects values outside these choices.
- Applied migration 0007 locally: normalized Islam/Muslim/Moslem to Moslem, Christian/Christianity to Christian, other nonblank values to Other, and preserved blanks.
- Verified registration/edit/profile coverage and choice validation; system and migration-drift checks pass.
- Next milestone: continue student profile refinements as requested.
- Final verification: all 271 Django tests pass.


## Guardian-only contact details

- Removed Student.contact_phone from the model, registration/edit forms and student profile. Guardian phone/email fields and linked guardian contact displays remain available.
- Applied migration 0008 locally to remove the student contact column. Updated registration coverage to verify that guardian phone remains and student contact phone is absent.
- System and migration-drift checks pass. Next milestone: continue student registration refinements as requested.
- Final verification: all 271 Django tests pass; diff check is clean.


## NBS registration numbers for new students

- New registrations through the student workspace and Django admin now use NBS-0001 format with a minimum of four digits; numbers naturally expand after 9999.
- Kept the existing transactional counter, existing student numbers, portal usernames and historical records unchanged. No schema or data migration is needed.
- Updated registration and admin tests to verify the NBS format and continued numbering alongside legacy STD records.
- Next milestone: continue registration refinements as requested.
- Verification: all 271 Django tests pass; system, migration-drift and diff checks pass.


## Promotion decision terminology and probation

- The promotion decision dropdown now offers Promoted, Promoted On Probation and Try Again.
- Both promotion outcomes advance to a higher class in a later academic year. Try Again repeats the source class/stream in that later year.
- Probation is stored as a distinct promotion decision and included in the historical snapshot; student and completed source enrollment status remain Promoted. Legacy transfer, withdrawal and graduation decisions remain readable and preserved.
- Updated draft preview and batch instructions. Applied promotions migration 0002 locally; system and migration-drift checks pass.
- Next milestone: continue promotion workflow refinements as requested.
- Final verification: all 273 Django tests pass, including probation advancement and exact dropdown choices; diff check passes.
