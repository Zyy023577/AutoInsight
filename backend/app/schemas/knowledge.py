"""知识图谱与车型对比 API Schema。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.car import CarRecord


class Provenance(BaseModel):
    source_name: str
    source_url: str | None = None
    collected_at: str
    data_status: str
    source_type: str


class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    provenance: Provenance


class KnowledgeGraphResponse(BaseModel):
    data_mode: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ComparisonField(BaseModel):
    field: str
    values: dict[str, Any]
    provenance: dict[str, Provenance]


class ComparisonResponse(BaseModel):
    data_mode: str
    cars: list[CarRecord]
    fields: list[ComparisonField]
