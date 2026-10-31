# Top Class: restore missing numeric grading

Hosted finding: assessment 18, Top / Islamic Studies / Mid Term, is open with no linked grading scheme and no reports. Top uses Primary grading. No hosted data has been changed by the local work.

This package contains only the updated correct_assessment_grades management command and these instructions. It does not need the nursery progress migrations or new models. Extract at the application root containing manage.py.

## Identify the source

Activate the cPanel application virtual environment and load the normal production environment. Run:

```sh
python manage.py shell --settings=config.settings.production <<'PY'
from apps.academics.models import GradingScheme
for s in GradingScheme.objects.filter(is_active=True, mode='numeric').select_related('section').order_by('section_id', '-pk'):
    print('ID:', s.pk, '| Section:', s.section.name, '| Name:', s.name)
    print('Bands:', list(s.rules.values('label', 'minimum', 'maximum', 'points')))
    print('Used by:', list(s.assessments.values_list('pk', 'academic_class__name', 'report_group')))
PY
```

Select the confirmed Primary scheme used by the relevant current exams; do not guess an ID or choose an old version just because it is active. Use an active School Admin or Super Admin username for --actor.

## Preview and apply

Replace PRIMARY_SCHEME_ID and ADMIN_USERNAME below. Take the normal database backup before applying.

```sh
python manage.py correct_assessment_grades --assessment 18 --expected-scheme 0 --source-scheme PRIMARY_SCHEME_ID --actor ADMIN_USERNAME --settings=config.settings.production
```

The preview prints the source and proposed bands, validates them, then rolls back all changes. After confirming the source bands:

```sh
python manage.py correct_assessment_grades --assessment 18 --expected-scheme 0 --source-scheme PRIMARY_SCHEME_ID --actor ADMIN_USERNAME --settings=config.settings.production --apply
python manage.py check --settings=config.settings.production
```

Reload the marks page. No mark re-entry or restart is needed for this database correction.

## Behaviour

- Only an open assessment without any generated reports can be repaired.
- Expected scheme 0 requires the link to still be empty; a repeat apply is rejected.
- Source must be active numeric grading from the same school with valid 0-100 coverage.
- Copies the bands, points, aggregate configuration and divisions into the target class's section, then links the assessment in one transaction with an audit entry.
- Cross-section required-subject configurations are rejected rather than guessing subject equivalents.
- Existing marks, original Primary rules and other assessment links remain unchanged. The new scheme becomes the target section's newest default for future ordinary exams, consistent with section-based grading.
- If the source is not the intended Primary scale, do not apply. Do not use this command on published reports.
