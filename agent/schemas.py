"""
Pydantic schemas for structured LLM output.

These schemas serve two purposes:
1. They define the exact JSON the LLM must produce (included in prompts)
2. They validate the LLM's response — if the model hallucinates wrong types,
   Pydantic catches it before bad data enters the AgentState

The rule: every field the LLM produces MUST pass through one of these schemas
before it's accepted into state. No blind JSON trusting.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Job Description Schema ────────────────────────────────────────────────────

class ParsedJD(BaseModel):
    """
    Structured representation of a job description.
    Populated by: parse_jd node.
    """
    role_title: str = Field(default="", description="Exact job title from posting")
    company_name: str = Field(default="", description="Company name")
    required_skills: List[str] = Field(default_factory=list, description="Must-have skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Nice-to-have skills")
    experience_level: str = Field(
        default="not_specified",
        description="junior | mid | senior | lead | executive | not_specified"
    )
    responsibilities: List[str] = Field(default_factory=list, description="Key job responsibilities")
    ats_keywords: List[str] = Field(
        default_factory=list,
        description="Important keywords ATS systems look for"
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="Concerning language or unreasonable requirements"
    )
    company_values: List[str] = Field(default_factory=list, description="Stated culture/values")
    location: Optional[str] = Field(default=None, description="Job location")
    employment_type: Optional[str] = Field(
        default=None,
        description="full-time | part-time | contract | remote | hybrid | on-site"
    )
    salary_range: Optional[str] = Field(default=None, description="Stated salary information")


# ── Resume Schema ─────────────────────────────────────────────────────────────

class ContactInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None


class WorkExperience(BaseModel):
    company: str = ""
    role: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    responsibilities: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str = ""
    degree: Optional[str] = None
    field: Optional[str] = None
    graduation_year: Optional[str] = None
    gpa: Optional[str] = None


class Project(BaseModel):
    name: str = ""
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class ParsedResume(BaseModel):
    """
    Structured representation of a resume.
    Populated by: parse_resume node.
    """
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    summary: Optional[str] = None
    work_experience: List[WorkExperience] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    total_years_experience: Optional[float] = None


# ── Skill Gap Analysis Schema ─────────────────────────────────────────────────

class SkillClassification(BaseModel):
    """
    Classification of a single JD skill against the candidate's profile.

    Used inside SkillGapAnalysis for both required and preferred skills.
    HIDDEN_STRENGTH skills don't belong here — they live in hidden_strengths.
    """
    skill: str = Field(description="The skill name from the JD")
    classification: str = Field(
        description="STRONG_MATCH | PARTIAL_MATCH | GAP"
    )
    evidence: Optional[str] = Field(
        default=None,
        description="One sentence citing evidence from the resume, or null if GAP"
    )


class SkillGapAnalysis(BaseModel):
    """
    Full skill gap analysis result.
    Populated by: skill_gap_analysis node (Phase 4).

    This is the bridge between Phase 2 (parsing) and Phase 6–7 (writing).
    The resume rewriter and cover letter generator read this to know:
    - What to lead with (STRONG_MATCH → talking points)
    - What to frame carefully (PARTIAL_MATCH → bridging language)
    - What to omit or address honestly (GAP → gaps_to_address)
    - What to proactively add (hidden_strengths)
    """
    # Per-skill classifications
    required_skills: List[SkillClassification] = Field(
        default_factory=list,
        description="Classification of each required JD skill"
    )
    preferred_skills: List[SkillClassification] = Field(
        default_factory=list,
        description="Classification of each preferred JD skill"
    )
    hidden_strengths: List[str] = Field(
        default_factory=list,
        description="Resume skills NOT in the JD but valuable for this role"
    )

    # Quantitative
    overall_match_score: int = Field(
        default=0,
        description="0-100 integer. 80+=strong, 60-79=viable, <60=significant gaps"
    )

    # Qualitative
    experience_level_match: str = Field(
        default="unknown",
        description="above_target | matches | below_target"
    )
    key_talking_points: List[str] = Field(
        default_factory=list,
        description="What to emphasise in the resume and cover letter"
    )
    gaps_to_address: List[str] = Field(
        default_factory=list,
        description="Important skill gaps that need strategic handling"
    )
    recommendation: str = Field(
        default="unknown",
        description="strong_candidate | viable_candidate | significant_gaps"
    )


# ── Company Intelligence Schema ───────────────────────────────────────────────

class CompanyIntelligence(BaseModel):
    """
    Company intelligence gathered by the RAG pipeline.
    Populated by: company_research node (Phase 5).

    Used by:
    - cover_letter_generator → personalise the opening, reference values
    - cold_email_drafter → tailor outreach to what matters to this company
    """
    company_name: str = Field(default="")
    mission: Optional[str] = Field(
        default=None, description="Company mission statement or purpose"
    )
    culture_values: List[str] = Field(
        default_factory=list,
        description="Stated or inferred company values and culture signals"
    )
    recent_highlights: List[str] = Field(
        default_factory=list,
        description="Recent news, product launches, or notable achievements"
    )
    technologies_mentioned: List[str] = Field(
        default_factory=list,
        description="Technologies referenced in company/job materials"
    )
    talking_points: List[str] = Field(
        default_factory=list,
        description="Compelling angles to use in cover letter and emails"
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="Concerns or warning signs (optional — don't force)"
    )
    source: str = Field(
        default="jd_only",
        description="web_scraped | jd_only | combined"
    )
    confidence: str = Field(
        default="low",
        description="high | medium | low — reflects data quality"
    )


# ── Rewritten Resume Schema ───────────────────────────────────────────────────

class RewrittenExperienceEntry(BaseModel):
    """
    One work experience entry with AI-rewritten bullet points.

    UNCHANGED: company, role, start_date, end_date, is_current
    REWRITTEN: bullets (combination of responsibilities + achievements,
               reordered and rephrased for ATS and JD alignment)
    """
    company: str = ""
    role: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    bullets: List[str] = Field(
        default_factory=list,
        description="Reordered and JD-aligned bullet points (max 5 per role)"
    )


class RewrittenResume(BaseModel):
    """
    ATS-optimised, JD-tailored resume content.
    Populated by: resume_rewriter node (Phase 6).

    Factual data (contact info, dates, company names, titles, education)
    is NEVER modified — only text content is rewritten.

    Used by:
    - package_store (Phase 9) → merged with original factual data to produce PDF
    - quality_checker (Phase 8) → scores the rewrite quality
    """
    professional_summary: str = Field(
        default="",
        description="Tailored 3-4 sentence professional summary for this specific role"
    )
    work_experience: List[RewrittenExperienceEntry] = Field(
        default_factory=list,
        description="Experience entries with rewritten bullets only"
    )
    skills: List[str] = Field(
        default_factory=list,
        description="Reordered skills list — JD-relevant skills first"
    )

    # Metadata for quality checking and user transparency
    ats_score_estimate: int = Field(
        default=0,
        description="Estimated ATS keyword match score after rewrite (0-100)"
    )
    changes_made: List[str] = Field(
        default_factory=list,
        description="Plain English log of what was changed (shown to user)"
    )



