"""
Phase 2 verification script.

Run inside the FastAPI container to test parse_jd and parse_resume
against a real Ollama instance:

    docker exec -it jobundo_fastapi python verify_phase2.py

What it tests:
1. Ollama connectivity
2. parse_jd on a sample job description
3. parse_resume on a sample resume text (converted to fake PDF bytes)

Expects Ollama to be running with the configured LLM_MODEL.
"""
import sys
import uuid
import json
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAMPLE_JD = """
Software Engineer — Backend (Python)
Stripe · San Francisco, CA (Hybrid) · Full-time

About the role:
We're looking for a backend Software Engineer to join our Payments Infrastructure team.
You'll design and build the systems that process millions of payments daily.

What you'll do:
- Design and implement scalable microservices in Python and Go
- Collaborate with product and design teams to build new payment features
- Write thorough tests and participate in code reviews
- On-call rotation for production systems

Requirements:
- 3+ years of experience in backend development
- Strong proficiency in Python (Django, FastAPI, or Flask)
- Experience with distributed systems and high-availability architectures
- Familiarity with PostgreSQL and Redis
- Experience with Docker and Kubernetes

Nice to have:
- Experience with Go
- Knowledge of payment systems or financial infrastructure
- Open source contributions

We value: user-first thinking, long-term quality, transparency, and diversity.
Salary: $130,000 – $180,000 + equity
"""

SAMPLE_RESUME_TEXT = """
Alex Johnson
alex.johnson@email.com | +1 (555) 123-4567 | San Francisco, CA
linkedin.com/in/alexjohnson | github.com/alexjohnson

PROFESSIONAL SUMMARY
Backend engineer with 5 years of experience building scalable Python services.
Passionate about distributed systems and developer tooling.

WORK EXPERIENCE

Senior Backend Engineer — Acme Corp (2021 – Present)
• Designed and built a microservices architecture handling 2M daily API requests
• Reduced p99 latency by 40% by migrating to async FastAPI from synchronous Django
• Led a team of 4 engineers on a payment integration project
• Tech: Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes

Backend Engineer — StartupXYZ (2019 – 2021)
• Built REST APIs serving 500K users using Django REST Framework
• Implemented background job processing with Celery and RabbitMQ
• Wrote comprehensive unit and integration tests (90% coverage)
• Tech: Python, Django, MySQL, Celery, AWS

SKILLS
Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS, Git

EDUCATION
B.Sc. Computer Science — UC Berkeley (2019)

CERTIFICATIONS
AWS Certified Developer — Associate
"""


def test_ollama_connection():
    """Check that Ollama is reachable."""
    import httpx
    from config import settings

    logger.info(f"Testing Ollama connection at {settings.ollama_base_url}...")
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        models = [m["name"] for m in response.json().get("models", [])]
        logger.info(f"✅ Ollama reachable. Available models: {models}")
        if settings.llm_model not in " ".join(models):
            logger.warning(
                f"⚠️  Configured model '{settings.llm_model}' not found in Ollama. "
                f"Pull it with: docker exec jobundo_ollama ollama pull {settings.llm_model}"
            )
        return True
    except Exception as e:
        logger.error(f"❌ Ollama not reachable: {e}")
        return False


def test_parse_jd():
    """Run parse_jd on a sample job description."""
    from nodes.parse_jd import parse_jd

    state = {
        "run_id": str(uuid.uuid4()),
        "user_id": 1,
        "jd_raw": SAMPLE_JD,
        "jd_url": None,
        "resume_pdf_bytes": b"",
        "user_tone": "professional",
        "jd_parsed": None,
        "resume_parsed": None,
        "skill_alignment": None,
        "company_intelligence": None,
        "resume_rewritten": None,
        "cover_letter_content": None,
        "cold_email_variants": None,
        "quality_score": None,
        "quality_feedback": None,
        "retry_count": 0,
        "retry_target_node": None,
        "resume_pdf": None,
        "cover_letter_pdf": None,
        "current_step": "",
        "steps_completed": [],
        "errors": [],
    }

    logger.info("\n" + "="*60)
    logger.info("TEST: parse_jd")
    logger.info("="*60)

    result = parse_jd(state)

    if result.get("jd_parsed"):
        jd = result["jd_parsed"]
        logger.info("✅ parse_jd succeeded")
        logger.info(f"  role_title:       {jd.get('role_title')}")
        logger.info(f"  company_name:     {jd.get('company_name')}")
        logger.info(f"  experience_level: {jd.get('experience_level')}")
        logger.info(f"  required_skills:  {jd.get('required_skills')}")
        logger.info(f"  ats_keywords:     {jd.get('ats_keywords')}")
        logger.info(f"  red_flags:        {jd.get('red_flags')}")
        return True
    else:
        logger.error(f"❌ parse_jd failed. Errors: {result.get('errors')}")
        return False


def test_parse_resume():
    """Run parse_resume using a fake PDF created from sample text."""
    from nodes.parse_resume import parse_resume
    from reportlab.pdfgen import canvas
    import io as io_module

    # Create a real PDF from sample text using reportlab
    logger.info("\n" + "="*60)
    logger.info("TEST: parse_resume")
    logger.info("="*60)

    buffer = io_module.BytesIO()
    c = canvas.Canvas(buffer)
    y = 750
    for line in SAMPLE_RESUME_TEXT.strip().split("\n"):
        c.drawString(50, y, line[:90])  # avoid overflow
        y -= 14
        if y < 50:
            c.showPage()
            y = 750
    c.save()
    pdf_bytes = buffer.getvalue()
    logger.info(f"Created test PDF ({len(pdf_bytes)} bytes)")

    state = {
        "run_id": str(uuid.uuid4()),
        "user_id": 1,
        "jd_raw": "",
        "jd_url": None,
        "resume_pdf_bytes": pdf_bytes,
        "user_tone": "professional",
        "jd_parsed": None,
        "resume_parsed": None,
        "skill_alignment": None,
        "company_intelligence": None,
        "resume_rewritten": None,
        "cover_letter_content": None,
        "cold_email_variants": None,
        "quality_score": None,
        "quality_feedback": None,
        "retry_count": 0,
        "retry_target_node": None,
        "resume_pdf": None,
        "cover_letter_pdf": None,
        "current_step": "",
        "steps_completed": [],
        "errors": [],
    }

    result = parse_resume(state)

    if result.get("resume_parsed"):
        resume = result["resume_parsed"]
        logger.info("✅ parse_resume succeeded")
        contact = resume.get("contact_info", {})
        logger.info(f"  name:            {contact.get('name')}")
        logger.info(f"  email:           {contact.get('email')}")
        logger.info(f"  work_experience: {len(resume.get('work_experience', []))} entries")
        logger.info(f"  skills:          {resume.get('skills')}")
        logger.info(f"  years_exp:       {resume.get('total_years_experience')}")
        return True
    else:
        logger.error(f"❌ parse_resume failed. Errors: {result.get('errors')}")
        return False


if __name__ == "__main__":
    logger.info("JobUndo — Phase 2 Verification")
    logger.info("================================\n")

    results = {}

    results["ollama"] = test_ollama_connection()

    if results["ollama"]:
        results["parse_jd"] = test_parse_jd()
        results["parse_resume"] = test_parse_resume()
    else:
        logger.error("Skipping node tests — Ollama not reachable.")
        results["parse_jd"] = False
        results["parse_resume"] = False

    logger.info("\n" + "="*60)
    logger.info("RESULTS")
    logger.info("="*60)
    all_passed = True
    for test, passed in results.items():
        icon = "✅" if passed else "❌"
        logger.info(f"  {icon} {test}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)
