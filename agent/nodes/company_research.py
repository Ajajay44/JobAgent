"""
company_research node — Phase 5.

Full RAG pipeline:
  1. Fetch  — scrape job URL and/or company website with httpx + BeautifulSoup
  2. Chunk  — split text into overlapping chunks (RecursiveCharacterTextSplitter)
  3. Embed  — nomic-embed-text via OllamaEmbeddings
  4. Store  — pgvector (langchain-postgres PGVector)
  5. Retrieve — similarity search for role-relevant chunks
  6. Synthesise — LLM produces CompanyIntelligence from retrieved context

Fallback chain (graceful degradation):
  Web scrape succeeds        → source="web_scraped", confidence="high"
  Web scrape fails, JD exists → LLM extracts from JD text directly
                                source="jd_only", confidence="medium"
  Both fail                  → minimal stub, confidence="low"

The node NEVER blocks the rest of the pipeline.
If all data sources fail, it returns None and the pipeline continues —
the cover letter / emails will simply have less personalisation.

Data flow:
  state['jd_url'], state['jd_parsed'], state['jd_raw']
      → web fetch (if URL available)
      → text cleaning + chunking
      → OllamaEmbeddings (nomic-embed-text)
      → PGVector store + similarity_search
      → LLM synthesis
      → CompanyIntelligence.model_validate()
      → state['company_intelligence'] (dict)
"""
import re
import json
import time
import logging
from typing import List, Optional, Tuple

import httpx
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from pydantic import ValidationError

from state import AgentState
from schemas import CompanyIntelligence
from llm import get_llm
from config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
TOP_K_CHUNKS = 5          # chunks to retrieve for synthesis
MAX_TEXT_CHARS = 15_000   # cap per URL to avoid context overflow
FETCH_TIMEOUT = 10        # seconds per HTTP request
MAX_CONTEXT_CHARS = 4000  # total retrieved context passed to LLM


# ── Web fetching ──────────────────────────────────────────────────────────────

SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# LinkedIn and auth-gated sites we know won't work without a session
BLOCKED_DOMAINS = {"linkedin.com", "indeed.com", "glassdoor.com", "lever.co"}


def _is_blocked_url(url: str) -> bool:
    """Return True if the URL is known to block scraping."""
    for domain in BLOCKED_DOMAINS:
        if domain in url:
            return True
    return False


def _fetch_url(url: str) -> Optional[str]:
    """
    Fetch a URL and return clean text.
    Returns None if fetch fails for any reason.
    """
    if _is_blocked_url(url):
        logger.info(f"Skipping blocked domain: {url}")
        return None

    try:
        with httpx.Client(
            headers=SCRAPE_HEADERS,
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                logger.debug(f"Non-HTML content type at {url}: {content_type}")
                return None
            return response.text
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url}")
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} for {url}")
    except Exception as e:
        logger.warning(f"Fetch failed for {url}: {type(e).__name__}: {e}")
    return None


def _html_to_text(html: str) -> str:
    """
    Convert HTML to clean plain text using BeautifulSoup.
    Removes nav, footer, scripts, styles — keeps main content only.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Remove elements that aren't content
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "noscript", "form", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {3,}", " ", text)
        return text.strip()[:MAX_TEXT_CHARS]

    except Exception as e:
        logger.warning(f"HTML parsing failed: {e}")
        # Crude fallback: strip all HTML tags with regex
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()[:MAX_TEXT_CHARS]


def _infer_company_url(company_name: str) -> Optional[str]:
    """
    Heuristically guess a company's homepage URL.
    Simple and often wrong — used only as a best-effort fallback.
    """
    if not company_name or len(company_name) < 2:
        return None
    safe = re.sub(r"[^a-z0-9]", "", company_name.lower())
    if not safe:
        return None
    return f"https://www.{safe}.com"


# ── Vector store ──────────────────────────────────────────────────────────────

def _get_vectorstore(collection_name: str) -> PGVector:
    """
    Create a PGVector instance for the given collection.

    Why psycopg2 here instead of asyncpg?
    langchain-postgres PGVector uses psycopg2 (sync). Our asyncpg connection
    is for the FastAPI health check only. Both connect to the same PostgreSQL
    instance, using different drivers for different purposes.
    """
    embeddings = OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=settings.embed_model,
    )
    return PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=settings.sync_database_url,
        use_jsonb=True,
    )


def _embed_and_store(texts: List[str], collection_name: str) -> PGVector:
    """Chunk, embed, and store texts in pgvector. Returns the vectorstore."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    docs = [Document(page_content=t) for t in texts if t.strip()]
    chunks = splitter.split_documents(docs)
    logger.debug(f"Created {len(chunks)} chunks from {len(docs)} documents")

    vectorstore = _get_vectorstore(collection_name)
    vectorstore.add_documents(chunks)
    return vectorstore


