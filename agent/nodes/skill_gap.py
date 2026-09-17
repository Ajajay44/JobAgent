"""
skill_gap_analysis node — Phase 4.

Reads jd_parsed and resume_parsed from state, calls Ollama to classify
each JD skill against the candidate's profile, then computes an overall
match score and strategic recommendations.

Classification system:
  STRONG_MATCH — candidate explicitly has this skill with resume evidence
  PARTIAL_MATCH — candidate has adjacent/related skill (e.g. Docker → Kubernetes)
  GAP           — skill required but not evidenced in resume

  hidden_strengths — valuable resume skills not mentioned in the JD
  (surfaced proactively by Phase 6: resume rewriter)

Why format as text, not raw JSON?
  The LLM reasons better over human-readable structured text than raw JSON
  blobs. We convert jd_parsed + resume_parsed → readable summaries, pass
  those in, and get structured JSON back.

Data flow:
  state['jd_parsed']     (dict from ParsedJD)
  state['resume_parsed'] (dict from ParsedResume)
      → format as readable summaries
      → Ollama (JSON mode)
      → json.loads() → SkillGapAnalysis.model_validate()
      → state['skill_alignment'] (dict)
"""
import json
import time
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import AgentState
from schemas import SkillGapAnalysis
from llm import get_llm

logger = logging.getLogger(__name__)

# Cap lists to avoid context overflow on small models (e.g. llama3.2:3b)
MAX_REQUIRED = 15
MAX_PREFERRED = 10
MAX_EXPERIENCE_ENTRIES = 4
MAX_ACHIEVEMENTS = 2


# ── Input formatters ──────────────────────────────────────────────────────────

def _format_jd(jd: dict) -> str:
    """Convert ParsedJD dict to a readable summary for the LLM."""
    lines = [
        f"Role: {jd.get('role_title', 'Unknown')}",
        f"Company: {jd.get('company_name', 'Unknown')}",
        f"Experience Level Required: {jd.get('experience_level', 'not specified')}",
        "",
        "REQUIRED SKILLS (must have):",
    ]
    required = jd.get("required_skills", [])[:MAX_REQUIRED]
    for s in required:
        lines.append(f"  - {s}")

    preferred = jd.get("preferred_skills", [])[:MAX_PREFERRED]
    if preferred:
        lines.append("")
        lines.append("PREFERRED SKILLS (nice to have):")
        for s in preferred:
            lines.append(f"  - {s}")

    responsibilities = jd.get("responsibilities", [])[:5]
    if responsibilities:
        lines.append("")
        lines.append("KEY RESPONSIBILITIES:")
        for r in responsibilities:
            lines.append(f"  - {r}")

    return "\n".join(lines)


def _format_resume(resume: dict) -> str:
    """Convert ParsedResume dict to a readable summary for the LLM."""
    contact = resume.get("contact_info", {})
    years = resume.get("total_years_experience")
    years_str = f"{years} years" if years else "unknown"

    lines = [
        f"Candidate: {contact.get('name', 'Unknown')}",
        f"Total Experience: {years_str}",
        "",
        "SKILLS:",
    ]
    for s in resume.get("skills", []):
        lines.append(f"  - {s}")

    experiences = resume.get("work_experience", [])[:MAX_EXPERIENCE_ENTRIES]
    if experiences:
        lines.append("")
        lines.append("WORK EXPERIENCE:")
        for exp in experiences:
            current = " [CURRENT]" if exp.get("is_current") else ""
            period = ""
            if exp.get("start_date"):
                period = f" ({exp['start_date']} – {exp.get('end_date', 'present')})"
            lines.append(f"  {exp.get('role', '?')} at {exp.get('company', '?')}{period}{current}")

            techs = exp.get("technologies", [])
            if techs:
                lines.append(f"    Tech: {', '.join(techs[:12])}")

            for ach in exp.get("achievements", [])[:MAX_ACHIEVEMENTS]:
                lines.append(f"    ✓ {ach}")

    certs = resume.get("certifications", [])
    if certs:
        lines.append("")
        lines.append("CERTIFICATIONS:")
        for c in certs:
            lines.append(f"  - {c}")

    return "\n".join(lines)


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior technical recruiter and skills analyst.
Your task: objectively classify how well a candidate's profile matches a job description.

CLASSIFICATION RULES (for required and preferred skills):
  STRONG_MATCH — candidate explicitly has this skill, evidenced in their resume
  PARTIAL_MATCH — candidate has adjacent/related skills (e.g. has Docker → Kubernetes asked)
  GAP — no evidence of this skill in the resume

HIDDEN STRENGTHS:
  List resume skills NOT explicitly in the JD but still valuable for this role.

SCORING:
  overall_match_score: 0–100 integer
    90–100: exceptional match     
    75–89:  strong match          
    60–74:  viable, some gaps     
    40–59:  significant gaps      
    <40:    poor fit

  experience_level_match: "above_target" | "matches" | "below_target"
  recommendation: "strong_candidate" | "viable_candidate" | "significant_gaps"

RULES:
  - Base ALL classifications on the resume evidence provided. Do not assume.
  - Be specific in the evidence field — cite role name or technology.
  - If a skill is a GAP, set evidence to null.
  - key_talking_points: what to emphasise in the resume / cover letter (3–5 points)
  - gaps_to_address: important missing skills (only true gaps, 1–4 points)

