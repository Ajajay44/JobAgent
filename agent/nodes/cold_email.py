"""
cold_email_drafter node — Phase 7.

Generates 3 cold outreach email variants targeting different contexts:
  - formal       → HR / recruiter contact via job portal
  - casual       → warm intro to an engineer on the team
  - referral_style → asking a mutual connection for an intro

Each variant is complete with subject line + body.
The referral_style variant sets up the ask naturally without being pushy.

Temperature: 0.65 — emails need to sound human and varied.
"""
import json
import time
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import AgentState
from schemas import ColdEmailOutput
from llm import get_llm

logger = logging.getLogger(__name__)


# ── Context builder ───────────────────────────────────────────────────────────

def _format_context(state: AgentState) -> str:
    jd = state.get("jd_parsed") or {}
    intel = state.get("company_intelligence") or {}
    alignment = state.get("skill_alignment") or {}
    rewritten = state.get("resume_rewritten") or {}
    parsed = state.get("resume_parsed") or {}

    contact = parsed.get("contact_info", {})
    candidate_name = contact.get("name", "the candidate")
    years_exp = parsed.get("total_years_experience", "several")

    top_skills = (rewritten.get("skills") or parsed.get("skills", []))[:6]
    talking_points = alignment.get("key_talking_points", [])

    lines = [
        f"ROLE: {jd.get('role_title', 'Unknown')} at {jd.get('company_name', 'Unknown')}",
        f"CANDIDATE: {candidate_name}, {years_exp} years experience",
        f"TOP SKILLS: {', '.join(top_skills)}",
        f"TONE PREFERENCE: {state.get('user_tone', 'professional')}",
        "",
    ]
    if intel.get("mission"):
        lines.append(f"COMPANY MISSION: {intel['mission']}")
    if talking_points:
        lines.append("KEY ANGLES:")
        for tp in talking_points[:3]:
            lines.append(f"  - {tp}")

    return "\n".join(lines)


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert cold email copywriter for job seekers.
Write 3 distinct cold email variants for the same job application.

VARIANT TYPES:
1. formal       — professional, structured, appropriate for HR/recruiter
2. casual       — warm, conversational, for an engineer/peer on the team
3. referral_style — assumes a mutual connection or alumni angle; asks for an intro

RULES FOR ALL VARIANTS:
- Subject line: specific and compelling (not "Job Application")
- Under 200 words per email body — respect people's time
- Lead with VALUE or CONNECTION, not "I want a job"
- One specific detail that shows you researched the company
- Clear, single call to action at the end
- No attachments mentioned — keep it light for cold outreach

Return ONLY valid JSON. No markdown fences.\
"""

USER_PROMPT = """\
Write 3 cold email variants using this context:

{context}

Required JSON:
{{
  "variants": [
    {{
      "variant_type": "formal",
      "subject": "...",
      "body": "...",
      "tone_notes": "Use when contacting HR or via job portal messaging"
    }},
    {{
      "variant_type": "casual",
      "subject": "...",
      "body": "...",
      "tone_notes": "Use when reaching out to an engineer or team member on LinkedIn/email"
    }},
    {{
      "variant_type": "referral_style",
      "subject": "...",
      "body": "...",
      "tone_notes": "Use when you have a mutual connection or alumni link; sets up the ask"
    }}
  ]
}}\
"""


# ── Node ──────────────────────────────────────────────────────────────────────

def cold_email_drafter(state: AgentState) -> dict:
    run_id = state["run_id"]
    start_time = time.time()
    logger.info(f"[{run_id}] cold_email_drafter: starting")

    if not state.get("jd_parsed"):
        return _skip(run_id, "jd_parsed is missing")

    context = _format_context(state)
    llm = get_llm(temperature=0.65, json_mode=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=USER_PROMPT.format(context=context)),
    ]

    for attempt in range(1, 3):
        try:
            response = llm.invoke(messages)
            parsed = json.loads(response.content.strip())
            validated = ColdEmailOutput.model_validate(parsed)

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"[{run_id}] cold_email_drafter: done in {duration_ms}ms "
                f"— {len(validated.variants)} variants"
            )
            return {
                "current_step": "cold_email_drafter",
                "steps_completed": ["cold_email_drafter"],
                "cold_email_variants": [v.model_dump() for v in validated.variants],
            }
        except json.JSONDecodeError as e:
            logger.warning(f"[{run_id}] cold_email attempt {attempt}: bad JSON — {e}")
        except ValidationError as e:
            logger.warning(f"[{run_id}] cold_email attempt {attempt}: schema failed — {e}")
        except Exception as e:
            logger.error(f"[{run_id}] cold_email attempt {attempt}: {type(e).__name__}: {e}")
            break

    ms = int((time.time() - start_time) * 1000)
    msg = f"cold_email_drafter failed in {ms}ms"
    logger.error(f"[{run_id}] {msg}")
    return {"current_step": "cold_email_drafter", "steps_completed": ["cold_email_drafter"],
            "cold_email_variants": None, "errors": [msg]}


def _skip(run_id: str, reason: str) -> dict:
    logger.warning(f"[{run_id}] cold_email_drafter skipped: {reason}")
    return {"current_step": "cold_email_drafter", "steps_completed": ["cold_email_drafter"],
            "cold_email_variants": None, "errors": [f"cold_email_drafter: {reason}"]}
