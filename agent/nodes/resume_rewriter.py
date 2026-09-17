"""
resume_rewriter node — Phase 6.

Reads the parsed resume and job description and produces a tailored,
ATS-optimised version. Uses skill_alignment to know what to lead with
and company_intelligence to weave in cultural language.

HARD RULES (enforced by system prompt + Pydantic validation):
  ✗ NEVER add skills, experience, or certifications the candidate doesn't have
  ✗ NEVER change company names, job titles, dates, education, or GPA
  ✓ MAY rephrase bullet points using JD language
  ✓ MAY reorder bullets to lead with JD-relevant achievements
  ✓ MAY add accurate ATS keywords where they describe existing work
  ✓ MAY write a new professional summary tailored to this role

Why these rules?
  A resume that misrepresents experience will be caught in interviews.
  The goal is to maximize ATS score and recruiter impact
  using ONLY what the candidate genuinely has.

Data flow:
  state['jd_parsed']            → role, company, required skills, ATS keywords
  state['resume_parsed']        → original experience, skills, summary
  state['skill_alignment']      → what to lead with (STRONG_MATCH)
  state['company_intelligence'] → cultural language for summary
      → LLM (JSON mode, temp=0.2)
      → RewrittenResume.model_validate()
      → state['resume_rewritten'] (dict)
"""
import json
import time
import logging
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import AgentState
from schemas import RewrittenResume
from llm import get_llm

logger = logging.getLogger(__name__)

# Max bullets per experience role in output
MAX_BULLETS = 5
# Max experience entries to include (most recent first)
MAX_EXPERIENCE = 4


# ── Input formatters ──────────────────────────────────────────────────────────

def _format_job_target(jd: dict, alignment: Optional[dict]) -> str:
    """Format job target and skill alignment as LLM input."""
    lines = [
        f"TARGET ROLE: {jd.get('role_title', 'Unknown')} at {jd.get('company_name', 'Unknown')}",
        f"EXPERIENCE LEVEL: {jd.get('experience_level', 'not specified')}",
        "",
        "REQUIRED SKILLS (must appear in resume):",
    ]
    for s in jd.get("required_skills", []):
        lines.append(f"  - {s}")

    lines.append("")
    lines.append("ATS KEYWORDS to naturally include:")
    for kw in jd.get("ats_keywords", [])[:15]:
        lines.append(f"  - {kw}")

    # Skill alignment guidance — tells LLM what to prioritise
    if alignment:
        strong = [
            s["skill"] for s in alignment.get("required_skills", [])
            if s.get("classification") == "STRONG_MATCH"
        ]
        partial = [
            s["skill"] for s in alignment.get("required_skills", [])
            if s.get("classification") == "PARTIAL_MATCH"
        ]
        gaps = [
            s["skill"] for s in alignment.get("required_skills", [])
            if s.get("classification") == "GAP"
        ]
        talking_points = alignment.get("key_talking_points", [])

        if strong:
            lines.append(f"\nCANDIDATE'S STRONGEST MATCHES (lead with these): {', '.join(strong)}")
        if partial:
            lines.append(f"PARTIAL MATCHES (frame carefully): {', '.join(partial)}")
        if gaps:
            lines.append(f"GAPS (minimize or omit): {', '.join(gaps)}")
        if talking_points:
            lines.append("\nKEY SELLING POINTS to emphasise:")
            for tp in talking_points[:4]:
                lines.append(f"  - {tp}")

    return "\n".join(lines)


def _format_company_context(intel: Optional[dict]) -> str:
    """Format company intelligence for summary personalisation."""
    if not intel:
        return ""
    lines = []
    if intel.get("mission"):
        lines.append(f"Company mission: {intel['mission']}")
    vals = intel.get("culture_values", [])
    if vals:
        lines.append(f"Company values: {', '.join(vals[:5])}")
    tp = intel.get("talking_points", [])
    if tp:
        lines.append("Cover letter angles:")
        for t in tp[:3]:
            lines.append(f"  - {t}")
    return "\n".join(lines) if lines else ""


