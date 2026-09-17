"""
package_store node — Phase 9.

Generates PDF documents for the rewritten resume and the cover letter
using ReportLab, and stores them in the state as raw bytes.

These bytes will be returned to the Django backend (via AgentRunResponse)
and saved to the Django database/S3.
"""
import io
import time
import logging
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListItem, ListFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from state import AgentState

logger = logging.getLogger(__name__)


def _generate_cover_letter_pdf(cover_letter: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=72, leftMargin=72,
        topMargin=72, bottomMargin=72
    )
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    
    story = []
    
    # Subject Line
    if cover_letter.get("subject_line"):
        story.append(Paragraph(f"<b>Subject:</b> {cover_letter['subject_line']}", normal_style))
        story.append(Spacer(1, 0.2 * inch))

    # Greeting
    if cover_letter.get("greeting"):
        story.append(Paragraph(cover_letter["greeting"], normal_style))
        story.append(Spacer(1, 0.2 * inch))

    # Opening Paragraph
    if cover_letter.get("opening_paragraph"):
        story.append(Paragraph(cover_letter["opening_paragraph"], normal_style))
        story.append(Spacer(1, 0.15 * inch))

    # Body Paragraphs
    for para in cover_letter.get("body_paragraphs", []):
        story.append(Paragraph(para, normal_style))
        story.append(Spacer(1, 0.15 * inch))

    # Closing Paragraph
    if cover_letter.get("closing_paragraph"):
        story.append(Paragraph(cover_letter["closing_paragraph"], normal_style))
        story.append(Spacer(1, 0.2 * inch))

    # Signoff
    if cover_letter.get("signoff"):
        story.append(Paragraph(cover_letter["signoff"], normal_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _generate_resume_pdf(original_resume: dict, rewritten_resume: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        name="ResumeTitle",
        parent=styles["Heading1"],
        alignment=1, # Center
        spaceAfter=14
    )
    heading_style = styles["Heading2"]
    normal_style = styles["Normal"]
    bullet_style = styles["Bullet"]
    
    story = []
    
    contact = original_resume.get("contact_info", {})
    name = contact.get("name", "Name Not Provided")
    story.append(Paragraph(name, title_style))
    
    # Contact info line
    contact_parts = []
    for field in ["email", "phone", "location", "linkedin", "github", "portfolio"]:
        val = contact.get(field)
        if val:
            contact_parts.append(val)
    if contact_parts:
        story.append(Paragraph(" | ".join(contact_parts), ParagraphStyle(name="Contact", parent=normal_style, alignment=1)))
    
    story.append(Spacer(1, 0.2 * inch))
    
    # Summary
    summary = rewritten_resume.get("professional_summary")
    if summary:
        story.append(Paragraph("Professional Summary", heading_style))
        story.append(Paragraph(summary, normal_style))
        story.append(Spacer(1, 0.15 * inch))
        
    # Experience
    experience = rewritten_resume.get("work_experience", [])
    if experience:
        story.append(Paragraph("Work Experience", heading_style))
        for exp in experience:
            role = exp.get("role", "")
            company = exp.get("company", "")
            start = exp.get("start_date", "")
            end = "Present" if exp.get("is_current") else exp.get("end_date", "")
            
            header_text = f"<b>{role}</b> — {company} ({start} - {end})"
            story.append(Paragraph(header_text, normal_style))
            
            bullet_items = [ListItem(Paragraph(b, bullet_style)) for b in exp.get("bullets", [])]
            if bullet_items:
                story.append(ListFlowable(bullet_items, bulletType='bullet', start='circle'))
                
            story.append(Spacer(1, 0.1 * inch))
            
    # Skills
    skills = rewritten_resume.get("skills", [])
    if skills:
        story.append(Paragraph("Skills", heading_style))
        story.append(Paragraph(", ".join(skills), normal_style))
        story.append(Spacer(1, 0.15 * inch))
        
    # Education
    education = original_resume.get("education", [])
    if education:
        story.append(Paragraph("Education", heading_style))
        for edu in education:
            inst = edu.get("institution", "")
            deg = edu.get("degree", "")
            fld = edu.get("field", "")
            yr = edu.get("graduation_year", "")
            
            edu_str = f"<b>{inst}</b>"
            if deg and fld:
                edu_str += f" — {deg} in {fld}"
            elif deg:
                edu_str += f" — {deg}"
            if yr:
                edu_str += f" ({yr})"
                
            story.append(Paragraph(edu_str, normal_style))
            story.append(Spacer(1, 0.05 * inch))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def package_store(state: AgentState) -> dict:
    run_id = state["run_id"]
    start_time = time.time()
    logger.info(f"[{run_id}] package_store: starting PDF generation")

    resume_pdf = None
    cover_letter_pdf = None
    errors = []

    rewritten_resume = state.get("resume_rewritten")
    original_resume = state.get("resume_parsed")
    cover_letter = state.get("cover_letter_content")

    if rewritten_resume and original_resume:
        try:
            resume_pdf = _generate_resume_pdf(original_resume, rewritten_resume)
            logger.info(f"[{run_id}] Generated resume PDF ({len(resume_pdf)} bytes)")
        except Exception as e:
            msg = f"Failed to generate resume PDF: {e}"
            logger.error(f"[{run_id}] {msg}")
            errors.append(msg)

    if cover_letter:
        try:
            cover_letter_pdf = _generate_cover_letter_pdf(cover_letter)
            logger.info(f"[{run_id}] Generated cover letter PDF ({len(cover_letter_pdf)} bytes)")
        except Exception as e:
            msg = f"Failed to generate cover letter PDF: {e}"
            logger.error(f"[{run_id}] {msg}")
            errors.append(msg)

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[{run_id}] package_store: done in {duration_ms}ms")

    return {
        "current_step": "package_store",
        "steps_completed": ["package_store"],
        "resume_pdf": resume_pdf,
        "cover_letter_pdf": cover_letter_pdf,
        "errors": errors
    }
