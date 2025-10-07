import os
import re
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus.frames import Frame

# --- CONFIGURATION ---
OUTPUT_DIR = "output/"

# --- STYLES ---
styles = getSampleStyleSheet()

# Custom Title Style
title_style = ParagraphStyle(
    name='TitleStyle',
    parent=styles['h1'],
    fontSize=18,
    leading=22,
    alignment=TA_CENTER,
    spaceAfter=0.2 * inch,
)

# Custom Header Style
header_style = ParagraphStyle(
    name='HeaderStyle',
    parent=styles['h2'],
    fontSize=14,
    leading=18,
    alignment=TA_LEFT,
    spaceBefore=0.15 * inch,
    spaceAfter=0.1 * inch,
)

# Custom Body Text Style
body_style = ParagraphStyle(
    name='BodyStyle',
    parent=styles['Normal'],
    fontSize=11,
    leading=13,
    alignment=TA_LEFT,
    spaceAfter=0.05 * inch,
)

# --- PAGE TEMPLATE ---
def page_template(canvas, doc):
    canvas.saveState()
    # Footer
    footer_text = f"Page {doc.page}"
    canvas.setFont('Helvetica', 9)
    canvas.drawString(letter[0] - inch, 0.75 * inch, footer_text)
    canvas.restoreState()

def generate_pdf(input_txt_path, output_pdf_path):
    """Converts a text file into a styled PDF document."""
    doc = SimpleDocTemplate(output_pdf_path, pagesize=letter)
    story = []

    # Define frames for the page template
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    doc.addPageTemplates([PageTemplate(id='OneCol', frames=frame, onPage=page_template)])

    with open(input_txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Extract Title (first non-empty line)
    title = ""
    content_lines = []
    for line in lines:
        if line.strip():
            title = line.strip()
            content_lines = lines[lines.index(line) + 1:]
            break
    
    if title:
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.2 * inch))

    # Process remaining lines
    in_table = False
    table_data = []
    for line in content_lines:
        stripped_line = line.strip()

        # Handle table detection
        if stripped_line.startswith('|') and stripped_line.endswith('|'):
            if not in_table:
                in_table = True
                table_data = []
            table_data.append([cell.strip() for cell in stripped_line.split('|')[1:-1]])
            continue
        elif in_table:
            # End of table
            from reportlab.platypus import Table, TableStyle
            from reportlab.lib import colors
            if table_data:
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 12),
                    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('BOX', (0,0), (-1,-1), 1, colors.black),
                ]))
                story.append(table)
                story.append(Spacer(1, 0.2 * inch))
            in_table = False
            table_data = []

        if in_table:
            continue

        # Handle --- separator
        if stripped_line == '---':
            story.append(Spacer(1, 0.5 * inch))
            continue

        if not stripped_line:
            story.append(Spacer(1, 0.1 * inch)) # Add space for empty lines
            continue

        # Convert Markdown bold/italic to HTML-like tags for ReportLab
        # Handle bold first, then italic, to ensure proper nesting if they overlap
        processed_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', stripped_line)
        processed_line = re.sub(r'\*(.*?)\*', r'<i>\1</i>', processed_line)

        # Check for sub-headers (###)
        if processed_line.startswith('### '):
            story.append(Paragraph(processed_line[4:], header_style))
            story.append(Spacer(1, 0.05 * inch))
        # Check for bullet points (*)
        elif processed_line.startswith('* '):
            story.append(Paragraph(f"  • {processed_line[2:]}", body_style))
        # Check for numbered lists
        elif re.match(r'^\d+\.\s', processed_line):
            story.append(Paragraph(f"  {processed_line}", body_style))
        # Check for labels (Title:, URL:, Summary:, Description:)
        elif re.match(r'^(Title|URL|Summary|Description):\s', processed_line):
            parts = processed_line.split(':', 1)
            if len(parts) == 2:
                label = parts[0].strip()
                content = parts[1].strip()
                story.append(Paragraph(f"<b>{label}:</b> {content}", body_style))
            else:
                story.append(Paragraph(processed_line, body_style))
        # Handle <ul><li> tags within text (e.g., from LLM output in tables)
        elif '<ul' in processed_line or '<li' in processed_line:
            # Simple conversion for now, can be improved with more robust HTML parsing
            processed_line = processed_line.replace('<ul>', '').replace('</ul>', '')
            processed_line = processed_line.replace('<li>', '  • ').replace('</li>', '')
            story.append(Paragraph(processed_line, body_style))
        else:
            story.append(Paragraph(processed_line, body_style))

    try:
        doc.build(story)
        print(f"Successfully generated PDF: {output_pdf_path}")
    except Exception as e:
        print(f"Error generating PDF {output_pdf_path}: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    summary_a_txt = os.path.join(OUTPUT_DIR, "summary_A.txt")
    summary_b_txt = os.path.join(OUTPUT_DIR, "summary_B.txt")

    summary_a_pdf = os.path.join(OUTPUT_DIR, "summary_A.pdf")
    summary_b_pdf = os.path.join(OUTPUT_DIR, "summary_B.pdf")

    if os.path.exists(summary_a_txt):
        generate_pdf(summary_a_txt, summary_a_pdf)
    else:
        print(f"Error: {summary_a_txt} not found. Please run app.py first.")

    if os.path.exists(summary_b_txt):
        generate_pdf(summary_b_txt, summary_b_pdf)
    else:
        print(f"Error: {summary_b_txt} not found. Please run app.py first.")