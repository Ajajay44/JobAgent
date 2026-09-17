"""
AgentState — the shared data structure flowing through the LangGraph workflow.

Every node in the graph reads from and writes to this TypedDict.
LangGraph manages merging node outputs back into the state between steps.

Design principles:
- All fields are explicitly typed — no surprise keys
- Annotated[List, operator.add] fields ACCUMULATE (append) across retries
- All other fields OVERWRITE on each node execution
- Optional fields start as None and are populated by their respective nodes
"""
from typing import TypedDict, Optional, List, Annotated
import operator


class AgentState(TypedDict):
    # ── Run identity ──────────────────────────────────────────────────────
    run_id: str          # UUID string, created by Django before calling FastAPI
    user_id: str         # Django user UUID — for DB writes and user isolation

    # ── Raw inputs from the user ──────────────────────────────────────────
    jd_raw: str                  # full job description text
    jd_url: Optional[str]        # optional URL (used by company_research node)
    resume_pdf_bytes: bytes      # the uploaded PDF as raw bytes
    user_tone: str               # e.g. "professional", "conversational"

    # ── Parsed intermediate data ──────────────────────────────────────────
    # Populated by: parse_jd (Phase 2)
    jd_parsed: Optional[dict]    # role_title, company, skills, keywords, etc.

    # Populated by: parse_resume (Phase 2)
    resume_parsed: Optional[dict]  # contact, experience, skills, education, etc.

    # ── Analysis ──────────────────────────────────────────────────────────
    # Populated by: skill_gap_analysis (Phase 4)
    skill_alignment: Optional[dict]      # STRONG_MATCH / PARTIAL_MATCH / GAP / HIDDEN_STRENGTH

    # Populated by: company_research (Phase 5)
    company_intelligence: Optional[dict]  # sourced from RAG pipeline

    # ── Generated outputs ─────────────────────────────────────────────────
    # Populated by: resume_rewriter (Phase 6)
    resume_rewritten: Optional[dict]

    # Populated by: cover_letter_generator (Phase 7)
    cover_letter_content: Optional[dict]  # structured cover letter

    # Populated by: cold_email_drafter (Phase 7)
    cold_email_variants: Optional[list]   # list of 3 EmailVariant dicts

    # Populated by: linkedin_referral_drafter (Phase 7)
    linkedin_referral: Optional[dict]     # connection_note + follow_up_message

    # ── Quality loop ──────────────────────────────────────────────────────
    # Populated by: quality_checker (Phase 8)
    quality_score: Optional[int]         # 0–100
    quality_feedback: Optional[dict]     # structured feedback for retry

    # Retry control
    retry_count: int                     # incremented on each retry
    retry_target_node: Optional[str]     # which node to jump back to

    # ── Final artifacts ───────────────────────────────────────────────────
    # Populated by: package_store (Phase 9)
    resume_pdf: Optional[bytes]
    cover_letter_pdf: Optional[bytes]

    # ── Observability ─────────────────────────────────────────────────────
    current_step: str

    # These use operator.add — LangGraph APPENDS new values rather than overwriting.
    # This is how we accumulate a log of all steps across retries.
    steps_completed: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
