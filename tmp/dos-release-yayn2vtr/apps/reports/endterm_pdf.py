"""Printable reports built solely from recorded results and comments."""
from html import escape
from io import BytesIO
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .formatting import report_number
from .presentation import report_summary


def endterm_pdf(report):
    data = report.snapshot
    output = BytesIO()
    width = 186 * mm
    burgundy, charcoal, pale, line, gold = [colors.HexColor(c) for c in ('#800020', '#333333', '#F8F1F3', '#e4d4d9', '#B89B5E')]
    body = ParagraphStyle('Report', fontName='Helvetica', fontSize=9, leading=13, textColor=charcoal)
    small = ParagraphStyle('Small', parent=body, fontSize=8, leading=11)
    title = ParagraphStyle('School', parent=body, fontName='Helvetica-Bold', fontSize=18, leading=21, textColor=burgundy)
    heading = ParagraphStyle('Heading', parent=body, fontName='Helvetica-Bold', textColor=colors.white)

    def p(value, style=body):
        return Paragraph(escape(str(value if value is not None else '-')).replace('\n', '<br/>'), style)

    def table(rows, widths, header=False, row_backgrounds=None, **kwargs):
        result = Table(rows, colWidths=widths, hAlign='LEFT', **kwargs)
        rules = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 7),
                 ('RIGHTPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 4),
                 ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]
        if header:
            rules += [('BACKGROUND', (0, 0), (-1, 0), burgundy), ('GRID', (0, 0), (-1, -1), .4, line),
                      ('ROWBACKGROUNDS', (0, 1), (-1, -1), row_backgrounds or [colors.white, pale])]
        result.setStyle(TableStyle(rules))
        return result

    def section(text):
        result = table([[p(text, heading)]], [width])
        result.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), burgundy), ('LINEBELOW', (0,0),(-1,-1),.6,gold)]))
        result.keepWithNext = True
        return result

    logo = settings.BASE_DIR / 'static' / 'img' / 'nihad-logo.png'
    brand = [p(data['school'], title)]
    brand += [p(data[key], small) for key in ('motto', 'school_address', 'school_phone', 'school_email') if data.get(key)]
    period = [
    p(data['assessment'] + ' report'),
    p('Academic year: ' + data['year'], small),
    p('Term: ' + data['term'], small),
]
    story = [table([[Image(str(logo), width=23*mm, height=23*mm, kind='proportional') if logo.exists() else '', brand, period]], [28*mm, 111*mm, 47*mm]), Spacer(1, 4*mm), section('STUDENT INFORMATION')]
    info = [('Student', data['student']), ('Registration number', data['registration_number']), ('Class', data['class'])]
    info += [(label, data[key]) for key, label in [('stream', 'Stream'), ('gender', 'Gender')] if data.get(key)]
    info_cells = [[p(label, small), p(value)] for label, value in info]
    info_rows = [info_cells[i:i+2] + ([''] if len(info_cells[i:i+2]) == 1 else []) for i in range(0, len(info_cells), 2)]
    student_info = table(info_rows, [73*mm, 73*mm])
    photo = report.enrollment.student.photo
    if photo:
        try:
            with photo.open('rb') as source:
                photo_image = Image(BytesIO(source.read()), width=26*mm, height=32*mm, kind='proportional')
            story.append(table([[photo_image, student_info]], [30*mm, 156*mm]))
        except (OSError, ValueError):
            story.append(student_info)
    else:
        story.append(student_info)
    story.append(Spacer(1, 3*mm))
    numeric = data.get('mode') == 'numeric'
    sets = data.get('exam_sets', [])
    points = data.get('aggregate') is not None
    columns = ['Subject / learning area'] + [f"{item['name']}\n{report_number(item['weight'])}%" for item in sets]
    if numeric:
        columns += ['Final mark' if sets else 'Mark']
    columns += ['Grade / level'] + (['Points'] if points else [])
    rows = [[p('ACADEMIC PERFORMANCE', heading)] + [''] * (len(columns)-1), [p(c, heading) for c in columns]]
    for row in data['subjects']:
        values = [row['subject']] + [('Absent' if item.get('absent') else report_number(item['score'])) for item in row.get('exam_sets', [])]
        if numeric:
            values += ['Absent' if row.get('absent') else report_number(row.get('score'))]
        values += [row.get('grade')] + ([row.get('points')] if points else [])
        rows.append([p(value) for value in values])
    marks_table = table(rows, [64*mm] + [(width-64*mm)/(len(columns)-1)]*(len(columns)-1), header=True, repeatRows=2,
                        row_backgrounds=[colors.Color(1,1,1,alpha=0), colors.Color(248/255,241/255,243/255,alpha=.55)])
    marks_table.setStyle(TableStyle([('SPAN', (0,0),(-1,0)), ('LINEBELOW',(0,0),(-1,0),.6,gold), ('BACKGROUND',(0,1),(-1,1),burgundy)]))
    story.append(marks_table)
    if numeric:
        story.append(p('Marks out of ' + report_number(data['maximum_score']) + ('. Final mark = ' + ' + '.join(f"{s['name']} ({report_number(s['weight'])}%)" for s in sets) if sets else ''), small))
    if data.get('has_absences') or (numeric and data.get('average') is None):
        story.append(p('Absent for one or more exam results. Overall results and position are not calculated.', small))
    summary = report_summary(data)
    if summary:
        story += [Spacer(1, 3*mm), table([[p(label, small) for label, value in summary], [p(value) for label, value in summary]], [width/len(summary)]*len(summary))]
    if data.get('promotion_decision'):
        story += [section('PROMOTION DECISION: ' + data['promotion_decision'])]
    story.append(Spacer(1, 3*mm))
    comments = []
    for key, label, comment in [('teacher', 'Class-teacher comment', report.teacher_comment), ('headteacher', 'Headteacher comment', report.headteacher_comment)]:
        cell = [p(label), Spacer(1, 2*mm), p(comment or 'Pending'), Spacer(1, 5*mm)]
        # if data.get(key + '_name'):
        #     cell.append(p(data[key + '_name'], small))
        # if data.get(key + '_comment_date'):
        #     cell.append(p('Date: ' + data[key + '_comment_date'], small))
        #cell += [Spacer(1, 3*mm), p('Signature: ____________________', small)]
        comments.append(cell)
    comment_table = table([comments], [width/2]*2, splitInRow=1)
    comment_table.setStyle(TableStyle([('BACKGROUND', (0,0),(-1,-1),pale), ('BOX',(0,0),(-1,-1),.5,line), ('LINEAFTER',(0,0),(0,-1),.5,line)]))
    story += [comment_table, Spacer(1, 5*mm)]
    closing = [p('Next term begins: ' + data['next_term_start'])] if data.get('next_term_start') else []
    if numeric and data.get('grading_key'):
        key_style = ParagraphStyle('GradingKey', parent=small, fontSize=6.5, leading=9, alignment=1)
        key_heading = ParagraphStyle('GradingKeyHeading', parent=key_style, textColor=colors.white, fontName='Helvetica-Bold')
        # Keep configurable schemes readable, even with more than nine grades.
        key_content = [p('Grading key', small), Spacer(1, 1*mm)]
        for start in range(0, len(data['grading_key']), 9):
            bands = data['grading_key'][start:start+9]
            key_table = table([
                [p('Grade', key_heading)] + [p(item['grade'], key_heading) for item in bands],
                [p('Range (%)', key_style)] + [p(item['range'], key_style) for item in bands],
            ], [19*mm] + [109*mm/len(bands)]*len(bands), header=True)
            key_table.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 2), ('RIGHTPADDING', (0,0), (-1,-1), 2)]))
            key_content += [key_table, Spacer(1, 1*mm)]
        key_content += [p('< means below the upper limit.', small), Spacer(1, 2*mm)]
        closing = key_content + closing
    # if report.published_at:
    #     closing.append(p('Published ' + report.published_at.strftime('%d %b %Y'), small))
    stamp = table([[p('School stamp', small)], ['']], [48*mm], rowHeights=[10*mm, 16*mm])
    stamp.setStyle(TableStyle([('BOX',(0,0),(-1,-1),.5,line)]))
    story.append(table([[closing, stamp]], [132*mm, 54*mm]))

    def footer(canvas, doc):
        if logo.exists():
            canvas.saveState()
            canvas.setFillAlpha(.10)
            size = 110 * mm
            canvas.drawImage(str(logo), (A4[0]-size)/2, (A4[1]-size)/2,
                             width=size, height=size, preserveAspectRatio=True,
                             anchor='c', mask='auto')
            canvas.restoreState()
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(charcoal)
        # canvas.drawString(12*mm, 10*mm, f"{data['registration_number']} | {report.get_status_display()} | Version {report.version}")
        canvas.drawRightString(198*mm, 10*mm, f'Page {doc.page}')
        canvas.restoreState()

    SimpleDocTemplate(output, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm, topMargin=10*mm, bottomMargin=18*mm, title=data['assessment'] + ' report', author=data['school']).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
