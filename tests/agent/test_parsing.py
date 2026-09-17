"""
Phase 2 parsing tests — no Ollama required.

Tests:
1. Pydantic schema validation (ParsedJD, ParsedResume)
2. PDF text extraction with pdfplumber
3. Node behaviour when inputs are missing
4. Prompt injection: JD content cannot override system prompt (structural check)

Run with:
    docker exec -it jobundo_fastapi python -m pytest tests/agent/test_parsing.py -v
"""
import io
import sys
import os
import uuid
import json

import pytest
from pydantic import ValidationError

# Add agent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../agent"))


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestParsedJD:
    def test_valid_full(self):
        from schemas import ParsedJD
        jd = ParsedJD(
            role_title="Software Engineer",
            company_name="Acme",
            required_skills=["Python", "Django"],
            preferred_skills=["Go"],
            experience_level="senior",
            responsibilities=["Build APIs"],
            ats_keywords=["Python", "REST"],
            red_flags=[],
            company_values=["transparency"],
        )
        assert jd.role_title == "Software Engineer"
        assert jd.experience_level == "senior"

    def test_defaults_on_empty(self):
        from schemas import ParsedJD
        jd = ParsedJD()
        assert jd.role_title == ""
        assert jd.required_skills == []
        assert jd.location is None

    def test_model_dump_is_serializable(self):
        from schemas import ParsedJD
        jd = ParsedJD(role_title="Engineer", company_name="Stripe")
        dumped = jd.model_dump()
        assert isinstance(dumped, dict)
        # Must be JSON-serializable (goes into AgentState → PostgreSQL JSONB)
        json.dumps(dumped)


class TestParsedResume:
    def test_valid_full(self):
        from schemas import ParsedResume, ContactInfo, WorkExperience
        resume = ParsedResume(
            contact_info=ContactInfo(name="Alex", email="alex@example.com"),
            work_experience=[
                WorkExperience(
                    company="Acme", role="Engineer",
                    responsibilities=["Built APIs"],
                    technologies=["Python"],
                )
            ],
            skills=["Python", "Django"],
            total_years_experience=3.5,
        )
        assert resume.contact_info.name == "Alex"
        assert len(resume.work_experience) == 1
        assert resume.total_years_experience == 3.5

    def test_defaults_on_empty(self):
        from schemas import ParsedResume
        resume = ParsedResume()
        assert resume.contact_info.name is None
        assert resume.work_experience == []
        assert resume.skills == []

    def test_model_dump_serializable(self):
        from schemas import ParsedResume
        resume = ParsedResume()
        json.dumps(resume.model_dump())


# ── PDF extraction tests ──────────────────────────────────────────────────────

def _make_pdf(text: str) -> bytes:
    """Create a real PDF from text using reportlab."""
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 750
    for line in text.split("\n"):
        c.drawString(50, y, line[:90])
        y -= 14
        if y < 50:
            c.showPage()
            y = 750
    c.save()
    return buffer.getvalue()


class TestPDFExtraction:
    def test_extract_real_pdf(self):
        from nodes.parse_resume import extract_text_from_pdf
        pdf_bytes = _make_pdf("Hello World\nThis is a test resume.")
        text = extract_text_from_pdf(pdf_bytes)
        assert "Hello" in text
        assert len(text) > 0

    def test_empty_bytes_returns_empty(self):
        from nodes.parse_resume import extract_text_from_pdf
        assert extract_text_from_pdf(b"") == ""

    def test_multi_line_pdf(self):
        from nodes.parse_resume import extract_text_from_pdf
        content = "Alex Johnson\nSoftware Engineer\nPython Django FastAPI"
        pdf_bytes = _make_pdf(content)
        text = extract_text_from_pdf(pdf_bytes)
        assert "Alex Johnson" in text or "Alex" in text  # pdfplumber may merge lines


# ── Node behaviour without Ollama ─────────────────────────────────────────────

def _base_state(**overrides) -> dict:
    state = {
        "run_id": str(uuid.uuid4()),
        "user_id": 1,
        "jd_raw": "",
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
    state.update(overrides)
    return state


class TestParseJDNode:
    def test_empty_jd_returns_error(self):
        """parse_jd should handle empty JD without calling LLM."""
        from nodes.parse_jd import parse_jd
        state = _base_state(jd_raw="")
        result = parse_jd(state)
        assert result["jd_parsed"] is None
        assert len(result["errors"]) > 0
        assert "empty" in result["errors"][0].lower()

    def test_returns_required_state_keys(self):
        """parse_jd should always return current_step and steps_completed."""
        from nodes.parse_jd import parse_jd
        state = _base_state(jd_raw="")
        result = parse_jd(state)
        assert "current_step" in result
        assert "steps_completed" in result
        assert result["current_step"] == "parse_jd"
        assert "parse_jd" in result["steps_completed"]


class TestParseResumeNode:
    def test_empty_bytes_returns_error(self):
        """parse_resume should handle missing PDF bytes without calling LLM."""
        from nodes.parse_resume import parse_resume
        state = _base_state(resume_pdf_bytes=b"")
        result = parse_resume(state)
        assert result["resume_parsed"] is None
        assert len(result["errors"]) > 0

    def test_returns_required_state_keys(self):
        from nodes.parse_resume import parse_resume
        state = _base_state(resume_pdf_bytes=b"")
        result = parse_resume(state)
        assert "current_step" in result
        assert "steps_completed" in result
        assert result["current_step"] == "parse_resume"


# ── Prompt injection structural check ─────────────────────────────────────────

class TestPromptInjectionGuard:
    """
    We can't fully test LLM prompt injection resistance without a live model.
    But we can verify the structural guards are in place in the prompts.
    """
    def test_jd_system_prompt_has_security_boundary(self):
        from nodes.parse_jd import SYSTEM_PROMPT
        assert "SECURITY BOUNDARY" in SYSTEM_PROMPT
        assert "data" in SYSTEM_PROMPT.lower() or "DATA" in SYSTEM_PROMPT

    def test_jd_user_prompt_wraps_content_in_delimiters(self):
        from nodes.parse_jd import USER_PROMPT
        assert "JOB DESCRIPTION START" in USER_PROMPT
        assert "JOB DESCRIPTION END" in USER_PROMPT

    def test_resume_system_prompt_has_anti_fabrication_rule(self):
        from nodes.parse_resume import SYSTEM_PROMPT
        # Must explicitly prohibit fabrication
        assert "NEVER" in SYSTEM_PROMPT or "never" in SYSTEM_PROMPT
        assert "fabricate" in SYSTEM_PROMPT.lower() or "invent" in SYSTEM_PROMPT.lower()

    def test_resume_user_prompt_wraps_content_in_delimiters(self):
        from nodes.parse_resume import USER_PROMPT
        assert "RESUME START" in USER_PROMPT
        assert "RESUME END" in USER_PROMPT
