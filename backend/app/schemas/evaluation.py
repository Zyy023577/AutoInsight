"""评测结果 API Schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluationSummary(BaseModel):
    status: str
    sample_count: int
    completed_count: int
    accuracy: float | None = None
    macro_f1: float | None = None
    entity: dict[str, Any] | None = None
    error_count: int
    latency_ms: dict[str, float | None]
    tokens: dict[str, int | None]


class EvaluationReportResponse(BaseModel):
    dataset_type: str
    rule_baseline: EvaluationSummary
    prompt_strategies: list[dict[str, Any]]
    report_path: str | None = None


class PromptExperimentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    strategy_id: Literal["A", "B", "C"]


class PromptExperimentResponse(BaseModel):
    strategy_id: str
    prompt_version: str
    text: str
    intent: str
    entities: dict[str, Any]
    raw_output: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None


class LLMConfigRequest(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str = Field(default="https://api.deepseek.com", min_length=1, max_length=500)
    model: str = Field(default="deepseek-chat", min_length=1, max_length=100)
    persist: bool | None = None


class LLMConfigResponse(BaseModel):
    configured: bool
    base_url: str
    model: str
    persistence: str = "process_memory_only"
