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

# ── Phase 6: Real implementation ──────────────────────────────────────────────
from nodes.resume_rewriter import resume_rewriter

# ── Phase 7: Real implementations ────────────────────────────────────────────
from nodes.cover_letter import cover_letter_generator
from nodes.cold_email import cold_email_drafter
from nodes.linkedin_referral import linkedin_referral_drafter

logger = logging.getLogger(__name__)


def _stub(state: AgentState, node: str) -> None:
    logger.info(f"[run={state['run_id']}] node={node} — stub (not yet implemented)")


# ── Phase 8: Real implementation ──────────────────────────────────────────────
from nodes.quality_check import quality_checker

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

