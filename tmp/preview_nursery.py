import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from pathlib import Path
from types import SimpleNamespace
from apps.reports.endterm_pdf import endterm_pdf
from apps.reports.comments import suggest_headteacher_comment
import pymupdf
items=[('social','Social Development','Shares toys and joins group activities.'),('environment','My Environment','Identifies familiar places and describes sunny weather.'),('hygiene','Personal Hygiene','Washes hands independently before meals.'),('numbers','Numbers','Counts five objects; needs help recognising written numbers.'),('language','Language','Recognises familiar sounds and enjoys stories.'),('oral','Oral Expression','Talks about familiar experiences with confidence.'),('writing','Pre-writing & Pre-reading','Traces lines with guidance and enjoys colouring.'),('physical','Physical Development','Runs, balances and joins ball games confidently.')]
data=dict(school='NIHAD BABY SCHOOL AND DAY CARE',motto='A CHILD TIME EXPERIENCE',assessment='End-Term',year='2026',term='Term 3',student='Sample Learner',registration_number='DEMO-001',section='Nursery',**{'class':'Baby'},stream='East',nursery_progress=True,mode='descriptive',next_term_start=None,subjects=[dict(subject=name,grade='Achieved' if i%2==0 else 'Developing',observation=obs,illustration=key) for i,(key,name,obs) in enumerate(items)])
comment=suggest_headteacher_comment(data,None,assessment_id=1,enrollment_id=1)['comment']
report=SimpleNamespace(snapshot=data,enrollment=SimpleNamespace(student=SimpleNamespace(photo=None)),teacher_comment='',headteacher_comment=comment,published_at=None)
path=Path('output/pdf/nursery-progress-implemented-preview.pdf');path.write_bytes(endterm_pdf(report))
doc=pymupdf.open(path)
print('Pages:',len(doc))
for i,page in enumerate(doc):
 page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(f'tmp/pdfs/nursery-implemented-{i}.png')
