"""
cover_letter_generator node — Phase 7.

Generates a tailored, professional cover letter using:
  - jd_parsed        → role, company, responsibilities
  - resume_rewritten → professional summary + best achievements
  - skill_alignment  → what to lead with, key talking points
  - company_intel    → mission, values, talking points for personalisation

Output: CoverLetterOutput (structured + full_text as a single string)

Temperature: 0.6 — needs to write fluently, not robotically.
json_mode=True — we still want the structured fields for quality checking.
"""
import json
import time
import logging
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import AgentState
from schemas import CoverLetterOutput
from llm import get_llm

logger = logging.getLogger(__name__)


# ── Context builders ──────────────────────────────────────────────────────────

def _best_resume_data(state: AgentState) -> dict:
    """Use rewritten resume if available, fall back to original."""
    rewritten = state.get("resume_rewritten")
    parsed = state.get("resume_parsed") or {}
    if rewritten:
        return {
            "summary": rewritten.get("professional_summary", ""),
            "experience": rewritten.get("work_experience", []),
            "skills": rewritten.get("skills", []),
        }
    return {
        "summary": parsed.get("summary", ""),
        "experience": parsed.get("work_experience", []),
        "skills": parsed.get("skills", []),
    }


def _format_context(state: AgentState) -> str:
    jd = state.get("jd_parsed") or {}
    intel = state.get("company_intelligence") or {}
    alignment = state.get("skill_alignment") or {}
    resume = _best_resume_data(state)
    user_tone = state.get("user_tone", "professional")

    lines = [
        f"ROLE: {jd.get('role_title', 'Unknown')} at {jd.get('company_name', 'Unknown')}",
        f"TONE: {user_tone}",
        "",
    ]

    if intel.get("mission"):
        lines.append(f"COMPANY MISSION: {intel['mission']}")
    if intel.get("culture_values"):
        lines.append(f"COMPANY VALUES: {', '.join(intel['culture_values'][:4])}")
    if intel.get("talking_points"):
        lines.append("PERSONALISATION ANGLES:")
        for tp in intel["talking_points"][:3]:
            lines.append(f"  - {tp}")

    lines.append("")
    talking_points = alignment.get("key_talking_points", [])
    if talking_points:
        lines.append("CANDIDATE'S KEY SELLING POINTS:")
        for tp in talking_points[:4]:
            lines.append(f"  - {tp}")

    lines.append("")
    if resume["summary"]:
        lines.append(f"CANDIDATE SUMMARY: {resume['summary']}")

    lines.append("")
    lines.append("TOP ACHIEVEMENTS (use these as evidence):")
    exp_list = resume["experience"][:3]
    for exp in exp_list:
        role_label = f"{exp.get('role', '?')} at {exp.get('company', '?')}"
        # Support both 'bullets' (rewritten) and 'achievements' (original)
        bullets = exp.get("bullets", []) or exp.get("achievements", [])
        if bullets:
            lines.append(f"  [{role_label}]")
            for b in bullets[:3]:
                lines.append(f"    • {b}")

    return "\n".join(lines)


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert cover letter writer. Write a compelling, tailored cover letter
for the specified role.

STYLE RULES:
- 3-4 paragraphs, ~300-400 words total
- Opening: hook with genuine interest in THIS company and role (not generic)
- Body: evidence-based, specific achievements — no vague claims
- Closing: cultural fit + enthusiastic call to action
- Tone: matches the requested tone (professional/conversational/enthusiastic)
- Never use clichés: "I am writing to express my interest..." is forbidden
- Never mention salary, benefits, or personal circumstances

STRUCTURE RULES:
- opening_paragraph: 2-3 sentences, why THIS company specifically
- body_paragraphs: 2 paragraphs — one technical, one about growth/impact
- closing_paragraph: cultural fit + next step request
- full_text: the complete letter assembled as one string

Return ONLY valid JSON. No markdown fences.\
"""

USER_PROMPT = """\
Write a cover letter using the context below:

{context}

Required JSON output:
{{
  "subject_line": "Application for [Role] — [Candidate Name or top skill]",
  "greeting": "Dear Hiring Manager,",
  "opening_paragraph": "2-3 sentences hook",
  "body_paragraphs": [
    "First body paragraph: technical fit + specific achievement",
    "Second body paragraph: growth mindset + cultural alignment"
  ],
  "closing_paragraph": "Cultural fit reference + call to action",
  "signoff": "Sincerely,",
  "full_text": "Complete letter with all paragraphs assembled, separated by newlines",
  "word_count": 320
}}\
"""


# ── Node ──────────────────────────────────────────────────────────────────────

def cover_letter_generator(state: AgentState) -> dict:
    run_id = state["run_id"]
    start_time = time.time()
    logger.info(f"[{run_id}] cover_letter_generator: starting")

    if not state.get("jd_parsed"):
        return _skip(run_id, "jd_parsed is missing")
    if not state.get("resume_parsed") and not state.get("resume_rewritten"):
        return _skip(run_id, "no resume data available")

    context = _format_context(state)
    llm = get_llm(temperature=0.6, json_mode=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=USER_PROMPT.format(context=context)),
    ]

    for attempt in range(1, 3):
        try:
            response = llm.invoke(messages)
            parsed = json.loads(response.content.strip())
            validated = CoverLetterOutput.model_validate(parsed)

            # Auto-compute word count if not set by LLM
            if not validated.word_count and validated.full_text:
                validated.word_count = len(validated.full_text.split())

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"[{run_id}] cover_letter_generator: done in {duration_ms}ms "
                f"— words={validated.word_count}"
            )
            return {
                "current_step": "cover_letter_generator",
                "steps_completed": ["cover_letter_generator"],
                "cover_letter_content": validated.model_dump(),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"[{run_id}] cover_letter attempt {attempt}: bad JSON — {e}")
        except ValidationError as e:
            logger.warning(f"[{run_id}] cover_letter attempt {attempt}: schema failed — {e}")
        except Exception as e:
            logger.error(f"[{run_id}] cover_letter attempt {attempt}: {type(e).__name__}: {e}")
            break

    return _fail(run_id, "all attempts failed", start_time)


def _skip(run_id: str, reason: str) -> dict:
    logger.warning(f"[{run_id}] cover_letter_generator skipped: {reason}")
    return {"current_step": "cover_letter_generator", "steps_completed": ["cover_letter_generator"],
            "cover_letter_content": None, "errors": [f"cover_letter_generator: {reason}"]}


def _fail(run_id: str, reason: str, start_time: float) -> dict:
    ms = int((time.time() - start_time) * 1000)
    msg = f"cover_letter_generator failed in {ms}ms: {reason}"
    logger.error(f"[{run_id}] {msg}")
    return {"current_step": "cover_letter_generator", "steps_completed": ["cover_letter_generator"],
            "cover_letter_content": None, "errors": [msg]}
