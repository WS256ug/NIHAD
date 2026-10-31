# Namecheap DOS role update

This package adds Director of Studies (DOS) to the existing Islamic placements baseline (repository commit a57248a). It excludes the unfinished nursery-report changes and leaves roster-import and grade-repair commands untouched. No dependency or static-file changes are needed.

## Upload and check

Upload `artifacts/namecheap-dos-update-20261031.zip` to `/home/ugatrrvu/private-updates/`, outside the website directory. Extract into a new empty folder `/home/ugatrrvu/private-updates/dos-20261031`. Do not extract over the application yet.

In cPanel Terminal, activate the existing environment and run the read-only compatibility check:

```sh
source /home/ugatrrvu/virtualenv/nihad.ugatec.com/3.13/bin/activate
cd /home/ugatrrvu/private-updates/dos-20261031
python check_dos_release.py /home/ugatrrvu/nihad.ugatec.com
```

Proceed only after `CHECK PASSED`. A mismatch means the hosted files need to be compared and merged first; do not overwrite them. The check accepts the supported baseline or this exact update and normalizes Windows/Linux line endings.

## Apply

Pause staff editing. Make a private backup of the application and database through the normal cPanel backup process. With the extracted package as the current directory, copy only the included application directories:

```sh
cp -R apps/. /home/ugatrrvu/nihad.ugatec.com/apps/
cp -R templates/. /home/ugatrrvu/nihad.ugatec.com/templates/
cd /home/ugatrrvu/nihad.ugatec.com
python manage.py showmigrations accounts --settings=config.settings.production
python manage.py migrate accounts --plan --settings=config.settings.production
python manage.py migrate accounts --settings=config.settings.production
python manage.py check --settings=config.settings.production
```

Use the normal production environment variables. Migration 0006 adds DOS to user role choices and the database constraint. It creates no accounts and changes no existing roles. Restart the Python application using cPanel after the checks pass.

## Verify

Sign in as School Admin or Super Admin. Under Accounts, create a staff account with **Director of Studies (DOS)**. Sign in with that account and verify its dashboard, academic setup, subjects, allocations, marks, report review and promotions. Finance, expenses, Accounts administration and school profile editing must be denied. Headteacher access is unchanged.

DOS can approve and publish reports. Existing report headings still say Headteacher comment; the actual approving staff member is recorded in the report and audit trail.

Before reopening to users, a failed deployment can be rolled back by restoring the matching application/database backup together. Do not remove the DOS database constraint value after creating DOS accounts, and do not restore old data over subsequent school activity.

## Status

Prepared for manual upload. No hosted files or database records have been changed by this session.

Validation: the isolated DOS release passed all 360 baseline tests, Django system checks and migration-drift checks. The full working tree previously passed 382 tests. Package compatibility checks were verified against the baseline, a mismatched file and an already-installed update.
