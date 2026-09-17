"""
linkedin_referral_drafter node — Phase 7 (user-requested feature).

Generates two LinkedIn messages using a two-step referral strategy:

Step 1 — Connection Note (≤300 chars, LinkedIn's hard limit):
  - Sent with the connection request
  - NO ask yet — just a genuine reason to connect
  - Specific to the company/role — not generic "I admire your company"
  - Goal: get the connection accepted

Step 2 — Follow-up Message (sent after they accept):
  - Warmer tone — they've accepted, there's rapport
  - More direct about the role and the referral ask
  - Clearly explains what you're asking (internal referral or just a chat)
  - Respects their time — gives them an easy out

Also provides:
  - who_to_target   — which LinkedIn roles/titles to search for
  - personalization_tips — how to customize these messages further

Why a two-step strategy?
  Asking for a referral in the connection request itself is the #1 mistake
  job seekers make on LinkedIn. It reads as transactional and gets ignored.
  Building even minimal rapport first (they accepted) dramatically increases
  response rates.

Temperature: 0.5 — warm and human, but still professional and focused.
"""
import json
import time
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import AgentState
from schemas import LinkedInReferralOutput
from llm import get_llm

logger = logging.getLogger(__name__)


# ── Context builder ───────────────────────────────────────────────────────────

def _format_context(state: AgentState) -> str:
    jd = state.get("jd_parsed") or {}
    intel = state.get("company_intelligence") or {}
    alignment = state.get("skill_alignment") or {}
    parsed = state.get("resume_parsed") or {}
    rewritten = state.get("resume_rewritten") or {}

    contact = parsed.get("contact_info", {})
    candidate_name = contact.get("name", "the candidate")
    years_exp = parsed.get("total_years_experience", "several")

    top_skills = (rewritten.get("skills") or parsed.get("skills", []))[:5]
    strong_matches = [
        s["skill"] for s in (alignment.get("required_skills") or [])
        if s.get("classification") == "STRONG_MATCH"
    ][:3]

    talking_points = alignment.get("key_talking_points", [])

    lines = [
        f"ROLE: {jd.get('role_title', 'Unknown')}",
        f"COMPANY: {jd.get('company_name', 'Unknown')}",
        f"CANDIDATE: {candidate_name}, {years_exp} years experience",
        f"STRONGEST SKILLS: {', '.join(strong_matches or top_skills[:3])}",
    ]

    if intel.get("mission"):
        lines.append(f"COMPANY MISSION: {intel['mission']}")
    if intel.get("culture_values"):
        lines.append(f"COMPANY VALUES: {', '.join(intel['culture_values'][:3])}")
    if talking_points:
        lines.append("CANDIDATE ANGLES:")
        for tp in talking_points[:2]:
            lines.append(f"  - {tp}")

    return "\n".join(lines)


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert LinkedIn outreach strategist helping a job seeker request a referral.

TWO-STEP STRATEGY:
1. Connection note (≤300 chars): get the connection accepted — NO ask yet
2. Follow-up message: sent after accepting — warmer, more direct about referral

CONNECTION NOTE RULES (CRITICAL):
- Hard limit: 300 characters INCLUDING spaces and punctuation
- Do NOT ask for referral here — just a genuine reason to connect
- Reference something specific about the company or role
- End with a soft, human note (not "I'd love to connect!")
- Count your characters carefully — MUST be ≤300

FOLLOW-UP MESSAGE RULES:
- 3-4 short paragraphs
- Start by thanking them for connecting
- Mention the specific role you're applying for
- Briefly why you're a strong fit (1-2 sentences max)
- Politely ask if they'd be comfortable providing a referral OR a 15-min chat
- Give them an easy out — "totally understand if not"

WHO TO TARGET:
- Search LinkedIn for employees in similar roles (engineers, PMs) at the company
- Avoid messaging the hiring manager directly — use peers
- Alumni connections are gold — always mention the common school/company

PERSONALIZATION TIPS: provide 3-4 specific, actionable tips

Return ONLY valid JSON. No markdown.\
"""

USER_PROMPT = """\
Create LinkedIn referral messages for this situation:

{context}

Required JSON:
{{
  "connection_note": "≤300 character message to send with connection request. NO referral ask. Be genuine and specific.",
  "follow_up_message": "Longer follow-up after they accept the connection. More direct about the referral request.",
  "personalization_tips": [
    "Search LinkedIn for '[Role] at [Company]' to find the right people to message",
    "Mention any alumni connection if you share a university or former employer",
    "Reference a specific project, blog post, or product feature they worked on",
    "If you have a mutual connection, name-drop them in the connection note"
  ],
  "who_to_target": "Look for Software Engineers, Engineering Managers, or Tech Leads at [Company] on LinkedIn — avoid messaging the hiring manager directly"
}}\
"""


# ── Node ──────────────────────────────────────────────────────────────────────

def linkedin_referral_drafter(state: AgentState) -> dict:
    """
    Generate LinkedIn referral request messages (connection note + follow-up).

    Uses a two-step approach:
    1. Connection note ≤300 chars (no ask — just connect)
    2. Follow-up message after acceptance (more direct referral ask)
    """
    run_id = state["run_id"]
    start_time = time.time()
    logger.info(f"[{run_id}] linkedin_referral_drafter: starting")

    if not state.get("jd_parsed"):
        return _skip(run_id, "jd_parsed is missing")

    context = _format_context(state)
    llm = get_llm(temperature=0.5, json_mode=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=USER_PROMPT.format(context=context)),
    ]

    for attempt in range(1, 3):
        try:
            response = llm.invoke(messages)
            parsed_dict = json.loads(response.content.strip())
            validated = LinkedInReferralOutput.model_validate(parsed_dict)

            # Enforce the 300-char LinkedIn limit
            if len(validated.connection_note) > 300:
                logger.warning(
                    f"[{run_id}] linkedin: connection_note too long "
                    f"({len(validated.connection_note)} chars) — truncating"
                )
                validated.connection_note = validated.connection_note[:297] + "..."

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"[{run_id}] linkedin_referral_drafter: done in {duration_ms}ms — "
                f"note={len(validated.connection_note)}chars "
                f"followup={len(validated.follow_up_message)}chars"
            )
            return {
                "current_step": "linkedin_referral_drafter",
                "steps_completed": ["linkedin_referral_drafter"],
                "linkedin_referral": validated.model_dump(),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"[{run_id}] linkedin attempt {attempt}: bad JSON — {e}")
        except ValidationError as e:
            logger.warning(f"[{run_id}] linkedin attempt {attempt}: schema — {e}")
        except Exception as e:
            logger.error(f"[{run_id}] linkedin attempt {attempt}: {type(e).__name__}: {e}")
            break

    ms = int((time.time() - start_time) * 1000)
    msg = f"linkedin_referral_drafter failed in {ms}ms"
    logger.error(f"[{run_id}] {msg}")
    return {"current_step": "linkedin_referral_drafter", "steps_completed": ["linkedin_referral_drafter"],
            "linkedin_referral": None, "errors": [msg]}


def _skip(run_id: str, reason: str) -> dict:
    logger.warning(f"[{run_id}] linkedin_referral_drafter skipped: {reason}")
    return {"current_step": "linkedin_referral_drafter", "steps_completed": ["linkedin_referral_drafter"],
            "linkedin_referral": None, "errors": [f"linkedin_referral_drafter: {reason}"]}