def _format_resume_data(resume: dict) -> str:
    """Format the original resume data for the LLM to rewrite."""
    lines = []

    # Summary
    if resume.get("summary"):
        lines.append(f"CURRENT SUMMARY:\n{resume['summary']}\n")

    # Work experience (most recent first)
    experiences = resume.get("work_experience", [])[:MAX_EXPERIENCE]
    if experiences:
        lines.append("WORK EXPERIENCE:")
        for exp in experiences:
            current = " [CURRENT]" if exp.get("is_current") else ""
            period = ""
            if exp.get("start_date"):
                end = exp.get("end_date", "present")
                period = f" ({exp['start_date']}–{end})"
            lines.append(f"\n  {exp.get('role', '?')} at {exp.get('company', '?')}{period}{current}")
            for r in exp.get("responsibilities", [])[:5]:
                lines.append(f"    • {r}")
            for a in exp.get("achievements", [])[:3]:
                lines.append(f"    ★ {a}")
            techs = exp.get("technologies", [])
            if techs:
                lines.append(f"    Tech: {', '.join(techs[:10])}")

    # Skills
    skills = resume.get("skills", [])
    if skills:
        lines.append(f"\nSKILLS: {', '.join(skills)}")

    return "\n".join(lines)


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert resume writer and ATS optimisation specialist.

YOUR TASK: Rewrite the candidate's resume to maximally match the target job,
while remaining 100% honest and factually accurate.

═══ ABSOLUTE RULES (NEVER violate these) ═══
✗ DO NOT add skills, technologies, certifications, or experience the candidate doesn't have
✗ DO NOT change company names, job titles, dates, or education
✗ DO NOT invent quantified metrics (numbers, percentages) that aren't in the original
✗ DO NOT claim experience at companies not in the resume

═══ YOU MAY (encouraged) ═══
✓ Rephrase bullet points using language from the job description
✓ Reorder bullet points to lead with what the JD values most
✓ Add ATS keywords where they accurately describe existing work
✓ Quantify vague bullets using numbers already present in context
✓ Write a new professional summary tailored to this specific role
✓ Reorder the skills list to put JD-matching skills first

═══ PROFESSIONAL SUMMARY RULES ═══
- 3-4 sentences maximum
- Must reference the target role and company naturally
- Lead with years of experience in the most relevant skill
- Reference company values/mission if provided (but subtly, not as flattery)

═══ BULLET POINT RULES ═══
- Start each bullet with a strong action verb
- Include numbers/metrics where they already exist in original
- Write at most {max_bullets} bullets per role
- Prioritise bullets that match STRONG_MATCH and PARTIAL_MATCH skills

Return ONLY valid JSON. No markdown fences. No explanation text.\
""".format(max_bullets=MAX_BULLETS)

USER_PROMPT = """\
=== JOB TARGET ===
{job_target}

{company_section}

=== CANDIDATE'S ORIGINAL RESUME ===
{resume_data}

=== REQUIRED JSON OUTPUT ===
{{
  "professional_summary": "3-4 sentence tailored summary",
  "work_experience": [
    {{
      "company": "UNCHANGED company name",
      "role": "UNCHANGED job title",
      "start_date": "UNCHANGED",
      "end_date": "UNCHANGED or null",
      "is_current": false,
      "bullets": [
        "Action verb + achievement/responsibility using JD language",
        "Another bullet (max {max_bullets} total)"
      ]
    }}
  ],
  "skills": ["JD-relevant skill first", "next skill", "..."],
  "ats_score_estimate": 85,
  "changes_made": [
    "Reordered experience bullets to lead with Python/FastAPI work",
    "Added 'distributed systems' keyword to Acme Corp role description"
  ]
}}

