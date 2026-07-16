"""Structured outputs used at the three model-powered stages."""

from pydantic import BaseModel, ConfigDict, Field


class CandidateTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    description: str
    quote: str
    importance: int = Field(ge=1, le=5)


class DiaryExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    themes: list[CandidateTheme]


class CanonicalTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    candidate_ids: list[str]


class ThemeSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    themes: list[CanonicalTheme]


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diary_id: str
    date: str
    text: str


class ThemeAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str
    quotes: list[EvidenceQuote]
    uncertainty: str