def _retrieve(vectorstore: PGVector, query: str) -> str:
    """Retrieve top-K chunks and return as a single context string."""
    docs = vectorstore.similarity_search(query, k=TOP_K_CHUNKS)
    context = "\n\n---\n\n".join(d.page_content for d in docs)
    return context[:MAX_CONTEXT_CHARS]


# ── LLM synthesis ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_SYNTHESIS = """\
You are a company intelligence analyst. Extract structured information about a company
from the provided context (job posting and/or company website content).

EXTRACTION RULES:
1. Extract only what is explicitly stated or clearly inferable from the context
2. Do NOT fabricate mission statements, values, or news not present in the context
3. talking_points should be specific and actionable for a job applicant
4. red_flags should only be noted if genuinely concerning — leave empty if nothing stands out
5. Return ONLY valid JSON — no markdown, no explanation

REQUIRED JSON STRUCTURE:
{
  "company_name": "string",
  "mission": "mission statement or null",
  "culture_values": ["value1", "value2"],
  "recent_highlights": ["recent news or achievement"],
  "technologies_mentioned": ["tech stack items"],
  "talking_points": ["specific personalisation angle for cover letter"],
  "red_flags": [],
  "source": "web_scraped | jd_only | combined",
  "confidence": "high | medium | low"
}\
"""

USER_PROMPT_SYNTHESIS = """\
Company: {company_name}
Role: {role_title}
Source: {source}

=== CONTEXT ===
{context}

Extract company intelligence and return the JSON structure.\
"""

USER_PROMPT_JD_ONLY = """\
Company: {company_name}
Role: {role_title}

=== JOB DESCRIPTION (only source available) ===
{jd_text}

