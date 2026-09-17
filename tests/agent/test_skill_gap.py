"""
Phase 4 tests — Skill Gap Analysis

Tests that run WITHOUT Ollama:
1. Schema validation (SkillClassification, SkillGapAnalysis)
2. JD/resume input formatters
3. Node behaviour when inputs are missing or None
4. Prompt structural checks (security + instruction clarity)

Run with:
    docker exec -it jobundo_fastapi python -m pytest tests/agent/test_skill_gap.py -v
"""
import sys
import os
import uuid
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../agent"))


# ── Schema tests ──────────────────────────────────────────────────────────────

class TestSkillClassification:
    def test_strong_match(self):
        from schemas import SkillClassification
        sc = SkillClassification(
            skill="Python",
            classification="STRONG_MATCH",
            evidence="5 years Python at Acme Corp",
        )
        assert sc.classification == "STRONG_MATCH"
        assert sc.evidence is not None

    def test_gap_has_null_evidence(self):
        from schemas import SkillClassification
        sc = SkillClassification(skill="Kubernetes", classification="GAP")
        assert sc.evidence is None

    def test_model_dump_serializable(self):
        from schemas import SkillClassification
        sc = SkillClassification(skill="Docker", classification="PARTIAL_MATCH")
        json.dumps(sc.model_dump())


class TestSkillGapAnalysis:
    def test_defaults_on_empty(self):
        from schemas import SkillGapAnalysis
        analysis = SkillGapAnalysis()
        assert analysis.required_skills == []
        assert analysis.overall_match_score == 0
        assert analysis.recommendation == "unknown"

    def test_full_valid_analysis(self):
        from schemas import SkillGapAnalysis, SkillClassification
        analysis = SkillGapAnalysis(
            required_skills=[
                SkillClassification(skill="Python", classification="STRONG_MATCH",
                                    evidence="5 years"),
                SkillClassification(skill="Kubernetes", classification="GAP"),
            ],
            preferred_skills=[
                SkillClassification(skill="Go", classification="GAP"),
            ],
            hidden_strengths=["System design", "High-availability"],
            overall_match_score=78,
            experience_level_match="matches",
            key_talking_points=["Strong Python background", "Production scale"],
            gaps_to_address=["Kubernetes ramp-up needed"],
            recommendation="viable_candidate",
        )
        assert analysis.overall_match_score == 78
        assert len(analysis.required_skills) == 2
        assert len(analysis.hidden_strengths) == 2

    def test_model_dump_serializable(self):
        from schemas import SkillGapAnalysis, SkillClassification
        analysis = SkillGapAnalysis(
            required_skills=[SkillClassification(skill="Python", classification="STRONG_MATCH")],
            overall_match_score=85,
        )
        json.dumps(analysis.model_dump())


# ── Input formatter tests ─────────────────────────────────────────────────────

SAMPLE_JD = {
    "role_title": "Backend Engineer",
    "company_name": "Stripe",
    "experience_level": "senior",
    "required_skills": ["Python", "PostgreSQL", "Docker"],
    "preferred_skills": ["Go", "Terraform"],
    "responsibilities": ["Build APIs", "Maintain infrastructure"],
}

SAMPLE_RESUME = {
    "contact_info": {"name": "Alex Johnson"},
    "total_years_experience": 5.0,
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "work_experience": [
        {
            "company": "Acme Corp",
            "role": "Senior Backend Engineer",
            "is_current": True,
            "start_date": "2021",
            "end_date": None,
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
            "achievements": ["Reduced latency by 40%"],
        }
    ],
    "certifications": ["AWS Certified Developer"],
}


