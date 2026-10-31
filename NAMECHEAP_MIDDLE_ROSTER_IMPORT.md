# Middle Class roster import

See [Student roster import reference](STUDENT_ROSTER_IMPORT_REFERENCE.md) for the consolidated Baby/Middle history, code explanation, troubleshooting and hosted verification.

Updated 2026-10-30. User requested the same import process as Baby and explicitly confirmed admission/enrollment date 2026-10-30. Temporary birth date remains 2026-01-01 for school-admin correction; supplied guardian relationships are preserved.

## Files and configuration

1. Extract namecheap-middle-roster-import-20261030.zip into the application root containing manage.py, replacing the earlier import_student_roster.py. No migrations or new dependencies are needed. The updated importer still supports the Baby CSV.
2. In School setup, ensure the Nursery section has an active Middle class with two active streams: **Daises** and **Lavenders**. Daises is the exact spelling supplied in the CSV; do not silently change it to Daisies. If another official spelling is preferred, correct the CSV/configuration together and run a fresh preview.
3. Upload middle_class_roster.csv to ~/private-imports/middle_class_roster.csv outside the public website folder. The private CSV is not included in this code package.
4. Activate the cPanel application virtual environment and change into the application folder as before.

## Preview all 25 students

```sh
python manage.py import_student_roster --file ~/private-imports/middle_class_roster.csv --actor ws --academic-year '2026/27' --section-name 'Nursery' --class-name 'Middle' --admission-date 2026-10-30 --temporary-birth-date 2026-01-01 --settings=config.settings.production
```

Expected placement summary: Daises 14 students; Lavenders 11 students. Do not pass --stream-name: the command uses each CSV row's Stream value. Both streams must exist before any records can be saved. Repeated source row numbers are allowed across different streams, and audit messages include stream and source number.

Preview ends with PREVIEW PASSED: 25 students validated. No records saved. Registration numbers printed by the preview are provisional.

## Apply after successful preview

Use the normal database backup before importing. Confirm the year/class/stream counts in the preview, then run:

```sh
python manage.py import_student_roster --file ~/private-imports/middle_class_roster.csv --actor ws --academic-year '2026/27' --section-name 'Nursery' --class-name 'Middle' --admission-date 2026-10-30 --temporary-birth-date 2026-01-01 --expected-sha256 ec176e75f3a86556967a281c5f57ddda591673d1cf2411a5b3e030a5a51fd34c --settings=config.settings.production --apply
```

The checksum above belongs to the reviewed source file. If the file changes, rerun preview and use its new checksum.

Success: Imported 25 students with guardian contacts and Main enrollments. Refresh Students, choose Middle and filter each stream. Never repeat a successful import; duplicate checks stop exact/reordered full-name matches rather than silently creating them again.

## Retained rules

- Source has 25 Active students across two streams, with no admission-date column. The explicit --admission-date fills only missing dates; any existing CSV admission date takes precedence and is validated.
- 2026-01-01 birth dates are temporary and recorded as such in audit history. School administrators must correct them later.
- Full displayed names remain in supplied order; name components follow the same first-token/middle-tokens/last-token split as the Baby import.
- Slash-listed guardians become separate contacts with the same supplied relationship. Shared phone lists are retained for each guardian without guessing ownership. Missing guardian surnames are explicitly recorded as (not supplied).
- Leading zeros are restored only for nine-digit contacts beginning with 7. Unexpected numeric phone formats are retained and flagged rather than guessed.
- Existing matching guardian contacts can be reused for siblings. Potential existing students, ambiguous guardians, missing streams, wrong class, invalid rows or audit failures abort the entire transaction.
- No portal accounts or Islamic Studies placements are created. Set those up through the normal application workflows if needed.
- Admission/enrollment on 30 October 2026 means these students will not appear in exams dated earlier than that date. Earlier enrollment requires factual corrected admission dates, not an automatic backdate.

## Verification

The actual 25-row file passed a full preview in an isolated test database; zero students remained after rollback. Regression tests cover multiple streams, repeated source numbers between streams, missing dates, conflicting stream overrides and missing-stream rollback, alongside the original Baby import tests. Hosted configuration/duplicates must still pass the hosted preview. No hosted records were changed locally.
