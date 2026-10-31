from pathlib import Path
exec(Path('tmp/implement_nursery.py').read_text().split("m='apps/academics/models.py'")[0])
edit('apps/reports/nursery.py','size=40','size=32')
edit('apps/reports/nursery.py','        c.drawImage(str(settings.BASE_DIR', '        top, bottom = [(0, 444), (444, 858), (858, 1320), (1320, 1774)][row]\n        scale = size / (bottom - top)\n        c.drawImage(str(settings.BASE_DIR')
edit('apps/reports/nursery.py','-column * size, -(3-row) * size, width=2*size, height=4*size)', '-column * size, -(1774-bottom)*scale, width=2*size, height=1774*scale)')
edit('apps/reports/endterm_pdf.py','rowHeights=[10*mm, 16*mm]', "rowHeights=[8*mm, 12*mm] if data.get('nursery_progress') else [10*mm, 16*mm]")
