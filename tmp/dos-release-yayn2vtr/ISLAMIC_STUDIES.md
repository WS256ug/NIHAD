# Separate Islamic Studies reports

Students registered with religion **Islam** participate in Islamic Studies. The
existing stored value `Moslem` remains compatible; registration and student
profiles now display it as Islam. Christian, Other and blank religion values do
not qualify for new Islamic assessments.

## School setup

1. In Academics > Subjects, choose **Islamic Studies** as the report group for
   Lugha, Qur'an, Fiqh, Tarbiya and any other Islamic subjects. Use the student's
   normal school section (for example Primary), with the usual teacher and
   class/stream assignments. Common subjects belong to **Main School**.
2. Check that participating students have religion Islam in registration.
3. Create a Mid-Term assessment with report group Islamic Studies for each
   relevant class/stream and term. Create a separate End-Term assessment in the
   same group. Main School assessments can use the same assessment type, class,
   stream and term without conflict.
4. Enter marks in the usual marks sheets. Islamic sheets list only eligible
   students and Islamic subjects. Complete any configured marks review, close
   the assessment and generate reports.
5. Complete class-teacher comments, headteacher review and publication as usual.

Each group has its own subject results, totals, averages, aggregates and optional
ranking. Grade rules remain configured by the student's school section. Ranking
uses only eligible students with complete results in that assessment. A grading
scheme requiring specific subjects must be compatible with the assessment's
subjects; missing required subjects are never silently ignored.

Islamic report titles identify the group in staff lists, portal reports, HTML
and PDF. Assessment-type settings still control whether Mid-Term is screen-only
and whether an assessment uses Set One and Set Two. Existing portal ownership,
fee-clearance, publication and correction rules apply to both groups.

## Existing records

The migration assigns existing subjects and assessments to Main School. It does
not infer groups from names, move marks, or rewrite existing report snapshots.
Unused subjects can be assigned to Islamic Studies. Subjects already used for
marks or marks-sheet review cannot change group: create a new subject with a
distinct name/code and allocate it for a new academic period. Keep the old
subject and assignments for historical reports. Do not reuse an old all-year
assignment when configuring a new report structure; its historical marks are
still required by the existing reporting rules.

An assessment's report group cannot change after creation. If a student's
religion changes after marks or reports exist, that assessment retains their
participation for review and audited corrections. Their new religion determines
eligibility for future assessments. Previously published reports remain intact.

## Deployment to Namecheap

Upload the changed application/template files and both new migrations together:
`academics/0008_islamic_report_groups` and `students/0009_alter_student_religion`.
In the existing hosting virtual environment and project directory, run:

```bash
python manage.py migrate --noinput --settings=config.settings.production
python manage.py check --settings=config.settings.production
```

Restart the Python application, then configure the groups and assessments using
the steps above. This feature does not require new packages or CSS changes.
Local migrations and tests use SQLite; no changes have been applied to the hosted
database by the development agent.
