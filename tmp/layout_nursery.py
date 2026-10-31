from pathlib import Path
exec(Path('tmp/implement_nursery.py').read_text().split("m='apps/academics/models.py'")[0])
edit('apps/reports/endterm_pdf.py', "area = [NurseryPicture(row.get('illustration')), p(row['subject'])] if row.get('illustration') else p(row['subject'])", "area = table([[NurseryPicture(row.get('illustration')), p(row['subject'])]], [17*mm, 30*mm]) if row.get('illustration') else p(row['subject'])\n            if row.get('illustration'):\n                area.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))")
edit('apps/reports/endterm_pdf.py','splitInRow=1)', "splitInRow=0 if data.get('nursery_progress') else 1)")
