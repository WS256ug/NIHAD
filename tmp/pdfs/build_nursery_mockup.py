from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
import pymupdf
out=Path('output/pdf'); out.mkdir(parents=True,exist_ok=True)
burgundy=colors.HexColor('#850029'); blush=colors.HexColor('#F8F1F3'); ink=colors.HexColor('#30282B'); muted=colors.HexColor('#70666A'); gold=colors.HexColor('#BD9550')
styles={
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=9,leading=13,textColor=ink),
 'small':ParagraphStyle('small',fontName='Helvetica',fontSize=8,leading=11,textColor=muted),
 'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=17,leading=20,textColor=burgundy),
 'white':ParagraphStyle('white',fontName='Helvetica-Bold',fontSize=9,leading=12,textColor=colors.white),
 'bold':ParagraphStyle('bold',fontName='Helvetica-Bold',fontSize=9,leading=13,textColor=ink),
}
def p(s,style='body'): return Paragraph(s,styles[style])
def bar(text):
 t=Table([[p(text,'white')]],colWidths=[511]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),burgundy),('LEFTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)])); return t
story=[]
head=Table([[Image('static/img/nihad-logo.jpg',width=65,height=65),p('NIHAD BABY SCHOOL<br/>AND DAY CARE','title')]],colWidths=[78,433]);head.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0)]));story += [head,Spacer(1,6),p('A CHILD TIME EXPERIENCE','small'),Spacer(1,12)]
t=Table([[p('BABY CLASS PROGRESS REPORT','bold'),p('2026  |  TERM 3  |  END OF TERM','small')]],colWidths=[281,230]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),blush),('BOX',(0,0),(-1,-1),0.5,gold),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]));story += [t,Spacer(1,12),bar('STUDENT INFORMATION')]
info=Table([[p('Student name','small'),p('Registration number','small'),p('Class / stream','small')],[p('Sample Learner','bold'),p('DEMO-001','bold'),p('Baby / East','bold')]],colWidths=[220,151,140]);info.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,0),8),('BOTTOMPADDING',(0,1),(-1,1),9)]));story += [info,Spacer(1,8),bar('LEARNING AND DEVELOPMENT')]
rows=[('Social Development','Achieved','Shares materials, greets others politely and joins group play.'),('My Environment','Developing','Names familiar places; is learning to describe different weather.'),('Personal Hygiene','Achieved','Washes hands independently and follows daily hygiene routines.'),('Numbers','Developing','Counts familiar objects with support and recognises basic shapes.'),('Language','Developing','Recognises familiar letter sounds and enjoys listening to stories.'),('Oral Expression','Achieved','Talks about familiar experiences and answers simple questions.'),('Pre-writing & Pre-reading','Developing','Enjoys colouring and picture reading; needs practice tracing lines.'),('Physical Development','Achieved','Runs, balances and participates confidently in movement games.')]
data=[[p('Learning area','white'),p('Progress level','white'),p('Teacher observation','white')]]+[[p(a,'bold'),p(b),p(c)] for a,b,c in rows]
t=Table(data,colWidths=[143,89,279]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),burgundy),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,blush]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,1),(-1,-1),0.35,colors.HexColor('#E5DADC'))]));story += [t,Spacer(1,9),p('<b>Progress key:</b> Emerging - beginning with support; Developing - growing confidence;<br/>Achieved - works independently; Excellent - applies skills confidently and consistently.','small'),Spacer(1,12),bar('COMMENTS AND NEXT STEPS')]
comments=Table([[p('CLASS TEACHER','small'),p('HEADTEACHER','small')],[p('A cheerful learner who enjoys group activities. Practise counting everyday objects and tracing lines at home.'),p('Good progress in confidence and independence. Continue supporting language through stories and conversation.')],[p('Signature: __________________','small'),p('Signature: __________________','small')]],colWidths=[255.5,255.5]); comments.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),blush),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEAFTER',(0,0),(0,-1),0.5,colors.white)])); story += [comments,Spacer(1,12)]
foot=Table([[p('<b>Next term begins:</b> To be confirmed','small'),p('SCHOOL STAMP','small')]],colWidths=[370,141],rowHeights=[38]);foot.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(1,0),(1,0),0.5,colors.HexColor('#D7C6CC')),('TOPPADDING',(0,0),(-1,-1),7)]));story +=[foot]
def footer(c,doc):
 c.setStrokeColor(gold);c.line(42,35,553,35);c.setFont('Helvetica',7);c.setFillColor(muted);c.drawString(42,24,'DESIGN MOCKUP - Fictional learner and illustrative observations');c.drawRightString(553,24,f'Page {doc.page}')
path=out/'nursery-progress-report-mockup.pdf'
SimpleDocTemplate(str(path),pagesize=(595,842),rightMargin=42,leftMargin=42,topMargin=30,bottomMargin=46).build(story,onFirstPage=footer,onLaterPages=footer)
d=pymupdf.open(path);print('Pages:',len(d));d[0].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save(str(out/'nursery-progress-report-mockup.png'))
