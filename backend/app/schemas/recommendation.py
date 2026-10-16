"""可解释推荐 API Schema。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.car import CarRecord


class RecommendationRequest(BaseModel):
    budget_max: int | None = Field(default=None, ge=0)
    energy_type: str | None = None
    body_type: str | None = None
    range_min_km: int | None = Field(default=None, ge=0)
    usage_scenario: str | None = None
    excluded_energy_types: list[str] = Field(default_factory=list)
    excluded_body_types: list[str] = Field(default_factory=list)
    preferred_attributes: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)

    @field_validator("weights")
    @classmethod
    def weights_must_be_non_negative(cls, value: dict[str, float]) -> dict[str, float]:
        if any(weight < 0 for weight in value.values()):
            raise ValueError("推荐权重不能为负数")
        return value


class RecommendationResult(BaseModel):
    car: CarRecord
    hard_constraints_met: bool
    matched_constraints: list[str] = Field(default_factory=list)
    unmet_constraints: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    soft_score: float = Field(ge=0, le=100)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    explanation: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    data_mode: str
    total_candidates: int = Field(ge=0)
    hard_match_count: int = Field(ge=0)
    results: list[RecommendationResult]
