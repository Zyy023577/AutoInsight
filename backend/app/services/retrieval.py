"""基于 SQLite 结构化记录的汽车证据检索。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from backend.app.schemas.car import CarOpinion, CarRecord
from backend.app.schemas.knowledge import Provenance
from backend.app.schemas.nlp import IntentLabel, NlpAnalysis
from backend.app.schemas.rag import EvidenceItem
from backend.app.schemas.recommendation import RecommendationRequest
from backend.app.services.car_catalog import CarCatalog
from backend.app.services.recommendation import RecommendationService


@dataclass
class RetrievalResult:
    evidence: list[EvidenceItem]
    strict_match_count: int = 0
    reason: str = ""


class StructuredRetriever:
    """先查 SQLite 结构化数据，再生成有限、可引用的证据集合。"""

    def __init__(self, catalog: CarCatalog, recommendation_service: RecommendationService):
        self.catalog = catalog
        self.recommendation_service = recommendation_service

    def retrieve(self, analysis: NlpAnalysis) -> RetrievalResult:
        cars = self.catalog.list_cars()
        if analysis.intent == IntentLabel.PURCHASE_RECOMMENDATION:
            return self._retrieve_recommendation(analysis, cars)

        named_cars = self._find_named_cars(analysis.text, cars)
        if analysis.intent == IntentLabel.MODEL_COMPARISON and len(named_cars) < 2:
            return RetrievalResult([], reason="知识库中没有找到问题中提到的至少两个车型")
        if not named_cars:
            return RetrievalResult([], reason="知识库中没有找到问题对应的明确车型")
        return RetrievalResult(self._car_evidence(named_cars, analysis.intent))

    def _retrieve_recommendation(
        self, analysis: NlpAnalysis, cars: list[CarRecord]
    ) -> RetrievalResult:
        entities = analysis.entities
        request = RecommendationRequest(
            budget_max=entities.budget_max,
            energy_type=entities.energy_type,
            body_type=entities.body_type,
            range_min_km=entities.range_min_km,
            usage_scenario=entities.usage_scenarios[0] if entities.usage_scenarios else None,
            excluded_energy_types=[
                str(item.value)
                for item in entities.negative_constraints
                if item.field == "energy_type"
            ],
            excluded_body_types=[
                str(item.value)
                for item in entities.negative_constraints
                if item.field == "body_type"
            ],
            preferred_attributes=entities.focus_attributes,
        )
        recommendation = self.recommendation_service.recommend(cars, request)
        strict_matches = [item.car for item in recommendation.results if item.hard_constraints_met]
        selected = strict_matches[:3] if strict_matches else [item.car for item in recommendation.results[:3]]
        evidence = self._car_evidence(selected, IntentLabel.PURCHASE_RECOMMENDATION)
        if strict_matches:
            reason = "已找到满足全部已声明硬约束的 Demo 候选"
        else:
            reason = "没有找到同时满足全部硬约束的 Demo 候选"
        return RetrievalResult(evidence, len(strict_matches), reason)

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).lower())

    def _find_named_cars(self, question: str, cars: list[CarRecord]) -> list[CarRecord]:
        normalized_question = self._normalize(question)
        matched: list[CarRecord] = []
        for car in cars:
            candidates = [car.id, car.brand, car.model, f"{car.brand}{car.model}"]
            if any(self._normalize(candidate) in normalized_question for candidate in candidates):
                matched.append(car)
        return matched

    def _car_evidence(self, cars: list[CarRecord], intent: IntentLabel) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for car in cars:
            fields: list[tuple[str, object, str]] = [
                ("price_min", car.price_min, "最低演示价格"),
                ("price_max", car.price_max, "最高演示价格"),
                ("energy_type", car.energy_type, "能源类型"),
                ("body_type", car.body_type, "车身类型"),
                ("range_km", car.range_km, "续航演示数据"),
                ("usage_scenarios", car.usage_scenarios, "适用场景"),
            ]
            if intent == IntentLabel.USER_REVIEW:
                fields = []
            for field, value, label in fields:
                if value is None or value == []:
                    continue
                evidence.append(self._make_evidence(car, field, value, f"{car.model}的{label}为{value}"))
            if intent in (IntentLabel.USER_REVIEW, IntentLabel.MODEL_COMPARISON):
                for opinion in car.opinions:
                    evidence.append(self._opinion_evidence(car, opinion))
            if intent == IntentLabel.USER_REVIEW:
                for highlight in car.highlights:
                    evidence.append(
                        self._make_evidence(car, "highlight", highlight, f"{car.model}的演示特征：{highlight}")
                    )
        return evidence

    @staticmethod
    def _make_evidence(car: CarRecord, field: str, value: object, statement: str) -> EvidenceItem:
        return EvidenceItem(
            evidence_id="",
            car_id=car.id,
            subject=car.model,
            field=field,
            value=value,
            statement=statement,
            provenance=Provenance(
                source_name=car.source_name,
                source_url=car.source_url,
                collected_at=car.collected_at,
                data_status=car.data_status,
                source_type=car.source_type,
            ),
        )

    @staticmethod
    def _opinion_evidence(car: CarRecord, opinion: CarOpinion) -> EvidenceItem:
        return EvidenceItem(
            evidence_id="",
            car_id=car.id,
            subject=car.model,
            field=f"opinion:{opinion.attribute}",
            value={"sentiment": opinion.sentiment, "text": opinion.text},
            statement=f"{car.model}关于{opinion.attribute}的演示观点：{opinion.text}",
            provenance=Provenance(
                source_name=opinion.source_name,
                source_url=None,
                collected_at=opinion.collected_at,
                data_status=car.data_status,
                source_type="人工构造演示观点",
            ),
        )
