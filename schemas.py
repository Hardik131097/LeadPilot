"""
Structured-output schemas (Pydantic). These play the same role as Zod schemas
in Flowise/LangChain JS: every LLM answer must match the schema, otherwise
the agent asks the LLM to fix it, and finally falls back to rule-based output.
"""
from typing import List

from pydantic import BaseModel, Field


class ResearchOutput(BaseModel):
    account_summary: str = Field(description="2-sentence profile of the account")
    pain_points: List[str] = Field(min_length=1, max_length=3, description="up to 3 short pain points")
    hook: str = Field(description="one factual personalisation hook taken from the lead data")
    best_case_study: str = Field(default="", description="title of the most relevant retrieved case study, or empty")


class QualificationOutput(BaseModel):
    justification: str = Field(description="2 sentences explaining the score to a sales rep")
    angle: str = Field(description="the single best value proposition to lead with")


class OutreachOutput(BaseModel):
    subject: str = Field(max_length=80)
    email_body: str = Field(min_length=40)
    linkedin_note: str = Field(max_length=400)
