import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_wellness_pdf(user_data, plan):
    """
    Generates a beautifully styled PDF report for the wellness plan.
    Returns: BytesIO object containing the PDF data.
    """
    buffer = io.BytesIO()
    
    # Page setup
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#2E8B57")     # Sea Green
    c_secondary = colors.HexColor("#4682B4")   # Steel Blue (subtle contrast)
    c_dark = colors.HexColor("#2F4F4F")        # Dark Slate
    c_light = colors.HexColor("#F4F7F6")       # Soft greenish white for table cells
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_primary,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=12,
        leading=16,
        textColor=c_dark,
        spaceAfter=20
    )
    
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primary,
        spaceBefore=15,
        spaceAfter=10,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=c_dark
    )
    
    bold_body_style = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )
    
    affirmation_style = ParagraphStyle(
        'AffirmationText',
        parent=body_style,
        fontName='Helvetica-Oblique',
        fontSize=12,
        leading=16,
        textColor=c_primary,
        alignment=1,  # Centered
        spaceBefore=8,
        spaceAfter=8
    )

    # 1. Header (Logo & Title)
    story.append(Paragraph("🧠 CalmMind AI", title_style))
    story.append(Paragraph("Your Personal Mental Wellness Companion", subtitle_style))
    
    # Divider line
    divider = Table([[""]], colWidths=[500], rowHeights=[2])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_primary),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 15))
    
    # 2. User Profile Summary Table
    story.append(Paragraph("User Profile Summary", section_title_style))
    
    profile_data = [
        [Paragraph("Name:", bold_body_style), Paragraph(user_data.get('name', 'N/A'), body_style),
         Paragraph("Occupation:", bold_body_style), Paragraph(user_data.get('occupation', 'N/A'), body_style)],
        [Paragraph("Stress Level:", bold_body_style), Paragraph(user_data.get('stress_level', 'N/A'), body_style),
         Paragraph("Avg Sleep Hours:", bold_body_style), Paragraph(f"{user_data.get('sleep_hours', 'N/A')} hours", body_style)],
        [Paragraph("Wellness Goal:", bold_body_style), Paragraph(user_data.get('goal', 'N/A'), body_style),
         Paragraph("Current Challenge:", bold_body_style), Paragraph(user_data.get('challenge', 'N/A'), body_style)]
    ]
    
    profile_table = Table(profile_data, colWidths=[100, 150, 100, 150])
    profile_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_light),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('BOX', (0,0), (-1,-1), 1, c_primary)
    ]))
    story.append(profile_table)
    story.append(Spacer(1, 15))
    
    # 3. Personalized Routines Section
    story.append(Paragraph("Personalized Daily Wellness Routines", section_title_style))
    
    routines_data = [
        [Paragraph("🌅 Morning Routine", bold_body_style), Paragraph("☀ Afternoon Routine", bold_body_style), Paragraph("🌙 Evening Routine", bold_body_style)]
    ]
    
    # Wrap routine lists in Paragraph flowables to prevent overflow
    morning_flowables = [Paragraph(f"• {step}", bullet_style) for step in plan.get('morning_routine', [])]
    afternoon_flowables = [Paragraph(f"• {step}", bullet_style) for step in plan.get('afternoon_routine', [])]
    evening_flowables = [Paragraph(f"• {step}", bullet_style) for step in plan.get('evening_routine', [])]
    
    routines_data.append([morning_flowables, afternoon_flowables, evening_flowables])
    
    routines_table = Table(routines_data, colWidths=[166, 166, 166])
    routines_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOX', (0,0), (-1,-1), 1, c_primary),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_primary),
    ]))
    
    # Fix header text color in table styles since we passed Paragraph
    routines_data[0] = [
        Paragraph("🌅 Morning Routine", ParagraphStyle('HCol1', parent=bold_body_style, textColor=colors.white, alignment=1)),
        Paragraph("☀ Afternoon Routine", ParagraphStyle('HCol2', parent=bold_body_style, textColor=colors.white, alignment=1)),
        Paragraph("🌙 Evening Routine", ParagraphStyle('HCol3', parent=bold_body_style, textColor=colors.white, alignment=1))
    ]
    
    story.append(routines_table)
    story.append(Spacer(1, 15))
    
    # 4. Breathing Exercise Section
    story.append(Paragraph("Recommended Breathing Exercise", section_title_style))
    
    b_exercise = plan.get('breathing_exercise', {})
    breathing_data = [
        [Paragraph("Exercise Name:", bold_body_style), Paragraph(b_exercise.get('name', 'N/A'), body_style)],
        [Paragraph("Duration:", bold_body_style), Paragraph(b_exercise.get('duration', 'N/A'), body_style)],
        [Paragraph("Instructions:", bold_body_style), Paragraph(b_exercise.get('instructions', 'N/A'), body_style)],
        [Paragraph("Benefits:", bold_body_style), Paragraph(b_exercise.get('benefits', 'N/A'), body_style)]
    ]
    
    breathing_table = Table(breathing_data, colWidths=[120, 380])
    breathing_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_light),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('BOX', (0,0), (-1,-1), 1, c_primary)
    ]))
    story.append(breathing_table)
    story.append(Spacer(1, 15))
    
    # 5. Affirmation & Weekly Guidance
    story.append(Paragraph("Daily Affirmation & Guidance", section_title_style))
    
    # Affirmation Card
    aff_text = plan.get('affirmation', 'I take each day one step at a time.')
    aff_card = Table([[Paragraph(f'"{aff_text}"', affirmation_style)]], colWidths=[500])
    aff_card.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EAF2EC")), # soft light green
        ('PADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, c_primary),
    ]))
    story.append(aff_card)
    story.append(Spacer(1, 10))
    
    # Weekly Guidance Checklist
    story.append(Paragraph("Weekly Mindful Milestones:", bold_body_style))
    for guide in plan.get('weekly_guidance', []):
        story.append(Paragraph(f"🌱 {guide}", bullet_style))
        
    story.append(Spacer(1, 25))
    
    # Footer timestamp
    timestamp_style = ParagraphStyle(
        'DocFooter',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        textColor=colors.gray,
        alignment=1  # Centered
    )
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y - %I:%M %p')} | CalmMind AI Wellness Program", timestamp_style))
    
    # Build document
    doc.build(story)
    
    buffer.seek(0)
    return buffer
