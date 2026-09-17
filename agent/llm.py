"""
Centralized Ollama LLM client factory.

Why centralized?
- Changing models is a single env var change, not a code hunt
- All nodes use the same client configuration
- Easy to add retries, logging, or swap providers later

JSON mode:
- format="json" tells Ollama to guarantee syntactically valid JSON output
- This does NOT guarantee the JSON matches our schema — that's Pydantic's job
- Together they form a two-layer validation chain:
    Ollama (valid JSON) → Pydantic (correct structure) → AgentState
"""
import logging
from langchain_ollama import ChatOllama
from config import settings

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.1, json_mode: bool = True) -> ChatOllama:
    """
    Create and return a configured Ollama LLM instance.

    Args:
        temperature: Controls output randomness.
            0.0 = deterministic (good for structured extraction)
            0.7 = more creative (good for writing)
        json_mode: If True, Ollama enforces valid JSON output.
            Use True for parse_jd, parse_resume, quality_checker.
            Use False for cover_letter, cold_email (free-form prose).

    Returns:
        Configured ChatOllama instance, ready to invoke.
    """
    logger.debug(
        f"Creating LLM client: model={settings.llm_model} "
        f"temp={temperature} json_mode={json_mode}"
    )
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.llm_model,
        temperature=temperature,
        format="json" if json_mode else None,
        # Reasonable timeout — local models can be slow
        timeout=120,
    )