Return ONLY valid JSON. No markdown, no explanation.\
"""

USER_PROMPT = """\
Analyse this match and return the JSON structure:

=== JOB DESCRIPTION ===
{jd_summary}

=== CANDIDATE PROFILE ===
{resume_summary}

=== REQUIRED JSON STRUCTURE ===
{{
  "required_skills": [
    {{"skill": "Python", "classification": "STRONG_MATCH", "evidence": "5 years Python in 2 roles"}},
    {{"skill": "Kubernetes", "classification": "GAP", "evidence": null}}
  ],
  "preferred_skills": [
    {{"skill": "Go", "classification": "GAP", "evidence": null}}
  ],
  "hidden_strengths": ["System design", "High-availability architecture"],
  "overall_match_score": 78,
  "experience_level_match": "matches",
  "key_talking_points": [
    "Strong Python + FastAPI background with production scale",
    "Proven track record reducing latency by 40%"
  ],
  "gaps_to_address": ["Kubernetes — would need ramp-up time"],
  "recommendation": "viable_candidate"
}}

Classify ALL required and preferred skills listed above. Do not skip any.\
"""


# ── Node function ─────────────────────────────────────────────────────────────

MAX_PARSE_ATTEMPTS = 2


def skill_gap_analysis(state: AgentState) -> dict:
    """
    Classify JD skills against the candidate's resume profile.

    Requires: jd_parsed and resume_parsed (both from Phase 2).
    If either is missing (Phase 2 node failed), this node skips and
    adds an error — the graph continues through stubs.
    """
    run_id = state["run_id"]
    jd_parsed = state.get("jd_parsed")
    resume_parsed = state.get("resume_parsed")
    start_time = time.time()

    logger.info(f"[{run_id}] skill_gap_analysis: starting")

    # ── Guard: need both parsed inputs ────────────────────────────────────
    if not jd_parsed and not resume_parsed:
        return _skip(run_id, "both jd_parsed and resume_parsed are missing")
    if not jd_parsed:
        return _skip(run_id, "jd_parsed is missing — parse_jd must have failed")
    if not resume_parsed:
        return _skip(run_id, "resume_parsed is missing — parse_resume must have failed")

    # ── Format inputs for LLM ─────────────────────────────────────────────
    jd_summary = _format_jd(jd_parsed)
    resume_summary = _format_resume(resume_parsed)

    required_count = len(jd_parsed.get("required_skills", [])[:MAX_REQUIRED])
    preferred_count = len(jd_parsed.get("preferred_skills", [])[:MAX_PREFERRED])
    logger.debug(
        f"[{run_id}] skill_gap_analysis: "
        f"classifying {required_count} required + {preferred_count} preferred skills"
    )

    llm = get_llm(temperature=0.0, json_mode=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=USER_PROMPT.format(
            jd_summary=jd_summary,
            resume_summary=resume_summary,
        )),
    ]

    last_error = None

    for attempt in range(1, MAX_PARSE_ATTEMPTS + 1):
        try:
            logger.debug(f"[{run_id}] skill_gap_analysis: LLM call attempt {attempt}")
            response = llm.invoke(messages)
            raw_text = response.content.strip()

            parsed_dict = json.loads(raw_text)
            validated = SkillGapAnalysis.model_validate(parsed_dict)

            duration_ms = int((time.time() - start_time) * 1000)

            strong = sum(
                1 for s in validated.required_skills
                if s.classification == "STRONG_MATCH"
            )
            gaps = sum(
                1 for s in validated.required_skills
                if s.classification == "GAP"
            )

            logger.info(
                f"[{run_id}] skill_gap_analysis: done in {duration_ms}ms — "
                f"score={validated.overall_match_score} "
                f"strong={strong} gaps={gaps} "
                f"hidden={len(validated.hidden_strengths)} "
                f"recommendation={validated.recommendation}"
            )

            return {
                "current_step": "skill_gap_analysis",
                "steps_completed": ["skill_gap_analysis"],
                "skill_alignment": validated.model_dump(),
            }

        except json.JSONDecodeError as e:
            last_error = f"skill_gap_analysis attempt {attempt}: invalid JSON — {e}"
            logger.warning(f"[{run_id}] {last_error}")

        except ValidationError as e:
            last_error = f"skill_gap_analysis attempt {attempt}: schema validation failed — {e}"
            logger.warning(f"[{run_id}] {last_error}")

        except Exception as e:
            last_error = f"skill_gap_analysis attempt {attempt}: {type(e).__name__}: {e}"
            logger.error(f"[{run_id}] {last_error}")
            break

    duration_ms = int((time.time() - start_time) * 1000)
    logger.error(f"[{run_id}] skill_gap_analysis: all attempts failed in {duration_ms}ms")

    return {
        "current_step": "skill_gap_analysis",
        "steps_completed": ["skill_gap_analysis"],
        "skill_alignment": None,
        "errors": [last_error or "skill_gap_analysis: unknown failure"],
    }


def _skip(run_id: str, reason: str) -> dict:
    """Return a skip result when prerequisites aren't met."""
    msg = f"skill_gap_analysis skipped: {reason}"
    logger.warning(f"[{run_id}] {msg}")
    return {
        "current_step": "skill_gap_analysis",
        "steps_completed": ["skill_gap_analysis"],
        "skill_alignment": None,
        "errors": [msg],
    }
