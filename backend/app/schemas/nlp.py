"""意图识别与汽车实体抽取的统一 Schema。"""

from __future__ import annotations

from enum import Enum
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class IntentLabel(str, Enum):
    PURCHASE_RECOMMENDATION = "购车推荐"
    MODEL_COMPARISON = "车型对比"
    PARAMETER_QUERY = "参数查询"
    PRICE_QUERY = "价格查询"
    USER_REVIEW = "用户评价"
    USAGE_KNOWLEDGE = "用车知识"
    OTHER = "其他"


INTENT_ALIASES = {
    "purchase_recommendation": IntentLabel.PURCHASE_RECOMMENDATION.value,
    "recommendation": IntentLabel.PURCHASE_RECOMMENDATION.value,
    "purchase": IntentLabel.PURCHASE_RECOMMENDATION.value,
    "comparison": IntentLabel.MODEL_COMPARISON.value,
    "model_comparison": IntentLabel.MODEL_COMPARISON.value,
    "parameter_query": IntentLabel.PARAMETER_QUERY.value,
    "parameter": IntentLabel.PARAMETER_QUERY.value,
    "price_query": IntentLabel.PRICE_QUERY.value,
    "price": IntentLabel.PRICE_QUERY.value,
    "user_review": IntentLabel.USER_REVIEW.value,
    "review": IntentLabel.USER_REVIEW.value,
    "usage_knowledge": IntentLabel.USAGE_KNOWLEDGE.value,
    "usage": IntentLabel.USAGE_KNOWLEDGE.value,
    "other": IntentLabel.OTHER.value,
}


def normalize_llm_payload(payload: object) -> dict[str, object]:
    """把常见的模型格式漂移归一化后再进入严格 Schema 校验。"""

    if not isinstance(payload, dict):
        raise ValueError("模型输出顶层必须是 JSON 对象")

    normalized = dict(payload)
    intent = normalized.get("intent")
    if isinstance(intent, str):
        cleaned_intent = intent.strip()
        normalized["intent"] = INTENT_ALIASES.get(
            cleaned_intent.lower(),
            cleaned_intent,
        )

    entities = normalized.get("entities", {})
    if entities is None:
        normalized["entities"] = {}
    elif isinstance(entities, list):
        # 策略 A 偶尔直接返回车型数组，统一解释为 models 字段。
        normalized["entities"] = {"models": entities}
    elif not isinstance(entities, dict):
        raise ValueError("模型输出的 entities 必须是 JSON 对象")
    else:
        entities = dict(entities)
        _normalize_constraint_container(entities, "hard_constraints", "contains")
        _normalize_constraint_container(entities, "soft_preferences", "contains")
        _normalize_constraint_container(entities, "negative_constraints", "not")
        normalized["entities"] = entities

    return normalized


def _normalize_constraint_container(
    entities: dict[str, object],
    field_name: str,
    default_operator: str,
) -> None:
    """把模型返回的字典式约束转换为 ConstraintRecord 数组。"""

    value = entities.get(field_name)
    if value is None:
        entities[field_name] = []
        return
    if isinstance(value, list):
        normalized_records = []
        for item in value:
            if isinstance(item, dict):
                record = dict(item)
                record.setdefault("operator", default_operator)
                record.setdefault("source_text", "llm_structured_output")
                normalized_records.append(record)
            else:
                normalized_records.append(
                    {
                        "field": field_name,
                        "operator": default_operator,
                        "value": str(item),
                        "source_text": "llm_structured_output",
                    }
                )
        entities[field_name] = normalized_records
        return
    if not isinstance(value, dict):
        raise ValueError(f"模型输出的 {field_name} 必须是数组或对象")

    records = []
    for constraint_field, raw_values in value.items():
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        for raw_value in values:
            if raw_value is None:
                continue
            if isinstance(raw_value, (str, int)):
                record_value: str | int = raw_value
            else:
                record_value = json.dumps(raw_value, ensure_ascii=False)
            records.append(
                {
                    "field": constraint_field,
                    "operator": default_operator,
                    "value": record_value,
                    "source_text": "llm_structured_output",
                }
            )
            if field_name == "hard_constraints" and constraint_field == "models":
                _append_unique(entities, "models", raw_value if isinstance(raw_value, list) else [raw_value])
            if field_name == "soft_preferences" and constraint_field == "comparison_aspects":
                _append_unique(
                    entities,
                    "focus_attributes",
                    raw_value if isinstance(raw_value, list) else [raw_value],
                )
    entities[field_name] = records


def _append_unique(entities: dict[str, object], field_name: str, values: list[object]) -> None:
    existing = entities.get(field_name)
    items = existing if isinstance(existing, list) else []
    for value in values:
        if value not in items:
            items.append(value)
    entities[field_name] = items


class AnalysisStrategy(str, Enum):
    RULE_BASELINE = "rule_baseline"
    LLM_STRUCTURED = "llm_structured"


class ConstraintRecord(BaseModel):
    """保留原文证据的结构化约束，避免把偏好误当硬约束。"""

    field: str
    operator: Literal["eq", "gte", "lte", "between", "contains", "not"]
    value: int | str
    source_text: str


class ExtractedEntities(BaseModel):
    brands: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    energy_type: str | None = None
    body_type: str | None = None
    range_min_km: int | None = Field(default=None, ge=0)
    usage_scenarios: list[str] = Field(default_factory=list)
    configurations: list[str] = Field(default_factory=list)
    focus_attributes: list[str] = Field(default_factory=list)
    hard_constraints: list[ConstraintRecord] = Field(default_factory=list)
    soft_preferences: list[ConstraintRecord] = Field(default_factory=list)
    negative_constraints: list[ConstraintRecord] = Field(default_factory=list)
    ambiguous_mentions: list[str] = Field(default_factory=list)
    unrecognized_mentions: list[str] = Field(default_factory=list)

    @field_validator(
        "brands",
        "models",
        "usage_scenarios",
        "configurations",
        "focus_attributes",
        "ambiguous_mentions",
        "unrecognized_mentions",
        mode="before",
    )
    @classmethod
    def normalize_string_collections(cls, value: object) -> list[str]:
        """兼容模型偶尔返回的结构化车型对象，统一成前端可展示的字符串。"""

        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in items:
            if isinstance(item, str):
                normalized.append(item)
                continue
            if isinstance(item, dict):
                parts = [item.get(key) for key in ("brand", "model", "trim")]
                label = " ".join(
                    str(part).strip()
                    for part in parts
                    if part is not None and str(part).strip()
                )
                normalized.append(label or json.dumps(item, ensure_ascii=False))
                continue
            normalized.append(str(item))
        return normalized


class NlpAnalysis(BaseModel):
    text: str
    intent: IntentLabel
    intent_evidence: list[str] = Field(default_factory=list)
    entities: ExtractedEntities
    strategy: AnalysisStrategy
    parser_status: Literal["parsed", "failed"] = "parsed"
    raw_output: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    strategy: AnalysisStrategy = AnalysisStrategy.RULE_BASELINE

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("问题不能为空")
        return cleaned