class TestInputFormatters:
    def test_format_jd_contains_role(self):
        from nodes.skill_gap import _format_jd
        result = _format_jd(SAMPLE_JD)
        assert "Backend Engineer" in result
        assert "Stripe" in result

    def test_format_jd_contains_all_required_skills(self):
        from nodes.skill_gap import _format_jd
        result = _format_jd(SAMPLE_JD)
        for skill in SAMPLE_JD["required_skills"]:
            assert skill in result, f"Skill '{skill}' missing from JD format"

    def test_format_resume_contains_candidate_name(self):
        from nodes.skill_gap import _format_resume
        result = _format_resume(SAMPLE_RESUME)
        assert "Alex Johnson" in result

    def test_format_resume_contains_skills(self):
        from nodes.skill_gap import _format_resume
        result = _format_resume(SAMPLE_RESUME)
        assert "Python" in result
        assert "FastAPI" in result

    def test_format_resume_contains_experience(self):
        from nodes.skill_gap import _format_resume
        result = _format_resume(SAMPLE_RESUME)
        assert "Acme Corp" in result
        assert "Senior Backend Engineer" in result

    def test_format_jd_caps_skills_at_max(self):
        from nodes.skill_gap import _format_jd, MAX_REQUIRED
        jd = {**SAMPLE_JD, "required_skills": [f"skill{i}" for i in range(30)]}
        result = _format_jd(jd)
        # Should not contain skills beyond MAX_REQUIRED
        count = result.count("skill")
        assert count <= MAX_REQUIRED


# ── Node behaviour without Ollama ─────────────────────────────────────────────

def _base_state(**overrides) -> dict:
    state = {
        "run_id": str(uuid.uuid4()),
        "user_id": "user-uuid-123",
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


class TestSkillGapNode:
    def test_skips_when_both_none(self):
        """Node should skip gracefully when both parsed inputs are None."""
        from nodes.skill_gap import skill_gap_analysis
        state = _base_state(jd_parsed=None, resume_parsed=None)
        result = skill_gap_analysis(state)
        assert result["skill_alignment"] is None
        assert len(result["errors"]) > 0
        assert "missing" in result["errors"][0].lower()

    def test_skips_when_jd_none(self):
        from nodes.skill_gap import skill_gap_analysis
        state = _base_state(jd_parsed=None, resume_parsed={"contact_info": {}})
        result = skill_gap_analysis(state)
        assert result["skill_alignment"] is None
        assert any("jd_parsed" in e for e in result["errors"])

    def test_skips_when_resume_none(self):
        from nodes.skill_gap import skill_gap_analysis
        state = _base_state(jd_parsed={"role_title": "Eng"}, resume_parsed=None)
        result = skill_gap_analysis(state)
        assert result["skill_alignment"] is None
        assert any("resume_parsed" in e for e in result["errors"])

    def test_always_returns_required_state_keys(self):
        """Node must always return current_step and steps_completed."""
        from nodes.skill_gap import skill_gap_analysis
        state = _base_state()
        result = skill_gap_analysis(state)
        assert "current_step" in result
        assert "steps_completed" in result
        assert result["current_step"] == "skill_gap_analysis"
        assert "skill_gap_analysis" in result["steps_completed"]


# ── Prompt structural checks ──────────────────────────────────────────────────

class TestPromptDesign:
    def test_system_prompt_has_classification_rules(self):
        from nodes.skill_gap import SYSTEM_PROMPT
        assert "STRONG_MATCH" in SYSTEM_PROMPT
        assert "PARTIAL_MATCH" in SYSTEM_PROMPT
        assert "GAP" in SYSTEM_PROMPT

    def test_system_prompt_has_scoring_guidance(self):
        from nodes.skill_gap import SYSTEM_PROMPT
        assert "overall_match_score" in SYSTEM_PROMPT

    def test_user_prompt_has_jd_and_resume_placeholders(self):
        from nodes.skill_gap import USER_PROMPT
        assert "{jd_summary}" in USER_PROMPT
        assert "{resume_summary}" in USER_PROMPT

    def test_user_prompt_has_classify_all_instruction(self):
        """Prompt must tell LLM to classify ALL skills, not just some."""
        from nodes.skill_gap import USER_PROMPT
        prompt_lower = USER_PROMPT.lower()
        assert "all" in prompt_lower and "skip" in prompt_lower

    def test_user_prompt_has_json_example(self):
        """Prompt includes a JSON example to guide output format."""
        from nodes.skill_gap import USER_PROMPT
        assert "STRONG_MATCH" in USER_PROMPT
        assert "overall_match_score" in USER_PROMPT
