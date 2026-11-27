"""Pydantic output contracts for SignalGuard v2.

These models are passed to Agno as ``output_schema`` so the provider enforces
the JSON shape (native structured outputs), and Pydantic enforces the value
ranges. The relevance total is *computed* in Python from the four criteria, so
the old "score does not match rubric sum" failure mode no longer exists.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RiskCategory = Literal["NONE", "SECURITY", "COMPATIBILITY", "SUSPICION"]

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

RUBRIC_LIMITS = {
    "novelty": 25,
    "technical_relevance": 30,
    "applicability": 25,
    "timeliness": 20,
}


class RelevanceRubric(BaseModel):
    """Weighted relevance rubric. The total is derived, never asked for."""

    model_config = ConfigDict(extra="forbid")

    novelty: int = Field(ge=0, le=25, description="0-25: how new the idea, release or capability is")
    technical_relevance: int = Field(
        ge=0, le=30, description="0-30: how central the topic is to applied AI/LLM engineering"
    )
    applicability: int = Field(ge=0, le=25, description="0-25: how directly a developer can use it now")
    timeliness: int = Field(ge=0, le=20, description="0-20: why the team should care now")
    reasoning: str = Field(description="One concise sentence justifying the scores")

    @property
    def score(self) -> int:
        return self.novelty + self.technical_relevance + self.applicability + self.timeliness


class RiskAssessmentLLM(BaseModel):
    """Raw risk judgement returned by the model, before deterministic arbitration."""

    model_config = ConfigDict(extra="forbid")

    risk_level: RiskLevel
    risk_category: RiskCategory
    breaking_changes: bool = Field(
        description="True only for explicit backward-incompatible changes, removals or ended support"
    )
    concerns: List[str] = Field(description="Short concerns; empty when risk is LOW/NONE")
    evidence_quotes: List[str] = Field(
        description="Verbatim quotes copied from the signal that support the judgement"
    )
