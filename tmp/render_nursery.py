exec(Path('tmp/implement_nursery.py').read_text().split("m='apps/academics/models.py'")[0])
edit('apps/academics/forms.py','("section", "code", "name", "report_group")','("section", "code", "name", "report_group", "illustration")')
f='templates/reports/endterm.html'
edit(f,'    <h3 class="endterm-section-heading">Academic performance</h3>', '''    {% if data.nursery_progress %}
    <h3 class="endterm-section-heading">Learning and development</h3>
    <div class="table-scroll"><table class="endterm-marks nursery-results"><thead><tr><th>Learning area</th><th>Progress level</th><th>Teacher observation</th></tr></thead>
    <tbody>{% for row in data.subjects %}<tr><th scope="row">{% if row.illustration %}<span class="nursery-picture nursery-picture-{{ row.illustration }}" aria-hidden="true"></span>{% endif %}{{ row.subject }}</th><td>{{ row.grade }}</td><td>{{ row.observation|linebreaksbr }}</td></tr>{% endfor %}</tbody></table></div>
    {% else %}
    <h3 class="endterm-section-heading">Academic performance</h3>''')
edit(f,'    {% if data.exam_sets %}<p class="endterm-calculation">','    {% endif %}\n    {% if data.exam_sets %}<p class="endterm-calculation">')
edit(f,'    <div><h3>Class-teacher comment</h3>', '    {% if not data.nursery_progress %}<div><h3>Class-teacher comment</h3>')
edit(f,'    <div><h3>Headteacher comment</h3>', '    {% endif %}<div><h3>Headteacher comment</h3>')
edit('apps/reports/views.py',"'reports/midterm.html' if report.screen_only else 'reports/endterm.html'", "'reports/midterm.html' if report.screen_only and not report.snapshot.get('nursery_progress') else 'reports/endterm.html'")
f='apps/reports/endterm_pdf.py'
edit(f,'    marks_table = table(rows, [64*mm]', '''    if data.get('nursery_progress'):
        from .nursery import NurseryPicture
        columns = ['Learning area', 'Progress level', 'Teacher observation']
        rows = [[p('LEARNING AND DEVELOPMENT', heading), '', ''], [p(c, heading) for c in columns]]
        for row in data['subjects']:
            area = [NurseryPicture(row.get('illustration')), p(row['subject'])] if row.get('illustration') else p(row['subject'])
            rows.append([area, p(row['grade']), p(row.get('observation', ''))])
    marks_table = table(rows, [64*mm]''')
edit(f,"[64*mm] + [(width-64*mm)/(len(columns)-1)]*(len(columns)-1)","([52*mm, 32*mm, 102*mm] if data.get('nursery_progress') else [64*mm] + [(width-64*mm)/(len(columns)-1)]*(len(columns)-1))")
edit(f,"        cell = [p(label)","        if key == 'teacher' and data.get('nursery_progress'):\n            continue\n        cell = [p(label)")
edit(f,'[width/2]*2, splitInRow=1','[width/len(comments)]*len(comments), splitInRow=1')
