"""
Agent node stubs — Phase 1.

Each function is a placeholder that will be implemented in its respective phase.
All nodes follow the same contract:
    Input:  AgentState  (the full graph state)
    Output: dict        (partial state — LangGraph merges this back in)

LangGraph merges only the keys you return. You don't have to return the full state.
"""
import logging
from state import AgentState

logger = logging.getLogger(__name__)


def _log(state: AgentState, node: str) -> None:
    logger.info(f"[run={state['run_id']}] node={node} (Phase 1 stub)")


def parse_jd(state: AgentState) -> dict:
    """
    Phase 2: Extract structured data from the raw job description.
    Output keys: jd_parsed
    """
    _log(state, "parse_jd")
    return {
        "current_step": "parse_jd",
        "steps_completed": ["parse_jd"],
        "jd_parsed": None,
    }


def parse_resume(state: AgentState) -> dict:
    """
    Phase 2: Extract structured data from the resume PDF bytes.
    Output keys: resume_parsed
    """
    _log(state, "parse_resume")
    return {
        "current_step": "parse_resume",
        "steps_completed": ["parse_resume"],
        "resume_parsed": None,
    }


def skill_gap_analysis(state: AgentState) -> dict:
    """
    Phase 4: Compare JD requirements against resume.
    Classifications: STRONG_MATCH | PARTIAL_MATCH | GAP | HIDDEN_STRENGTH
    Output keys: skill_alignment
    """
    _log(state, "skill_gap_analysis")
    return {
        "current_step": "skill_gap_analysis",
        "steps_completed": ["skill_gap_analysis"],
        "skill_alignment": None,
    }


def company_research(state: AgentState) -> dict:
    """
    Phase 5: RAG pipeline — fetch, chunk, embed, store, retrieve company data.
    Output keys: company_intelligence
    """
    _log(state, "company_research")
    return {
        "current_step": "company_research",
        "steps_completed": ["company_research"],
        "company_intelligence": None,
    }


def resume_rewriter(state: AgentState) -> dict:
    """
    Phase 6: Tailor resume to job. NEVER fabricate facts.
    Output keys: resume_rewritten
    """
    _log(state, "resume_rewriter")
    return {
        "current_step": "resume_rewriter",
        "steps_completed": ["resume_rewriter"],
        "resume_rewritten": None,
    }


def cover_letter_generator(state: AgentState) -> dict:
    """
    Phase 7: Generate personalised cover letter.
    Output keys: cover_letter_content
    """
    _log(state, "cover_letter_generator")
    return {
        "current_step": "cover_letter_generator",
        "steps_completed": ["cover_letter_generator"],
        "cover_letter_content": None,
    }


def cold_email_drafter(state: AgentState) -> dict:
    """
    Phase 7: Draft 3 cold outreach email variants.
    Output keys: cold_email_variants
    """
    _log(state, "cold_email_drafter")
    return {
        "current_step": "cold_email_drafter",
        "steps_completed": ["cold_email_drafter"],
        "cold_email_variants": [],
    }


def quality_checker(state: AgentState) -> dict:
    """
    Phase 8: Score output quality (0-100). Provide structured feedback for retry.
    Output keys: quality_score, quality_feedback, retry_count, retry_target_node
    """
    _log(state, "quality_checker")
    return {
        "current_step": "quality_checker",
        "steps_completed": ["quality_checker"],
        # Phase 1: always pass to avoid infinite loops
        "quality_score": 100,
        "quality_feedback": {},
        "retry_count": state.get("retry_count", 0),
        "retry_target_node": None,
    }


def package_store(state: AgentState) -> dict:
    """
    Phase 9: Generate PDFs and persist results to database.
    Output keys: resume_pdf, cover_letter_pdf
    """
    _log(state, "package_store")
    return {
        "current_step": "package_store",
        "steps_completed": ["package_store"],
        "resume_pdf": None,
        "cover_letter_pdf": None,
    }
