# Namecheap grade correction — 2026-10-21

This update supplies the nine bands from the school's printed key and ranks newly generated reports by total score. It changes one explicitly selected open assessment, only if it has no generated reports. Marks and historical grading schemes are preserved. Other assessments keep their existing scheme; the new version becomes the latest section configuration for future assessments.

The JSON file supplies grade points 1–9 corresponding to D1–F9. Existing aggregate settings, required subjects and division ranges are copied, not redesigned. Review these points if the school uses a different aggregate policy.

1. Back up application files and database, and pause academic editing during correction.
2. Extract `namecheap-grades-update-20261021.zip` in the application root containing `manage.py`, preserving directories and replacing the included files.
3. Activate the application's virtual environment using cPanel's activation command. Ensure production environment variables are loaded.
4. Run:

   ```sh
   python manage.py check --settings=config.settings.production
   ```

5. Preview assessment 9, replacing `ADMIN_USERNAME` with an active school administrator's username:

   ```sh
   python manage.py correct_assessment_grades --assessment 9 --expected-scheme 2 --actor ADMIN_USERNAME --rules deployment/nihad_grade_bands.json --settings=config.settings.production
   ```

   The preview prints current and proposed bands, validates the entire configuration and rolls back all writes. Check the assessment name and ranges. The command rejects a changed scheme ID, a closed assessment, descriptive marks or any existing reports. If rejected, retain the output for diagnosis; do not delete reports or bypass the guard.

6. Apply the same reviewed correction:

   ```sh
   python manage.py correct_assessment_grades --assessment 9 --expected-scheme 2 --actor ADMIN_USERNAME --rules deployment/nihad_grade_bands.json --apply --settings=config.settings.production
   ```

7. Restart the Python application in cPanel and reload the marks sheet. Confirm 55 → C6, 66 → C4, 77/78 → C3, 44 → P8, 88 → D2, 28 → F9, 98 → D1. The command prints the new scheme ID. Repeating the original apply command is rejected because scheme 2 is no longer linked.

No migration, dependency installation or collectstatic is required. For a different assessment, inspect its ID and current scheme first and preview that assessment explicitly. This package does not bulk-modify all assessments.

Existing reports retain their saved grades and positions. Reports already generated require a separate authorized correction workflow; this command intentionally stops for those assessments.

## Rollback

Restore the packaged runtime files from the application backup if necessary. Restoring code does not reverse the audited grading configuration change. The original scheme remains available; do not overwrite the database with an old backup after newer school records have been added. A configuration reversal must receive the same scoped review as the correction.
