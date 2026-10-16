"""汽车领域 API Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CarOpinion(BaseModel):
    attribute: str
    sentiment: str
    text: str
    source_name: str
    collected_at: str


class CarRecord(BaseModel):
    id: str
    brand: str
    model: str
    version: str | None = None
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    energy_type: str
    body_type: str
    range_km: int | None = Field(default=None, ge=0)
    usage_scenarios: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    opinions: list[CarOpinion] = Field(default_factory=list)
    source_name: str
    source_url: str | None = None
    collected_at: str
    data_status: str
    source_type: str


class CarListResponse(BaseModel):
    total: int = Field(ge=0)
    data_mode: str
    cars: list[CarRecord]


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str
    data_mode: str
    car_count: int = Field(ge=0)
