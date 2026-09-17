"""
LangGraph agent workflow — Phase 7.

Topology:
    parse_jd
        ↓
    parse_resume
        ↓
    skill_gap_analysis
        ↓
    company_research
        ↓
    resume_rewriter
        ↓
    cover_letter_generator
        ↓
    cold_email_drafter
        ↓
    linkedin_referral_drafter       ← Phase 7 (new)
        ↓
    quality_checker
        ↓ (conditional)
    ┌───────────────────────────────┐
    │  score >= 70  → package_store │
    │  max retries  → package_store │
    │  score < 70   → retry target  │
    └───────────────────────────────┘
        ↓
    END
"""
import logging
from langgraph.graph import StateGraph, END

from state import AgentState
from nodes import (
    parse_jd,
    parse_resume,
    skill_gap_analysis,
    company_research,
    resume_rewriter,
    cover_letter_generator,
    cold_email_drafter,
    linkedin_referral_drafter,
    quality_checker,
    package_store,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
QUALITY_THRESHOLD = 70


def should_retry(state: AgentState) -> str:
    """
    Conditional edge function called after quality_checker.

    LangGraph reads the return value and uses it as the name of the next node.
    This is how we implement the retry loop without infinite recursion.
    """
    score = state.get("quality_score", 0) or 0
    retries = state.get("retry_count", 0)
    target = state.get("retry_target_node", "resume_rewriter")

    if score >= QUALITY_THRESHOLD:
        logger.info(f"[run={state['run_id']}] Quality check passed (score={score}). Packaging.")
        return "package_store"

    if retries >= MAX_RETRIES:
        logger.warning(
            f"[run={state['run_id']}] Max retries ({MAX_RETRIES}) reached. "
            f"Storing best-effort result."
        )
        return "package_store"

    logger.info(
        f"[run={state['run_id']}] Quality check failed (score={score}). "
        f"Retry {retries + 1}/{MAX_RETRIES} → {target}"
    )
    return target


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph agent workflow."""
    workflow = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────
    workflow.add_node("parse_jd", parse_jd)
    workflow.add_node("parse_resume", parse_resume)
    workflow.add_node("skill_gap_analysis", skill_gap_analysis)
    workflow.add_node("company_research", company_research)
    workflow.add_node("resume_rewriter", resume_rewriter)
    workflow.add_node("cover_letter_generator", cover_letter_generator)
    workflow.add_node("cold_email_drafter", cold_email_drafter)
    workflow.add_node("linkedin_referral_drafter", linkedin_referral_drafter)
    workflow.add_node("quality_checker", quality_checker)
    workflow.add_node("package_store", package_store)

    # ── Entry point ───────────────────────────────────────────────────────
    workflow.set_entry_point("parse_jd")

    # ── Linear edges ──────────────────────────────────────────────────────
    workflow.add_edge("parse_jd", "parse_resume")
    workflow.add_edge("parse_resume", "skill_gap_analysis")
    workflow.add_edge("skill_gap_analysis", "company_research")
    workflow.add_edge("company_research", "resume_rewriter")
    workflow.add_edge("resume_rewriter", "cover_letter_generator")
    workflow.add_edge("cover_letter_generator", "cold_email_drafter")
    workflow.add_edge("cold_email_drafter", "linkedin_referral_drafter")
    workflow.add_edge("linkedin_referral_drafter", "quality_checker")

    # ── Conditional retry edge ────────────────────────────────────────────
    # The keys of the mapping are all possible return values of should_retry().
    # LangGraph requires every possible return value to be mapped.
    workflow.add_conditional_edges(
        "quality_checker",
        should_retry,
        {
            "package_store": "package_store",
            "resume_rewriter": "resume_rewriter",
            "cover_letter_generator": "cover_letter_generator",
            "cold_email_drafter": "cold_email_drafter",
            "linkedin_referral_drafter": "linkedin_referral_drafter",
        },
    )

    workflow.add_edge("package_store", END)

    return workflow.compile()


# Module-level compiled graph — imported by main.py
agent_graph = build_graph()
