"""RAG 问答与证据 Schema。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.knowledge import Provenance
from backend.app.schemas.nlp import NlpAnalysis


class RagMode(str, Enum):
    DEMO_GROUNDED = "demo_grounded"
    LLM_GROUNDED = "llm_grounded"


class EvidenceItem(BaseModel):
    evidence_id: str
    car_id: str | None = None
    subject: str
    field: str
    value: Any
    statement: str
    provenance: Provenance


class RagAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: RagMode = RagMode.DEMO_GROUNDED

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("问题不能为空")
        return cleaned


class RagAnswerResponse(BaseModel):
    question: str
    analysis: NlpAnalysis
    evidence: list[EvidenceItem] = Field(default_factory=list)
    answer: str
    citations: list[str] = Field(default_factory=list)
    mode: RagMode
    grounded: bool
    refusal_reason: str | None = None
    parser_status: str = "parsed"
    raw_output: str | None = None


class LLMAnswerPayload(BaseModel):
    answer: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False
