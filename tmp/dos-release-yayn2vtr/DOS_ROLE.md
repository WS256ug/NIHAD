# Director of Studies (DOS)

School Admin and Super Admin can create a staff account under Accounts and select **Director of Studies (DOS)**. DOS signs in through the normal staff login and opens the DOS dashboard.

DOS can manage sections, years, terms, classes, streams and the current academic period; teacher profiles linked to existing teacher accounts; subjects and teaching/class-teacher allocations; assessment types and assessments; grading and divisions; marks entry and review; report generation, comments, approval, publication and audited corrections; and promotion batches. Existing validation, closed-assessment protections and historical record rules still apply.

DOS can view students and their academic history. Student registration, guardian administration, portal credentials and staff account administration remain with administrators. DOS cannot view or edit fees, payments, receipts, expenses or financial summaries, or change the school profile and its fee-clearance policy. Headteacher permissions are unchanged.

Report approval by DOS uses the existing report review workflow and records the actual approving user in the audit trail and report signoff. Existing report headings still say Headteacher comment.

## Deployment

Deploy the updated application files and accounts migration 0006, then run `python manage.py migrate accounts` using the deployment virtual environment and restart the application. The migration adds the role to the database constraint and choices; it does not create accounts or change existing roles. It has been applied to the local development database. Hosted deployment has not been performed.
