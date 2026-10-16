"""汽车推荐服务：硬约束过滤优先，软偏好评分可解释。"""

from __future__ import annotations

from backend.app.schemas.car import CarRecord
from backend.app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationResult,
)


DEFAULT_WEIGHTS = {
    "空间": 1.0,
    "舒适性": 1.0,
    "智能化": 1.0,
    "能耗": 1.0,
    "续航": 1.0,
    "性价比": 1.0,
}

ATTRIBUTE_TERMS = {
    "空间": ("空间", "座舱", "后排"),
    "舒适性": ("舒适", "座椅"),
    "智能化": ("智能", "辅助驾驶", "激光雷达"),
    "能耗": ("能耗", "省电"),
    "续航": ("续航",),
    "性价比": ("性价比",),
}


class RecommendationService:
    def recommend(
        self, cars: list[CarRecord], request: RecommendationRequest
    ) -> RecommendationResponse:
        results = [self._evaluate(car, request) for car in cars]
        results.sort(key=lambda item: (not item.hard_constraints_met, -item.soft_score, item.car.id))
        return RecommendationResponse(
            data_mode="demo",
            total_candidates=len(results),
            hard_match_count=sum(item.hard_constraints_met for item in results),
            results=results,
        )

    def _evaluate(self, car: CarRecord, request: RecommendationRequest) -> RecommendationResult:
        matched: list[str] = []
        unmet: list[str] = []
        missing: list[str] = []

        if request.budget_max is not None:
            if car.price_max is None:
                missing.append("price_max")
                unmet.append(f"缺少预算上限数据（要求不超过{request.budget_max}元）")
            elif car.price_max <= request.budget_max:
                matched.append(f"预算不超过{request.budget_max}元")
            else:
                unmet.append(f"价格上限{car.price_max}元超过预算{request.budget_max}元")

        if request.energy_type:
            if car.energy_type == request.energy_type:
                matched.append(f"能源类型为{request.energy_type}")
            else:
                unmet.append(f"能源类型为{car.energy_type}，不满足{request.energy_type}")

        if request.body_type:
            if car.body_type == request.body_type:
                matched.append(f"车身类型为{request.body_type}")
            else:
                unmet.append(f"车身类型为{car.body_type}，不满足{request.body_type}")

        if request.range_min_km is not None:
            if car.range_km is None:
                missing.append("range_km")
                unmet.append(f"缺少续航数据（要求至少{request.range_min_km}公里）")
            elif car.range_km >= request.range_min_km:
                matched.append(f"续航至少{request.range_min_km}公里")
            else:
                unmet.append(f"续航{car.range_km}公里低于要求{request.range_min_km}公里")

        if request.usage_scenario:
            if request.usage_scenario in car.usage_scenarios:
                matched.append(f"适用于{request.usage_scenario}")
            elif not car.usage_scenarios:
                unmet.append(f"缺少使用场景数据（要求适用于{request.usage_scenario}）")
                missing.append("usage_scenarios")
            else:
                unmet.append(f"未记录适用于{request.usage_scenario}")

        if car.energy_type in request.excluded_energy_types:
            unmet.append(f"能源类型{car.energy_type}在排除列表中")
        if car.body_type in request.excluded_body_types:
            unmet.append(f"车身类型{car.body_type}在排除列表中")

        weights = {**DEFAULT_WEIGHTS, **request.weights}
        breakdown: dict[str, float] = {}
        explanation: list[str] = []
        searchable = " ".join(car.highlights + car.usage_scenarios + [car.body_type, car.energy_type])
        requested_weight = 0.0
        matched_weight = 0.0
        for attribute in request.preferred_attributes:
            weight = weights.get(attribute, 1.0)
            requested_weight += weight
            terms = ATTRIBUTE_TERMS.get(attribute, (attribute,))
            if any(term in searchable for term in terms):
                matched_weight += weight
                breakdown[attribute] = weight
                explanation.append(f"软偏好匹配：{attribute}（权重{weight:g}）")
            else:
                breakdown[attribute] = 0.0
                explanation.append(f"软偏好暂无依据：{attribute}")

        soft_score = round(matched_weight / requested_weight * 100, 2) if requested_weight else 0.0
        hard_met = not unmet
        if hard_met:
            explanation.insert(0, "满足全部已声明硬约束")
        else:
            explanation.insert(0, "未满足全部硬约束，不应作为硬约束推荐结果")
        if missing:
            explanation.append("存在缺失数据：" + "、".join(dict.fromkeys(missing)))

        return RecommendationResult(
            car=car,
            hard_constraints_met=hard_met,
            matched_constraints=matched,
            unmet_constraints=unmet,
            missing_data=list(dict.fromkeys(missing)),
            soft_score=soft_score,
            score_breakdown=breakdown,
            explanation=explanation,
        )
