# Import Baby / Lillies roster on Namecheap

See [Student roster import reference](STUDENT_ROSTER_IMPORT_REFERENCE.md) for the consolidated history, code explanation, troubleshooting and hosted verification. The later Middle package supports both formats; do not replace it with the older Baby command.

Prepared 2026-10-30. The user explicitly authorised 2026-01-01 as the temporary date of birth for every learner, for school-admin correction later, and retaining the supplied guardian relationships.

## Package and CSV

Extract namecheap-student-roster-import-20261030.zip into the existing application root containing manage.py. It adds a management command only; it needs no database migration and no nursery-report deployment.

Upload baby_class_lillies_roster.csv separately into a private directory outside public_html and the public website document root. The commands below assume ~/private-imports/baby_class_lillies_roster.csv. The private student CSV is deliberately not included in the code package.

Activate the existing cPanel application's Python environment and run from the application root with the usual production environment variables loaded.

## Preview

```sh
python manage.py import_student_roster --file ~/private-imports/baby_class_lillies_roster.csv --actor ws --academic-year '2026/27' --section-name 'Nursery' --class-name 'Baby' --stream-name 'Lillies' --temporary-birth-date 2026-01-01 --settings=config.settings.production
```

This validates the entire file through the application's actual registration/enrollment services and rolls back the preview. It checks existing students before creating anything. Confirm the target year, class and stream printed at the top. The command does not create or guess school configuration; names must match exactly, ignoring case. If the class is called Baby Class or the stream is spelled Lilies on hosting, use that actual configured name.

Successful preview ends with PREVIEW PASSED: 34 students validated. No records saved. Preview registration numbers are provisional.

## Apply

After a successful preview and the normal database backup, run:

```sh
python manage.py import_student_roster --file ~/private-imports/baby_class_lillies_roster.csv --actor ws --academic-year '2026/27' --section-name 'Nursery' --class-name 'Baby' --stream-name 'Lillies' --temporary-birth-date 2026-01-01 --expected-sha256 c6f981a4424270b4b5fd7f878161f207f83cf4824a5c5a5476c4483a50c65087 --settings=config.settings.production --apply
```

The hash above identifies the CSV reviewed locally. If the CSV changes, preview it again and use the newly printed hash. A changed file cannot be applied with the old hash.

Success is announced after commit: Imported 34 students with guardian contacts and Main enrollments. Refresh Students and filter the class/stream. Do not repeat an import that already succeeded; exact student-name token matches cause the whole batch to stop rather than duplicate records.

## Data handling and corrections

- All 34 CSV records are Active. Dates of birth are 2026-01-01 as explicitly requested. Each student's audit history records that the date is TEMPORARY and requires correction.
- Admission dates are read from the CSV: 2026-10-30. Main enrollment dates use the same dates. This means these enrollments will not be eligible for exams held before 30 October 2026. Do not backdate automatically. If an actual earlier admission/enrollment date is supplied, correct the CSV and preview again.
- The section/year/class/stream in the example commands are explicit proposed placement choices and appear in the preview. No data is assigned to a different or similarly named class automatically.
- Names remain in the CSV's supplied order. For the application's separate fields, first token is first name, last token is last name and the intervening tokens are middle name. Confirm these component labels later; full displayed names retain their original order.
- Slash-separated guardian names become separate contacts linked to the student with the SAME supplied relationship, as requested. First listed guardian is primary. No parent genders/roles or emergency-contact status are inferred.
- Where multiple phone numbers are listed, the complete contact list is retained on each listed guardian; ownership of individual numbers is not guessed. Administrators should later assign phones to the correct guardian.
- Nine-digit numbers beginning with 7 regain their dropped leading zero. Other digit-only numbers are preserved; CSV source rows 27 and 29 need phone-length review. No digits are silently removed.
- A guardian with only one supplied name gets the explicit surname marker (not supplied), not an invented surname; update through guardian editing later.
- Exact matching guardian name plus complete phone-list records are reused for siblings. Shared phone numbers alone do not merge people. Ambiguous multiple existing guardian matches stop the import.
- Student duplicate checks use case-insensitive full-name tokens, including reordered names. This is not fuzzy identity matching: inspect existing records for misspellings before applying. A detected match stops the entire batch for review; existing records are never overwritten.
- Muslim maps to the system's stored Moslem / displayed Islam value. Religion alone does not create Islamic Studies enrollments.
- Registration numbers use the normal school sequence. No separate guardian accounts, passwords, or student portal accounts are created by this import. Use the existing student portal-access workflow to issue credentials after registration.
- Any invalid row, permission failure, wrong placement, duplicate or audit failure rolls back the entire transaction.

## Validation

Seven dedicated regression tests cover preview rollback (including student numbers and audit records), apply, retained relationships, temporary birth dates, repeated imports, reordered-name duplicates, late-row rollback, stale file hashes, placement/permissions, shared guardian reuse, missing surnames and unmodified unusual phone digits.

The actual 34-row source CSV also passed an isolated test-database preview with zero students remaining afterwards. Hosted matching/configuration still needs the hosted preview above. No hosted data has been changed from the local workspace.
