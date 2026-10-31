# Baby and Middle progress reports

Implemented 2026-10-29. This update is separate from the Islamic placements deployment package.

## Setup

1. Apply academics migrations 0010 and 0011. On deployment use the production settings and environment, then collect static files and restart the application.
2. Create or confirm the Nursery section and the Baby/Middle classes through school configuration. Keep student enrollments in their actual classes.
3. Create the editable starting levels and learning areas using an active School Admin or Super Admin account ID:

   ```powershell
   .\.venv\Scripts\python.exe manage.py setup_nursery_progress --section SECTION_ID --actor ADMIN_USER_ID
   ```

   Replace the IDs with records in the target database. The command is transactional and idempotent, does not create accounts or enrollments, and does not replace existing subjects or default section grades. It creates Emerging, Developing, Achieved and Excellent as editable defaults. Administrators can configure scheme/rules through Django admin; do not edit schemes already used for results. Create a new nursery-only scheme for future changes.

4. In Subjects, review the eight learning areas and choose each area's illustration. Existing subjects matched by name are preserved: choose their illustration manually. Configure which areas apply to each class through teaching assignments; Baby and Middle can have different assignments.
5. Create the Baby or Middle exam. Enable **Nursery progress report** and choose **Nursery progress levels**. This choice must belong to the class's section. Use descriptive grading without Set One/Set Two. Enable **Require marks review** if sheet approval is required. Use an assessment type with online-only reports disabled when PDF and print are needed.
6. Assign teachers to the learning areas and ensure learners have eligible enrollments. No separate guardian accounts are required.

## Teacher workflow

Open the exam, choose a learning area/stream, select each learner's progress level and type the observation based on their actual abilities. Save progress at any time. A level can be saved without an observation temporarily, but the sheet cannot be submitted or closed until every assessed learner has both. Mark absent learners explicitly; no capability or low level is inferred from absence.

When enabled, submit sheets for review. Reviewers approve them, then the School Admin closes the exam and generates reports. Teachers do not open individual reports to enter observations or add a separate class-teacher comment.

## Reports and corrections

Reports contain the saved observations and illustrations, an automatic headteacher comment summarising recorded levels, and the existing school branding/stamp. No teacher signature is printed. The headteacher reviews or edits the comment and approves; an administrator publishes. Parent portal access and fee restrictions remain enforced.

To correct observations after generation, a School Admin opens **report correction** on the exam. Teachers edit the reopened sheets; complete the review/close/generate process again. Old report versions preserve the earlier observations. The nursery headteacher review screen explains this correction route rather than returning the report for a class-teacher comment.

The standard eight-area sample fits on one A4 page. Longer observations may produce additional pages; printable HTML and PDF use the same saved data. The sample in output/pdf/nursery-progress-implemented-preview.pdf is fictional.

## Illustration provenance

Asset: static/img/nursery-learning-atlas.png. Created with the built-in image-generation tool, then copied into this repository. HTML and PDF render cells from the original atlas without external network requests.

Prompt: Create a single illustration atlas for a nursery report: exactly 2 columns and 4 rows of equal rectangular cells, no margins or gutters. Each cell has plain white background, all art inset safely inside cell, no text or numbers except counting blocks. Consistent colourful children's-book cartoon style, Black African preschool children, crisp outlines, cheerful friendly expressions. Row 1 left: two children sharing toys; right: home tree and sunshine. Row 2 left: child washing hands at sink; right: colourful counting blocks 1 2 3. Row 3 left: child reading a book; right: two children talking. Row 4 left: child drawing with crayons; right: children playing ball. Portrait image aspect ratio 1:2. Eight separate complete scenes in a regular 2x4 grid, no borders, no titles, no watermark. This is one sprite atlas for clipping individual cells in HTML and PDF reports.

## Verification

All 364 Django tests pass, including draft validation, transaction rollback, observation-only edits, stale submissions, access checks, HTML escaping, report publication/history, configuration selection and setup idempotency. System and migration-drift checks pass. Local migrations are applied; hosted deployment and staff acceptance remain pending.