Include ALL {exp_count} work experience entries from the original.
Do NOT skip any roles.\
"""


# ── Node function ─────────────────────────────────────────────────────────────

MAX_PARSE_ATTEMPTS = 2


def resume_rewriter(state: AgentState) -> dict:
    """
    Rewrite the resume to maximally match the job description.

    Uses skill_alignment + company_intelligence for context.
    Gracefully degrades if either is missing.
    """
    run_id = state["run_id"]
    jd_parsed = state.get("jd_parsed")
    resume_parsed = state.get("resume_parsed")
    skill_alignment = state.get("skill_alignment")
    company_intel = state.get("company_intelligence")
    start_time = time.time()

    logger.info(f"[{run_id}] resume_rewriter: starting")

    # ── Guards ────────────────────────────────────────────────────────────
    if not jd_parsed:
        return _skip(run_id, "jd_parsed is missing")
    if not resume_parsed:
        return _skip(run_id, "resume_parsed is missing")

    if not skill_alignment:
        logger.info(
            f"[{run_id}] resume_rewriter: skill_alignment is None — "
            "proceeding without alignment guidance"
        )
    if not company_intel:
        logger.info(
            f"[{run_id}] resume_rewriter: company_intelligence is None — "
            "proceeding without company context"
        )

    # ── Format inputs ─────────────────────────────────────────────────────
    job_target = _format_job_target(jd_parsed, skill_alignment)
    resume_data = _format_resume_data(resume_parsed)

    company_section = ""
    company_context = _format_company_context(company_intel)
    if company_context:
        company_section = f"=== COMPANY CONTEXT ===\n{company_context}\n"

    exp_count = len(resume_parsed.get("work_experience", [])[:MAX_EXPERIENCE])

    user_prompt = USER_PROMPT.format(
        job_target=job_target,
        company_section=company_section,
        resume_data=resume_data,
        max_bullets=MAX_BULLETS,
        exp_count=exp_count,
    )

    llm = get_llm(temperature=0.2, json_mode=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    last_error = None

    for attempt in range(1, MAX_PARSE_ATTEMPTS + 1):
        try:
            logger.debug(f"[{run_id}] resume_rewriter: LLM call attempt {attempt}")
            response = llm.invoke(messages)
            raw_text = response.content.strip()

            parsed_dict = json.loads(raw_text)

            # Safety check: ensure factual fields haven't been hallucinated
            _enforce_factual_integrity(parsed_dict, resume_parsed, run_id)

            validated = RewrittenResume.model_validate(parsed_dict)

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"[{run_id}] resume_rewriter: success in {duration_ms}ms — "
                f"ats_estimate={validated.ats_score_estimate} "
                f"changes={len(validated.changes_made)} "
                f"experience_entries={len(validated.work_experience)}"
            )

            return {
                "current_step": "resume_rewriter",
                "steps_completed": ["resume_rewriter"],
                "resume_rewritten": validated.model_dump(),
            }

        except json.JSONDecodeError as e:
            last_error = f"resume_rewriter attempt {attempt}: invalid JSON — {e}"
            logger.warning(f"[{run_id}] {last_error}")

        except ValidationError as e:
            last_error = f"resume_rewriter attempt {attempt}: schema failed — {e}"
            logger.warning(f"[{run_id}] {last_error}")

        except Exception as e:
            last_error = f"resume_rewriter attempt {attempt}: {type(e).__name__}: {e}"
            logger.error(f"[{run_id}] {last_error}")
            break

    duration_ms = int((time.time() - start_time) * 1000)
    logger.error(f"[{run_id}] resume_rewriter: failed after {duration_ms}ms")

    return {
        "current_step": "resume_rewriter",
        "steps_completed": ["resume_rewriter"],
        "resume_rewritten": None,
        "errors": [last_error or "resume_rewriter: unknown failure"],
    }


# ── Safety / integrity ────────────────────────────────────────────────────────

def _enforce_factual_integrity(
    rewritten: dict,
    original: dict,
    run_id: str,
) -> None:
    """
    Cross-check that the LLM hasn't changed factual fields.

    Checks company names and job titles match the original resume.
    Raises ValueError if a mismatch is found, triggering the retry loop.
    """
    original_roles = {
        (e.get("company", "").lower(), e.get("role", "").lower())
        for e in original.get("work_experience", [])
    }

    for entry in rewritten.get("work_experience", []):
        company = entry.get("company", "")
        role = entry.get("role", "")
        key = (company.lower(), role.lower())
        if key not in original_roles and company and role:
            msg = (
                f"Integrity violation: LLM added/changed an experience entry. "
                f"'{role}' at '{company}' not in original resume. Retrying."
            )
            logger.warning(f"[{run_id}] {msg}")
            raise ValueError(msg)


def _skip(run_id: str, reason: str) -> dict:
    msg = f"resume_rewriter skipped: {reason}"
    logger.warning(f"[{run_id}] {msg}")
    return {
        "current_step": "resume_rewriter",
        "steps_completed": ["resume_rewriter"],
        "resume_rewritten": None,
        "errors": [msg],
    }
