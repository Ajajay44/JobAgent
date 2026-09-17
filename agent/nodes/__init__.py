"""
Agent nodes — Phase 2.

parse_jd and parse_resume are now real LLM-powered implementations.
All other nodes remain stubs — they will be replaced phase by phase.

Import pattern: graph.py always imports from this package.
Node files (parse_jd.py, parse_resume.py, etc.) contain the actual logic.
This file is the single public interface — graph.py never changes its imports.
"""
import logging
from state import AgentState

# ── Phase 2: Real implementations ─────────────────────────────────────────────
from nodes.parse_jd import parse_jd
from nodes.parse_resume import parse_resume

# ── Phase 4: Real implementation ──────────────────────────────────────────────
from nodes.skill_gap import skill_gap_analysis

# ── Phase 5: Real implementation ──────────────────────────────────────────────
from nodes.company_research import company_research

logger = logging.getLogger(__name__)


def _stub(state: AgentState, node: str) -> None:
    logger.info(f"[run={state['run_id']}] node={node} — stub (not yet implemented)")



# ── Phase 6 stub ──────────────────────────────────────────────────────────────
def resume_rewriter(state: AgentState) -> dict:
    """Phase 6: Tailor resume to job. NEVER fabricate facts."""
    _stub(state, "resume_rewriter")
    return {
        "current_step": "resume_rewriter",
        "steps_completed": ["resume_rewriter"],
        "resume_rewritten": None,
    }


# ── Phase 7 stubs ─────────────────────────────────────────────────────────────
def cover_letter_generator(state: AgentState) -> dict:
    """Phase 7: Generate personalised cover letter."""
    _stub(state, "cover_letter_generator")
    return {
        "current_step": "cover_letter_generator",
        "steps_completed": ["cover_letter_generator"],
        "cover_letter_content": None,
    }


def cold_email_drafter(state: AgentState) -> dict:
    """Phase 7: Draft 3 cold outreach email variants."""
    _stub(state, "cold_email_drafter")
    return {
        "current_step": "cold_email_drafter",
        "steps_completed": ["cold_email_drafter"],
        "cold_email_variants": [],
    }


# ── Phase 8 stub ──────────────────────────────────────────────────────────────
def quality_checker(state: AgentState) -> dict:
    """Phase 8: Score output quality (0-100). Always passes until Phase 8."""
    _stub(state, "quality_checker")
    return {
        "current_step": "quality_checker",
        "steps_completed": ["quality_checker"],
        "quality_score": 100,
        "quality_feedback": {},
        "retry_count": state.get("retry_count", 0),
        "retry_target_node": None,
    }


# ── Phase 9 stub ──────────────────────────────────────────────────────────────
def package_store(state: AgentState) -> dict:
    """Phase 9: Generate PDFs and persist results to database."""
    _stub(state, "package_store")
    return {
        "current_step": "package_store",
        "steps_completed": ["package_store"],
        "resume_pdf": None,
        "cover_letter_pdf": None,
    }

