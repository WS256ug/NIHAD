# Independent Islamic Studies classes — 2026-10-25

Students retain one registration number and account, with separate Main and Islamic Studies enrollments. For example, a student can be P.4 Main and P.3 Islamic Studies in the same year. Only students whose religion is Islam can receive a new Islamic Studies enrollment. Religion alone no longer adds a student to a marks sheet.

## Deployment

This incremental package requires the current project baseline, including students migration 0009, academics 0008 (Islamic report groups), promotions 0002, reports 0001 and schools 0004. Deploy and verify on a staging copy first. It changes enrollment, assignment and promotion schemas; replacing files alone is insufficient.

1. Pause staff editing and back up the application and database. Keep users out until migrations and restart finish.
2. Extract `namecheap-islamic-placements-update-20261025.zip` in the application root containing `manage.py`, preserving directories and replacing the included files.
3. Activate the cPanel application's virtual environment and load its production environment variables.
4. Run:

   ```sh
   python manage.py showmigrations students academics promotions reports schools --settings=config.settings.production
   python manage.py migrate --plan --settings=config.settings.production
   python manage.py migrate --settings=config.settings.production
   python manage.py check --settings=config.settings.production
   ```

5. Restart the cPanel Python application. Reload browser pages, particularly any marks sheets opened before deployment. No new dependencies or static assets are required.
6. Verify a Main/Islamic placement pair, teacher access, marks, report class and fees before resuming school use.

## Assign a student's Islamic class

1. Open Students and the student's profile. Ensure Religion is **Islam**.
2. Under Enrollment history, select **Add enrollment**.
3. Choose **Islamic Studies**, the academic year, the Islamic class and its optional stream. The enrollment date must cover the assessment date for the student to appear on its sheet.
4. Save. Keep the existing Main enrollment. Both placements are labelled in staff and parent history.
5. Assign Islamic subjects to the teacher in that Islamic class. Class-teacher assignments now also require a programme choice; select Islamic Studies for Islamic report comments.
6. Open an Islamic Studies assessment for that class. Its roster, marks, report class and ranking use Islamic placements. Main assessments continue to use Main placements.

Student search includes a Programme filter. Add or configure classes and streams through the normal school configuration; no class names are hard-coded. If an Islamic enrollment already exists, inspect it before adding another. A class transfer closes that programme's enrollment and creates a later one without overlapping dates. Existing marked history cannot be reassigned through the enrollment form. Correcting an already assessed wrong class requires a separately reviewed academic correction; do not delete marks or reports.

## Existing data

- Every original enrollment remains Main, so ordinary fees and financial history keep their original links.
- For students with recorded Islamic marks or reports, the migration creates a matching Islamic enrollment for the previously recorded class and dates, then moves those Islamic references together. All report versions, snapshot contents, comments, marks, revisions and publication data are preserved. Submitted/approved sheet references are remapped to the copied enrollment IDs.
- Students without existing Islamic results receive no guessed placement. Administrators assign their actual Islamic class explicitly.
- Existing class-teacher assignments previously covered both report groups. The migration preserves that access as two programme-specific assignments. Review/deactivate the Islamic assignment if a different teacher should cover it. New assignments choose one programme.
- A later religion change does not erase previous Islamic marks or reports. Existing recorded assessment participation remains available for authorized historical correction; new Islamic assessments require religion Islam and a matching dated placement.
- Promotion batches now select a programme. Islamic promotion/repetition advances only Islamic enrollment and does not change Main placement or overall student status. Main school departure still requires closing all current enrollments.
- Ordinary fees can only be assigned to Main enrollments; adding Islamic enrollment does not create extra charges. Existing grade schemes and grade ranges are not changed by this update.

## Rollback

The history migration is deliberately irreversible: independently advanced enrollments cannot safely be merged automatically. Before reopening to users, rollback requires restoring the matching pre-deployment code and database backup together. After new records are entered, use a reviewed forward correction instead of restoring an old database over newer school activity.
