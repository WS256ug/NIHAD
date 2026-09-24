"""PDF output shares the same immutable report data and authorization as HTML."""
from html import escape
from decimal import Decimal
from .formatting import report_number
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def document_pdf(title, subtitle, columns, rows, paragraphs=()):
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles['Title'].textColor = colors.HexColor('#174e48')
    styles['BodyText'].leading = 14
    def paragraph(value, style='BodyText'):
        return Paragraph(escape(report_number(value) if isinstance(value, Decimal) else str(value)).replace('\n', '<br/>'), styles[style])
    story = [paragraph(title, 'Title'), paragraph(subtitle), Spacer(1, 6 * mm)]
    if columns:
        data = [[paragraph(value) for value in columns]] + [[paragraph('' if value is None else value) for value in row] for row in rows]
        table = Table(data, repeatRows=1, hAlign='LEFT', colWidths=[(174 * mm) / len(columns)] * len(columns))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0f0eb')),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#174e48')),
            ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor('#d9e0dd')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story += [table, Spacer(1, 6 * mm)]
    for label, value in paragraphs:
        story += [paragraph(label, 'Heading3'), paragraph(value), Spacer(1, 3 * mm)]
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#52635e'))
        canvas.drawString(18 * mm, 12 * mm, 'School record · Private')
        canvas.drawRightString(192 * mm, 12 * mm, f'Page {doc.page}')
        canvas.restoreState()
    SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=22 * mm, title=title, author='School Administration').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def report_pdf(report):
    data = report.snapshot
    numeric = data['mode'] == 'numeric'
    columns = ['Subject', 'Score', 'Grade', 'Points'] if numeric else ['Learning area', 'Level']
    rows = [[row['subject'], report_number(row['score']), row['grade'], row['points']] if numeric else [row['subject'], row['grade']] for row in data['subjects']]
    details = [('Student', f"{data['student']} · {data['registration_number']}"), ('Class and period', f"{data['section']} / {data['class']} {data['stream']} · {data['year']} / {data['term']} / {data['assessment']}")]
    if numeric and data['average'] is not None:
        details.append(('Results', f"Total: {report_number(data['total'])} · Average: {report_number(data['average'])}% · Maximum per subject: {report_number(data['maximum_score'])}"))
    elif numeric:
        details.append(('Results', 'Absent for one or more subjects. Overall results and position are not calculated.'))
    if data['aggregate'] is not None:
        details.append(('Aggregate and division', f"Aggregate: {data['aggregate']} · Division: {data['division']}"))
    if data['position'] is not None:
        details.append(('Position', f"{data['position']} / {data['cohort_size']}"))
    details += [('Class-teacher comment', report.teacher_comment or 'Pending'), ('Headteacher comment', report.headteacher_comment or 'Pending')]
    return document_pdf(data['school'], f"Student report · {data['student']} · {data['registration_number']} · {report.get_status_display()} · Version {report.version}", columns, rows, details)
