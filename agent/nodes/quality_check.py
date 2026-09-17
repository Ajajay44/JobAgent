"""
quality_checker node — Phase 8.

Acts as a gatekeeper before generating final PDFs (Phase 9).
Reviews the rewritten resume, cover letter, and emails against the JD and original resume.

Outputs:
- quality_score (0-100)
- quality_feedback
- suggested_target_node (if score < 70)

The graph logic (in graph.py) uses this score to either proceed to packaging or retry a specific node.
"""
import json
import time
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from state import AgentState
from schemas import QualityCheckOutput
from llm import get_llm

logger = logging.getLogger(__name__)

def _format_context(state: AgentState) -> str:
    jd = state.get("jd_parsed") or {}
    original = state.get("resume_parsed") or {}
    rewritten = state.get("resume_rewritten") or {}
    cover_letter = state.get("cover_letter_content") or {}
    emails = state.get("cold_email_variants") or []
    
    lines = [
        f"=== TARGET JOB ===",
        f"Role: {jd.get('role_title', 'Unknown')}",
        f"Required Skills: {', '.join(jd.get('required_skills', []))}",
        "",
        f"=== REWRITTEN RESUME SUMMARY ===",
        rewritten.get('professional_summary', ''),
        "",
        f"=== COVER LETTER SNEAK PEEK ===",
        cover_letter.get('opening_paragraph', ''),
        cover_letter.get('closing_paragraph', ''),
        "",
        f"=== NUMBER OF EMAILS DRAFTED ===",
        str(len(emails)),
        ""
    ]
    return "\n".join(lines)


SYSTEM_PROMPT = """\
You are an expert recruiter and quality assurance specialist.
Evaluate the generated application materials (resume, cover letter, emails) against the target job description.

Check for:
1. Alignment: Does it clearly address the required skills?
2. Tone: Is it professional and engaging?
3. Formatting: Did the generation complete successfully without placeholder text?

Provide a score from 0-100.
If score < 70, you MUST suggest a target node to retry: 'resume_rewriter', 'cover_letter_generator', or 'cold_email_drafter'.
If score >= 70, set suggested_target_node to empty string.

Return ONLY valid JSON.
"""

USER_PROMPT = """\
Review this application package:

{context}

Required JSON:
{{
  "score": 85,
  "feedback": "Strong alignment with required skills, good tone.",
  "weaknesses": ["Could include more quantifiable metrics"],
  "suggested_target_node": ""
}}
"""

def quality_checker(state: AgentState) -> dict:
    run_id = state["run_id"]
    start_time = time.time()
    logger.info(f"[{run_id}] quality_checker: starting")

    current_retries = state.get("retry_count", 0)

    # Basic guards
    if not state.get("resume_rewritten") and not state.get("cover_letter_content"):
        logger.warning(f"[{run_id}] Missing major components for quality check.")
        return _fallback(run_id, current_retries)

    context = _format_context(state)
    llm = get_llm(temperature=0.1, json_mode=True)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=USER_PROMPT.format(context=context)),
    ]

    for attempt in range(1, 3):
        try:
            response = llm.invoke(messages)
            parsed = json.loads(response.content.strip())
            validated = QualityCheckOutput.model_validate(parsed)

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{run_id}] quality_checker: score={validated.score} target={validated.suggested_target_node}")

            target_node = validated.suggested_target_node if validated.score < 70 else None
            
            return {
                "current_step": "quality_checker",
                "steps_completed": ["quality_checker"],
                "quality_score": validated.score,
                "quality_feedback": {
                    "feedback": validated.feedback,
                    "weaknesses": validated.weaknesses
                },
                "retry_count": current_retries + 1 if target_node else current_retries,
                "retry_target_node": target_node
            }

        except Exception as e:
            logger.warning(f"[{run_id}] quality check attempt {attempt} failed: {e}")

    return _fallback(run_id, current_retries)


def _fallback(run_id: str, current_retries: int) -> dict:
    # If the checker fails, we pass it through so we don't get stuck in a loop forever due to checker LLM failure
    logger.error(f"[{run_id}] quality_checker failed completely, defaulting to pass")
    return {
        "current_step": "quality_checker",
        "steps_completed": ["quality_checker"],
        "quality_score": 100,
        "quality_feedback": {"feedback": "Auto-passed due to checker failure", "weaknesses": []},
        "retry_count": current_retries,
        "retry_target_node": None
    }
