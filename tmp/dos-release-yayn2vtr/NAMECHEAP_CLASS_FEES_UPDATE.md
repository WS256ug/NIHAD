# Namecheap class fee assignment update - 2026-10-12

Incremental update for the existing application with the October 4 fees/portal update already installed, including finance migration 0003. If that update is not installed, install `namecheap-portal-fees-update-20261004.zip` using its instructions first.

## Install

1. Back up the existing application files and database. Pause staff use during replacement.
2. Upload `namecheap-class-fees-update-20261012.zip` into the application root (the folder containing `manage.py`). Extract there and overwrite matching files, preserving folders.
3. Activate the existing application virtual environment using the command shown in cPanel's Python application setup. Change to the application root and ensure its production environment variables are loaded.
4. Run:

   ```sh
   python manage.py showmigrations finance --settings=config.settings.production
   python manage.py check --database default --settings=config.settings.production
   ```

   Finance migration 0003 must already be marked `[X]`. This package adds no migrations, dependencies or static files; no migrate, pip install or collectstatic command is needed for this update.
5. Restart the existing Python application in cPanel.
6. Open Fees as a school administrator or bursar and confirm that Assign class fees opens correctly. Remove the uploaded ZIP and manifest from the server after installation.

## Use

Choose Fees > Assign class fees, select the fee structure for the class and term, and confirm. The structure determines the class, academic year and optional stream. Current enrollments starting on or before the term's end receive the charge. A structure without a stream covers all streams in that class.

Use this only when the selected fee category applies to the whole group. For example, a Boarding fee should not be assigned across a mixed Day/Boarding class; use Assign individual fees for those exceptions.

Existing assignments are skipped, including cancelled charges and charges with individual agreements. Repeating the operation can assign the same fee to newly enrolled students without charging existing assignments twice. Each student's payments, balances and agreements remain individual.

On staging, verify a class assignment and repeat it to confirm that existing assignments are skipped; check a stream-specific structure and an individual statement. Only perform intended school fee assignments in production.

## Contents and validation

The archive contains five runtime files, the class-assignment regression tests, development notes and this guide. Paths are relative to the application root. `UPDATE_MANIFEST.sha256` contains a checksum for each included file. No environment files, local databases, media, virtual environments or Passenger configuration are included.

All 341 local tests passed for this implementation. Django system and migration-drift checks passed. Hosted deployment and browser visual verification remain pending.

## Rollback

Restore the five runtime files from the pre-update backup and restart the application. Charges created by this feature are ordinary audited fee charges and remain compatible with the previous code. Restoring code does not undo assignments; use the existing authorized cancellation workflow for mistaken charges. Do not delete financial records or restore an old database over newer payments.
