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
