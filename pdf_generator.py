"""
PDF Generator module: Formats Q&A into professional student worksheet answer sheets using ReportLab.
Converts Markdown formatting (bold, italic, bullets, headers, tables) into clean PDF flowables.
"""
import os
import re
from xml.sax.saxutils import escape as xml_escape
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import config


def format_text_markup(text: str) -> str:
    """Escapes XML and converts standard markdown inline syntax to ReportLab HTML tags."""
    if not text:
        return ""
    text = xml_escape(text)
    # Convert bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Convert italic: *text* -> <i>text</i>
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # Convert markdown headings ### -> bold colored text
    text = re.sub(r'(?m)^#{1,4}\s*(.+?)$', r'<b><font color="#0c2461">\1</font></b>', text)
    # Convert bullet points: * or - -> bullet symbol
    text = re.sub(r'(?m)^[\*\-]\s+', r'&bull;&nbsp;&nbsp;', text)
    # Linebreaks
    text = text.replace('\n', '<br/>')
    return text


def format_answer_flowables(raw_text: str, base_style: ParagraphStyle, cell_style: ParagraphStyle, cell_head_style: ParagraphStyle) -> list:
    """
    Parses answer text into ReportLab flowables:
    - Text blocks are converted with bold/italic/bullets/headers.
    - Markdown pipe tables (| a | b |) are converted into styled ReportLab Table flowables.
    """
    flowables = []
    lines = raw_text.strip().split('\n')
    i = 0
    text_buffer = []

    def flush_text():
        if text_buffer:
            combined = '\n'.join(text_buffer).strip()
            if combined:
                formatted = format_text_markup(combined)
                flowables.append(Paragraph(formatted, base_style))
            text_buffer.clear()

    while i < len(lines):
        line = lines[i].strip()
        # Detect markdown table block (lines starting and ending with |)
        if line.startswith('|') and line.endswith('|'):
            flush_text()
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                table_lines.append(lines[i].strip())
                i += 1

            table_data = []
            is_first = True
            for t_line in table_lines:
                # Check for separator line (e.g. |---|---|)
                cleaned = re.sub(r'[\s\-:|]', '', t_line)
                if not cleaned:
                    continue  # Skip separator line

                cells = [c.strip() for c in t_line.split('|')[1:-1]]
                row_cells = []
                for cell in cells:
                    cell_formatted = format_text_markup(cell)
                    st = cell_head_style if is_first else cell_style
                    row_cells.append(Paragraph(cell_formatted, st))
                if row_cells:
                    table_data.append(row_cells)
                    is_first = False

            if table_data:
                col_count = max(len(r) for r in table_data)
                # Pad rows that have fewer cells
                for r in table_data:
                    while len(r) < col_count:
                        r.append(Paragraph("", cell_style))
                col_width = 532.0 / col_count
                t = Table(table_data, colWidths=[col_width] * col_count)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8ecf1')),
                    ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#ced6e0')),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe4ea')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                flowables.append(Spacer(1, 4))
                flowables.append(t)
                flowables.append(Spacer(1, 6))
        else:
            text_buffer.append(lines[i])
            i += 1

    flush_text()
    return flowables


def generate_assignment_pdf(session_id: int, slo_num: int, qa_list: list, output_filename: str, output_dir: str = None, additional_qa_list: list = None, additional_title: str = "Additional Questions from DOCX Worksheet") -> str:
    """
    Builds an answer PDF sheet with header metadata and structured Q&A.
    output_dir: optional directory to save to (defaults to config.OUTPUT_DIR).
    additional_qa_list: optional additional questions/answers (e.g. from DOCX) to append below.
    """
    save_dir = output_dir or config.OUTPUT_DIR
    os.makedirs(save_dir, exist_ok=True)
    output_path = os.path.join(save_dir, output_filename)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1e3799"),
        fontName="Helvetica-Bold"
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=11,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2f3542"),
        fontName="Helvetica-Bold"
    )

    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2f3542")
    )

    q_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Heading3'],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0c2461"),
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=4
    )

    ans_style = ParagraphStyle(
        'AnswerStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e272e"),
        alignment=TA_JUSTIFY,
        spaceBefore=3,
        spaceAfter=6
    )

    cell_style = ParagraphStyle(
        'TableContentStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2f3542")
    )

    cell_head_style = ParagraphStyle(
        'TableHeaderStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0c2461"),
        fontName="Helvetica-Bold"
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("SRM INSTITUTE OF SCIENCE AND TECHNOLOGY", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Department of {config.DEPARTMENT}", subtitle_style))
    story.append(Paragraph(f"Course: {config.COURSE_CODE} - {config.COURSE_NAME}", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3799"), spaceAfter=10))

    # Meta Table (Student & Session info)
    unit_num = session_id // 100
    session_num = session_id % 100
    meta_data = [
        [
            Paragraph(f"<b>Student Name:</b> {getattr(config, 'STUDENT_NAME', config.FULL_NAME)}", meta_style),
            Paragraph(f"<b>Unit:</b> {unit_num} | <b>Session:</b> {session_num}", meta_style)
        ],
        [
            Paragraph(f"<b>Register No:</b> {config.USER_ID}", meta_style),
            Paragraph(f"<b>SLO:</b> {slo_num} (Code: {session_id}{slo_num})", meta_style)
        ],
        [
            Paragraph(f"<b>Specialisation & Section:</b> {getattr(config, 'SPECIALISATION_SECTION', getattr(config, 'SECTION', ''))}", meta_style),
            Paragraph(f"<b>Department:</b> {config.DEPARTMENT}", meta_style)
        ]
    ]

    meta_table = Table(meta_data, colWidths=[300, 232])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f2f6")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#ced6e0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # Q&A Items
    for idx, item in enumerate(qa_list, 1):
        q_text = format_text_markup(item.get('question', ''))
        story.append(Paragraph(f"<b>Q{idx}. {q_text}</b>", q_style))

        # Add "Answer:" label
        story.append(Paragraph("<b>Answer:</b>", ans_style))

        # Format and append answer content flowables (paragraphs and tables)
        ans_flowables = format_answer_flowables(
            item.get('answer', ''), ans_style, cell_style, cell_head_style
        )
        story.extend(ans_flowables)

        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dfe4ea"), spaceAfter=8))

    # Additional Q&A (e.g. from DOCX worksheet)
    if additional_qa_list:
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0c2461"), spaceAfter=10))
        story.append(Paragraph(f"<b>{additional_title.upper()}</b>", subtitle_style))
        story.append(Spacer(1, 8))

        start_num = len(qa_list) + 1
        for idx, item in enumerate(additional_qa_list, start_num):
            q_text = format_text_markup(item.get('question', ''))
            story.append(Paragraph(f"<b>Q{idx}. {q_text}</b>", q_style))
            story.append(Paragraph("<b>Answer:</b>", ans_style))
            ans_flowables = format_answer_flowables(
                item.get('answer', ''), ans_style, cell_style, cell_head_style
            )
            story.extend(ans_flowables)
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dfe4ea"), spaceAfter=8))

    doc.build(story)
    return output_path