Extract what you can about the company from the job description alone.
Set source to "jd_only" and confidence to "medium".
Return the JSON structure.\
"""


def _synthesise(
    company_name: str,
    role_title: str,
    context: str,
    source: str,
    jd_raw: str,
) -> Optional[CompanyIntelligence]:
    """Call LLM to synthesise CompanyIntelligence from retrieved context."""
    llm = get_llm(temperature=0.1, json_mode=True)

    if context:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_SYNTHESIS),
            HumanMessage(content=USER_PROMPT_SYNTHESIS.format(
                company_name=company_name,
                role_title=role_title,
                source=source,
                context=context,
            )),
        ]
    else:
        # Fallback: extract from JD text directly
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_SYNTHESIS),
            HumanMessage(content=USER_PROMPT_JD_ONLY.format(
                company_name=company_name,
                role_title=role_title,
                jd_text=jd_raw[:5000],
            )),
        ]

    try:
        response = llm.invoke(messages)
        parsed = json.loads(response.content.strip())
        validated = CompanyIntelligence.model_validate(parsed)
        return validated
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        logger.warning(f"Synthesis failed: {type(e).__name__}: {e}")
        return None


# ── Node function ─────────────────────────────────────────────────────────────

def company_research(state: AgentState) -> dict:
    """
    RAG pipeline: fetch → chunk → embed → store → retrieve → synthesise.

    Always returns (never raises). If all steps fail, returns
    company_intelligence=None and adds an error. Pipeline continues.
    """
    run_id = state["run_id"]
    jd_parsed = state.get("jd_parsed") or {}
    jd_raw = state.get("jd_raw", "")
    jd_url = state.get("jd_url")

    company_name = jd_parsed.get("company_name") or "Unknown Company"
    role_title = jd_parsed.get("role_title") or "Unknown Role"

    start_time = time.time()
    logger.info(
        f"[{run_id}] company_research: starting — "
        f"company={company_name!r} role={role_title!r}"
    )

    # ── Step 1: Collect text from available sources ────────────────────────
    texts: List[str] = []
    sources_used: List[str] = []

    # Try job posting URL
    if jd_url:
        logger.info(f"[{run_id}] company_research: fetching JD URL: {jd_url}")
        html = _fetch_url(jd_url)
        if html:
            text = _html_to_text(html)
            if len(text) > 200:
                texts.append(text)
                sources_used.append("job_posting")
                logger.info(f"[{run_id}] Fetched JD URL: {len(text)} chars")

    # Try company homepage
    company_url = _infer_company_url(company_name)
    if company_url and company_name != "Unknown Company":
        logger.info(f"[{run_id}] company_research: fetching company URL: {company_url}")
        html = _fetch_url(company_url)
        if html:
            text = _html_to_text(html)
            if len(text) > 200:
                texts.append(text)
                sources_used.append("company_website")
                logger.info(f"[{run_id}] Fetched company website: {len(text)} chars")

    # ── Step 2: Determine source + fallback ───────────────────────────────
    if not texts:
        logger.info(
            f"[{run_id}] company_research: no web content — "
            "falling back to JD-only extraction"
        )
        # JD-only fallback — no embeddings needed
        intel = _synthesise(
            company_name=company_name,
            role_title=role_title,
            context="",
            source="jd_only",
            jd_raw=jd_raw,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        if intel:
            logger.info(
                f"[{run_id}] company_research (jd_only): done in {duration_ms}ms "
                f"— confidence={intel.confidence}"
            )
            return _success(intel, run_id, duration_ms)
        else:
            return _failure(run_id, "synthesis from JD failed", start_time)

    # ── Step 3: Embed + store in pgvector ─────────────────────────────────
    collection_name = f"cr_{run_id[:12].replace('-', '')}"
    vectorstore = None
    try:
        logger.info(
            f"[{run_id}] company_research: embedding {len(texts)} source(s) "
            f"into collection {collection_name!r}"
        )
        vectorstore = _embed_and_store(texts, collection_name)
    except Exception as e:
        logger.warning(
            f"[{run_id}] company_research: embedding failed ({e}) — "
            "falling back to JD-only"
        )
        intel = _synthesise(
            company_name=company_name,
            role_title=role_title,
            context="",
            source="jd_only",
            jd_raw=jd_raw,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        return _success(intel, run_id, duration_ms) if intel else _failure(
            run_id, f"embedding failed and JD-only synthesis also failed: {e}", start_time
        )

    # ── Step 4: Retrieve relevant chunks ──────────────────────────────────
    query = (
        f"company culture values mission strategy {role_title} "
        f"{company_name} team engineering"
    )
    try:
        context = _retrieve(vectorstore, query)
        logger.info(
            f"[{run_id}] company_research: retrieved {len(context)} chars of context"
        )
    except Exception as e:
        logger.warning(f"[{run_id}] company_research: retrieval failed: {e}")
        context = ""

    # ── Step 5: Synthesise ─────────────────────────────────────────────────
    source_label = "combined" if len(sources_used) > 1 else sources_used[0] if sources_used else "jd_only"
    intel = _synthesise(
        company_name=company_name,
        role_title=role_title,
        context=context,
        source=source_label,
        jd_raw=jd_raw,
    )

    # ── Step 6: Cleanup pgvector collection ───────────────────────────────
    try:
        vectorstore.drop_embeddings()
        logger.debug(f"[{run_id}] Dropped pgvector collection {collection_name!r}")
    except Exception as e:
        logger.debug(f"[{run_id}] Could not drop collection (non-critical): {e}")

    duration_ms = int((time.time() - start_time) * 1000)

    if intel:
        logger.info(
            f"[{run_id}] company_research: done in {duration_ms}ms — "
            f"source={intel.source} confidence={intel.confidence} "
            f"talking_points={len(intel.talking_points)}"
        )
        return _success(intel, run_id, duration_ms)
    else:
        return _failure(run_id, "LLM synthesis produced invalid output", start_time)


def _success(intel: CompanyIntelligence, run_id: str, duration_ms: int) -> dict:
    return {
        "current_step": "company_research",
        "steps_completed": ["company_research"],
        "company_intelligence": intel.model_dump(),
    }


def _failure(run_id: str, reason: str, start_time: float) -> dict:
    duration_ms = int((time.time() - start_time) * 1000)
    msg = f"company_research failed in {duration_ms}ms: {reason}"
    logger.error(f"[{run_id}] {msg}")
    return {
        "current_step": "company_research",
        "steps_completed": ["company_research"],
        "company_intelligence": None,
        "errors": [msg],
    }
