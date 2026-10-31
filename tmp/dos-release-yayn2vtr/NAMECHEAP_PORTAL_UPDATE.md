# Namecheap fees and student portal update — 2026-10-04

This is an incremental update for the existing school application, not a fresh installation. Install it on the same code baseline that already has Islamic Studies, report grading keys, and report watermarks. If the server is older, reconcile its code and migrations before installing this patch.

## Included changes

- Audited individual fee agreements and reversals, with net balances used for payment limits and report clearance.
- Student statements show Charged, Paid and Balance; original fees and concession details remain staff-only.
- Fees and payments and Reports sidebar links; portal home shows summaries.
- Published reports listed by academic period, with View and supported Print/PDF actions, fee-clearance messages and no internal revision details.
- Finance migration `0003_feeconcession_concessionreversal_and_more`, plus the updated regression tests.

The archive contains files relative to the application root (the directory containing `manage.py`). `UPDATE_MANIFEST.sha256` lists checksums. No environment files, databases, uploaded media, virtual environments, or Passenger configuration are included. No dependency or static-asset changes are required.

## Installation

1. Schedule a short maintenance window. Back up the production database and the current application files outside the public web directory. Pause use of the application until the update is complete.
2. Upload `namecheap-portal-fees-update-20261004.zip` to the application root. Extract there, overwriting the matching files while preserving directories. Do not replace `.env`, media, the virtual environment, or the existing Passenger startup file.
3. In cPanel's Python application setup, copy the activation command for this application's existing virtual environment. Run that command in Terminal, then change to the application root. Use that environment's Python for every command below. Confirm the existing production environment variables are loaded.
4. Inspect the migration state and planned changes:

   ```sh
   python manage.py showmigrations finance --settings=config.settings.production
   python manage.py migrate --plan --settings=config.settings.production
   ```

   Finance migrations 0001 and 0002 should already be applied; the new pending finance migration is 0003. If other migrations are pending, confirm that their matching application code is installed before proceeding. Do not fake migrations.

5. Apply and verify:

   ```sh
   python manage.py migrate --noinput --settings=config.settings.production
   python manage.py check --database default --settings=config.settings.production
   python manage.py check --deploy --settings=config.settings.production
   python manage.py showmigrations finance --settings=config.settings.production
   ```

   Confirm finance 0003 is marked `[X]`. If a command fails, keep the application in maintenance and resolve it before restarting. No `collectstatic` is needed for this package because it does not change static files.

6. Restart the existing application using its cPanel Python application controls, then end maintenance after verification. Remove the uploaded ZIP and deployment manifest from the server when finished.

## Verify after restarting

- Sign in as a student. Sidebar contains Fees and payments and Reports. Home cards are summaries.
- Open the fee statement: Charged, Paid, Balance, payments and receipts appear; original/agreed fee labels and concession history do not.
- Open Reports: only that student's published reports appear, newest periods first. Online-only reports offer View; printable reports also offer Print and Download PDF.
- A student with outstanding fees sees the balance and a fees link. Direct HTML/print/PDF report requests remain denied until clearance.
- Staff can open a fee statement and Set agreed fee. For an authorized agreement of 600,000 against an 800,000 charge, Charged becomes 600,000; after 600,000 is paid the charge is cleared. Other outstanding charges still prevent report clearance under the existing overall-balance policy.
- Confirm internal agreement reasons and revision information remain accessible to authorized staff. Use real financial changes only when approved by the school; use a staging copy for test agreements and payments.

## Rollback

The new migration adds tables; it does not rewrite existing charges or payments. Do not simply roll back code after staff have created agreements: old calculations would ignore concessions and could show incorrect balances. Pause access and reconcile any new financial activity before restoring a coordinated code/database backup. Do not reverse migration 0003 after it contains financial records; that would delete agreement history.

## Validation

All 336 local Django tests passed before packaging, including negotiated clearance, portal access isolation, and report action checks. Local system and migration-drift checks passed. The hosted MySQL/MariaDB migration and browser/mobile appearance must be verified on the target environment; this package has not been deployed automatically.
